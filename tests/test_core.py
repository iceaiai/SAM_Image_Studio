import copy
import json
import math
from pathlib import Path
import numpy as np
import pytest
from scipy import ndimage as ndi
from samstudio.domain import Calibration,Document,Group,History,ImageFrame,ProjectStore,pack_array,unpack_array,pack_mask,unpack_mask
from samstudio.processing import (shape_mask,fill_holes,smooth_mask,refine_objects,filter_proposals,
    display_rgb,neighbor_fill,patch_fill,measurements,mask_contours,raster_contours)

@pytest.mark.parametrize("shape",[(1,1),(5,11),(256,129)])
def test_mask_codec_exact_holes_and_padding(shape):
    rng=np.random.default_rng(4);m=rng.random(shape)>.4
    assert np.array_equal(m,unpack_mask(pack_mask(m),shape))

@pytest.mark.parametrize("dtype",[np.uint8,np.uint16,np.float32,np.float64,np.complex64])
def test_array_codec_preserves_data_type(dtype):
    a=np.arange(63).reshape(7,9).astype(dtype)
    assert np.array_equal(a,unpack_array(pack_array(a)))
    assert unpack_array(pack_array(a)).dtype==a.dtype

def test_bad_saved_arrays_are_rejected():
    value=pack_array(np.zeros((3,3),np.uint16));value["shape"]=[2,2]
    with pytest.raises(ValueError):unpack_array(value)
    with pytest.raises(ValueError):unpack_array({"dtype":"O","shape":[1],"data":""})

def test_calibration_anisotropic_and_unit_conversion():
    cal=Calibration(.2,.3,"nm","file",True)
    assert cal.area(2500)==pytest.approx(150)
    assert cal.area(2500,"µm")==pytest.approx(.00015)
    assert not Calibration(0,.3,"nm","bad",True).valid
    assert not Calibration(1,1,"pixels","bad",True).valid
    assert not Calibration(float('nan'),1,"nm","bad",True).valid

def test_autosave_recovery_backup_and_image_identity(document,tmp_path):
    store=ProjectStore(tmp_path/"annotations");store.save(document)
    document.objects[0].name="Revised";document.revision+=1;store.save(document)
    restored=Document(document.frame);assert store.load(restored)[0]
    assert restored.objects[0].name=="Revised"
    assert np.array_equal(restored.objects[0].mask,document.objects[0].mask)
    store.path(document).write_text('{broken')
    recovered=Document(document.frame);assert 'backup' in store.load(recovered)[1]
    wrong=Document(ImageFrame(document.frame.source_path,np.zeros(document.frame.shape,np.uint16)))
    with pytest.raises(ValueError):wrong.restore(document.state())

def test_history_batch_undo_redo_keeps_group_and_pixel_masks(document,tmp_path):
    store=ProjectStore(tmp_path);history=History(document,lambda:store.save(document))
    original=document.objects[0].mask.copy();ident=document.objects[0].id
    history.apply("fill",lambda:setattr(document.objects[0],"mask",fill_holes(original)))
    assert document.objects[0].pixel_area>original.sum()
    assert history.undo();assert np.array_equal(document.objects[0].mask,original)
    assert document.objects[0].id==ident
    assert history.redo();assert document.objects[0].pixel_area>original.sum()
    restored=Document(document.frame);store.load(restored)
    assert np.array_equal(restored.objects[0].mask,document.objects[0].mask)

def test_failed_edit_rolls_back_atomically(document):
    history=History(document);previous=document.state()
    def mutation():
        document.objects.clear();raise ValueError('bad edit')
    with pytest.raises(ValueError):history.apply("bad",mutation)
    assert document.state()==previous

@pytest.mark.parametrize("kind,points",[("rectangle",[[3,4],[13,14]]),("polygon",[[2,3],[20,3],[20,20],[3,18]]),("circle",[[5,5],[25,25]]),("ellipse",[[2,2],[35,20]])])
def test_shape_area_and_source_bounds(kind,points):
    mask=shape_mask(kind,points,(40,40));assert mask.shape==(40,40);assert mask.any()
    assert not mask[39].any()
    if kind=='rectangle':assert mask.sum()==100

def test_invalid_geometry_rejected():
    with pytest.raises(ValueError):shape_mask('polygon',[[1,2],[3,4]],(10,10))
    with pytest.raises(ValueError):shape_mask('rectangle',[[1,1],[1,4]],(10,10))
    with pytest.raises(ValueError):shape_mask('polygon',[[1,2],[3,4],[float('nan'),1]],(10,10))

def test_roi_and_existing_annotations_are_never_overwritten():
    protected=np.zeros((40,50),bool);protected[8:20,8:20]=True
    roi=np.zeros_like(protected);roi[5:30,5:35]=True
    candidates=[np.ones_like(protected),protected.copy(),np.ones_like(protected)]
    original=protected.copy();output=filter_proposals(candidates,protected,roi,min_area=1)
    assert len(output)==1
    assert not (output[0]&protected).any()
    assert not (output[0]&~roi).any()
    assert np.array_equal(protected,original)

def test_fill_holes_threshold_and_other_objects(document):
    mask=document.objects[0].mask;before=int(mask.sum())
    assert fill_holes(mask,50).sum()==before
    assert fill_holes(mask,100).sum()==before+100
    protected=np.zeros_like(mask);protected[23:26,23:26]=True
    output=fill_holes(mask,protected=protected)
    assert not (output&protected).any()

def test_smoothing_changes_boundary_not_source_or_identity(document):
    raw=document.frame.raw.copy();obj=document.objects[0]
    result=refine_objects(document,[obj.id],"smooth",1.)
    assert not np.array_equal(result[obj.id],obj.mask)
    assert np.array_equal(document.frame.raw,raw)
    assert not result[obj.id][20:30,20:30].any()
    obj.locked=True
    with pytest.raises(ValueError):refine_objects(document,[obj.id],"holes")

def test_multiple_refinements_keep_distinct_objects(document):
    second=np.zeros(document.frame.shape,bool);second[70:110,70:110]=True;second[80:85,80:85]=False
    obj=document.add_object("mask",mask=second)
    ids=[o.id for o in document.objects];results=refine_objects(document,ids,"holes")
    assert set(results)==set(ids)
    assert not (results[ids[0]]&results[ids[1]]).any()
    assert sum(int(m.sum()) for m in results.values())==45*45+40*40

@pytest.mark.parametrize("dtype",[np.uint8,np.uint16,np.float32])
def test_neighbor_fill_and_patch_preserve_unmodified_pixels(dtype):
    raw=np.arange(50*60).reshape(50,60).astype(dtype);target=np.zeros((50,60),bool);target[10:20,15:30]=True
    for result in (neighbor_fill(raw,target),patch_fill(raw,target,[[0,0,8,8],[40,30,52,44]])):
        assert result.dtype==raw.dtype
        assert np.array_equal(result[~target],raw[~target])
    with pytest.raises(ValueError):neighbor_fill(raw,np.ones(raw.shape,bool))
    with pytest.raises(ValueError):patch_fill(raw,target,[[15,10,25,15]])

def test_display_changes_are_separate_from_source(document):
    raw=document.frame.raw.copy();a=display_rgb(raw);b=display_rgb(raw,.2,1.5)
    assert a.dtype==np.uint8 and a.shape==(*raw.shape,3)
    assert not np.array_equal(a,b);assert np.array_equal(raw,document.frame.raw)
    assert np.isfinite(display_rgb(np.full((3,4),np.nan))).all()

def test_measurements_recalculate_and_exclude_points(document):
    document.add_object('point',[[1.,2.]])
    rows,excluded=measurements(document);assert len(rows)==1 and excluded==1
    before=rows[0]['physical_area'];document.objects[0].mask=fill_holes(document.objects[0].mask)
    after=measurements(document)[0][0]['physical_area'];assert after>before
    document.calibration=Calibration()
    rows,_=measurements(document);assert rows[0]['physical_area'] is None
    assert rows[0]['pixel_value']==document.objects[0].pixel_area

