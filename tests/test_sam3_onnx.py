"""Miniature graph/GUI contract tests. These do not measure SAM model accuracy."""
import gzip
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper
import pytest

from samstudio.inference import CATALOG, InferenceEngine
from samstudio.sam3_onnx import Sam3OnnxBackend, model_directory, runtime_providers


def graph(path, inputs, values):
    nodes = [helper.make_node("Constant", [], [name], value=numpy_helper.from_array(value)) for name, value in values.items()]
    outputs = [helper.make_tensor_value_info(name, helper.np_dtype_to_tensor_dtype(value.dtype), list(value.shape)) for name, value in values.items()]
    model = helper.make_model(helper.make_graph(nodes, path.stem, inputs, outputs), opset_imports=[helper.make_opsetid("", 21)])
    model.ir_version = 10
    onnx.checker.check_model(model)
    onnx.save(model, path)


@pytest.fixture
def tiny_backend(tmp_path):
    # Real ONNX Runtime executes these tiny constant graphs. They mimic only
    # input/output contracts, never the scientific/model behavior of SAM3.
    vision = {name: np.zeros((1, 1, 2, 2), np.float32) for name in
              ["vision_pos_enc_0", "vision_pos_enc_1", "vision_pos_enc_2", "backbone_fpn_0", "backbone_fpn_1", "backbone_fpn_2"]}
    graph(tmp_path / "sam3_image_encoder.onnx", [helper.make_tensor_value_info("image", TensorProto.UINT8, [3, 1008, 1008])], vision)
    language = {"text_attention_mask": np.zeros((1, 32), bool), "text_memory": np.ones((32, 1, 256), np.float32),
                "text_embeds": np.ones((32, 1, 1024), np.float32)}
    graph(tmp_path / "sam3_language_encoder.onnx", [helper.make_tensor_value_info("tokens", TensorProto.INT64, [1, 32])], language)
    arrays = dict(vision, language_mask=language["text_attention_mask"], language_features=language["text_memory"],
                  original_height=np.asarray(24, np.int64), original_width=np.asarray(32, np.int64),
                  box_coords=np.zeros((1, 1, 4), np.float32), box_labels=np.ones((1, 1), np.int64), box_masks=np.ones((1, 1), bool))
    inputs = [helper.make_tensor_value_info(name, helper.np_dtype_to_tensor_dtype(value.dtype), list(value.shape)) for name, value in arrays.items()]
    masks = np.zeros((2, 1, 24, 32), bool)
    masks[0, 0, 2:10, 3:12] = True; masks[1, 0, 12:20, 20:28] = True
    graph(tmp_path / "sam3_decoder.onnx", inputs, {"masks": masks, "boxes": np.zeros((2, 4), np.float32), "scores": np.asarray([.9, .6], np.float32)})
    bpe = tmp_path / "miniature-test-vocabulary.gz"
    with gzip.open(bpe, "wt") as f:
        f.write("#version: 0.2\n")
    return Sam3OnnxBackend(tmp_path, bpe)


def engine(backend):
    result = InferenceEngine()
    result.spec = next(s for s in CATALOG if s.family == "SAM3 ONNX")
    result.predictor = backend; result.model = backend
    return result


def test_real_runtime_contract_original_size_filter_roi_and_scores(tiny_backend):
    e = engine(tiny_backend); rgb = np.zeros((24, 32, 3), np.uint8)
    masks = e.infer(rgb, whole=True, text_prompt="black dots", min_score=.7)
    assert len(masks) == 1 and masks[0].shape == (24, 32) and masks[0][3, 4]
    assert e.last_proposal_scores == pytest.approx([.9])
    roi = np.zeros((24, 32), bool); roi[:, :8] = True
    masks = e.infer(rgb, roi=roi, whole=False, text_prompt="black dots", min_score=.5)
    assert len(masks) == 1 and not np.any(masks[0] & ~roi)
    assert masks[0].sum() == 40
    protected = np.zeros_like(roi); protected[2:10, 3:12] = True
    assert not e.infer(rgb, whole=True, protected=protected, text_prompt="black dots", min_score=.7)


def test_prompt_changes_reuse_image_features_but_changed_pixels_do_not(tiny_backend):
    calls = {k: 0 for k in tiny_backend.sessions}
    class Counted:
        def __init__(self, name, native): self.name, self.native = name, native
        def __getattr__(self, name): return getattr(self.native, name)
        def run(self, *args):
            calls[self.name] += 1
            return self.native.run(*args)
    tiny_backend.sessions = {k: Counted(k, v) for k, v in tiny_backend.sessions.items()}
    rgb = np.zeros((24, 32, 3), np.uint8)
    tiny_backend.segment(rgb, "black dots"); tiny_backend.segment(rgb.copy(), "particles")
    assert calls == {"image_encoder": 1, "language_encoder": 2, "decoder": 2}
    rgb[0, 0] = 1; tiny_backend.segment(rgb, "particles")
    assert calls == {"image_encoder": 2, "language_encoder": 2, "decoder": 3}


def test_reject_unsupported_visual_prompts_and_long_text(tiny_backend):
    e = engine(tiny_backend); rgb = np.zeros((24, 32, 3), np.uint8)
    with pytest.raises(ValueError, match="text"):
        e.predict(rgb, [[10, 10, 1]])
    with pytest.raises(ValueError, match="requires text"):
        e.infer(rgb, whole=True)
    with pytest.raises(ValueError, match="Clear point"):
        e.infer(rgb, points=[[10, 10, 1]], text_prompt="black dots")
    with pytest.raises(ValueError, match="30 prompt tokens"):
        tiny_backend.segment(rgb, "verylongprompt" * 50)


def test_public_asset_resolution_rejects_missing_and_corrupt_sidecars(tmp_path):
    with pytest.raises(ValueError, match="folder"):
        model_directory(tmp_path / "sam3.pt")
    with pytest.raises(ValueError, match="missing"):
        model_directory(tmp_path)
    (tmp_path / "sam3_image_encoder.onnx").write_bytes(b"not a model")
    with pytest.raises(ValueError, match="checksum"):
        model_directory(tmp_path)


def test_cuda_requires_nonbase_conda_and_real_provider(monkeypatch):
    runtime = SimpleNamespace(get_available_providers=lambda: ["CPUExecutionProvider"])
    monkeypatch.delenv("CONDA_PREFIX", raising=False)
    with pytest.raises(ValueError, match="dedicated Conda"):
        runtime_providers("cuda", runtime)
    monkeypatch.setenv("CONDA_PREFIX", "/opt/anaconda3")
    with pytest.raises(ValueError, match="non-base"):
        runtime_providers("cuda", runtime)
    monkeypatch.setenv("CONDA_PREFIX", "/opt/envs/samstudio-gpu")
    with pytest.raises(RuntimeError, match="provider is unavailable"):
        runtime_providers("cuda", runtime)


def test_model_manager_has_folder_selection_and_honest_capabilities(qtbot):
    from samstudio.dialogs import ModelDialog
    dialog = ModelDialog(InferenceEngine()); qtbot.addWidget(dialog)
    dialog.family.setCurrentText("SAM3 ONNX")
    assert "folder" in dialog.browse_button.text()
    assert "No Hugging Face" in dialog.info.text()
    assert "does not support native point/shape" in dialog.info.text()
    dialog.family.setCurrentText("SAM3.1")
    assert ".pt" in dialog.browse_button.text() and "approved" in dialog.info.text()


def test_gui_text_alias_roi_and_acceptance(window, document, tiny_backend, qtbot):
    # App dispatch/persistence is tested separately from the tiny ONNX graphs.
    class Predictor:
        def segment(self, rgb, text, progress=None, cancel=None):
            assert text == "black dots"
            mask = np.zeros(rgb.shape[:2], bool); mask[5:45, 5:80] = True
            return [mask], [.9]
    window.documents[document.frame.key] = document
    from samstudio.domain import History
    window.histories[document.frame.key] = History(document)
    window.stores[document.frame.key] = window._store_for(document.frame)
    window.current_key = document.frame.key; window.canvas.set_document(document)
    window.engine = engine(Predictor()); document.text_aliases = {"particles": "black dots"}
    window.auto_checkbox.setChecked(False); window._refresh()
    window.mode.setCurrentText("Segment"); window.tool_actions["rectangle"].trigger()
    window.scope.setCurrentIndex(window.scope.findData("roi"))
    document.draft["roi"] = {"kind": "rectangle", "points": [[0, 0], [40, 60]]}
    window.text_prompt.setText("particles"); window.run_text_segmentation()
    qtbot.waitUntil(lambda: not window.busy, timeout=10000)
    assert not window.errors and len(window.canvas.preview_masks) == 1
    assert not window.canvas.preview_masks[0][:, 41:].any()
    previous = len(document.objects); window.accept_preview()
    assert len(document.objects) == previous + 1
    assert document.objects[-1].provenance["effective_text_prompt"] == "black dots"
    assert document.objects[-1].provenance["text_backend"] == "SAM3 ONNX"
    assert not window.scope.model().item(window.scope.findData("automatic")).isEnabled()
