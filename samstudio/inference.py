from __future__ import annotations

import gc
import hashlib
import json
import os
import threading
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .processing import bounding_box, filter_proposals


_TORCH_RUNTIME_LOCK = threading.RLock()
_TORCH_RUNTIME_READY = False


def initialize_torch_runtime():
    """Initialize native CPU thread pools once, before Qt starts model workers.

    Reconfiguring PyTorch's process-wide OpenMP pool from a QRunnable can crash
    a cold process in torchvision's first contiguous tensor conversion. Model
    construction/embedding/prediction still run in the background worker.
    """
    global _TORCH_RUNTIME_READY
    with _TORCH_RUNTIME_LOCK:
        import torch
        if not _TORCH_RUNTIME_READY:
            torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
            # Force a parallel strided-to-contiguous conversion on the caller
            # thread, rather than during the first Qt background inference.
            torch.zeros((3, 256, 256)).transpose(1, 2).contiguous().sum().item()
            _TORCH_RUNTIME_READY = True
    return torch


def data_directory():
    override = os.environ.get("SAM_STUDIO_DATA_DIR")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))) / "SAMImageStudio"
    return Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))) / "sam-image-studio"


@dataclass(frozen=True)
class ModelSpec:
    family: str
    variant: str
    filename: str
    url: str = ""
    config: str = ""
    sha256: str = ""

    @property
    def label(self):
        return f"{self.family} / {self.variant}"


CATALOG = [
    ModelSpec("SAM1", "ViT-B", "sam_vit_b_01ec64.pth", "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth", "vit_b", "ec2df62732614e57411cdcf32a23ffdf28910380d03139ee0f4fcbe91eb8c912"),
    ModelSpec("SAM1", "ViT-L", "sam_vit_l_0b3195.pth", "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_l_0b3195.pth", "vit_l"),
    ModelSpec("SAM1", "ViT-H", "sam_vit_h_4b8939.pth", "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth", "vit_h"),
]
for version, stamp, prefix in [("SAM2", "072824", "sam2"), ("SAM2.1", "092824", "sam2.1")]:
    for label, suffix, cfg in [("Tiny", "tiny", "t"), ("Small", "small", "s"), ("Base+", "base_plus", "b+"), ("Large", "large", "l")]:
        filename = f"{prefix}_hiera_{suffix}.pt"
        config = f"configs/{prefix}/{prefix}_hiera_{cfg}.yaml"
        if prefix == "sam2":
            config = f"configs/sam2/sam2_hiera_{cfg}.yaml"
        checksum = "7402e0d864fa82708a20fbd15bc84245c2f26dff0eb43a4b5b93452deb34be69" if version == "SAM2.1" and label == "Tiny" else ""
        CATALOG.append(ModelSpec(version, label, filename,
            f"https://dl.fbaipublicfiles.com/segment_anything_2/{stamp}/{filename}", config, checksum))
CATALOG.append(ModelSpec("SAM3 ONNX", "ViT-H · text prompts", "sam3-onnx-v3", config="sam3-onnx-v3"))
CATALOG.append(ModelSpec("SAM3", "Native interactive", "sam3.pt", config="sam3"))
CATALOG.append(ModelSpec("SAM3.1", "Multiplex · GPU only", "sam3.1_multiplex.pt", config="sam3.1"))


def check_cancel(cancel):
    if cancel and cancel.is_set():
        raise InterruptedError("Operation cancelled.")


def file_digest(path, cancel=None):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(4 * 1024 * 1024):
            check_cancel(cancel)
            digest.update(block)
    return digest.hexdigest()


def download_file(url: str, destination: Path, sha256="", progress=None, cancel=None):
    """No partially downloaded file is ever promoted to a usable checkpoint."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if not sha256 or file_digest(destination, cancel) == sha256:
            return destination
        raise ValueError(f"Checksum mismatch in cached model {destination.name}. Remove this file and retry.")
    temporary = destination.with_suffix(destination.suffix + ".part")
    done = temporary.stat().st_size if temporary.exists() else 0
    headers = {"User-Agent": "SAMImageStudio/1.0"}
    if done:
        headers["Range"] = f"bytes={done}-"
    check_cancel(cancel)
    try:
        try:
            response = urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=45)
        except urllib.error.HTTPError as error:
            if error.code != 416 or not done:
                raise
            # A stale .part may already contain the complete file, or may be
            # longer than a newer remote file. Restart rather than getting stuck.
            if sha256 and file_digest(temporary, cancel) == sha256:
                os.replace(temporary, destination)
                return destination
            response = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": headers["User-Agent"]}), timeout=45)
            done = 0
        if done and response.status != 206:
            done = 0
        if response.status == 206:
            content_range = re.match(r"bytes (\d+)-(\d+)/(\d+|\*)", response.headers.get("Content-Range", ""))
            if not content_range or int(content_range[1]) != done:
                response.close()
                raise ValueError("The download server returned an invalid resume range. Delete the .part file and retry.")
        total = int(response.headers.get("Content-Length", "0")) + done
        with response, temporary.open("ab" if done else "wb") as output:
            while block := response.read(1024 * 1024):
                check_cancel(cancel)
                output.write(block)
                done += len(block)
                if progress:
                    progress(f"Downloading {destination.name}: {done/1048576:.1f}" + (f" / {total/1048576:.1f} MB" if total else " MB"))
            output.flush()
            os.fsync(output.fileno())
        check_cancel(cancel)
        if total and done != total:
            raise ValueError("The model download is incomplete. Retry to resume it.")
        if sha256 and file_digest(temporary, cancel) != sha256:
            temporary.unlink(missing_ok=True)
            raise ValueError("Downloaded model checksum failed. The file was discarded. Retry the download.")
        if temporary.stat().st_size < 1024:
            raise ValueError("The downloaded model is unexpectedly small.")
        os.replace(temporary, destination)
        return destination
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"Download failed (HTTP {error.code}). Check internet/proxy access or select a compatible local checkpoint.") from error


class InferenceEngine:
    def __init__(self):
        self.spec: ModelSpec | None = None
        self.device = "cpu"
        self.predictor = None
        self.model = None
        self.processor = None
        self._image_key = None
        self._text_state = None
        self._lock = threading.RLock()
        self.text_grounder = None
        self.last_proposal_scores = []

    @property
    def ready(self):
        return self.predictor is not None

    def load(self, spec: ModelSpec, device="cpu", checkpoint=None, progress=None, cancel=None, hf_token=None):
        if spec.family == "SAM3 ONNX":
            from .sam3_onnx import Sam3OnnxBackend, model_directory
            if device == "auto":
                from .hardware import automatic_device
                device = automatic_device()
            if device != "cpu" and not re.fullmatch(r"cuda(?::[0-9]+)?", device):
                raise ValueError("Select CPU or NVIDIA CUDA.")
            # Check the runtime/provider before downloading several GiB.
            try:
                import onnxruntime as ort
                import ftfy
                from .sam3_onnx import runtime_providers
                runtime_providers(device, ort)
            except ImportError as error:
                raise RuntimeError("Install the SAM3 ONNX runtime first: python scripts/install_onnx_runtime.py --device cpu (or cuda). " + str(error)) from error
            directory, tokenizer = model_directory(checkpoint, progress, cancel)
            with self._lock:
                predictor = Sam3OnnxBackend(directory, tokenizer, device, progress, cancel)
                self.model, self.predictor, self.processor = predictor, predictor, None
                self.spec, self.device, self._image_key, self._text_state = spec, device, None, None
            gc.collect()
            return {"model": spec.label, "device": device, "checkpoint": str(directory)}
        torch = initialize_torch_runtime()
        if device == "auto":
            from .hardware import automatic_device
            device = automatic_device()
        if device != "cpu" and not re.fullmatch(r"cuda(?::[0-9]+)?",device):
            raise ValueError("Select CPU or NVIDIA CUDA.")
        if device.startswith("cuda") and not os.environ.get("CONDA_PREFIX"):
            raise ValueError("GPU execution requires a dedicated Conda environment. Follow GPU/README.md.")
        if device.startswith("cuda") and not torch.cuda.is_available():
            raise ValueError("CUDA is unavailable in this environment. Use CPU or install the optional GPU environment with a compatible NVIDIA driver.")
        if spec.family in ("SAM3", "SAM3.1") and not device.startswith("cuda"):
            raise ValueError("The optional native SAM3 backend is enabled for CUDA only in this release. Use SAM1/SAM2 on CPU.")
        if checkpoint:
            path = Path(checkpoint).expanduser().resolve()
            if path.suffix.lower() not in (".pt", ".pth") or not path.is_file():
                raise ValueError("Select an existing compatible .pt or .pth checkpoint.")
        elif spec.family in ("SAM3", "SAM3.1"):
            try:
                from huggingface_hub import hf_hub_download
                download_options = {"token": hf_token} if hf_token else {}
                path = Path(hf_hub_download("facebook/"+spec.family.lower(), spec.filename, **download_options))
            except Exception as error:
                detail = str(error).replace(hf_token, "[redacted]") if hf_token else str(error)
                raise RuntimeError(f"{spec.family} requires approved checkpoint access. Paste a read token in Model manager, use your local Hugging Face login, or select a local {spec.filename} checkpoint. " + detail) from None
        else:
            path = download_file(spec.url, data_directory() / "models" / spec.filename, spec.sha256, progress, cancel)
        check_cancel(cancel)
        if progress:
            progress(f"Loading {spec.label} on {device.upper()}…")
        with self._lock, torch.inference_mode():
            try:
                if spec.family == "SAM1":
                    from segment_anything import sam_model_registry, SamPredictor
                    model = sam_model_registry[spec.config](checkpoint=str(path))
                    model.to(device).eval()
                    predictor = SamPredictor(model)
                    processor = None
                elif spec.family in ("SAM2", "SAM2.1"):
                    from sam2.build_sam import build_sam2
                    from sam2.sam2_image_predictor import SAM2ImagePredictor
                    model = build_sam2(spec.config, str(path), device=device, apply_postprocessing=False)
                    predictor = SAM2ImagePredictor(model)
                    processor = None
                elif spec.family == "SAM3.1":
                    from sam3.model_builder import build_sam3_multiplex_video_predictor
                    from .sam31_backend import Sam31Backend
                    with torch.cuda.device(device):
                        model = build_sam3_multiplex_video_predictor(checkpoint_path=str(path),
                            use_fa3=False, compile=False, warm_up=False, async_loading_frames=False)
                    predictor = Sam31Backend(model, device)
                    processor = None
                else:
                    from sam3.model_builder import build_sam3_image_model
                    from sam3.model.sam3_image_processor import Sam3Processor
                    model = build_sam3_image_model(checkpoint_path=str(path), load_from_HF=False,
                                                  device=device, enable_inst_interactivity=True, compile=False)
                    predictor = model.inst_interactive_predictor
                    processor = Sam3Processor(model, device=device)
            except ImportError as error:
                raise RuntimeError(f"The {spec.family} backend is not installed or cannot import. Use its optional installation instructions. Details: {error}") from error
            except (RuntimeError, KeyError, ValueError) as error:
                raise RuntimeError(f"Cannot load {spec.label}. The .pt/.pth must match the selected architecture/configuration. Details: {error}") from error
            check_cancel(cancel)
            self.model, self.predictor, self.processor = model, predictor, processor
            self.spec, self.device, self._image_key, self._text_state = spec, device, None, None
        gc.collect()
        return {"model": spec.label, "device": device, "checkpoint": str(path)}

    def _set_image(self, rgb, progress=None, cancel=None):
        if not rgb.flags.writeable:
            rgb = rgb.copy()
        key = (rgb.shape,hashlib.sha256(rgb.tobytes()).hexdigest())
        if self._image_key != key:
            check_cancel(cancel)
            if progress:
                progress("Computing image embedding…")
            if self.spec and self.spec.family == "SAM3":
                # The official interactive predictor has no independent backbone.
                # Sam3Image.predict_inst consumes features prepared by Sam3Processor.
                from PIL import Image
                self._text_state = self.processor.set_image(Image.fromarray(rgb))
            else:
                self.predictor.set_image(rgb)
                self._text_state = None
            self._image_key = key
        check_cancel(cancel)

    def predict(self, rgb, points=None, box=None, progress=None, cancel=None):
        if not self.ready:
            raise ValueError("Load a SAM model first.")
        if self.spec and self.spec.family == "SAM3 ONNX":
            raise ValueError("This SAM3 ONNX export supports text prompts only. Use text with an optional ROI, or select SAM3.1 for native point/shape prompts.")
        import torch
        with self._lock, torch.inference_mode():
            if self.spec and self.spec.family == "SAM3.1":
                return self.predictor.predict(np.ascontiguousarray(rgb,dtype=np.uint8), points, box, cancel)
            self._set_image(np.ascontiguousarray(rgb, dtype=np.uint8), progress, cancel)
            coords = np.asarray([[p[0], p[1]] for p in points], np.float32) if points else None
            labels = np.asarray([int(p[2]) for p in points], np.int32) if points else None
            if coords is None and box is None:
                raise ValueError("Add a positive point or draw an ROI first.")
            options = dict(point_coords=coords, point_labels=labels,
                           box=np.asarray(box, np.float32) if box is not None else None,
                           multimask_output=True)
            if self.spec and self.spec.family == "SAM3":
                masks, scores, _ = self.model.predict_inst(self._text_state, **options)
            else:
                masks, scores, _ = self.predictor.predict(**options)
            check_cancel(cancel)
            masks = np.asarray(masks, dtype=bool)
            scores = np.asarray(scores, dtype=float).reshape(-1)
            if masks.ndim == 2:
                masks = masks[None]
            if masks.shape[1:] != rgb.shape[:2] or len(scores) != len(masks):
                raise ValueError("The model returned invalid mask dimensions.")
            best = int(np.argmax(scores))
            return masks[best], float(scores[best])

    def infer(self, rgb, points=None, roi=None, protected=None, whole=False, grid=8,
              min_score=.70, min_area=8, max_objects=300, progress=None, cancel=None, text_prompt=""):
        if not self.ready:
            raise ValueError("Load a SAM model first.")
        shape = rgb.shape[:2]
        protected = np.zeros(shape, bool) if protected is None else np.asarray(protected, bool)
        if protected.shape != shape or roi is not None and roi.shape != shape:
            raise ValueError("ROI/protected masks do not match the image dimensions.")
        self.last_proposal_scores = []
        def finish(candidates, scores, clip):
            output = filter_proposals(candidates, protected, clip, min_area)
            self.last_proposal_scores = []
            for mask in output:
                overlaps = [int((mask & candidate).sum()) / max(1, int((mask | candidate).sum())) for candidate in candidates]
                score = scores[int(np.argmax(overlaps))] if overlaps and scores else None
                self.last_proposal_scores.append(float(score) if score is not None and np.isfinite(score) else None)
            return output
        if self.spec and self.spec.family == "SAM3 ONNX":
            if points:
                raise ValueError("Clear point prompts for SAM3 ONNX. Use a text prompt and an optional area ROI; native geometric prompts require SAM3.1.")
            if not text_prompt.strip():
                raise ValueError("SAM3 ONNX requires text, for example black dots. Automatic grid and shape-only concepts are not supported by this export.")
            with self._lock:
                candidates, scores = self.predictor.segment(np.ascontiguousarray(rgb, dtype=np.uint8), text_prompt, progress, cancel)
            pairs = [(mask, score) for mask, score in zip(candidates, scores) if score >= min_score]
            result = finish([p[0] for p in pairs], [p[1] for p in pairs], None if whole else roi)[:max_objects]
            self.last_proposal_scores = self.last_proposal_scores[:len(result)]
            return result
        if text_prompt.strip():
            if self.spec.family == "SAM3.1":
                with self._lock:
                    masks,scores = self.predictor.concepts(rgb,text=text_prompt,cancel=cancel)
                return finish(masks,scores,None if whole else roi)[:max_objects]
            if self.spec.family == "SAM1":
                raise ValueError("Text prompts are available for SAM2 / SAM2.1 with Grounding DINO, or native SAM3.")
            if self.spec.family in ("SAM2", "SAM2.1"):
                from .text_prompts import TextGrounder
                if self.text_grounder is None:
                    self.text_grounder = TextGrounder()
                boxes, detection_scores = self.text_grounder.detect(rgb,text_prompt,self.device,progress=progress,cancel=cancel)
                masks, scores = [], []
                for index, box in enumerate(boxes[:max_objects]):
                    check_cancel(cancel)
                    if progress:progress(f"Segmenting text detection {index+1}/{min(len(boxes),max_objects)}…")
                    mask, score = self.predict(rgb, box=box, cancel=cancel)
                    masks.append(mask);scores.append(score)
                return finish(masks,scores,None if whole else roi)
            if self.processor is None:
                raise ValueError("Load a compatible text backend first.")
            import torch
            from PIL import Image
            with self._lock, torch.inference_mode():
                check_cancel(cancel)
                state = self.processor.set_image(Image.fromarray(rgb))
                state = self.processor.set_text_prompt(text_prompt.strip(), state)
                masks = state["masks"].detach().cpu().numpy().reshape(-1, *shape).astype(bool)
                scores = state.get("scores")
                scores = scores.detach().cpu().numpy().reshape(-1).tolist() if scores is not None else [None]*len(masks)
                check_cancel(cancel)
            return finish(list(masks), scores, None if whole else roi)
        # Whole-image *scope* does not select automatic grid generation when
        # the user supplied a point or shape. Native SAM predicts one prompted
        # object in either scope; only the optional final ROI clipping differs.
        if points or roi is not None or not whole:
            box = None
            if roi is not None:
                x, y, w, h = bounding_box(roi)
                if w == 0 or h == 0:
                    raise ValueError("The ROI is empty.")
                box = [x, y, x + w, y + h]
            if not points and box is None:
                raise ValueError("Draw an ROI or add prompt points. Use Whole image for automatic grid segmentation.")
            mask, score = self.predict(rgb, points, box, progress, cancel)
            return finish([mask], [score], None if whole else roi)
        if not 2 <= int(grid) <= 64:
            raise ValueError("Grid points per side must be between 2 and 64.")
        candidates, candidate_scores = [], []
        h, w = shape
        xs, ys = (np.arange(grid) + .5) * w / grid, (np.arange(grid) + .5) * h / grid
        count = 0
        for y in ys:
            for x in xs:
                check_cancel(cancel)
                count += 1
                if progress:
                    progress(f"Automatic SAM prompts: {count}/{grid*grid}  •  {len(candidates)} candidate masks")
                if protected[min(h-1, int(y)), min(w-1, int(x))]:
                    continue
                mask, score = self.predict(rgb, [[float(x), float(y), 1]], None, None, cancel)
                area = int(mask.sum())
                if score >= min_score and min_area <= area <= h * w * .85:
                    candidates.append(mask);candidate_scores.append(score)
                if len(candidates) >= max_objects:
                    break
            if len(candidates) >= max_objects:
                break
        check_cancel(cancel)
        return finish(candidates,candidate_scores,None)


LAMA_URL = "https://github.com/enesmsahin/simple-lama-inpainting/releases/download/v0.1.0/big-lama.pt"
LAMA_SHA256 = "7ba7aa7ac37a4d41fdbbeba3a2af7ead18058552997e3a3cd1a3b2210c9e6b4c"


def lama_fill(rgb, target, checkpoint=None, progress=None, cancel=None):
    import torch
    import torch.nn.functional as F
    if target.all() or not target.any():
        raise ValueError("LaMa needs a nonempty removal region and some remaining background.")
    path = Path(checkpoint) if checkpoint else download_file(LAMA_URL, data_directory() / "models/big-lama.pt", LAMA_SHA256, progress=progress, cancel=cancel)
    if progress:
        progress("Loading LaMa inpainting model…")
    with torch.inference_mode():
        model = torch.jit.load(str(path), map_location="cpu").eval()
        image = torch.from_numpy(np.ascontiguousarray(rgb.transpose(2, 0, 1))).float()[None] / 255
        mask = torch.from_numpy(target.astype(np.float32))[None, None]
        h, w = target.shape
        pad = (0, (-w) % 8, 0, (-h) % 8)
        image = F.pad(image, pad, mode="reflect" if min(h, w) > 8 else "replicate")
        mask = F.pad(mask, pad)
        check_cancel(cancel)
        output = model(image, mask)
        if isinstance(output, dict):
            output = output["inpainted"]
        output = output[0, :, :h, :w].detach().cpu().numpy().transpose(1, 2, 0)
        check_cancel(cancel)
    if output.shape != rgb.shape or not np.isfinite(output).all():
        raise ValueError("LaMa returned an invalid image.")
    result = rgb.copy()
    result[target] = np.rint(np.clip(output[target], 0, 1) * 255).astype(np.uint8)
    return result

