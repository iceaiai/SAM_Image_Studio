"""Region complements, reversible pixel filtering and exact image/color exports."""
import copy
import json
from pathlib import Path

import numpy as np
import pytest
import tifffile
from PIL import Image
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QFileDialog, QInputDialog

from samstudio.dialogs import (ImageExportDialog, ImagePreviewDialog, MaskColorsDialog,
                               SaveMasksDialog, SmoothImageDialog)
from samstudio.domain import Document, History, ImageFrame, ProjectStore, unpack_mask
from samstudio.exports import (decode_coco_rle, export_coco, export_yolo, image_name,
                                save_image, save_image_versions, save_masks)
from samstudio.imageio import LoadResult
from samstudio.palette import LUT20, assign_colors, lookup_color
from samstudio.processing import display_rgb, shape_mask, smooth_image


def mount(window, doc):
    window._opened(LoadResult([doc.frame]))
    window.document.restore(doc.state());window._persist(window.document);window._refresh()
    return window.document


def add_second(doc):
    mask=np.zeros(doc.frame.shape,bool);mask[85:108,115:143]=True
    return doc.add_object("mask",mask=mask,provenance={"method":"manual"})


@pytest.mark.parametrize("mode",["Manual","Edit","Clean","Segment"])
@pytest.mark.parametrize("all_objects",[False,True])
def test_complement_is_pixel_region_in_every_mode(window,document,mode,all_objects):
    doc=mount(window,document);add_second(doc);doc.add_object("point",[[80,80]])
    window.mode.setCurrentText(mode)
    original=[o.mask.copy() for o in doc.objects if o.mask is not None]
    if all_objects:window.select_all_action.trigger()
    else:window.canvas.set_selected([doc.objects[0].id])
    expected=~(np.logical_or.reduce(original) if all_objects else original[0])
    window.invert_region_action.trigger()
    assert not window.errors and not window.canvas.selected
    assert np.array_equal(window._selection_mask(),expected)
    assert window.canvas._region is not None and expected[25,25]  # original object's hole
    assert not expected[12,12] and expected[0,0]
    assert np.array_equal(original[0],doc.objects[0].mask)
    window.invert_region();assert np.array_equal(window._selection_mask(),~expected)
    window.undo();assert np.array_equal(window._selection_mask(),expected)
    window.redo();assert np.array_equal(window._selection_mask(),~expected)


@pytest.mark.parametrize("mode",["Manual","Edit"])
def test_inverted_region_becomes_exact_editable_annotation(window,document,mode,tmp_path):
    doc=mount(window,document);original=doc.objects[0].mask.copy()
    window.mode.setCurrentText(mode);window.canvas.set_selected([doc.objects[0].id]);window.invert_region()
    window.create_region_object()
    created=doc.objects[-1]
    assert np.array_equal(created.mask,~original) and created.provenance["method"]=="manual"
    assert window.canvas.selected=={created.id} and doc.draft["roi"] is None
    assert created.id in {o.id for o in doc.foreground_objects()}
    record=json.loads(Path(export_coco([doc],tmp_path)["path"]).read_text())["annotations"][-1]
    assert np.array_equal(decode_coco_rle(record["segmentation"]),~original)
    assert not window.errors


def test_inverted_region_cleans_background_and_restores_exactly(window,document):
    doc=mount(window,document);raw=doc.frame.raw.copy();object_mask=doc.objects[0].mask.copy()
    window.mode.setCurrentText("Clean");window.select_all_objects();window.invert_region();window.remove_area()
    assert np.array_equal(doc.removed,~object_mask)
    assert np.array_equal(doc.working[object_mask],raw[object_mask])
    window.undo();assert doc.working is None and not doc.removed.any()
    assert np.array_equal(window._selection_mask(),~object_mask)


def test_empty_and_point_only_selections_are_explicit(window,document):
    doc=mount(window,document);doc.objects.clear();doc.add_object("point",[[20,20]])
    window.select_all_objects();window.invert_region()
    assert window.errors and doc.draft["roi"] is None
    window.errors.clear();doc.objects.clear();doc.add_object("mask",mask=np.ones(doc.frame.shape,bool))
    window.select_all_objects();window.invert_region()
    assert not window._selection_mask().any() and not window.region_object_action.isEnabled()
    window.invert_region();assert window._selection_mask().all()


def test_region_autosave_round_trip_and_corruption_are_atomic(document,tmp_path):
    selected=~document.objects[0].mask;document.set_region(selected,operation="invert")
    store=ProjectStore(tmp_path/"project");store.save(document)
    restored=Document(document.frame);assert store.load(restored)[0]
    assert np.array_equal(unpack_mask(restored.draft["roi"]["mask"]),selected)
    saved=restored.state();bad=copy.deepcopy(saved);bad["draft"]["roi"]["mask"]["shape"]=[2,3]
    with pytest.raises(ValueError):restored.restore(bad)
    assert restored.state()==saved


@pytest.mark.parametrize("automatic",[False,True])
def test_inverted_segmentation_clips_prompted_and_automatic_results(window,document,qtbot,automatic):
    from samstudio.inference import CATALOG
    doc=mount(window,document);original=doc.objects[0].mask.copy()
    window.mode.setCurrentText("Segment");window.auto_checkbox.setChecked(False)
    window.select_all_objects();window.invert_region();selected=window._selection_mask().copy()
    window.engine.spec=CATALOG[0];window.engine.predictor=object()
    calls=[]
    def infer(rgb,points,roi,protected,**kwargs):
        calls.append((points,roi,protected,kwargs))
        # Exercise GUI acceptance too, even if a backend returns pixels outside the ROI.
        return [np.ones(doc.frame.shape,bool)]
    window.engine.infer=infer
    window.scope.setCurrentIndex(window.scope.findData("automatic" if automatic else "prompt"))
    if not automatic:doc.draft["points"]=[[100,70,1]]
    window.run_inference();qtbot.waitUntil(lambda:not window.busy,timeout=10000)
    assert calls and np.all(calls[0][2][original])
    assert (calls[0][1] is None)==automatic
    if not automatic:assert calls[0][3]["whole"] is False
    window.accept_preview()
    assert not window.errors and np.array_equal(doc.objects[-1].mask,selected)
    assert np.array_equal(doc.objects[0].mask,original)


@pytest.mark.parametrize("method",["gaussian","median"])
@pytest.mark.parametrize("dtype",[np.uint8,np.uint16,np.int16,np.float32])
def test_smoothing_reduces_impulses_preserves_dtype_and_exact_unselected_pixels(method,dtype):
    rng=np.random.default_rng(9);raw=(100+rng.normal(0,10,(41,47))).astype(dtype)
    raw[20,20]=250
    target=np.zeros(raw.shape,bool);target[10:31,10:36]=True;original=raw.copy()
    result=smooth_image(raw,method,sigma=1.2,size=5,target=target)
    assert result.dtype==raw.dtype and result.shape==raw.shape
    assert result[target].astype(float).var()<raw[target].astype(float).var()
    assert result[20,20]<raw[20,20] and np.array_equal(result[~target],raw[~target])
    assert np.array_equal(raw,original)


@pytest.mark.parametrize("method",["gaussian","median"])
def test_rgb_smoothing_does_not_mix_channels_or_modify_alpha(method):
    raw=np.zeros((25,27,4),np.uint16);raw[...,1]=900;raw[...,2]=1800
    raw[...,3]=np.arange(25*27).reshape(25,27);raw[12,13,0]=60000
    result=smooth_image(raw,method,sigma=1,size=3)
    assert np.all(result[...,1]==900) and np.all(result[...,2]==1800)
    assert np.array_equal(result[...,3],raw[...,3])
    assert result[12,13,0]<raw[12,13,0]


@pytest.mark.parametrize("method",["gaussian","median"])
def test_smoothing_nonfinite_values_stay_local(method):
    raw=np.full((11,13),7.,np.float32);raw[3,3]=np.nan;raw[4,4]=np.inf;raw[5,5]=-np.inf
    result=smooth_image(raw,method)
    assert np.array_equal(np.isfinite(raw),np.isfinite(result))
    assert np.allclose(result[np.isfinite(result)],7)
    assert np.isnan(result[3,3]) and np.isposinf(result[4,4]) and np.isneginf(result[5,5])


def test_smoothing_replay_undo_json_and_delete_restore_previous_cleaned_image(document):
    target=np.zeros(document.frame.shape,bool);target[65:90,70:100]=True
    document.remove_for_cleaning(target);fill=document.frame.raw.copy();fill[target]=1234
    document.apply_cleaning_fill(fill,target,"neighbors");previous=document.working.copy()
    history=History(document);result=smooth_image(previous,sigma=2)
    history.apply("smooth",lambda:document.apply_image_smoothing(result,np.ones(target.shape,bool),"gaussian",{"sigma":2}))
    smoothing_id=document.objects[-1].id
    restored=Document(document.frame);restored.restore(json.loads(json.dumps(document.state())))
    restored.rebuild_cleaning();assert np.array_equal(restored.working,result)
    assert not restored.removed.any()
    history.undo();assert np.array_equal(document.working,previous)
    history.redo();assert np.array_equal(document.working,result)
    document.delete_objects([smoothing_id]);assert np.array_equal(document.working,previous)


@pytest.mark.parametrize("apply",[False,True])
def test_gui_smoothing_real_dialog_preview_and_cancel(window,document,qtbot,monkeypatch,apply):
    doc=mount(window,document);original=doc.frame.raw.copy()
    window.canvas.set_selected([doc.objects[0].id]);target=doc.objects[0].mask.copy()
    def configure(dialog):
        dialog.sigma.setValue(2)
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(SmoothImageDialog,"exec",configure)
    seen=[]
    def inspect_modal():
        dialog=QApplication.activeModalWidget()
        if not isinstance(dialog,ImagePreviewDialog):QTimer.singleShot(10,inspect_modal);return
        seen.append(dialog.windowTitle());dialog.resize(1060,560);dialog.grab()
        dialog.accept() if apply else dialog.reject()
    QTimer.singleShot(10,inspect_modal)
    window.smooth_image_dialog();qtbot.waitUntil(lambda:bool(seen) and not window.busy,timeout=15000)
    assert not window.errors and np.array_equal(doc.frame.raw,original)
    if apply:
        assert doc.working is not None and np.array_equal(doc.working[~target],original[~target])
        assert doc.cleaning_history[-1]["operation"]=="smooth_image" and window.cleaned_checkbox.isChecked()
        window.undo();assert doc.working is None
    else:assert doc.working is None and not doc.cleaning_history


def test_smoothing_excludes_unfilled_cleaning_pixels(window,document,qtbot,monkeypatch):
    doc=mount(window,document);pending=np.zeros(doc.frame.shape,bool);pending[60:75,80:100]=True
    doc.remove_for_cleaning(pending)
    monkeypatch.setattr(SmoothImageDialog,"exec",lambda self:QDialog.DialogCode.Accepted)
    monkeypatch.setattr(ImagePreviewDialog,"exec",lambda self:QDialog.DialogCode.Accepted)
    window.smooth_image_dialog();qtbot.waitUntil(lambda:not window.busy,timeout=15000)
    assert np.array_equal(doc.removed,pending)
    assert not (doc.objects[-1].mask & pending).any() and not window.errors


@pytest.mark.parametrize("original,cleaned",[(True,False),(False,True),(True,True)])
def test_save_image_versions_exact_tiff_and_calibration(document,tmp_path,original,cleaned):
    doc=document;raw=doc.frame.raw.copy();filtered=smooth_image(raw,sigma=2)
    doc.apply_image_smoothing(filtered,np.ones(doc.frame.shape,bool),"gaussian",{"sigma":2})
    paths=save_image_versions(doc,tmp_path/"images",original,cleaned)
    assert len(paths)==int(original)+int(cleaned)
    for filename in paths:
        pixels=tifffile.imread(filename);is_cleaned=Path(filename).stem.endswith("_cleaned")
        assert pixels.dtype==raw.dtype and np.array_equal(pixels,filtered if is_cleaned else raw)
        with tifffile.TiffFile(filename) as tf:
            metadata=json.loads(tf.pages[0].description)
            assert metadata["calibration"]["pixel_size_x"]==.2
            assert metadata["derived_image"]==is_cleaned
    assert np.array_equal(doc.frame.raw,raw)
    assert np.array_equal(tifffile.imread(doc.frame.source_path),raw)


def test_source_overwrite_is_rejected_and_missing_cleaned_export_writes_nothing(document,tmp_path):
    with pytest.raises(ValueError,match="cannot be overwritten"):save_image(document,document.frame.source_path)
    target=tmp_path/"new-export"
    with pytest.raises(ValueError):save_image_versions(document,target,True,True)
    assert not target.exists()


def test_save_masks_can_include_both_source_versions_and_records_colors(document,tmp_path):
    document.apply_image_smoothing(smooth_image(document.frame.raw),np.ones(document.frame.shape,bool),"gaussian",{})
    assign_colors(document,{"mode":"lut20","by":"object","offset":2})
    paths=save_masks(document,tmp_path,"png",color_mode="object_color",save_original_image=True,save_cleaned_image=True)
    assert len(paths)==3
    mapping=json.loads(next(tmp_path.glob("*_mask_mapping.json")).read_text())
    assert len(mapping["image_versions"])==2 and mapping["color_scheme"]["mode"]=="lut20"
    assert mapping["objects"][0]["object_color"]==LUT20[2][1]


@pytest.mark.parametrize("exporter",["coco","yolo"])
@pytest.mark.parametrize("primary,alternate,include",[("original",False,True),("cleaned",False,True),("cleaned",True,True),("original",False,False)])
def test_dataset_image_choices_match_real_pixels(document,tmp_path,exporter,primary,alternate,include):
    document.objects[0].mask[20:30,20:30]=True  # simple, exactly representable YOLO polygon
    raw=document.frame.raw.copy();result=np.flipud(raw).copy()
    document.apply_image_smoothing(result,np.ones(document.frame.shape,bool),"gaussian",{})
    kwargs={"include_images":include,"image_source":primary,"include_alternate":alternate}
    report=(export_coco if exporter=="coco" else export_yolo)([document],tmp_path,**kwargs)
    filename=image_name(document)
    if include:
        pixels=np.asarray(Image.open(tmp_path/"images"/filename))
        assert np.array_equal(pixels,display_rgb(result if primary=="cleaned" else raw))
    else:assert not (tmp_path/"images").exists()
    if alternate:assert np.array_equal(np.asarray(Image.open(tmp_path/"original_images"/filename)),display_rgb(raw))
    if exporter=="coco":
        record=json.loads(Path(report["path"]).read_text())["images"][0]
        assert record["exported_image_source"]==(primary if include else None)
        assert bool(record["image_versions"])==include
    else:assert report["exported_image_source"]==(primary if include else None)


def test_mixed_batch_processed_export_rejected_before_creating_files(document,tmp_path):
    second=Document(document.frame)
    document.apply_image_smoothing(smooth_image(document.frame.raw),np.ones(document.frame.shape,bool),"gaussian",{})
    output=tmp_path/"dataset"
    with pytest.raises(ValueError):export_coco([document,second],output,image_source="cleaned")
    assert not output.exists()


def test_lookup_table_twenty_unique_colors_cycles_and_survives_recovery(document):
    assert len(LUT20)==20 and len({color for _,color in LUT20})==20
    assign_colors(document,{"mode":"lut20","by":"object","offset":4})
    first=document.objects[0]
    for i in range(22):document.add_object("point",[[i+1,80]])
    assert first.color==LUT20[4][1] and document.objects[20].color==first.color
    saved=json.loads(json.dumps(document.state()));restored=Document(document.frame);restored.restore(saved)
    assert [o.color for o in restored.objects]==[o.color for o in document.objects]
    new=restored.add_object("point",[[2,3]])
    assert new.color==lookup_color(restored.next_object_number-2,4)


def test_lookup_group_assignment_and_default_keep_object_identity(document):
    first=document.objects[0];old_id=first.id;mask=first.mask.copy()
    second=add_second(document);document.ensure_group("Other");third=add_second(document)
    assign_colors(document,{"mode":"lut20","by":"group","offset":1},{first.id})
    assert first.color==second.color==document.groups[0].color==LUT20[1][1]
    assert third.color=="#148374" and first.id==old_id and np.array_equal(first.mask,mask)
    assign_colors(document,{"mode":"default","by":"object","offset":0})
    assert first.color==document.groups[0].color and third.color==document.groups[1].color


def test_locked_group_colors_fail_atomically_and_scheme_recovers(document):
    first=document.objects[0];second=add_second(document);second.locked=True
    previous=document.state();history=History(document)
    with pytest.raises(ValueError):history.apply("colors",lambda:assign_colors(document,{"mode":"lut20","by":"group","offset":1},{first.id}))
    assert document.state()==previous
    invalid=copy.deepcopy(previous);invalid["color_scheme"]["offset"]=20
    with pytest.raises(ValueError):document.restore(invalid)
    assert document.state()==previous


def test_color_dialog_all_presets_real_controls_and_gui_undo(window,document,qtbot,monkeypatch):
    doc=mount(window,document);add_second(doc);first_color=doc.objects[0].color
    def choose(dialog):
        assert len(dialog.swatches.buttons())==20
        dialog.show();dialog.resize(760,560);qtbot.wait(20);dialog.grab()
        dialog.mode.setCurrentIndex(1);dialog.swatches.button(6).click()
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(MaskColorsDialog,"exec",choose)
    window.assign_mask_colors()
    assert not window.errors and doc.objects[0].color==LUT20[6][1] and doc.color_scheme["offset"]==6
    window.undo();assert doc.objects[0].color==first_color and doc.color_scheme["mode"]=="default"
    window.redo();assert doc.objects[0].color==LUT20[6][1]


def test_save_controls_default_and_both_versions(window,document,qtbot,tmp_path,monkeypatch):
    doc=mount(window,document)
    dialog=ImageExportDialog([doc]);qtbot.addWidget(dialog)
    assert not dialog.cleaned.isEnabled()
    dialog.original.setChecked(False);assert not dialog.controls.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
    dataset=ImageExportDialog([doc],True);qtbot.addWidget(dataset)
    dataset.original.setChecked(False);assert dataset.controls.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
    doc.apply_image_smoothing(smooth_image(doc.frame.raw),np.ones(doc.frame.shape,bool),"gaussian",{})
    masks=SaveMasksDialog(doc);qtbot.addWidget(masks)
    masks.save_original.setChecked(True);masks.save_cleaned.setChecked(True)
    assert masks.values()["save_original_image"] and masks.values()["save_cleaned_image"]
    def both(dialog):dialog.original.setChecked(True);dialog.cleaned.setChecked(True);return QDialog.DialogCode.Accepted
    monkeypatch.setattr(ImageExportDialog,"exec",both)
    monkeypatch.setattr(QFileDialog,"getExistingDirectory",lambda *a,**k:str(tmp_path/"output"))
    window.export_images();assert len(list((tmp_path/"output").glob("*.tif")))==2
    monkeypatch.setattr(QInputDialog,"getItem",lambda *a,**k:("Current image",True))
    window.export_dataset("coco")
    records=json.loads((tmp_path/"output/annotations.coco.json").read_text())
    assert records["images"][0]["exported_image_source"]=="cleaned"
    assert set(records["images"][0]["image_versions"])=={"original","cleaned"} and not window.errors


def test_v12_project_load_defaults_to_original_color_assignment(document):
    data=document.state();data["schema_version"]=2;data.pop("color_scheme")
    restored=Document(document.frame);restored.restore(data)
    assert restored.color_scheme=={"mode":"default","by":"object","offset":0}


def test_smoothing_record_does_not_intercept_canvas_selection_and_stays_restorable(window,document,qtbot):
    doc=mount(window,document);original=doc.objects[0];raw=doc.frame.raw.copy()
    record=doc.apply_image_smoothing(smooth_image(raw),np.ones(doc.frame.shape,bool),"gaussian",{})
    window._refresh();qtbot.wait(20)
    qtbot.mouseClick(window.canvas,Qt.MouseButton.LeftButton,pos=window.canvas.to_widget([15,15]).toPoint())
    assert window.canvas.selected=={original.id}
    assert window.canvas.object_at([80,80]) is None
    window.select_all_action.trigger();assert window.canvas.selected=={original.id}
    window.invert_region();assert np.array_equal(window._selection_mask(),~original.mask)
    window.cancel_operation();window.canvas.set_selected([original.id]);window._canvas_selected(window.canvas.selected)
    window.mode.setCurrentText("Edit");assert window.edit_action.isEnabled() and window.canvas.edit_mode
    window.mode.setCurrentText("Manual")
    item=next(window.objects_tree.topLevelItem(i)for i in range(window.objects_tree.topLevelItemCount())
              if window.objects_tree.topLevelItem(i).data(0,Qt.ItemDataRole.UserRole)==record.id)
    qtbot.mouseClick(window.objects_tree.viewport(),Qt.MouseButton.LeftButton,pos=window.objects_tree.visualItemRect(item).center())
    assert window.canvas.selected=={record.id}
    window.delete_selected()
    assert doc.working is None and np.array_equal(doc.frame.raw,raw) and len(doc.objects)==1
    assert not window.errors
