"""Opt-in tests with genuine public checkpoints, never generated dummy weights."""
import gc
import json
import os
import time
import subprocess
import sys
from pathlib import Path
import numpy as np
import pytest
from PIL import Image
from samstudio.inference import CATALOG, InferenceEngine, lama_fill, file_digest, LAMA_SHA256
from samstudio.processing import shape_mask
from samstudio.domain import Document
from samstudio.imageio import load_file, LoadResult

pytestmark=pytest.mark.integration
WEIGHTS=Path(os.environ.get("SAM_STUDIO_TEST_WEIGHTS","not_provided"))
IMAGE=Path(os.environ.get("SAM_STUDIO_TEST_IMAGE","not_provided"))
REPORTS=[]


@pytest.fixture(scope="module",params=[("SAM1","ViT-B"),("SAM2.1","Tiny")])
def loaded_engine(request):
    family,variant=request.param
    spec=next(s for s in CATALOG if s.family==family and s.variant==variant)
    path=WEIGHTS/spec.filename
    if not path.is_file() or not IMAGE.is_file():
        pytest.skip("Set SAM_STUDIO_TEST_WEIGHTS and SAM_STUDIO_TEST_IMAGE to real downloaded assets.")
    started=time.perf_counter();engine=InferenceEngine();result=engine.load(spec,"cpu",path)
    assert result["device"]=="cpu" and engine.ready
    rgb=np.asarray(Image.open(IMAGE).convert("RGB").resize((600,400))).copy()
    report={"family":family,"variant":variant,"device":"cpu","checkpoint_sha256":file_digest(path),
            "load_seconds":round(time.perf_counter()-started,3)}
    REPORTS.append(report)
    yield engine,rgb,report
    engine.predictor=engine.model=engine.processor=None;gc.collect()


@pytest.mark.parametrize("automatic", [False, True])
def test_real_inverted_region_in_qt_prompt_and_grid(loaded_engine,window,qtbot,tmp_path,automatic):
    engine,rgb,report=loaded_engine
    path=tmp_path/"inverse-real-model.png";Image.fromarray(rgb).save(path)
    window._opened(LoadResult(load_file(path)));doc=window.document
    doc.ensure_group("Existing objects")
    accepted=np.zeros(doc.frame.shape,bool);accepted[75:100,135:155]=True
    original=doc.add_object("mask",mask=accepted,provenance={"method":"manual"})
    window.engine=engine;window.auto_checkbox.setChecked(False);window.mode.setCurrentText("Segment");window.tool_actions["rectangle"].trigger();window.scope.setCurrentIndex(window.scope.findData("single"))
    window.select_all_objects();window.invert_region();inverse=window._selection_mask().copy()
    window.options.update(grid=2,min_score=.2,min_area=4)
    if automatic:window.scope.setCurrentIndex(window.scope.findData("automatic"))
    else:window._prompt_added(167,125,1)
    window.run_inference();qtbot.waitUntil(lambda:not window.busy,timeout=120000)
    assert not window.errors and window.canvas.preview_masks
    assert all(not (mask & ~inverse).any() for mask in window.canvas.preview_masks)
    window.accept_preview()
    assert len(doc.objects)>1 and np.array_equal(doc.objects[0].mask,accepted) and doc.objects[0].id==original.id
    assert all(not (obj.mask & accepted).any() for obj in doc.objects[1:])
    report["v13_inverted_"+("grid" if automatic else "prompt")]=True


def test_real_segmentation_uses_smoothed_image_source(loaded_engine,window,qtbot,tmp_path):
    from samstudio.processing import smooth_image
    engine,rgb,report=loaded_engine
    path=tmp_path/"smoothed-real-model.png";Image.fromarray(rgb).save(path)
    window._opened(LoadResult(load_file(path)));doc=window.document;doc.ensure_group("Object")
    result=smooth_image(doc.frame.raw,sigma=.8)
    doc.apply_image_smoothing(result,np.ones(doc.frame.shape,bool),"gaussian",{"sigma":.8})
    window.engine=engine;window.auto_checkbox.setChecked(False);window.mode.setCurrentText("Segment");window.tool_actions["rectangle"].trigger();window.scope.setCurrentIndex(window.scope.findData("single"))
    window.cleaned_checkbox.setChecked(True);window._prompt_added(167,125,1);window.run_inference()
    qtbot.waitUntil(lambda:not window.busy,timeout=120000)
    assert not window.errors and window.canvas.preview_masks
    window.accept_preview();objects=doc.foreground_objects()
    assert objects and objects[0].provenance["input"]=="cleaned"
    assert np.array_equal(doc.frame.raw,rgb) and np.array_equal(doc.working,result)
    report["v13_smoothed_source_segmentation"]=True


def test_real_positive_point_and_box(loaded_engine):
    engine,rgb,report=loaded_engine
    started=time.perf_counter()
    mask,score=engine.predict(rgb,[[167,125,1]])
    assert mask.shape==rgb.shape[:2] and mask.dtype==bool and mask.any() and np.isfinite(score)
    boxed,box_score=engine.predict(rgb,box=[100,60,220,240])
    assert boxed.any() and np.isfinite(box_score)
    report.update(prompt_seconds=round(time.perf_counter()-started,3),point_area=int(mask.sum()),point_score=score,box_area=int(boxed.sum()))


def test_real_roi_clipping_negative_point_and_existing_object_protection(loaded_engine):
    engine,rgb,report=loaded_engine
    roi=shape_mask("ellipse",[[100,60],[230,230]],rgb.shape[:2])
    protected=np.zeros(roi.shape,bool);protected[105:145,150:185]=True
    result=engine.infer(rgb,points=[[167,125,1],[210,220,0]],roi=roi,protected=protected,min_area=1)
    assert result
    assert all(not (m & ~roi).any() and not (m & protected).any() for m in result)
    report["roi_area"]=sum(int(m.sum()) for m in result)


def test_real_whole_image_grid_preserves_accepted_pixels(loaded_engine):
    engine,rgb,report=loaded_engine
    protected=np.zeros(rgb.shape[:2],bool);protected[100:170,140:200]=True;before=protected.copy()
    started=time.perf_counter()
    result=engine.infer(rgb,whole=True,protected=protected,grid=2,min_score=.2,min_area=4)
    assert result and np.array_equal(protected,before)
    assert all(not (m & protected).any() for m in result)
    report.update(whole_seconds=round(time.perf_counter()-started,3),whole_new_masks=len(result))


def test_real_mismatched_checkpoint_rejected_and_previous_model_retained(loaded_engine,tmp_path):
    engine,rgb,report=loaded_engine
    import torch
    path=tmp_path/"wrong.pt";torch.save({"unrelated":torch.zeros(1)},path)
    previous=engine.predictor
    with pytest.raises(RuntimeError,match="Cannot load"):engine.load(engine.spec,checkpoint=path)
    assert engine.predictor is previous
    assert engine.predict(rgb,[[167,125,1]])[0].any()
    report["failed_load_preserved_predictor"]=True


def test_real_qt_preview_accept_autosave_reopen(loaded_engine,window,qtbot,tmp_path):
    engine,rgb,report=loaded_engine
    path=tmp_path/"real-model-image.png";Image.fromarray(rgb).save(path)
    window._opened(LoadResult(load_file(path)));doc=window.document
    window._commit("group",lambda:doc.ensure_group("Truck objects"))
    window.engine=engine;window.auto_checkbox.setChecked(False);window.mode.setCurrentText("Segment");window.tool_actions["rectangle"].trigger();window.scope.setCurrentIndex(window.scope.findData("single"))
    window._prompt_added(167,125,1)
    window.run_inference(force_whole=False)
    qtbot.waitUntil(lambda:not window.busy,timeout=120000)
    assert window.canvas.preview_masks and not window.errors
    window.accept_preview();assert len(doc.objects)==1 and doc.objects[0].mask.any()
    expected=doc.objects[0].mask.copy()
    restored=Document(doc.frame);assert window.stores[doc.frame.key].load(restored)[0]
    assert np.array_equal(restored.objects[0].mask,expected)
    assert restored.objects[0].provenance["model"]==engine.spec.label
    window.undo();assert not doc.objects
    window.redo();assert np.array_equal(doc.objects[0].mask,expected)
    report["qt_preview_accept_recovery"]=True


def test_real_prompted_whole_scope_matches_native_prediction_not_grid(loaded_engine):
    engine,rgb,report=loaded_engine
    points=[[167.,125.,1],[260.,300.,0]]
    expected,_=engine.predict(rgb,points)
    masks=engine.infer(rgb,points=points,whole=True,min_area=1)
    assert len(masks)==1 and np.array_equal(masks[0],expected)
    report["prompted_whole_scope_exact_native_prediction"]=True


def test_real_qt_prompts_created_before_model_load_then_new_clicks(loaded_engine,window,qtbot,tmp_path):
    from samstudio.dialogs import ModelDialog
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QDialog
    engine,rgb,report=loaded_engine
    # Smaller image makes the cold embedding practical while retaining real weights.
    path=tmp_path/"preload-prompts.png";Image.fromarray(rgb).save(path)
    window._opened(LoadResult(load_file(path)));doc=window.document
    window._commit("group",lambda:doc.ensure_group("Objects"))
    window.mode.setCurrentText("Segment");window.options.update(grid=2,max_objects=20);window._prompt_added(167,125,1)
    window._prompt_added(180,140,1)
    assert not window.engine.ready and len(doc.draft["points"])==2
    # Load through the actual GUI worker, with a genuine cached checkpoint.
    from unittest.mock import patch
    spec=engine.spec
    with patch.object(ModelDialog,"exec",return_value=QDialog.DialogCode.Accepted), \
         patch.object(ModelDialog,"values",return_value=(spec,"cpu",str(WEIGHTS/spec.filename))):
        window.model_dialog()
    qtbot.waitUntil(lambda:not window.busy,timeout=120000)
    assert window.engine.ready
    qtbot.mouseClick(window.canvas,Qt.MouseButton.RightButton,pos=window.canvas.to_widget([260,300]).toPoint())
    qtbot.waitUntil(lambda:not window.busy and bool(window.canvas.preview_masks),timeout=120000)
    # Check an additional click after a successful live preview as well.
    qtbot.mouseClick(window.canvas,Qt.MouseButton.LeftButton,pos=window.canvas.to_widget([170,130]).toPoint())
    qtbot.waitUntil(lambda:not window.busy and bool(window.canvas.preview_masks),timeout=120000)
    assert len(doc.draft["points"])==4 and not window.errors
    assert window.scope.currentData()=="prompt"
    assert any(m[125,167] for m in window.canvas.preview_masks)
    expected=[m.copy() for m in window.canvas.preview_masks]
    window.accept_preview();assert len(doc.objects)==len(expected)
    assert all(np.array_equal(o.mask,m) for o,m in zip(doc.objects,expected))
    report["preload_prompts_then_new_live_clicks"]=True


def test_real_lama_only_changes_selected_pixels():
    path=WEIGHTS/"big-lama.pt"
    if not path.is_file() or not IMAGE.is_file():pytest.skip("Provide real LaMa checkpoint and test image.")
    assert file_digest(path)==LAMA_SHA256
    rgb=np.asarray(Image.open(IMAGE).convert("RGB").resize((128,85))).copy()
    target=np.zeros(rgb.shape[:2],bool);target[25:50,30:55]=True
    started=time.perf_counter();output=lama_fill(rgb,target,path)
    assert output.shape==rgb.shape and output.dtype==rgb.dtype
    assert np.array_equal(output[~target],rgb[~target]) and np.any(output[target]!=rgb[target])
    REPORTS.append({"family":"LaMa","device":"cpu","checkpoint_sha256":LAMA_SHA256,
                    "inference_seconds":round(time.perf_counter()-started,3),"outside_region_unchanged":True})


def test_real_zoomed_pixel_prompt_then_cleaning_object_recovery(loaded_engine,window,qtbot,tmp_path):
    from PySide6.QtCore import QPointF, Qt
    engine,rgb,report=loaded_engine
    path=tmp_path/"zoomed-prompt.png";Image.fromarray(rgb).save(path)
    window._opened(LoadResult(load_file(path)));doc=window.document
    window._commit("group",lambda:doc.ensure_group("Particle"))
    window.engine=engine;window.mode.setCurrentText("Segment");window.tool_actions["point"].trigger()
    window.canvas.scale=40
    window.canvas.offset=QPointF(200-167.2*40,200-125.2*40)
    qtbot.mouseClick(window.canvas,Qt.MouseButton.LeftButton,pos=window.canvas.to_widget([167.2,125.2]).toPoint())
    qtbot.waitUntil(lambda:not window.busy and bool(window.canvas.preview_masks),timeout=120000)
    assert doc.draft["roi"] is None and len(doc.draft["points"])==1
    assert window.scope.currentData()=="prompt"
    expected=window.canvas.preview_masks[0].copy()
    assert any(m[125,167] for m in window.canvas.preview_masks)
    window.accept_preview();obj=doc.objects[0];window.canvas.set_selected([obj.id])
    window.mode.setCurrentText("Clean");window.delete_for_cleaning()
    assert obj.role=="cleaning" and obj.visible and np.array_equal(doc.removed,expected)
    restored=Document(doc.frame);assert window.stores[doc.frame.key].load(restored)[0]
    assert restored.objects[0].role=="cleaning" and np.array_equal(restored.removed,expected)
    restored.delete_objects([restored.objects[0].id]);assert restored.working is None
    assert not window.errors
    report["zoom_40x_point_and_cleaning_recovery"]=True


@pytest.mark.parametrize("family,filename",[("SAM1","sam_vit_b_01ec64.pth"),("SAM2.1","sam2.1_hiera_tiny.pt")])
def test_fresh_gui_process_real_model_loading_preexisting_points_and_histogram(family,filename,tmp_path):
    if not (WEIGHTS/filename).is_file():pytest.skip("Provide genuine checkpoint assets.")
    script=Path(__file__).resolve().parents[1]/"scripts/cold_start_smoke.py"
    for repetition in range(2):
        report=tmp_path/f"cold-{family}-{repetition}.json"
        result=subprocess.run([sys.executable,"-X","faulthandler",str(script),"--family",family,
            "--checkpoint",str(WEIGHTS/filename),"--report",str(report)],capture_output=True,text=True,timeout=180)
        assert result.returncode==0,result.stdout+result.stderr
        evidence=json.loads(report.read_text());assert evidence["fresh_process"] and not evidence["errors"]
        REPORTS.append(evidence)


@pytest.fixture(scope="module",autouse=True)
def save_results():
    yield
    if REPORTS:
        path=Path(os.environ.get("SAM_STUDIO_TEST_REPORT","docs/validation/real_models.json"))
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps({"real_checkpoint_tests":REPORTS,"not_verified":["NVIDIA CUDA","Native SAM3","SAM1 ViT-L/ViT-H","SAM2 Small/Base+/Large","Native Windows EXE"]},indent=2))


def test_real_text_alias_grounding_and_sam_segmentation(loaded_engine,window,qtbot,tmp_path):
    from samstudio.text_prompts import resolve_prompt,GROUNDING_MODEL,GROUNDING_REVISION
    engine,rgb,report=loaded_engine
    if engine.spec.family=='SAM1':
        with pytest.raises(ValueError,match='SAM2'):engine.infer(rgb,text_prompt='truck',whole=True)
        report['v14_text_rejected_on_sam1']=True
        return
    # A genuinely ineffective alias name resolves before the real detector runs.
    path=tmp_path/'text-real.png';Image.fromarray(rgb).save(path);window._opened(LoadResult(load_file(path)))
    doc=window.document;doc.ensure_group('Vehicles');doc.text_aliases={'sample vehicle':'truck'}
    window.engine=engine;window.auto_checkbox.setChecked(False);window.mode.setCurrentText('Segment');window.text_prompt.setText('sample vehicle')
    window.run_inference();qtbot.waitUntil(lambda:not window.busy,timeout=180000)
    assert not window.errors and window.canvas.preview_masks
    assert window._preview_context['effective_text_prompt']=='truck'
    window.accept_preview();assert doc.objects and all(o.mask.any() for o in doc.objects)
    assert all(o.provenance['confidence_score'] is not None for o in doc.objects)
    assert all(o.provenance['text_backend']=='Grounding DINO Tiny → SAM2' for o in doc.objects)
    report['v14_real_text_alias']={'input':'sample vehicle','effective':'truck','detector':GROUNDING_MODEL,'revision':GROUNDING_REVISION,'masks':len(doc.objects)}
    # Exact ROI clips grounded detections too; existing annotations stay protected.
    doc.objects=[];roi=np.zeros(doc.frame.shape,bool);roi[:220,:300]=True;doc.set_region(roi)
    window.run_inference();qtbot.waitUntil(lambda:not window.busy,timeout=180000)
    assert not window.errors and window.canvas.preview_masks and all(not (m & ~roi).any() for m in window.canvas.preview_masks)
    report['v14_text_exact_roi']=True


def test_real_lama_rotated_padding_fill_and_restoration(tmp_path):
    from samstudio.domain import ImageFrame,History
    from samstudio.transforms import rotate_document
    from samstudio.processing import neighbor_fill
    checkpoint=WEIGHTS/'big-lama.pt'
    if not checkpoint.is_file():pytest.skip('Genuine LaMa checkpoint required.')
    rgb=np.asarray(Image.open(IMAGE).convert('RGB').resize((240,160))).copy()
    doc=Document(ImageFrame(str(IMAGE),rgb));history=History(doc)
    target=history.apply('rotate',lambda:rotate_document(doc,30,'square'))
    record=doc.remove_for_cleaning(target)
    result=lama_fill(doc.working,target,checkpoint=checkpoint)
    doc.apply_cleaning_fill(result,target,'lama')
    assert not doc.removed.any() and not np.array_equal(doc.working[target],np.zeros_like(doc.working[target]))
    assert np.array_equal(doc.working[~target],doc.frame.raw[~target])
    doc.delete_objects([record.id]);assert np.array_equal(doc.working,doc.frame.raw)
    history.undo();assert np.array_equal(doc.frame.raw,rgb)
