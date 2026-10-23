"""Native Qt interactions, transform recovery and scientific measurement checks."""
import copy
import csv
import json
import math
from pathlib import Path
import cv2
import numpy as np
import pytest
import tifffile
from PySide6.QtCore import Qt,QTimer
from PySide6.QtWidgets import QApplication,QDialog,QDialogButtonBox,QFileDialog,QMessageBox
from samstudio.domain import Calibration,Document,History,ImageFrame,ProjectStore,pack_mask
from samstudio.imageio import LoadResult
from samstudio.processing import shape_mask,neighbor_fill
from samstudio.transforms import rotate_document,rotation_matrix,scaled_objects,apply_scaled_objects,warp_pixels
from samstudio.text_prompts import validate_aliases,resolve_prompt
from samstudio.statistics import METRICS,measurement_records,export_statistics,summary_records
from samstudio.dialogs import StatisticsDialog
from samstudio.dialogs_v14 import MaskScaleDialog,RotationDialog,PromptAliasesDialog,MorphologyDialog
from samstudio.exports import save_image,export_coco,decode_coco_rle
from samstudio import savepoints


def mount(window,document):
    window._opened(LoadResult([document.frame]));window.document.restore(document.state());window._persist(window.document);window._refresh();return window.document


def second(doc):
    mask=np.zeros(doc.frame.shape,bool);mask[78:110,110:145]=1
    return doc.add_object('mask',mask=mask,provenance={'method':'manual'})


def test_edit_canvas_switches_object_and_tree_switches_back(window,document,qtbot):
    doc=mount(window,document);other=second(doc);window._refresh();window.mode.setCurrentText('Edit')
    first=doc.objects[0];window.canvas.set_selected([first.id]);window._refresh()
    before=[o.mask.copy() for o in doc.objects]
    qtbot.mouseClick(window.canvas,Qt.MouseButton.LeftButton,pos=window.canvas.to_widget([122,90]).toPoint())
    assert window.canvas.selected=={other.id}
    assert window.objects_tree.selectedItems()[0].data(0,Qt.ItemDataRole.UserRole)==other.id
    window.objects_tree.clearSelection();window.objects_tree.topLevelItem(0).setSelected(True)
    assert window.canvas.selected=={first.id} and window.canvas.handle_radius==pytest.approx(5.1)
    for original,obj in zip(before,doc.objects):assert np.array_equal(original,obj.mask)
    assert not window.errors


@pytest.mark.parametrize('answer',[QMessageBox.StandardButton.Yes,QMessageBox.StandardButton.No,QMessageBox.StandardButton.Cancel])
@pytest.mark.parametrize('pending',['polygon','roi','points','preview'])
def test_mode_switch_resolves_unadded_content(window,document,qtbot,monkeypatch,answer,pending):
    doc=mount(window,document);window.auto_checkbox.setChecked(False)
    if pending!='polygon':window.mode.setCurrentText('Segment')
    old=window.canvas.mode;count=len(doc.objects)
    if pending=='polygon':window.canvas.set_tool('polygon');window.canvas._drawing=[[70,10],[95,10],[95,40],[70,40]]
    elif pending=='roi':doc.draft['roi']={'kind':'rectangle','points':[[70,10],[95,40]]}
    elif pending=='points':doc.draft['points']=[[75,20,1],[90,25,0]]
    else:
        mask=np.zeros(doc.frame.shape,bool);mask[70:100,70:95]=1;window.canvas.set_preview([mask]);window._preview_context={'method':'SAM','model':'contract test','device':'cpu','confidence_scores':[.93]}
    calls=[]
    monkeypatch.setattr(QMessageBox,'question',lambda *a,**k:calls.append(a[1]) or answer)
    window.mode.setCurrentText('Edit')
    assert calls==['Unadded shapes']
    if answer==QMessageBox.StandardButton.Cancel:
        assert window.mode.currentText()==old and window._pending_mode_content() and len(doc.objects)==count
    else:
        assert window.mode.currentText()=='Edit' and not window._pending_mode_content()
        assert len(doc.objects)==count+(answer==QMessageBox.StandardButton.Yes)
        if pending=='preview' and answer==QMessageBox.StandardButton.Yes:assert doc.objects[-1].provenance['confidence_score']==.93
    assert not window.errors


def test_mode_switch_native_confirmation_can_be_cancelled(window,document,qtbot):
    doc=mount(window,document);window.canvas.set_tool('polygon');window.canvas._drawing=[[70,10],[95,10],[95,40]]
    seen=[]
    def cancel():
        dialog=QApplication.activeModalWidget();seen.append(dialog.windowTitle());qtbot.mouseClick(dialog.button(QMessageBox.StandardButton.Cancel),Qt.MouseButton.LeftButton)
    QTimer.singleShot(20,cancel);window.mode.setCurrentText('Edit')
    assert seen==['Unadded shapes'] and window.mode.currentText()=='Manual' and len(window.canvas._drawing)==3


@pytest.mark.parametrize('angle',[30,45,60,90,180,270,-45])
@pytest.mark.parametrize('padding',['none','rectangle','square'])
def test_rotation_masks_dtype_calibration_and_recovery(document,angle,padding,tmp_path):
    doc=document;raw=doc.frame.raw.copy();old=doc.objects[0].mask.copy();matrix,shape=rotation_matrix(doc.frame.shape,angle,padding)
    physical_before=measurement_records(doc)[0][0]['area_physical'];hist=History(doc)
    hist.apply('rotate',lambda:rotate_document(doc,angle,padding))
    assert doc.frame.shape==shape and doc.frame.raw.dtype==raw.dtype and np.array_equal(doc.source_raw,raw)
    assert np.array_equal(doc.objects[0].mask,warp_pixels(old,matrix,shape,True))
    assert doc.calibration.pixel_area==pytest.approx(.06)
    if angle in (90,180,270) and padding=='rectangle':
        assert np.array_equal(doc.frame.raw,np.rot90(raw,angle//90));assert measurement_records(doc)[0][0]['area_physical']==pytest.approx(physical_before)
    saved=ProjectStore(tmp_path);saved.save(doc);fresh=Document(ImageFrame(doc.frame.source_path,raw,calibration=Calibration(.2,.3,'nm','test',True)));saved.load(fresh)
    assert fresh.frame.shape==shape and np.array_equal(fresh.objects[0].mask,doc.objects[0].mask)
    assert np.array_equal(fresh.working,doc.working)
    assert hist.undo() and np.array_equal(doc.frame.raw,raw) and np.array_equal(doc.objects[0].mask,old)
    assert hist.redo() and doc.frame.shape==shape


def test_repeated_rotation_physical_centroid_and_lengths_are_invariant(document):
    before=measurement_records(document)[0][0]
    rotate_document(document,90,'rectangle');rotate_document(document,90,'rectangle')
    after=measurement_records(document)[0][0]
    for key in ('area','length','width','centroid_x','centroid_y','feret_max','feret_min'):
        assert after[key+'_physical']==pytest.approx(before[key+'_physical'])


def test_rotation_replays_overlap_cleaning_and_restores_original_exports(document,tmp_path):
    raw=document.frame.raw.copy();mask=np.zeros(document.frame.shape,bool);mask[60:80,20:40]=1
    record=document.remove_for_cleaning(mask);fill=document.working.copy();fill[mask]=123;document.apply_cleaning_fill(fill,mask,'contract fixture')
    expected=np.rot90(document.working)
    rotate_document(document,90,'rectangle');assert np.array_equal(document.working,expected)
    document.delete_objects([record.id]);assert np.array_equal(document.working,np.rot90(raw))
    original=save_image(document,tmp_path/'original.tif','original');derived=save_image(document,tmp_path/'derived.tif','cleaned')
    assert np.array_equal(tifffile.imread(original),raw) and np.array_equal(tifffile.imread(derived),np.rot90(raw))
    result=json.loads(Path(export_coco([document],tmp_path/'dataset')['path']).read_text())
    assert result['images'][0]['width']==raw.shape[0] and result['images'][0]['samstudio_rotation']
    assert np.array_equal(decode_coco_rle(result['annotations'][0]['segmentation']),document.objects[0].mask)


def test_rotation_rejects_locked_and_bad_state_atomically(document):
    original=document.state();document.objects[0].locked=True
    with pytest.raises(ValueError,match='Unlock'):rotate_document(document,45,'square')
    document.restore(original);data=document.state();data['derived_base']={'invalid':1}
    with pytest.raises((ValueError,KeyError)):document.restore(data)
    assert np.array_equal(document.frame.raw,document.source_raw)


@pytest.mark.parametrize('fill',['black','neighbors'])
def test_native_rotation_dialog_flow_and_undo(window,document,qtbot,monkeypatch,fill):
    doc=mount(window,document);window.mode.setCurrentText('Edit');original=doc.frame.raw.copy();shape=doc.frame.shape
    monkeypatch.setattr(RotationDialog,'exec',lambda self:(self.angle.setValue(45),self.padding.setCurrentIndex(2),self.fill.setCurrentIndex(0 if fill=='black' else 1),QDialog.DialogCode.Accepted)[-1])
    from samstudio.main_window import ImagePreviewDialog
    monkeypatch.setattr(ImagePreviewDialog,'exec',lambda self:QDialog.DialogCode.Accepted)
    window.rotate_image_dialog();qtbot.waitUntil(lambda:not window.busy,timeout=30000)
    assert not window.errors and doc.frame.shape[0]==doc.frame.shape[1] and doc.frame.shape!=shape
    record=next(o for o in doc.objects if o.provenance.get('method')=='rotation padding')
    assert not doc.removed.any() and record.cleaning['method']==fill
    window.undo();assert np.array_equal(doc.frame.raw,original) and not doc.rotation
    window.redo();assert doc.rotation


def test_alias_validation_resolution_and_project_recovery(document,tmp_path):
    aliases=validate_aliases({'Nanoparticle':'particles','particles':'big dots','Powder':'big dots'})
    assert resolve_prompt('NANOPARTICLE. powder; dotted line',aliases)=='big dots. big dots. dotted line'
    document.text_aliases=aliases;store=ProjectStore(tmp_path);store.save(document);fresh=Document(document.frame);store.load(fresh);assert fresh.text_aliases==aliases
    result=json.loads(Path(export_coco([document],tmp_path/'coco')['path']).read_text());assert result['images'][0]['text_prompt_aliases']==aliases
    for invalid in ({'a':'b','b':'a'},{'a':' '},{'A':'b','a':'c'}):
        with pytest.raises(ValueError):validate_aliases(invalid)


def test_alias_dialog_and_sam2_text_ui(window,document,qtbot,monkeypatch):
    from samstudio.inference import CATALOG
    doc=mount(window,document);window.engine.spec=next(s for s in CATALOG if s.family=='SAM2.1');window._refresh();qtbot.waitUntil(window.text_prompt.isVisible)
    dialog=PromptAliasesDialog({},window);qtbot.addWidget(dialog);dialog.add_row('powder','big dots');assert dialog.values()=={'powder':'big dots'}
    doc.text_aliases=dialog.values();window.text_prompt.setText('powder');assert 'big dots' in window.text_prompt.toolTip()
    window.engine.spec=next(s for s in CATALOG if s.family=='SAM1');window._refresh();qtbot.waitUntil(lambda:not window.text_prompt.isVisible())


@pytest.mark.parametrize('factor',[.5,1.,1.75,2.])
def test_scale_preserves_original_shapes_holes_ids_and_group(document,factor):
    first=document.objects[0];first.mask=np.roll(first.mask,(30,40),axis=(0,1));other=second(document);ids={first.id,other.id};original=savepoints.capture(document)
    copies=scaled_objects(document,ids,factor);apply_scaled_objects(document,copies)
    assert {o.id for o in document.objects}==ids and len({o.group_id for o in document.objects})==1
    assert document.objects[0].pixel_area==pytest.approx(first.pixel_area*factor**2,rel=.12)
    savepoints.restore(document,original)
    for current,saved in zip(document.objects,original['objects']):assert current.to_dict()==saved


def test_savepoints_temporary_never_serialized_local_exact_roundtrip(document,tmp_path):
    original=savepoints.capture(document);temp=[original];before=set(tmp_path.iterdir());assert original['id'] not in json.dumps(document.state())
    scaled=scaled_objects(document,[document.objects[0].id],1.5);apply_scaled_objects(document,scaled);temp.append(savepoints.capture(document,'×1.5'))
    assert set(tmp_path.iterdir())==before
    folder=savepoints.write_local(original,tmp_path);assert (folder/'snapshot.json').exists() and list((folder/'masks').glob('*.png'))
    savepoints.restore(document,savepoints.read_local(folder));assert document.objects[0].to_dict()==original['objects'][0]
    rotate_document(document,90,'rectangle')
    with pytest.raises(ValueError,match='different image or rotation'):savepoints.restore(document,original)


def test_scale_dialog_manual_precision_group_and_temporary_list(window,document,qtbot,monkeypatch):
    doc=mount(window,document);second(doc);window.mode.setCurrentText('Edit');window.canvas.set_selected([doc.objects[0].id]);window._refresh()
    original=[o.to_dict() for o in doc.objects]
    def apply(self):
        self.scope.setCurrentIndex(1);self.factor.setValue(1.234);assert self.factor.value()==1.234;self.accept();return QDialog.DialogCode.Accepted
    monkeypatch.setattr(MaskScaleDialog,'exec',apply);window.scale_masks_dialog()
    assert not window.errors
    snaps=window.mask_savepoints[doc.frame.key];assert [s['name'] for s in snaps]==['original','×1.234']
    assert len(snaps[0]['objects'])==2 and snaps[0]['id'] not in json.dumps(doc.state())
    window.undo();assert [o.to_dict() for o in doc.objects]==original
    savepoints.restore(doc,snaps[0]);assert [o.to_dict() for o in doc.objects]==original


def test_morphology_metrics_rectangles_and_small_masks(document):
    document.objects=[];mask=np.zeros(document.frame.shape,bool);mask[30:50,40:80]=1
    obj=document.add_object('mask',mask=mask,provenance={'method':'manual','morphology':{'type':'polygon','sides':4}})
    row=measurement_records(document)[0][0]
    assert row['area_px']==800 and row['diameter_px']==pytest.approx(math.sqrt(3200/math.pi))
    assert row['feret_min_px']==pytest.approx(20) and row['feret_max_px']==pytest.approx(math.hypot(40,20))
    assert row['centroid_x_px']==59.5 and row['centroid_y_px']==39.5 and row['orientation_px']==0
    assert row['solidity_px']==pytest.approx(1) and row['corner_error_px']==pytest.approx(0)
    assert row['confidence_px'] is None and row['confidence_note']
    obj.mask=np.zeros(document.frame.shape,bool);obj.mask[0,0]=1
    row=measurement_records(document)[0][0];assert row['border_status_px']==1 and row['width_px']>0


@pytest.mark.parametrize('kind',['core-shell','hollow'])
def test_nested_morphology_requires_link_and_measures_shift_uniformity(document,kind):
    document.objects=[];yy,xx=np.ogrid[:128,:160];outer=(xx-70)**2+(yy-60)**2<=40**2;inner=(xx-75)**2+(yy-60)**2<=18**2
    parent=document.add_object('mask',mask=outer);child=document.add_object('mask',mask=inner)
    parent.provenance['morphology']={'type':kind,'inner_id':child.id}
    records,_=measurement_records(document);row=records[0]
    assert sum(r['particle_count_px'] for r in records)==1
    if kind=='core-shell':
        assert row['center_displacement_px']==pytest.approx(5) and row['displacement_direction_px']==pytest.approx(0)
        assert 18<row['shell_thickness_px']<24 and 0<row['shell_uniformity_px']<.4
    else:assert row['cavity_x_px']==pytest.approx(75) and 18<row['wall_thickness_px']<24
    child.mask=np.roll(inner,70,axis=1)
    invalid=measurement_records(document)[0][0]
    assert invalid['applicability_note'] and invalid['shell_thickness_px'] is None and invalid['wall_thickness_px'] is None


def test_statistics_up_to_nine_axes_names_limits_colors_resize_and_exports(document,qtbot,tmp_path):
    dialog=StatisticsDialog([document],document);qtbot.addWidget(dialog);dialog.show();dialog.unit.setCurrentText('Pixels')
    for i in range(1,9):dialog.metrics_list.item(i).setCheckState(Qt.CheckState.Checked)
    assert len(dialog.selected_metrics())==9 and len(dialog.figure.axes)==9
    dialog.metrics_list.item(9).setCheckState(Qt.CheckState.Checked);assert len(dialog.selected_metrics())==9
    dialog.axis_combo.setCurrentIndex(0);dialog.x_label.setText('Particle area');dialog.y_label.setText('Frequency')
    dialog.x_min.setText('0');dialog.x_max.setText('4000');dialog.x_step.setText('1000');dialog.y_min.setText('0');dialog.y_max.setText('3');dialog.y_step.setText('1');dialog.label_size.setValue(14);dialog._bar_color='#cc2233';dialog.apply_axes()
    ax=dialog.figure.axes[0];assert ax.get_xlabel()=='Particle area' and ax.get_ylabel()=='Frequency' and ax.get_xlim()==(0,4000)
    assert ax.patches[0].get_facecolor()[:3]==pytest.approx((.8,34/255,51/255))
    dialog.resize(1480,1000);dialog.canvas.draw();dialog.grab();plot=tmp_path/'plots.png';dialog.figure.savefig(plot);assert plot.stat().st_size>1000
    all_csv=tmp_path/'all.csv';export_statistics(dialog.records,all_csv);columns=next(csv.reader(all_csv.open(encoding='utf-8-sig')));assert 'wall_uniformity_physical' in columns
    selected=tmp_path/'selected.csv';export_statistics(dialog.records,selected,['area','confidence']);columns=next(csv.reader(selected.open(encoding='utf-8-sig')));assert 'area_px' in columns and 'feret_max_px' not in columns
    assert selected.with_name('selected_summary.csv').exists()
    assert len(METRICS)==len(set(METRICS)) and 'projected_area' not in METRICS and 'equivalent_diameter' not in METRICS


def test_native_new_dialogs_paint_and_resize_without_qt_virtual_collisions(document,qtbot):
    obj=document.objects[0]
    for dialog in (RotationDialog(document),MaskScaleDialog(document,[obj.id],[]),MorphologyDialog(document,obj),PromptAliasesDialog({})):
        qtbot.addWidget(dialog);dialog.show();dialog.resize(880,740);qtbot.wait(10);image=dialog.grab().toImage();assert not image.isNull();dialog.close()


def test_native_rotation_uses_explicit_background_group(window,document,qtbot,monkeypatch):
    doc=mount(window,document);group=doc.ensure_group('Reference texture');doc.add_object('rectangle',[[90,20],[120,50]],shape_mask('rectangle',[[90,20],[120,50]],doc.frame.shape),{'method':'manual'});doc.background_group_id=group.id
    window._refresh();window.mode.setCurrentText('Edit')
    def options(self):
        self.angle.setValue(30);self.padding.setCurrentIndex(1);self.fill.setCurrentIndex(3);return QDialog.DialogCode.Accepted
    monkeypatch.setattr(RotationDialog,'exec',options)
    from samstudio.main_window import ImagePreviewDialog
    monkeypatch.setattr(ImagePreviewDialog,'exec',lambda self:QDialog.DialogCode.Accepted)
    window.rotate_image_dialog();qtbot.waitUntil(lambda:not window.busy,timeout=30000)
    assert not window.errors and doc.working.dtype==document.frame.raw.dtype
    record=next(o for o in doc.objects if o.provenance.get('method')=='rotation padding')
    assert record.cleaning['method']=='patches' and not doc.removed.any()
    assert record.cleaning['steps'][-1]['background_group_id']==group.id
    assert np.array_equal(doc.working[~record.mask],doc.frame.raw[~record.mask])


def test_tree_native_checkbox_and_repeated_selection_keep_live_items(window,document,qtbot):
    doc=mount(window,document);second(doc);window._refresh();window.mode.setCurrentText('Edit')
    tree=window.objects_tree
    for i in range(12):
        item=tree.topLevelItem(i%2);rect=tree.visualItemRect(item)
        qtbot.mouseClick(tree.viewport(),Qt.MouseButton.LeftButton,pos=rect.center())
        assert window.canvas.selected=={doc.objects[i%2].id}
    item=tree.topLevelItem(0);ident=item.data(0,Qt.ItemDataRole.UserRole);item.setCheckState(0,Qt.CheckState.Unchecked)
    qtbot.waitUntil(lambda:not next(o for o in doc.objects if o.id==ident).visible)
    qtbot.wait(10);assert tree.topLevelItemCount()==2 and not window.errors


def test_invalid_inner_link_does_not_reduce_particle_count(document):
    other=second(document);document.objects[0].provenance['morphology']={'type':'core-shell','inner_id':other.id}
    rows,_=measurement_records(document);assert sum(r['particle_count_px'] for r in rows)==2
    assert rows[0]['shell_thickness_px'] is None and rows[0]['applicability_note']


def test_rotation_background_fill_rejects_previously_edited_sources(window,document,monkeypatch):
    doc=mount(window,document);group=doc.ensure_group('Texture');mask=np.zeros(doc.frame.shape,bool);mask[65:85,65:90]=True
    doc.add_object('mask',mask=mask,provenance={'method':'manual'});doc.background_group_id=group.id
    doc.apply_image_smoothing(doc.frame.raw.copy(),mask,'gaussian',{'sigma':1})
    window._refresh();window.mode.setCurrentText('Edit');before=doc.state()
    def choose(self):self.angle.setValue(45);self.fill.setCurrentIndex(3);return QDialog.DialogCode.Accepted
    monkeypatch.setattr(RotationDialog,'exec',choose);window.rotate_image_dialog()
    assert not window.busy and doc.state()==before and window.errors[-1][0]=='Background group'


def test_angle_and_shape_ratio_plots_use_selected_calibration_coordinates(document,qtbot,monkeypatch):
    import matplotlib.axes
    document.objects=[];mask=np.zeros(document.frame.shape,np.uint8);cv2.ellipse(mask,(75,60),(32,7),45,0,360,1,-1);document.add_object('mask',mask=mask.astype(bool))
    captured=[];original=matplotlib.axes.Axes.hist
    def hist(self,values,*a,**k):captured.append(list(values));return original(self,values,*a,**k)
    monkeypatch.setattr(matplotlib.axes.Axes,'hist',hist)
    dialog=StatisticsDialog([document],document);qtbot.addWidget(dialog)
    for key in ('orientation','aspect_ratio','circularity'):
        dialog.metric_combo.setCurrentIndex(dialog.metric_combo.findData(key));physical=captured[-1][0]
        row=dialog.records[0];assert physical==pytest.approx(row[key+'_physical'])
        dialog.unit.setCurrentText('Pixels');assert captured[-1][0]==pytest.approx(dialog.records[0][key+'_px'])
        dialog.unit.setCurrentText('Auto')
    assert abs(dialog.records[0]['orientation_px']-dialog.records[0]['orientation_physical'])>5
