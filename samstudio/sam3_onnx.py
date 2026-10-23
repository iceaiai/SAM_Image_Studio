"""Text-only SAM3 ONNX integration for the pinned public ViT-H export.

Implemented here using the exported graph contracts; no GPL AnyLabeling source
is included. Model artifacts retain their upstream SAM3 license. Native SAM3.1
and its geometric prompting are separate backends.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import threading

import cv2
import numpy as np

RELEASE_URL = "https://github.com/CVHub520/X-AnyLabeling/releases/download/v3.0.0/"
ASSETS = {
    "sam3_image_encoder.onnx": "3dd676271e9c459463f7026d8ab2c6318672cd89511f89c30b34cdf0a2e67a3f",
    "sam3_image_encoder.onnx.data": "03bd50b0703e2b04e2193ca831b7f9d5ecf40bc5287cc59b1970f56ab800c995",
    "sam3_language_encoder.onnx": "af80dffcd8fc369281b0422295244ba22f64e8424e9eefa111ac8966e9ea9ba6",
    "sam3_language_encoder.onnx.data": "1b03dabc657c1f2887d1b8ce2a3537467d4c033ea1f8c8be141fbca55e4b95f7",
    "sam3_decoder.onnx": "aca3109a1bf87d1589bf2a4a61c641fd97624152b21c6e9a5aa85735db398884",
    "sam3_decoder.onnx.data": "afae2f057f4c6e2478589877aa3d361a0d863cdfdb8259f7eee903f529188ac6",
}
BPE_NAME = "bpe_simple_vocab_16e6.txt.gz"
BPE_URL = "https://raw.githubusercontent.com/openai/CLIP/d05afc436d78f1c48dc0dbf8e5980a9d471f35f6/clip/" + BPE_NAME
BPE_SHA256 = "924691ac288e54409236115652ad4aa250f48203de50a9e4722a6ecd48d6804a"


def model_directory(local=None, progress=None, cancel=None):
    """Verify all sidecars or download the supported export; never fetch HF tokens."""
    from .inference import check_cancel, data_directory, download_file, file_digest
    root = Path(local).expanduser().resolve() if local else data_directory() / "models/sam3-onnx-v3"
    if local and not root.is_dir():
        raise ValueError("For SAM3 ONNX, select the folder containing all six .onnx/.onnx.data files, not a .pt checkpoint.")
    for name, digest in ASSETS.items():
        check_cancel(cancel)
        if local:
            path = root / name
            if not path.is_file():
                raise ValueError(f"SAM3 ONNX folder is missing {name}. Keep all six files together.")
            if progress:
                progress(f"Verifying {name}…")
            if file_digest(path, cancel) != digest:
                raise ValueError(f"SAM3 ONNX checksum mismatch: {name}. Use the supported v3.0.0 export.")
        else:
            download_file(RELEASE_URL + name, root / name, digest, progress, cancel)
    # The small, public CLIP vocabulary is cached separately from read-only
    # user model folders and is not a gated Hugging Face download.
    tokenizer = root / BPE_NAME
    if not tokenizer.exists():
        tokenizer = data_directory() / "models/clip-tokenizer" / BPE_NAME
        download_file(BPE_URL, tokenizer, BPE_SHA256, progress, cancel)
    elif file_digest(tokenizer, cancel) != BPE_SHA256:
        raise ValueError("CLIP vocabulary checksum mismatch. Restore the supported vocabulary.")
    return root, tokenizer


def runtime_providers(device, ort):
    """Select a real provider; CUDA failures must not silently become CPU runs."""
    if device == "cpu":
        return ["CPUExecutionProvider"]
    if not re.fullmatch(r"cuda(?::[0-9]+)?", device):
        raise ValueError("Select CPU or NVIDIA CUDA for SAM3 ONNX.")
    if not os.environ.get("CONDA_PREFIX"):
        raise ValueError("GPU execution requires a dedicated Conda environment.")
    if Path(os.environ["CONDA_PREFIX"]).name.lower() in ("base", "anaconda3", "miniconda3", "miniforge3"):
        raise ValueError("Activate a dedicated non-base Conda environment for GPU execution.")
    if "CUDAExecutionProvider" not in ort.get_available_providers():
        raise RuntimeError("ONNX CUDA provider is unavailable. Run scripts/install_onnx_runtime.py --device cuda in the dedicated GPU environment.")
    if hasattr(ort, "preload_dlls"):
        ort.preload_dlls()
    index = int(device.split(":")[1]) if ":" in device else 0
    return [("CUDAExecutionProvider", {"device_id": index}), "CPUExecutionProvider"]


class Sam3OnnxBackend:
    """Cached image/text encoders plus native-resolution text-decoder masks."""

    def __init__(self, directory, tokenizer_path, device="cpu", progress=None, cancel=None):
        from .inference import check_cancel
        try:
            import onnxruntime as ort
            from ._clip_tokenizer import SimpleTokenizer
        except ImportError as error:
            raise RuntimeError("SAM3 ONNX needs its optional runtime. Run python scripts/install_onnx_runtime.py --device cpu (or cuda in a GPU Conda environment). " + str(error)) from error
        self.device = device
        providers = runtime_providers(device, ort)
        options = ort.SessionOptions()
        options.intra_op_num_threads = max(1, min(4, os.cpu_count() or 1))
        options.inter_op_num_threads = 1
        options.log_severity_level = 3
        self.sessions = {}
        self._lock = threading.RLock()
        self._image_key = self._text_key = None
        self._features = self._language = None
        self.tokenizer = SimpleTokenizer(str(tokenizer_path))
        for kind in ("image_encoder", "language_encoder", "decoder"):
            check_cancel(cancel)
            if progress:
                progress(f"Loading SAM3 ONNX {kind.replace('_', ' ')} on {device}…")
            session = ort.InferenceSession(str(Path(directory) / f"sam3_{kind}.onnx"), sess_options=options, providers=providers)
            if device.startswith("cuda") and "CUDAExecutionProvider" not in session.get_providers():
                raise RuntimeError("ONNX Runtime could not initialize CUDA; no CPU fallback was accepted. Check CUDA/cuDNN DLLs and the GPU runtime installation.")
            if hasattr(session, "disable_fallback"):
                session.disable_fallback()
            self.sessions[kind] = session
        image_input = self.sessions["image_encoder"].get_inputs()
        if len(image_input) != 1 or image_input[0].shape != [3, 1008, 1008] or image_input[0].type != "tensor(uint8)":
            raise ValueError("Unsupported SAM3 image graph: expected uint8 RGB [3,1008,1008].")
        check_cancel(cancel)

    def tokens(self, text):
        """Official CLIP BPE IDs, start/end tokens and zero padding, context 32."""
        ids = [self.tokenizer.encoder["<|startoftext|>"]] + self.tokenizer.encode(text) + [self.tokenizer.encoder["<|endoftext|>"]]
        if len(ids) > 32:
            raise ValueError("This SAM3 ONNX export accepts at most 30 prompt tokens plus start/end. Shorten the effective text/alias.")
        result = np.zeros((1, 32), np.int64)
        result[0, :len(ids)] = ids
        return result

    def segment(self, rgb, text, progress=None, cancel=None):
        from .inference import check_cancel
        text = text.strip()
        if not text:
            raise ValueError("Enter a text prompt or alias for SAM3 ONNX, for example black dots.")
        rgb = np.ascontiguousarray(rgb)
        if rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3:
            raise ValueError("SAM3 ONNX expects an H×W×3 uint8 RGB image.")
        h, w = rgb.shape[:2]
        if not h or not w:
            raise ValueError("The image is empty.")
        token_ids = self.tokens(text)
        with self._lock:
            check_cancel(cancel)
            key = (rgb.shape, hashlib.sha256(rgb.tobytes()).digest())
            if key != self._image_key:
                if progress:
                    progress("SAM3 ONNX: encoding image…")
                image = np.ascontiguousarray(cv2.resize(rgb, (1008, 1008), interpolation=cv2.INTER_LINEAR).transpose(2, 0, 1))
                session = self.sessions["image_encoder"]
                values = session.run(None, {session.get_inputs()[0].name: image})
                self._features = dict(zip((x.name for x in session.get_outputs()), values))
                self._image_key = key
            check_cancel(cancel)
            if text != self._text_key:
                if progress:
                    progress("SAM3 ONNX: encoding text…")
                session = self.sessions["language_encoder"]
                values = session.run(None, {"tokens": token_ids})
                language = dict(zip((x.name for x in session.get_outputs()), values))
                self._language = {"language_mask": language["text_attention_mask"], "language_features": language["text_memory"]}
                self._text_key = text
            check_cancel(cancel)
            if progress:
                progress("SAM3 ONNX: decoding particle masks…")
            feed = dict(self._features, **self._language,
                        original_height=np.asarray(h, np.int64), original_width=np.asarray(w, np.int64),
                        box_coords=np.zeros((1, 1, 4), np.float32), box_labels=np.ones((1, 1), np.int64),
                        box_masks=np.ones((1, 1), bool))
            session = self.sessions["decoder"]
            values = session.run(None, {x.name: feed[x.name] for x in session.get_inputs()})
            output = dict(zip((x.name for x in session.get_outputs()), values))
            check_cancel(cancel)
            scores = np.asarray(output["scores"], float).reshape(-1)
            masks = np.asarray(output["masks"])
            if masks.size == 0 and not len(scores):
                return [], []
            if masks.ndim == 4 and masks.shape[1] == 1 and masks.shape[0] == len(scores):
                masks = masks[:, 0]
            elif masks.ndim == 4 and masks.shape[0] == 1 and masks.shape[1] == len(scores):
                masks = masks[0]
            if masks.shape != (len(scores), h, w) or masks.dtype != np.bool_ or not np.isfinite(scores).all():
                raise ValueError("SAM3 ONNX returned invalid Boolean mask dimensions or scores.")
            return list(masks), scores.tolist()

    @property
    def providers(self):
        return {name: session.get_providers() for name, session in self.sessions.items()}
