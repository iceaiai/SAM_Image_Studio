"""User-reported v1.0 failures, exercised through Qt events and model contracts."""
import copy
import threading
from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPaintDevice, QPainter
from PySide6.QtWidgets import QDialog, QDialogButtonBox

from samstudio.domain import Annotation, Document, ProjectStore
from samstudio.dialogs import RefinementDialog, StatisticsDialog
from samstudio.inference import CATALOG, InferenceEngine
from samstudio.processing import (curve_segments, mask_contours, raster_contours,
                                  refinement_geometry, shape_mask, smooth_contours)
from test_gui import open_image, drag


@pytest.mark.parametrize("kind", ["rectangle", "ellipse", "circle", "polygon"])
@pytest.mark.parametrize("whole", [False, True])
def test_area_prompt_is_one_native_prediction_and_scope_only_changes_clipping(kind, whole):
    engine = InferenceEngine(); engine.predictor = object()
    calls = []
    prediction = np.zeros((100, 140), bool); prediction[10:80, 10:110] = True
    engine.predict = lambda rgb, points, box, *a: (calls.append((points, box)) or prediction.copy(), .99)
    pts = [[25, 25], [85, 75]] if kind != "polygon" else [[25,25],[85,25],[85,75],[25,75]]
    roi = shape_mask(kind, pts, prediction.shape)
    protected = np.zeros_like(roi); protected[30:35, 30:35] = True
    masks = engine.infer(np.zeros((100,140,3), np.uint8), roi=roi, whole=whole,
                         protected=protected, min_area=1)
    assert len(calls) == len(masks) == 1
    assert calls[0][1] is not None
    expected = prediction & ~protected & (True if whole else roi)
    assert np.array_equal(masks[0], expected)


@pytest.mark.parametrize("whole", [False, True])
def test_point_prompt_never_runs_an_automatic_grid(whole):
    engine = InferenceEngine(); engine.predictor = object()
    calls=[]; mask=np.zeros((60,80),bool); mask[10:40,10:50]=True
    engine.predict=lambda rgb,points,box,*a: (calls.append((points,box)) or mask.copy(),.99)
    points=[[20.,20.,1],[70.,50.,0]]
    result=engine.infer(np.zeros((60,80,3),np.uint8),points=points,whole=whole,min_area=1)
    assert calls==[(points,None)] and len(result)==1 and result[0].sum()>1


def test_histogram_survives_native_paint_resize_filters_and_close(document, qtbot):
    dialog=StatisticsDialog([document],document);qtbot.addWidget(dialog)
    assert callable(dialog.metric)  # QPaintDevice virtual method, never a control.
    dialog.show();qtbot.wait(40)
    for unit in ["Pixels","nm","Auto"]:
        dialog.unit.setCurrentText(unit)
        for index in [0,1]:
            dialog.metric_combo.setCurrentIndex(index)
            dialog.resize(1000+index*23,700+index*17)
            qtbot.wait(20)
            # Rendering invokes the paint-device path which v1.0 shadowed.
            shot=dialog.grab();assert not shot.isNull()
            assert dialog.metric(QPaintDevice.PaintDeviceMetric.PdmWidth)>0
            dialog.canvas.draw();assert len(dialog.rows)==1
    dialog.close();qtbot.wait(30)


def test_prompted_scope_keeps_dots_and_shape_and_preserves_existing_masks(window,qtbot,tmp_path):
    doc=open_image(window,tmp_path,qtbot)
    window._shape_completed("rectangle",[[5,5],[20,20]])
    original=doc.objects[0].mask.copy()
    seen=[];mask=np.zeros(doc.frame.shape,bool);mask[45:65,45:65]=True
    def infer(rgb,points,roi,protected,**kwargs):
        seen.append((copy.deepcopy(points),roi.copy() if roi is not None else None,protected.copy(),kwargs))
        return [mask]
    window.engine=SimpleNamespace(ready=True,spec=CATALOG[0],device="cpu",infer=infer)
    window.auto_checkbox.setChecked(False);window.mode.setCurrentText("Segment");window.tool_actions["ellipse"].trigger();window.scope.setCurrentIndex(window.scope.findData("single"))
    window._shape_completed("ellipse",[[30,30],[80,90]])
    window._prompt_added(50,50,1)
    assert window.scope.currentData()=="single"
    window.run_inference();qtbot.waitUntil(lambda:not window.busy,timeout=5000)
    assert seen[0][0]==[[50,50,1]] and seen[0][1] is not None and seen[0][3]["whole"]
    window.accept_preview()
    assert np.array_equal(doc.objects[0].mask,original) and len(doc.objects)==2
    assert not window.errors


def test_point_rejects_roi_and_routes_whole_image_exemplars(window,qtbot,tmp_path):
    doc=open_image(window,tmp_path,qtbot)
    seen=[];mask=np.zeros(doc.frame.shape,bool);mask[25:65,25:65]=True
    def infer(rgb,points,roi,protected,**kwargs):
        seen.append((points,roi,kwargs));return [mask]
    window.engine=SimpleNamespace(ready=True,spec=CATALOG[0],device="cpu",infer=infer)
    window._example_inference=lambda engine,rgb,points,examples,protected,progress,cancel,text,options:infer(rgb,points,None,protected,whole=True)
    window.auto_checkbox.setChecked(False);window.mode.setCurrentText("Segment");window.scope.setCurrentIndex(window.scope.findData("single"))
    window.scope.setCurrentIndex(1);window._shape_completed("point",[[40,40]])
    assert window.scope.currentData()=="prompt"
    window.run_inference();qtbot.waitUntil(lambda:not window.busy,timeout=5000)
    assert seen[0][0]==[[40,40,1]] and seen[0][1] is None and seen[0][2]["whole"]
    assert window.canvas.preview_masks[0].sum()==1600 and not window.errors


def test_new_dots_while_predicting_are_coalesced_and_stale_result_discarded(window,qtbot,tmp_path):
    doc=open_image(window,tmp_path,qtbot);window.mode.setCurrentText("Segment");window.scope.setCurrentIndex(window.scope.findData("single"))
    entered=threading.Event();release=threading.Event();calls=[]
    def infer(rgb,points,roi,protected,**kwargs):
        calls.append(copy.deepcopy(points))
        if len(calls)==1:entered.set();release.wait(5)
        mask=np.zeros(doc.frame.shape,bool);mask[10:20,10:10+len(points)]=True
        return [mask]
    window.engine=SimpleNamespace(ready=True,spec=CATALOG[0],device="cpu",infer=infer)
    window._example_inference=lambda engine,rgb,points,examples,protected,progress,cancel,text,options:infer(rgb,points,None,protected,whole=True)
    window._prompt_added(20,20,1);window.preview_timer.stop();window.run_inference()
    qtbot.waitUntil(entered.is_set,timeout=5000)
    assert not window.canvas.read_only and window.canvas.prompt_input_only
    for p in [[30,30],[40,40]]:
        qtbot.mouseClick(window.canvas,Qt.MouseButton.LeftButton,pos=window.canvas.to_widget(p).toPoint())
    assert len(doc.draft["points"])==3 and window._pending_preview
    release.set()
    qtbot.waitUntil(lambda:len(calls)==2 and not window.busy,timeout=10000)
    assert len(calls[0])==1 and len(calls[1])==3
    assert window.canvas.preview_masks[0].sum()==30
    assert doc.revision==doc.saved_revision and not window.errors


def test_automatic_grid_is_an_explicit_choice_and_ignores_old_dots(window,qtbot,tmp_path):
    doc=open_image(window,tmp_path,qtbot);window.mode.setCurrentText("Segment");window.scope.setCurrentIndex(window.scope.findData("single"))
    window.auto_checkbox.setChecked(False);window._prompt_added(20,20,1)
    seen=[]
    def infer(rgb,points,roi,protected,**kwargs):
        seen.append((points,roi,kwargs));return []
    window.engine=SimpleNamespace(ready=True,spec=CATALOG[0],device="cpu",infer=infer)
    window.scope.setCurrentIndex(2);window.run_inference()
    qtbot.waitUntil(lambda:not window.busy,timeout=5000)
    assert seen[0][0]==[] and seen[0][1] is None and seen[0][2]["whole"]


def _mount_mask(window,doc):
    from samstudio.imageio import LoadResult
    window._opened(LoadResult([doc.frame]));window.document.restore(doc.state())
    window._persist(window.document);window.canvas.set_selected([window.document.objects[0].id])
    window._refresh();window.edit_object(True)
    return window.document


def test_mask_vertex_moves_preserve_every_other_handle_and_persist(window,document,qtbot,tmp_path):
    doc=_mount_mask(window,document);obj=doc.objects[0]
    before=window.canvas._geometry(obj);p=before["contours"][0]["points"][0]
    count=sum(len(c["points"]) for c in before["contours"])
    drag(qtbot,window.canvas,p,[p[0]-3,p[1]-3])
    after=window.canvas._geometry(obj)
    assert sum(len(c["points"]) for c in after["contours"])==count
    assert after["contours"][0]["points"][1:]==before["contours"][0]["points"][1:]
    assert after["contours"][1:]==before["contours"][1:]
    assert obj.contours is not None
    restore=Document(doc.frame);assert window.stores[doc.frame.key].load(restore)[0]
    assert restore.objects[0].contours==obj.contours
    assert np.array_equal(restore.objects[0].mask,obj.mask)
    window.undo();assert doc.objects[0].contours is None
    window.redo();assert doc.objects[0].contours==after["contours"]
    assert not window.errors


def test_clicking_a_vertex_without_drag_does_not_change_geometry_or_revision(window,document,qtbot):
    doc=_mount_mask(window,document);obj=doc.objects[0]
    p=window.canvas._geometry(obj)["contours"][0]["points"][0]
    state=doc.state();revision=doc.revision
    qtbot.mouseClick(window.canvas,Qt.MouseButton.LeftButton,pos=window.canvas.to_widget(p).toPoint())
    assert doc.revision==revision and doc.state()==state


def test_repeated_delete_expands_by_distance_inside_only_selected_object(window,qtbot,tmp_path):
    doc=open_image(window,tmp_path,qtbot)
    pts=[[20,20],[25,20],[35,20],[70,20],[70,70],[20,70]]
    window._shape_completed("polygon",pts)
    window._shape_completed("polygon",[[21,21],[27,21],[27,27],[21,27]])
    neighbor=doc.objects[1].to_dict();obj=doc.objects[0]
    window.canvas.set_selected([obj.id]);window._refresh();window.edit_object(True)
    window.canvas.vertex_delete_radius=20
    qtbot.mouseClick(window.canvas,Qt.MouseButton.LeftButton,pos=window.canvas.to_widget([20,20]).toPoint())
    for expected in [5,4,3]:
        qtbot.keyClick(window.canvas,Qt.Key.Key_Delete)
        assert len(doc.objects[0].points)==expected
        assert doc.objects[1].to_dict()==neighbor
    before=doc.objects[0].points.copy();qtbot.keyClick(window.canvas,Qt.Key.Key_Delete)
    assert doc.objects[0].points==before
    window.undo();assert len(doc.objects[0].points)==4
    assert not window.errors


def test_delete_radius_limits_edits_and_large_radius_still_protects_other_objects(window,qtbot,tmp_path):
    doc=open_image(window,tmp_path,qtbot)
    window._shape_completed("polygon",[[20,20],[30,20],[70,30],[70,70],[20,70]])
    window._shape_completed("rectangle",[[21,21],[24,24]])
    other=doc.objects[1].mask.copy();obj=doc.objects[0]
    window.canvas.set_selected([obj.id]);window._refresh();window.edit_object(True)
    window.canvas.vertex_delete_radius=5
    qtbot.mouseClick(window.canvas,Qt.MouseButton.LeftButton,pos=window.canvas.to_widget([20,20]).toPoint())
    qtbot.keyClick(window.canvas,Qt.Key.Key_Delete)
    qtbot.keyClick(window.canvas,Qt.Key.Key_Delete)
    assert len(obj.points)==4  # Next vertex is outside the five-pixel radius.
    window.canvas.vertex_delete_radius=10000
    qtbot.keyClick(window.canvas,Qt.Key.Key_Delete)
    assert len(obj.points)==3 and np.array_equal(other,doc.objects[1].mask)


def test_edit_mode_empty_click_never_draws_a_new_object(window,document,qtbot):
    doc=_mount_mask(window,document);count=len(doc.objects)
    window.canvas.set_tool("polygon")
    for p in [[90,80],[110,80],[100,100]]:
        qtbot.mouseClick(window.canvas,Qt.MouseButton.LeftButton,pos=window.canvas.to_widget(p).toPoint())
    qtbot.keyClick(window.canvas,Qt.Key.Key_Return)
    assert len(doc.objects)==count and not window.canvas._drawing


def test_edit_refresh_reuses_original_display_image(window,document,qtbot,monkeypatch):
    doc=_mount_mask(window,document)
    import samstudio.canvas as canvas_module
    original=canvas_module.display_rgb;calls=[]
    monkeypatch.setattr(canvas_module,"display_rgb",lambda *a,**k:(calls.append(1) or original(*a,**k)))
    p=window.canvas._geometry(doc.objects[0])["contours"][0]["points"][0]
    drag(qtbot,window.canvas,p,[p[0]-2,p[1]-2])
    window._refresh();window._refresh()
    assert calls==[]


def test_mask_contours_roundtrip_preserves_exact_holes(document):
    mask=document.objects[0].mask
    assert np.array_equal(raster_contours(mask_contours(mask),mask.shape),mask)


def test_saved_mask_cache_detects_in_place_mutation(document):
    obj=document.objects[0];before=obj.to_dict();obj.mask[0,0]=True
    after=obj.to_dict();assert before["mask"]!=after["mask"]
    restored=Annotation.from_dict(after,document.frame.shape)
    assert restored.mask[0,0]


def test_changing_scope_discards_preview_without_starting_grid(window,qtbot,tmp_path):
    doc=open_image(window,tmp_path,qtbot);window.mode.setCurrentText("Segment");window.scope.setCurrentIndex(window.scope.findData("single"))
    window.canvas.set_preview([np.ones(doc.frame.shape,bool)])
    window.scope.setCurrentIndex(2)
    assert not window.canvas.preview_masks and not window.preview_timer.isActive() and not window.busy


def test_new_shape_discards_previous_preview_before_accept(window,qtbot,tmp_path):
    doc=open_image(window,tmp_path,qtbot);window.mode.setCurrentText("Segment");window.scope.setCurrentIndex(window.scope.findData("single"))
    window.canvas.set_preview([np.ones(doc.frame.shape,bool)])
    window._shape_completed("rectangle",[[10,10],[30,30]])
    assert not window.canvas.preview_masks and not window.accept_button.isEnabled()


def test_saved_state_mutation_does_not_corrupt_mask_cache(document):
    obj=document.objects[0];before=obj.to_dict();expected=copy.deepcopy(before)
    before["mask"]["shape"][0]=1
    assert obj.to_dict()==expected


def test_curve_has_continuous_tangent_and_lower_radial_noise():
    theta=np.linspace(0,2*np.pi,256,endpoint=False)
    radius=40+3*np.sin(theta*32)
    points=np.c_[70+radius*np.cos(theta),70+radius*np.sin(theta)]
    mask=shape_mask("polygon",points,(140,140))
    result,contours=refinement_geometry(mask,4)
    assert result.any() and contours and all(c["curve"] for c in contours)
    p=np.asarray(contours[0]["points"])
    assert np.std(np.linalg.norm(p-[70,70],axis=1))<np.std(radius)*.6
    segments=curve_segments(p)
    for i,(_,_,c,d) in enumerate(segments):
        next_a,next_b,_,_=segments[(i+1)%len(segments)]
        assert np.allclose(d,next_a)
        assert np.allclose(d-c,next_b-next_a)


def test_curve_refinement_batch_apply_persists_and_undo_is_exact(window,document,qtbot,monkeypatch):
    doc=_mount_mask(window,document)
    m=np.zeros(doc.frame.shape,bool);m[75:110,85:125]=True
    second=doc.add_object("mask",mask=m);ids=[o.id for o in doc.objects]
    window.canvas.set_selected(ids);window._refresh();before=[o.mask.copy() for o in doc.objects]
    def accept(dialog):dialog.value.setValue(2);dialog.calculate();return QDialog.DialogCode.Accepted
    monkeypatch.setattr(RefinementDialog,"exec",accept)
    window.refine_masks("smooth")
    assert all(o.contours and all(c.get("curve") for c in o.contours) for o in doc.objects)
    assert not (doc.objects[0].mask&doc.objects[1].mask).any()
    assert not window.canvas.grab().isNull()
    restored=Document(doc.frame);window.stores[doc.frame.key].load(restored)
    assert restored.objects[0].contours==doc.objects[0].contours
    window.undo();assert all(np.array_equal(o.mask,m) for o,m in zip(doc.objects,before))
    assert not window.errors
