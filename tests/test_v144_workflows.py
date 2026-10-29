"""User-observed microscopy noise, input-state, rotation and selection regressions."""
import copy
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog,QMessageBox,QPushButton
from samstudio.image_processing import process_pixels
from samstudio.classical_segmentation import watershed_masks
from samstudio.transforms import rotate_document,reset_rotation
from samstudio.domain import Document,ImageFrame

@pytest.mark.parametrize('method,zero',[('Gaussian noise',{'sigma':0}),('Poisson noise',{'strength':0})])
def test_noise_zero_is_exact_for_narrow_signed_signal(method,zero):
    image=np.arange(900,dtype=np.int16).reshape(30,30)%130-9
    assert np.array_equal(process_pixels(image,method,zero),image)

@pytest.mark.parametrize('method',['Gaussian noise','Poisson noise'])
def test_narrow_int16_noise_is_added_in_observed_signal_units(method):
    image=np.full((180,220),60,np.int16);image[:,110:]=110
    result=process_pixels(image,method,{'seed':7})
    residual=result.astype(float)-image
    assert result.dtype==image.dtype
    assert .2<float(residual.std())<5  # Old full-int16 scaling produced thousands of counts.
    assert abs(residual.mean())<.1
    assert np.corrcoef(image.ravel(),result.ravel())[0,1]>.98
    assert np.array_equal(result,process_pixels(image,method,{'seed':7}))

@pytest.mark.parametrize('method',['Gaussian noise','Poisson noise'])
def test_noise_keeps_target_outside_and_rgba_alpha(method):
    image=np.zeros((50,60,4),np.uint16);image[...,:3]=np.linspace(20,120,60,dtype=np.uint16)[None,:,None];image[...,3]=30000
    mask=np.zeros(image.shape[:2],bool);mask[5:45,5:55]=True
    result=process_pixels(image,method,{'seed':8},mask)
    assert np.array_equal(result[~mask],image[~mask]) and np.array_equal(result[...,3],image[...,3])
    assert not np.array_equal(result[mask,:3],image[mask,:3])

def test_gaussian_absolute_data_units_and_unclipped_float_noise():
    image=np.full((150,150),75.,np.float32)
    out=process_pixels(image,'Gaussian noise',{'scale':'data_units','sigma':2.,'seed':5})
    assert 1.9<float((out-image).std())<2.1 and out.dtype==np.float32

def particles(bright=True):
    y,x=np.mgrid[:140,:180];a=(x-64)**2+(y-70)**2<27**2;b=(x-108)**2+(y-70)**2<27**2
    image=np.where(a|b,220,20).astype(np.uint8)
    return image if bright else 255-image

@pytest.mark.parametrize('polarity',['bright','dark'])
def test_watershed_splits_touching_particles_and_preserves_source(polarity):
    raw=particles(polarity=='bright');before=raw.copy()
    masks,info=watershed_masks(raw,{'polarity':polarity,'gaussian_sigma':1.,'seed_distance':25,'minimum_area':100})
    assert len(masks)==2 and not (masks[0]&masks[1]).any()
    assert all(1500<m.sum()<2600 for m in masks)
    assert info['polarity']==polarity and np.array_equal(raw,before)

def test_watershed_roi_and_empty_contrast():
    image=particles();roi=np.zeros(image.shape,bool);roi[:,:85]=True
    masks,_=watershed_masks(image,{'polarity':'bright','minimum_area':20},roi)
    assert masks and all(not (m&~roi).any() for m in masks)
    masks,info=watershed_masks(np.zeros((40,50),np.uint16))
    assert masks==[] and 'contrast' in info['reason']

def mount(window,document):
    from test_v141_processing_workspace import mount as attach
    return attach(window,document)

def test_processed_input_defaults_per_image_and_toggle_keeps_pixels(window,document):
    doc=mount(window,document)
    doc.apply_image_smoothing(doc.frame.raw//2,np.ones(doc.frame.shape,bool),'test',{})
    before=doc.working.copy();window._refresh()
    assert not window.cleaned_checkbox.isChecked()
    window.cleaned_checkbox.setChecked(True);window.cleaned_checkbox.setChecked(False)
    assert np.array_equal(doc.working,before)
    other=Document(ImageFrame('other.tif',np.ones((20,30),np.uint8)))
    window.documents[other.frame.key]=other
    window.select_document(other.frame.key)
    assert not window.cleaned_checkbox.isChecked() and not window.canvas.use_cleaned

def test_toggle_invalidates_preview_only_when_input_pixels_change(window,document):
    doc=mount(window,document);doc.apply_image_smoothing(doc.frame.raw//2,np.ones(doc.frame.shape,bool),'test',{})
    window.canvas.set_preview([doc.objects[0].mask]);window._preview_context={'input':'original'}
    window.cleaned_checkbox.setChecked(True)
    assert not window.canvas.preview_masks and window._preview_context is None

def test_forget_processing_keeps_annotation_orientation_and_supports_undo(window,document,monkeypatch):
    doc=mount(window,document);original=doc.objects[0].mask.copy()
    window._commit('process',lambda:doc.apply_image_smoothing(doc.frame.raw//2,np.ones(doc.frame.shape,bool),'test',{}))
    edited=doc.working.copy();window.cleaned_checkbox.setChecked(True)
    monkeypatch.setattr(QMessageBox,'question',lambda *a,**k:QMessageBox.StandardButton.Yes)
    window.forget_processed_image()
    assert doc.working is None and not doc.modified.any() and not window.cleaned_checkbox.isChecked()
    assert len(doc.objects)==1 and np.array_equal(doc.objects[0].mask,original)
    window.undo();assert np.array_equal(doc.working,edited)

def test_exact_rotation_reset_recovers_cropped_pixels_shapes_and_project(document):
    doc=document;original=doc.frame.raw.copy();mask=doc.objects[0].mask.copy();cal=copy.deepcopy(doc.calibration)
    rotate_document(doc,37,'none');rotate_document(doc,91,'square')
    restored=Document(doc.frame);restored.source_raw=doc.source_raw;restored.restore(doc.state())
    reset_rotation(restored)
    assert not restored.rotation and restored.rotation_reset_state is None
    assert np.array_equal(restored.frame.raw,original) and np.array_equal(restored.objects[0].mask,mask)
    assert restored.calibration==cal

def test_rotation_reset_button_and_undo(window,document,monkeypatch):
    doc=mount(window,document);window._commit('rotate',lambda:rotate_document(doc,31,'rectangle'));rotated=doc.frame.raw.copy()
    monkeypatch.setattr(QMessageBox,'question',lambda *a,**k:QMessageBox.StandardButton.Yes)
    window.reset_image_rotation();assert not doc.rotation
    window.undo();assert np.array_equal(doc.frame.raw,rotated) and doc.rotation

def test_all_three_panel_selection_buttons(window,document):
    doc=mount(window,document);doc.ensure_group('Other');window._refresh()
    for prefix,tree in [('objects',window.objects_tree),('groups',window.groups_tree),('images',window.files_tree)]:
        select=window.findChild(QPushButton,prefix+'Selectall');clear=window.findChild(QPushButton,prefix+'Deselectall')
        assert select and clear
        select.click();assert tree.selectedItems()
        clear.click();assert not tree.selectedItems()

def test_watershed_gui_preview_accept_and_parameter_help(window,document,qtbot,monkeypatch):
    from samstudio.analysis_dialogs import ParameterPreviewDialog
    image=particles();doc=Document(ImageFrame(str(Path(document.frame.source_path).with_name('particles.tif')),image));doc.ensure_group('Particles')
    mount(window,doc)
    monkeypatch.setattr(ParameterPreviewDialog,'exec',lambda d:QDialog.DialogCode.Accepted)
    window.watershed_dialog();qtbot.waitUntil(lambda:not window.busy,timeout=15000)
    assert not window.errors and len(window.canvas.preview_masks)==2
    assert not window.document.objects
    window.accept_preview();assert len(window.document.objects)==2
    assert all(o.provenance['method']=='Otsu + watershed' for o in window.document.objects)

def test_lama_context_parameters_preserve_outside_target(monkeypatch,tmp_path):
    import torch
    from samstudio.inference import lama_fill
    class Native:
        def eval(self):return self
        def __call__(self,image,mask):return torch.ones_like(image)*.8
    monkeypatch.setattr(torch.jit,'load',lambda *a,**k:Native())
    image=np.full((50,70,3),40,np.uint8);target=np.zeros((50,70),bool);target[20:30,25:40]=True
    output=lama_fill(image,target,tmp_path/'contract.pt',mask_dilation=2,context_margin=8,max_side=24,blend_width=2)
    assert np.array_equal(output[~target],image[~target]) and np.all(output[target]>=40) and output[25,32,0]==204
