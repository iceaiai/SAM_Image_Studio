"""Image-coordinate interactions, reversible cleaning objects, and exact save options."""
import copy
import json
import numpy as np
import pytest
from PIL import Image
from PySide6.QtCore import QPoint, QPointF, QTimer, Qt
from PySide6.QtWidgets import QApplication, QDialog, QInputDialog, QMenu, QStyleOptionViewItem, QToolBar
from samstudio.app import STYLE
from samstudio.domain import Document, History, pack_mask, unpack_array
from samstudio.exports import decode_coco_rle, export_coco, overlap_grayscale, render_mask_pixels, save_masks
from samstudio.imageio import LoadResult
from samstudio.processing import patch_fill, shape_mask, measurements
from samstudio.dialogs import SaveMasksDialog


def mount(window,document):
    window._opened(LoadResult([document.frame]))
    window.document.restore(document.state());window._persist(window.document);window._refresh()
    return window.document


def region(doc,corners):
    return shape_mask("rectangle",corners,doc.frame.shape)


def overlapping(doc,n=2):
    doc.objects.clear()
    for i in range(n):
        mask=region(doc,[[20+i*10,20],[60+i*10,60]])
        doc.add_object("mask",mask=mask,provenance={"method":"manual"})
    return doc.objects


@pytest.mark.parametrize("count,weight",[(1,255),(2,127),(3,85),(4,63)])
def test_grayscale_adds_exact_weight_without_overflow(document,count,weight):
    objects=overlapping(document,count)
    gray,base,maximum=overlap_grayscale(objects,document.frame.shape)
    counts=sum(o.mask.astype(int) for o in objects)
    assert base==weight and maximum==count
    assert np.array_equal(gray,counts*base)
    binary=render_mask_pixels(document,objects,"binary")
    assert np.all(binary[counts>0,:3]==255) and np.all(binary[counts==0,:3]==0)


@pytest.mark.parametrize("fmt",["png","tif","bmp"])
def test_weighted_save_pixels_and_mapping(document,tmp_path,fmt):
    objects=overlapping(document)
    paths=save_masks(document,tmp_path,fmt,color_mode="overlap_gray")
    pixels=np.asarray(Image.open(paths[0]));assert pixels.ndim==2
    expected,weight,_=overlap_grayscale(objects,document.frame.shape)
    assert np.array_equal(pixels,expected)
    mapping=json.loads(next(tmp_path.glob("*mapping.json")).read_text())
    assert mapping["weighted_grayscale"][0]["weight_per_object"]==weight


def test_each_object_export_keeps_full_gray_range(document,tmp_path):
    overlapping(document)
    paths=save_masks(document,tmp_path,"png","object","overlap_gray")
    assert len(paths)==2
    assert all(set(np.unique(np.asarray(Image.open(p))))=={0,255} for p in paths)


@pytest.mark.parametrize("color",["binary","overlap_gray","object_color","group_color"])
@pytest.mark.parametrize("source",[False,"original","cleaned"])
def test_transparent_background_with_either_overlay_source(document,color,source):
    objects=overlapping(document)
    document.working=np.full_like(document.frame.raw,900)
    rgba=render_mask_pixels(document,objects,color,source,40,True)
    union=np.logical_or.reduce([o.mask for o in objects])
    assert not rgba[~union].any()
    assert np.all(rgba[union,3]==(153 if source is False else 255))
    assert not np.array_equal(document.working,document.frame.raw)


def test_cleaned_overlay_uses_actual_cleaned_pixels_and_requires_cleaning(document):
    objects=overlapping(document)
    with pytest.raises(ValueError,match="Apply cleaning"):
        render_mask_pixels(document,objects,overlay="cleaned")
    document.working=np.zeros((*document.frame.shape,),np.uint16)
    cleaned=render_mask_pixels(document,objects,overlay="cleaned",transparency=100)
    original=render_mask_pixels(document,objects,overlay="original",transparency=100)
    assert not cleaned[...,:3].any() and original[...,:3].any()


def test_alpha_saved_as_real_png_channel(document,tmp_path):
    paths=save_masks(document,tmp_path,"png",transparent=True,overlay="original",transparency=50)
    out=np.asarray(Image.open(paths[0]))
    assert out.shape[-1]==4 and not out[~document.objects[0].mask,3].any()


def test_cleaning_objects_replay_overlaps_and_delete_restores_original(document):
    raw=document.frame.raw.copy()
    a=document.remove_for_cleaning(region(document,[[60,20],[100,60]]))
    b=document.remove_for_cleaning(region(document,[[80,40],[120,80]]))
    assert a.visible and b.visible and a.role==b.role=="cleaning"
    target=document.removed.copy();filled=raw.copy();filled[target]=1234
    document.apply_cleaning_fill(filled,target,"neighbors")
    document.delete_objects([a.id])
    assert np.array_equal(document.working[~b.mask],raw[~b.mask])
    assert np.all(document.working[b.mask]==1234) and not document.removed.any()
    document.delete_objects([b.id]);assert document.working is None and not document.modified.any()
    archived=document.cleaning_history[-1]
    assert archived["objects"][0]["cleaning"]["method"]=="neighbors"
    assert archived["objects"][0]["mask"] and "original acquired pixels" in archived["method"]
    assert np.array_equal(raw,document.frame.raw)


def test_deleting_later_region_reveals_earlier_unfilled_region(document):
    mask=region(document,[[60,20],[90,60]])
    a=document.remove_for_cleaning(mask)
    b=document.remove_for_cleaning(mask)
    # Fill only the later object, emulating a filled edit covering an old removal.
    from samstudio.domain import pack_array
    b.cleaning["values"]=pack_array(np.full_like(document.frame.raw[mask],222))
    b.cleaning["pending"]=pack_mask(np.zeros(mask.shape,bool));document.rebuild_cleaning()
    document.delete_objects([b.id])
    assert np.all(document.working[mask]==0) and np.array_equal(document.removed,a.mask)


def test_partial_restore_changes_object_footprint_without_losing_fill(document):
    mask=region(document,[[60,20],[100,80]])
    obj=document.remove_for_cleaning(mask)
    result=document.frame.raw.copy();result[mask]=4321
    document.apply_cleaning_fill(result,mask,"patches","texture-group")
    half=region(document,[[50,0],[80,128]])
    document.restore_cleaning_area(half)
    assert np.array_equal(obj.mask,mask & ~half)
    assert np.all(document.working[obj.mask]==4321)
    assert np.array_equal(document.working[half],document.frame.raw[half])


def test_cleaning_json_recovery_and_undo_redo_are_exact(document):
    history=History(document)
    mask=region(document,[[60,20],[100,80]])
    history.apply("remove",lambda:document.remove_for_cleaning(mask))
    removed=document.working.copy()
    filled=document.frame.raw.copy();filled[mask]=2468
    history.apply("fill",lambda:document.apply_cleaning_fill(filled,mask,"lama"))
    saved=json.loads(json.dumps(document.state()))
    recovered=Document(document.frame);recovered.restore(saved)
    assert recovered.objects[-1].cleaning["method"]=="lama"
    recovered.rebuild_cleaning();assert np.array_equal(recovered.working,document.working)
    history.undo();assert np.array_equal(document.working,removed) and document.removed.any()
    history.redo();assert np.all(document.working[mask]==2468)
    history.apply("delete",lambda:document.delete_objects([document.objects[-1].id]))
    assert document.working is None
    history.undo();assert np.all(document.working[mask]==2468)


def test_legacy_cleaning_load_creates_visible_restorable_object(document):
    document.working=document.frame.raw.copy()
    document.modified[65:80,70:95]=True
    document.working[document.modified]=333
    old=document.state()
    old["schema_version"]=1
    recovered=Document(document.frame);recovered.restore(old)
    cleaning=[o for o in recovered.objects if o.role=="cleaning"]
    assert len(cleaning)==1 and cleaning[0].visible
    recovered.delete_objects([cleaning[0].id]);assert recovered.working is None


def test_corrupt_cleaning_record_rejected_atomically(document):
    document.remove_for_cleaning(region(document,[[60,20],[90,60]]))
    original=document.state();bad=copy.deepcopy(original)
    bad["objects"][-1]["cleaning"]["pending"]=pack_mask(np.ones(document.frame.shape,bool))
    with pytest.raises(ValueError):document.restore(bad)
    assert document.state()==original


def test_coco_preserves_cleaning_objects_pixels_and_restoration_method(document,tmp_path):
    obj=document.remove_for_cleaning(region(document,[[60,20],[90,60]]))
    result=document.frame.raw.copy();result[obj.mask]=987
    document.apply_cleaning_fill(result,obj.mask,"patches","some-group-id")
    report=export_coco([document],tmp_path)
    data=json.loads(open(report["path"]).read());record=data["cleaning_annotations"][0]
    assert record["samstudio_id"]==obj.id and record["exclude_from_training"]
    assert np.array_equal(decode_coco_rle(record["segmentation"]),obj.mask)
    assert record["cleaning"]["method"]=="patches"
    assert record["cleaning"]["steps"][-1]["background_group_id"]=="some-group-id"
    restoration=data["images"][0]["samstudio_cleaning"]
    assert "original acquired pixels" in restoration["restoration"]
    assert np.array_equal(unpack_array(restoration["source_pixels"]),document.frame.raw)
    assert len(data["annotations"])==1


def test_cleaning_and_background_regions_excluded_from_masks_and_statistics(document):
    foreground=document.objects[0]
    cleaning=document.remove_for_cleaning(region(document,[[60,20],[90,60]]))
    document.ensure_group("Texture A")
    background=document.add_object("mask",mask=region(document,[[100,80],[130,110]]),provenance={"method":"manual"})
    document.background_group_id=background.group_id
    assert document.foreground_objects()==[foreground]
    assert np.array_equal(document.protected_mask(),foreground.mask)
    rows,_=measurements(document);assert [r["object_id"] for r in rows]==[foreground.id]
    pixels=render_mask_pixels(document,document.objects,"binary")
    assert not pixels[cleaning.mask,:3].any() and not pixels[background.mask,:3].any()


def test_arbitrary_background_group_and_irregular_region_only_samples_inside(document):
    document.ensure_group("Copper support")
    patch=shape_mask("ellipse",[[100,20],[145,65]],document.frame.shape)
    obj=document.add_object("ellipse",[[100,20],[145,65]],patch,{"method":"manual"})
    document.background_group_id=obj.group_id
    assert document.background_regions()==[obj]
    raw=np.full(document.frame.shape,65535,np.uint16);raw[patch]=73
    target=region(document,[[60,75],[90,100]])
    filled=patch_fill(raw,target,[o.mask for o in document.background_regions()])
    assert np.all(filled[target]==73) and np.array_equal(filled[~target],raw[~target])


def test_background_group_ignores_sam_objects(document):
    document.background_group_id=document.active_group
    assert not document.background_regions()  # fixture mask has no manual provenance


@pytest.mark.parametrize("scale",[0.5,1,2,12])
def test_polygon_snap_uses_screen_distance_at_every_zoom(window,document,qtbot,scale):
    doc=mount(window,document);doc.objects.clear();window.canvas.refresh()
    canvas=window.canvas;canvas.scale=scale;canvas.offset=QPointF(10,10)
    window.tool_actions["polygon"].trigger()
    start = canvas.to_widget((20, 20)).toPoint()
    for point in (start, start + QPoint(45, 0), start + QPoint(45, 40), start + QPoint(10, 0)):
        qtbot.mouseClick(canvas,Qt.MouseButton.LeftButton,pos=point)
    assert len(doc.objects)==1 and len(doc.objects[0].points)==3
    assert not canvas._drawing and not window.errors


def test_polygon_closing_distance_can_be_changed_or_disabled(window,document,qtbot,monkeypatch):
    doc=mount(window,document);doc.objects.clear();window.canvas.refresh()
    canvas=window.canvas;canvas.scale=2;canvas.offset=QPointF(5,5);window.tool_actions["polygon"].trigger()
    start = canvas.to_widget((20, 20)).toPoint()
    for point in (start, start + QPoint(46, 0), start + QPoint(46, 46), start + QPoint(18, 0)):
        qtbot.mouseClick(canvas,Qt.MouseButton.LeftButton,pos=point)
    assert not doc.objects and len(canvas._drawing)==4
    monkeypatch.setattr(QInputDialog, "getInt", lambda *args: (20, True))
    window.change_polygon_close_distance()
    assert window.settings.value("polygon_close_distance", type=int) == 20
    qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=start + QPoint(18, 0))
    assert len(doc.objects) == 1
    monkeypatch.setattr(QInputDialog, "getInt", lambda *args: (0, True))
    window.change_polygon_close_distance()
    for point in (start, start + QPoint(50, 0), start + QPoint(50, 46), start + QPoint(2, 0)):
        qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=point)
    assert len(doc.objects) == 1 and len(canvas._drawing) == 4
    qtbot.keyClick(canvas, Qt.Key.Key_Return)
    assert len(doc.objects) == 2


@pytest.mark.parametrize("mode",["Manual","Segment"])
@pytest.mark.parametrize("scale",[2,10,50])
def test_zoomed_point_click_never_becomes_a_subpixel_area(window,document,qtbot,mode,scale):
    doc=mount(window,document);doc.objects.clear();window.auto_checkbox.setChecked(False)
    window.mode.setCurrentText(mode);window.tool_actions["point"].trigger()
    window.canvas.scale=scale;window.canvas.offset=QPointF(10-20*scale,10-20*scale)
    qtbot.mouseClick(window.canvas,Qt.MouseButton.LeftButton,pos=window.canvas.to_widget([20.2,20.2]).toPoint())
    if mode=="Manual":assert len(doc.objects)==1 and doc.objects[0].kind=="point" and doc.objects[0].mask is None
    else:assert len(doc.draft["points"])==1 and doc.draft["roi"] is None
    assert not window.errors and not window.canvas._drawing


@pytest.mark.parametrize(("mode", "scope", "tool"), [
    ("Manual", None, "rectangle"),
    ("Clean", None, "circle"),
    ("Segment", "roi", "rectangle"),
    ("Segment", "prompt", "ellipse"),
])
def test_subpixel_area_gesture_is_transient_and_can_be_redrawn(window, document, qtbot, mode, scope, tool):
    doc = mount(window, document)
    window.auto_checkbox.setChecked(False)
    window.mode.setCurrentText(mode)
    window.tool_actions[tool].trigger()
    if scope:
        window.scope.setCurrentIndex(window.scope.findData(scope))
    canvas = window.canvas
    canvas.scale = 10
    canvas.offset = QPointF(-100, -100)

    def draw(end):
        qtbot.mousePress(canvas, Qt.MouseButton.LeftButton, pos=canvas.to_widget((20, 20)).toPoint())
        qtbot.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=canvas.to_widget(end).toPoint())

    before = doc.state()
    saved = window.stores[doc.frame.key].path(doc).read_bytes()
    for end in ((20, 20), (20.4, 31)):
        draw(end)
        assert "smaller than one pixel" in window.statusBar().currentMessage()
        assert not canvas._drawing and canvas._cursor is None and not window.errors
        assert doc.state() == before and window.stores[doc.frame.key].path(doc).read_bytes() == saved

    draw((30, 28))
    assert doc.revision == before["revision"] + 1 and not window.errors
    if mode == "Manual":
        assert doc.objects[-1].kind == tool and doc.objects[-1].mask.any()
    elif scope == "prompt":
        assert doc.draft["examples"][0]["kind"] == tool
    else:
        assert window._selection_mask().any()


def test_open_autosave_with_subpixel_roi_preserves_objects_and_valid_prompts(window, document):
    tiny = {"kind": "rectangle", "points": [[20, 25], [20, 25]]}
    usable = {"kind": "ellipse", "points": [[40, 40], [56, 48]], "label": 1}
    document.draft.update(roi=tiny, examples=[{**tiny, "label": 0}, usable], points=[[60, 60, 1]])
    window._store_for(document.frame).save(document)
    window._opened(LoadResult([document.frame]))

    restored = window.document
    assert restored.draft["roi"] is None
    assert restored.draft["examples"] == [usable]
    assert restored.draft["points"] == [[60, 60, 1]]
    assert [obj.to_dict() for obj in restored.objects] == [obj.to_dict() for obj in document.objects]
    assert not window.errors


def test_edit_mode_controls_radius_and_does_not_add_points(window,document,qtbot):
    doc=mount(window,document);obj=doc.objects[0]
    window.canvas.set_selected([obj.id]);window.mode.setCurrentText("Edit")
    qtbot.waitUntil(window.vertex_radius.isVisible,timeout=2000)
    assert window.canvas.edit_mode and window.vertex_radius.isVisible()
    assert window.canvas.handle_radius==pytest.approx(5.1)
    assert not window.tool_actions["polygon"].isEnabled()
    window.vertex_radius.setValue(37);assert window.canvas.vertex_delete_radius==37
    before=len(doc.objects);window._shape_completed("point",[[80,80]])
    assert len(doc.objects)==before
    window.mode.setCurrentText("Manual")
    qtbot.waitUntil(lambda:not window.vertex_radius.isVisible(),timeout=2000)
    assert not window.canvas.edit_mode and not window.vertex_radius.isVisible()
    window.mode.setCurrentText("Segment");qtbot.wait(5)
    assert not window.vertex_radius.isVisible()


def test_hand_pan_reset_fit_and_large_undo_buttons(window,document,qtbot):
    mount(window,document);canvas=window.canvas
    old=QPointF(canvas.offset);window.tool_actions["pan"].trigger()
    qtbot.mousePress(canvas,Qt.MouseButton.LeftButton,pos=canvas.rect().center())
    qtbot.mouseMove(canvas,canvas.rect().center()+QPointF(40,30).toPoint())
    qtbot.mouseRelease(canvas,Qt.MouseButton.LeftButton,pos=canvas.rect().center()+QPointF(40,30).toPoint())
    assert canvas.offset!=old
    canvas.scale=12;window.fit_action.trigger()
    h,w=window.document.frame.shape
    assert canvas.scale==pytest.approx(min((canvas.width()-40)/w,(canvas.height()-40)/h))
    for action in (window.undo_action,window.redo_action):
        button = next(toolbar.widgetForAction(action) for toolbar in window.drawing_toolbars if action in toolbar.actions())
        assert button.iconSize().width()==44 and button.height()==72


def test_two_drawing_columns_and_four_independent_top_toolbar_toggles(window, qtbot):
    window.setStyleSheet(STYLE)
    window.resize(1280, 720)
    window.set_drawing_icon_size(40)
    qtbot.wait(30)
    first, second = window.drawing_toolbars
    assert first.x() < second.x()
    assert first.widgetForAction(window.tool_actions["point"]).isVisible()
    assert second.widgetForAction(window.tool_actions["ellipse"]).isVisible()
    assert all(toolbar.widgetForAction(action).isVisible() for toolbar in (first, second) for action in toolbar.actions())
    bars = [window.findChild(QToolBar, name) for name in ("workflowToolbar", "imageToolbar", "regionToolbar", "promptToolbar")]
    toggles = window.toolbar_menu.actions()
    assert toggles == [bar.toggleViewAction() for bar in bars]
    for current, toggle in zip(bars, toggles):
        assert toggle.isChecked() and current.isVisible()
        toggle.trigger()
        assert current.isHidden() and not toggle.isChecked()
        assert not window.settings.value(f"toolbars/{current.objectName()}", type=bool)
        assert all(not bar.isHidden() for bar in bars if bar is not current)
        toggle.trigger()
        assert toggle.isChecked() and current.isVisible()


def test_combo_checkmark_changes_without_changing_model_data(window):
    delegate=window.mode.itemDelegate()
    for name in ["Manual","Segment","Clean","Edit"]:
        window.mode.setCurrentText(name)
        for row in range(window.mode.count()):
            option=QStyleOptionViewItem();delegate.initStyleOption(option,window.mode.model().index(row,0))
            assert option.text.endswith("√")== (row==window.mode.currentIndex())
        assert window.mode.currentText()==name and window.mode.currentData()==name


def test_delete_for_cleaning_context_only_in_clean_mode_and_undo(window,document,qtbot,monkeypatch):
    doc=mount(window,document);obj=doc.objects[0];raw=doc.frame.raw.copy();menus=[]
    def inspect():
        menu=QApplication.activePopupWidget()
        assert isinstance(menu,QMenu)
        menus.append([a.text() for a in menu.actions()]);menu.close()
    QTimer.singleShot(0,inspect)
    window.canvas.set_selected([obj.id]);window._show_object_context_menu(window.pos())
    assert "Delete for cleaning" not in menus[-1]
    window.mode.setCurrentText("Clean")
    QTimer.singleShot(0,inspect)
    qtbot.mouseClick(window.canvas,Qt.MouseButton.RightButton,pos=window.canvas.to_widget([40,40]).toPoint())
    assert "Delete for cleaning" in menus[-1]
    window.delete_for_cleaning();assert obj.role=="cleaning" and obj.visible and doc.removed.any()
    window.refine_selected_inference()
    assert "Cleaning regions" in window.errors[-1][1]
    window.errors.clear()
    recovered=Document(doc.frame);assert window.stores[doc.frame.key].load(recovered)[0]
    assert recovered.objects[0].role=="cleaning"
    assert window.canvas.show_cleaning and window.show_cleaning_button.isChecked()
    window.show_cleaning_button.setChecked(False);assert not window.canvas.show_cleaning
    assert window.canvas.object_at([40,40]) is None and doc.working is not None
    window.show_cleaning_button.setChecked(True)
    window.delete_selected();assert doc.working is None and not doc.objects
    window.undo();assert doc.objects[0].role=="cleaning" and doc.removed.any()
    window.redo();assert doc.working is None
    assert np.array_equal(raw,doc.frame.raw) and not window.errors


def test_background_picker_accepts_any_manual_group_name(window,document,monkeypatch):
    doc=mount(window,document);doc.ensure_group("Far field")
    mask=region(doc,[[100,80],[130,110]])
    doc.add_object("mask",mask=mask,provenance={"method":"manual"})
    monkeypatch.setattr(QInputDialog,"getItem",lambda *a,**k:("Far field",True))
    assert window.choose_background_group()
    assert doc.get_group(doc.background_group_id).name=="Far field" and not window.errors


def test_save_dialog_exposes_cleaned_overlay_and_independent_alpha(document,qtbot):
    document.working=document.frame.raw.copy()
    dialog=SaveMasksDialog(document);qtbot.addWidget(dialog)
    dialog.format.setCurrentIndex(dialog.format.findData("png"))
    dialog.overlay.setChecked(True);dialog.overlay_source.setCurrentIndex(dialog.overlay_source.findData("cleaned"))
    dialog.transparent.setChecked(True);dialog.transparency.setValue(35)
    assert dialog.values()["overlay"]=="cleaned" and dialog.values()["transparent"] and dialog.values()["transparency"]==35
    dialog.color.setCurrentIndex(dialog.color.findData("overlap_gray"))
    assert dialog.values()["color_mode"]=="overlap_gray"


def test_locked_cleaning_object_cannot_be_deleted_or_restored(document):
    obj=document.remove_for_cleaning(region(document,[[60,20],[90,60]]));obj.locked=True
    before=document.working.copy()
    with pytest.raises(ValueError,match="Unlock"):document.delete_objects([obj.id])
    with pytest.raises(ValueError,match="Unlock"):document.restore_cleaning_area(obj.mask)
    assert np.array_equal(document.working,before)


def test_only_cleaning_regions_disables_mask_save(document,qtbot):
    obj=document.objects[0];document.remove_for_cleaning(obj.mask,source=obj)
    dialog=SaveMasksDialog(document);qtbot.addWidget(dialog)
    from PySide6.QtWidgets import QDialogButtonBox
    assert not dialog.controls.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
    assert "no accepted object masks" in dialog.info.text()
