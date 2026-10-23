"""Qt event tests use real widgets; model contract tests are explicitly marked as doubles."""
from types import SimpleNamespace
import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialogButtonBox, QInputDialog
from PIL import Image

from samstudio.domain import Document, Calibration
from samstudio.imageio import LoadResult, load_file
from samstudio.dialogs import ModelDialog, SaveMasksDialog, RefinementDialog, CalibrationDialog
from samstudio.inference import CATALOG


def open_image(window, tmp_path, qtbot):
    path=tmp_path/"input.png"
    Image.fromarray(np.arange(160*120,dtype=np.uint8).reshape(120,160)).save(path)
    window.open_paths([str(path)])
    qtbot.waitUntil(lambda:not window.busy,timeout=10000)
    assert window.document is not None
    window._commit("test group",lambda:window.document.ensure_group("Particles"))
    return window.document


def drag(qtbot,canvas,a,b):
    qtbot.mousePress(canvas,Qt.MouseButton.LeftButton,pos=canvas.to_widget(a).toPoint())
    qtbot.mouseMove(canvas,canvas.to_widget(b).toPoint())
    qtbot.mouseRelease(canvas,Qt.MouseButton.LeftButton,pos=canvas.to_widget(b).toPoint())


@pytest.mark.parametrize("tool",["rectangle","circle","ellipse"])
def test_draw_via_mouse_and_shortcuts(window,qtbot,tmp_path,tool):
    doc=open_image(window,tmp_path,qtbot)
    window.tool_actions[tool].trigger()
    drag(qtbot,window.canvas,[20,20],[70,65])
    assert len(doc.objects)==1 and doc.objects[0].mask.any()
    saved=window.stores[doc.frame.key].path(doc)
    assert saved.exists() and doc.revision==doc.saved_revision
    qtbot.keyClick(window.canvas,Qt.Key.Key_Z,Qt.KeyboardModifier.ControlModifier)
    assert len(doc.objects)==0
    qtbot.keyClick(window.canvas,Qt.Key.Key_Y,Qt.KeyboardModifier.ControlModifier)
    assert len(doc.objects)==1
    assert not window.errors


def test_polygon_vertex_drag_delete_undo_preserves_exact_mask(window,qtbot,tmp_path):
    doc=open_image(window,tmp_path,qtbot)
    window.tool_actions["polygon"].trigger()
    for p in [[15,15],[80,15],[80,80],[15,80]]:
        qtbot.mouseClick(window.canvas,Qt.MouseButton.LeftButton,pos=window.canvas.to_widget(p).toPoint())
    qtbot.keyClick(window.canvas,Qt.Key.Key_Return)
    obj=doc.objects[0];original=obj.mask.copy()
    window.canvas.set_selected([obj.id]);window._refresh()
    qtbot.keyClick(window.canvas,Qt.Key.Key_E,Qt.KeyboardModifier.ControlModifier)
    assert window.canvas.edit_mode
    drag(qtbot,window.canvas,[15,15],[25,25])
    assert not np.array_equal(original,obj.mask)
    qtbot.mouseClick(window.canvas,Qt.MouseButton.LeftButton,pos=window.canvas.to_widget([80,15]).toPoint())
    qtbot.keyClick(window.canvas,Qt.Key.Key_Delete)
    assert len(doc.objects)==1 and len(doc.objects[0].points)==3
    window.undo();assert len(doc.objects[0].points)==4
    window.undo();assert np.array_equal(doc.objects[0].mask,original)
    assert not window.errors


def test_first_object_requests_group_once(window,qtbot,tmp_path,monkeypatch):
    path=tmp_path/"first.png";Image.fromarray(np.zeros((30,40),np.uint8)).save(path)
    window._opened(LoadResult(load_file(path)))
    asked=[]
    monkeypatch.setattr(QInputDialog,"getText",lambda *a,**k:(asked.append(1) or "Cells",True))
    window._shape_completed("rectangle",[[1,1],[15,20]])
    window._shape_completed("point",[[20,20]])
    assert len(asked)==1 and len(window.document.objects)==2
    assert all(o.group_id==window.document.groups[0].id for o in window.document.objects)


def test_delete_in_vertex_mode_without_active_vertex_preserves_object(window,qtbot,tmp_path):
    doc=open_image(window,tmp_path,qtbot)
    window._shape_completed("polygon",[[10,10],[80,10],[80,80],[10,80]])
    window.canvas.set_selected([doc.objects[0].id]);window._refresh();window.edit_object(True)
    window.canvas._active_vertex=None
    qtbot.keyClick(window.canvas,Qt.Key.Key_Delete)
    assert len(doc.objects)==1 and not window.errors


def test_escape_cancels_unfinished_polygon_and_preview(window,qtbot,tmp_path):
    doc=open_image(window,tmp_path,qtbot);window.tool_actions["polygon"].trigger()
    for point in [[10,10],[80,10]]:
        qtbot.mouseClick(window.canvas,Qt.MouseButton.LeftButton,pos=window.canvas.to_widget(point).toPoint())
    window.canvas.set_preview([np.ones(doc.frame.shape,bool)])
    assert window.canvas._drawing and window.canvas.preview_masks
    qtbot.keyClick(window.canvas,Qt.Key.Key_Escape)
    assert not window.canvas._drawing and not window.canvas.preview_masks and not doc.objects


def test_point_prompts_positive_negative_and_roi_are_autosaved(window,qtbot,tmp_path):
    doc=open_image(window,tmp_path,qtbot);window.mode.setCurrentText("Segment")
    window.auto_checkbox.setChecked(False)
    for button,p,label in [(Qt.MouseButton.LeftButton,[20,20],1),(Qt.MouseButton.RightButton,[80,80],0)]:
        qtbot.mouseClick(window.canvas,button,pos=window.canvas.to_widget(p).toPoint())
        assert doc.draft["points"][-1][2]==label
    window.tool_actions["ellipse"].trigger();drag(qtbot,window.canvas,[10,10],[100,90])
    restored=Document(doc.frame);assert window.stores[doc.frame.key].load(restored)[0]
    assert len(restored.draft["points"])==2 and restored.draft["examples"][0]["kind"]=="ellipse"
    assert not doc.objects


def test_clean_remove_restore_undo_and_source_untouched(window,qtbot,tmp_path):
    doc=open_image(window,tmp_path,qtbot);source=doc.frame.raw.copy()
    window.mode.setCurrentText("Clean");drag(qtbot,window.canvas,[10,10],[40,40])
    qtbot.keyClick(window.canvas,Qt.Key.Key_D,Qt.KeyboardModifier.ControlModifier)
    assert doc.removed.any() and np.all(doc.working[doc.removed]==0)
    assert np.array_equal(doc.frame.raw,source)
    window.restore_area();assert doc.working is None and not doc.removed.any()
    window.undo();assert doc.removed.any()
    window.redo();assert doc.working is None
    assert not window.errors


def test_locked_objects_and_visibility_controls(window,qtbot,tmp_path):
    doc=open_image(window,tmp_path,qtbot);window._shape_completed("rectangle",[[10,10],[30,30]])
    obj=doc.objects[0];window.canvas.set_selected([obj.id]);window._refresh()
    window.objects_tree.topLevelItem(0).setCheckState(3,Qt.CheckState.Checked)
    assert doc.objects[0].locked
    window.delete_selected();assert len(doc.objects)==1 and window.errors[-1][0]=="Locked object"
    window.objects_tree.topLevelItem(0).setCheckState(0,Qt.CheckState.Unchecked)
    assert not doc.objects[0].visible
    assert doc.protected_mask().any()


def test_multiple_images_stack_selection_and_resume(window,qtbot,tmp_path):
    import tifffile
    path=tmp_path/"stack.tif"
    tifffile.imwrite(path,np.zeros((3,50,60),np.uint16),metadata={"axes":"TYX"},photometric="minisblack")
    window.open_paths([str(path)]);qtbot.waitUntil(lambda:not window.busy,timeout=10000)
    assert len(window.documents)==3
    window._commit("group",lambda:window.document.ensure_group("One"))
    window._shape_completed("rectangle",[[5,5],[30,30]])
    key=window.current_key;mask=window.document.objects[0].mask.copy()
    parent=window.files_tree.topLevelItem(0);parent.setSelected(True)
    assert len(window.selected_images())==3
    window.close_current();assert len(window.documents)==2
    window.open_paths([str(path)]);qtbot.waitUntil(lambda:not window.busy,timeout=10000)
    assert len(window.documents)==3 and window.current_key==key
    assert np.array_equal(window.document.objects[0].mask,mask)


def test_failure_and_cancel_jobs_leave_gui_usable(window,qtbot,tmp_path):
    open_image(window,tmp_path,qtbot)
    def fail(progress,cancel):raise ValueError("Expected diagnostic")
    window._start_job("test",fail,lambda value:None)
    qtbot.waitUntil(lambda:not window.busy,timeout=5000)
    assert window.errors[-1][1]=="Expected diagnostic" and not window.canvas.read_only
    import threading
    entered=threading.Event()
    def cancellable(progress,cancel):
        entered.set();cancel.wait(5);raise InterruptedError("cancelled")
    window._start_job("test cancel",cancellable,lambda value:pytest.fail("cancel callback"))
    qtbot.waitUntil(entered.is_set,timeout=5000);window.cancel_operation()
    qtbot.waitUntil(lambda:not window.busy,timeout=5000)
    assert not window.canvas.read_only and len(window.errors)==1


def test_contract_preview_accept_provenance_and_protection(window,qtbot,tmp_path):
    # A GUI contract double. Real weights have separate integration tests.
    doc=open_image(window,tmp_path,qtbot);window._shape_completed("rectangle",[[5,5],[25,25]])
    prior=doc.objects[0].mask.copy();other=np.zeros(doc.frame.shape,bool);other[30:60,30:60]=True
    window.engine=SimpleNamespace(ready=True,spec=CATALOG[0],device="cpu",infer=lambda *a,**k:[other])
    window.run_inference(force_whole=True);qtbot.waitUntil(lambda:not window.busy,timeout=10000)
    window.engine.spec=CATALOG[1];window.cleaned_checkbox.setChecked(True)
    window.accept_preview()
    assert len(doc.objects)==2 and doc.objects[1].provenance["model"]==CATALOG[0].label
    assert doc.objects[1].provenance["input"]=="original" and np.array_equal(doc.objects[0].mask,prior)
    window.canvas.set_preview([prior]);window.accept_preview()
    assert len(doc.objects)==2 and window.errors[-1][0]=="Preview is no longer eligible"


def test_model_manager_cpu_default_local_checkpoint_and_sam3_notice(qtbot):
    dialog=ModelDialog(SimpleNamespace(spec=None));qtbot.addWidget(dialog)
    assert dialog.values()[1]=="cpu"
    dialog.family.setCurrentText("SAM2.1");dialog.variant.setCurrentText("Tiny");dialog.path.setText("local.pt")
    spec,device,path=dialog.values();assert spec.family=="SAM2.1" and path=="local.pt"
    dialog.family.setCurrentText("SAM3");assert "optional" in dialog.info.text().lower() and "CUDA" in dialog.info.text()


def test_calibration_dialog_preserves_picometer_metadata_units(qtbot):
    cal=Calibration(8.172883192,8.172883192,"pm","EMD metadata",True)
    dialog=CalibrationDialog(cal);qtbot.addWidget(dialog)
    restored=dialog.value()
    assert restored.valid and restored.length_unit=="pm"
    assert restored.area(100)==pytest.approx(cal.area(100))


def test_transparency_live_preview_and_numeric_options(document,qtbot):
    dialog=SaveMasksDialog(document,True);qtbot.addWidget(dialog)
    assert dialog.values()["file_format"]=="png" and dialog.values()["transparency"]==75
    assert not dialog.preview.pixmap().isNull()
    dialog.transparency.setValue(20);assert dialog.percent.text()=="20%"
    dialog.color.setCurrentIndex(dialog.color.findData("instance"))
    assert not dialog.transparency.isEnabled() and not dialog.overlay.isChecked()
    assert dialog.values()["transparency"]==0


def test_refinement_preview_apply_gating_and_physical_threshold(document,qtbot):
    dialog=RefinementDialog(document,[document.objects[0].id],"holes");qtbot.addWidget(dialog)
    apply=dialog.controls.button(QDialogButtonBox.StandardButton.Ok)
    assert not apply.isEnabled()
    dialog.units.setCurrentIndex(1);dialog.value.setValue(7)
    dialog.calculate();assert apply.isEnabled() and dialog.results[document.objects[0].id].sum()==2025
    dialog.value.setValue(5);assert not apply.isEnabled()
    dialog.calculate();assert dialog.results[document.objects[0].id].sum()==1925


def test_statistics_mixed_units_separate_and_live_update(window,qtbot,tmp_path):
    doc=open_image(window,tmp_path,qtbot);window._shape_completed("rectangle",[[5,5],[25,25]])
    doc.calibration=Calibration(.2,.3,"nm","test",True)
    from samstudio.domain import ImageFrame
    other=Document(ImageFrame(str(tmp_path/"other.png"),np.zeros((40,40),np.uint8)))
    other.ensure_group("Particles");m=np.zeros((40,40),bool);m[3:20,3:20]=True;other.add_object("mask",mask=m)
    window._opened(LoadResult([other.frame]));window.documents[other.frame.key]=other
    window.select_document(doc.frame.key);window.plot_statistics();dialog=window.stats_dialogs[0]
    dialog.scope.setCurrentIndex(1);assert len(dialog.figure.axes)==2 and len(dialog.rows)==2
    old=dialog.rows[0]["pixel_value"]
    window._commit("grow",lambda:doc.objects[0].mask.__setitem__((slice(30,40),slice(30,40)),True))
    assert dialog.rows[0]["pixel_value"]>old
    dialog.unit.setCurrentText("Pixels");assert len(dialog.figure.axes)==1
    dialog.close();assert not window.stats_dialogs
