import numpy as np
import pytest
from PySide6.QtWidgets import QDialog, QFileDialog, QInputDialog
from samstudio.imageio import LoadResult
from samstudio.dialogs import RefinementDialog,SaveMasksDialog,ImageExportDialog


def mount(window,document):
    window._opened(LoadResult([document.frame]))
    window.document.restore(document.state());window._persist(window.document);window._refresh()
    return window.document


@pytest.mark.parametrize("method",["neighbors","patches"])
def test_gui_cleaning_fill_apply_and_exact_undo(window,document,qtbot,monkeypatch,method):
    doc=mount(window,document);raw=doc.frame.raw.copy()
    doc.draft["roi"]={"kind":"rectangle","points":[[65,50],[95,80]]}
    window.remove_area();removed=doc.working.copy();assert doc.removed.any()
    if method=="patches":
        active=doc.active_group;group=doc.ensure_group("Reference texture")
        from samstudio.processing import shape_mask
        for corners in ([[2,70],[20,90]],[[110,10],[135,40]]):
            doc.add_object("rectangle",corners,shape_mask("rectangle",corners,doc.frame.shape),{"method":"manual"})
        doc.background_group_id=group.id;doc.active_group=active
    monkeypatch.setattr(QDialog,"exec",lambda self:QDialog.DialogCode.Accepted)
    window.fill_removed(method);qtbot.waitUntil(lambda:not window.busy,timeout=20000)
    assert not window.errors and not doc.removed.any()
    target=doc.modified;assert np.array_equal(doc.working[~target],raw[~target])
    assert doc.working.dtype==raw.dtype
    window.undo();assert doc.removed.any() and np.array_equal(doc.working,removed)


@pytest.mark.parametrize("method",["holes","smooth"])
def test_gui_refinement_preview_apply_recalculates_and_undo(window,document,qtbot,monkeypatch,method):
    doc=mount(window,document);window.canvas.set_selected([doc.objects[0].id]);window._refresh()
    original=doc.objects[0].mask.copy();ident=doc.objects[0].id
    def accept(dialog):
        dialog.calculate()
        assert dialog.results
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(RefinementDialog,"exec",accept)
    window.refine_masks(method)
    assert doc.objects[0].id==ident and doc.objects[0].provenance["last_refinement"]
    assert not np.array_equal(doc.objects[0].mask,original)
    window.undo();assert np.array_equal(doc.objects[0].mask,original)


def test_gui_save_export_commands_create_files(window,document,tmp_path,monkeypatch):
    mount(window,document)
    monkeypatch.setattr(QFileDialog,"getExistingDirectory",lambda *a,**k:str(tmp_path/"output"))
    monkeypatch.setattr(SaveMasksDialog,"exec",lambda self:QDialog.DialogCode.Accepted)
    window.save_mask_dialog()
    assert list((tmp_path/"output").glob("*.bmp"))
    window.save_mask_dialog(True);assert list((tmp_path/"output").glob("*.png"))
    monkeypatch.setattr(QInputDialog,"getItem",lambda *a,**k:("Current image",True))
    monkeypatch.setattr(ImageExportDialog,"exec",lambda self:QDialog.DialogCode.Accepted)
    window.export_dataset("coco")
    assert (tmp_path/"output"/"annotations.coco.json").exists() and not window.errors
