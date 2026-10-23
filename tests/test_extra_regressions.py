import json
from pathlib import Path
import numpy as np
import pytest
import tifffile
from samstudio.exports import label_map, save_masks, save_cleaned
from samstudio.exports import render_mask_pixels
from samstudio.processing import display_rgb
from samstudio.imageio import load_file


def test_per_object_numeric_ids_match_shared_mapping_even_with_points(document,tmp_path):
    document.add_object("point",[[5,5]])
    m=np.zeros(document.frame.shape,bool);m[70:90,70:90]=True
    obj=document.add_object("mask",mask=m)
    paths=save_masks(document,tmp_path,"tif","object","instance")
    mapping=json.loads(next(tmp_path.glob("*_mapping.json")).read_text())
    assert mapping["objects"][-1]["instance_id"]==3
    last=next(p for p in paths if obj.id[:8] in p)
    assert set(np.unique(tifffile.imread(last)))=={0,3}


def test_cleaned_output_cannot_overwrite_source(document):
    document.working=document.frame.raw.copy()
    with pytest.raises(ValueError,match="original"):save_cleaned(document,document.frame.source_path)


def test_binary_overlay_preserves_background_and_blends_only_masks(document):
    mask=document.objects[0].mask;base=display_rgb(document.frame.raw)
    output=render_mask_pixels(document,document.objects,"binary",True,50,False)
    assert np.array_equal(output[~mask,:3],base[~mask])
    assert np.array_equal(output[mask,:3],np.rint(base[mask]*.5+127.5).astype(np.uint8))
    assert np.all(output[...,3]==255)


def test_reusing_a_renamed_group_name_does_not_duplicate_ids(document):
    old=document.groups[0];old_name=old.name;old.name="Renamed"
    new=document.ensure_group(old_name)
    assert new.id!=old.id and len({g.id for g in document.groups})==2
    document.restore(document.state())


def test_embedding_cache_distinguishes_image_dimensions():
    from samstudio.inference import InferenceEngine
    class Predictor:
        count=0
        def set_image(self,rgb):self.count+=1
    engine=InferenceEngine();engine.predictor=Predictor()
    engine._set_image(np.zeros((3,4,3),np.uint8));engine._set_image(np.zeros((4,3,3),np.uint8))
    assert engine.predictor.count==2


@pytest.mark.parametrize("compression",["lzw","zstd","deflate"])
def test_compressed_scientific_tiff_roundtrip(tmp_path,compression):
    path=tmp_path/f"compressed_{compression}.tif"
    raw=np.arange(80*90,dtype=np.uint16).reshape(80,90)
    tifffile.imwrite(path,raw,compression=compression)
    frames=load_file(path)
    assert len(frames)==1 and np.array_equal(frames[0].raw,raw)
