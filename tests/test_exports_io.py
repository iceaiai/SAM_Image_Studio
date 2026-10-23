import json
import struct
from pathlib import Path
import numpy as np
import pytest
import tifffile
from PIL import Image
from samstudio.domain import Calibration,Document,ImageFrame
from samstudio.exports import (coco_rle,decode_coco_rle,export_coco,export_yolo,save_masks,save_cleaned,write_measurement_csv)
from samstudio.imageio import load_file,load_files,calibration_from_axes
from samstudio.processing import measurements

def test_coco_decodes_in_official_api_and_preserves_holes(document,tmp_path):
    from pycocotools.coco import COCO
    result=export_coco([document],tmp_path)
    coco=COCO(result['path']);ann=next(iter(coco.anns.values()))
    mask=coco.annToMask(ann).astype(bool)
    assert np.array_equal(mask,document.objects[0].mask)
    assert ann['area']==document.objects[0].pixel_area
    assert ann['physical_measurements']['area']==pytest.approx(ann['area']*.06)
    assert coco.imgs[1]['microscopy_calibration']['pixel_size_x']==.2
    assert (tmp_path/coco.imgs[1]['file_name']).exists()

@pytest.mark.parametrize("shape",[(1,1),(13,14),(128,160)])
def test_coco_rle_edge_cases(shape):
    for m in (np.zeros(shape,bool),np.ones(shape,bool),np.random.default_rng(3).random(shape)>.4):assert np.array_equal(m,decode_coco_rle(coco_rle(m)))

def test_yolo_rejects_lossy_holes_and_exports_explicit_conversion(document,tmp_path):
    with pytest.raises(ValueError,match='holes'):export_yolo([document],tmp_path/'strict')
    assert not (tmp_path/'strict').exists()
    result=export_yolo([document],tmp_path/'lossy',True)
    assert result['lossy_objects']
    line=next((tmp_path/'lossy/labels').glob('*.txt')).read_text().split()
    assert int(line[0])==0
    assert all(0<=float(v)<=1 for v in line[1:])

@pytest.mark.parametrize('format',['bmp','png','tif'])
@pytest.mark.parametrize('organization',['combined','object','group'])
@pytest.mark.parametrize('color',['binary','object_color','group_color'])
def test_rendered_mask_save_matrix(document,tmp_path,format,organization,color):
    paths=save_masks(document,tmp_path,format,organization,color)
    assert len(paths)==1
    with Image.open(paths[0]) as image:
        assert image.size==(160,128)
        if format=='bmp':
            assert image.mode=='RGB'
            assert struct.unpack('<H',Path(paths[0]).read_bytes()[28:30])[0]==24

def test_transparency_and_numeric_labels(document,tmp_path):
    paths=save_masks(document,tmp_path/'rgba','png',transparency=75,transparent=True)
    pixels=np.asarray(Image.open(paths[0]));mask=document.objects[0].mask
    assert set(np.unique(pixels[...,3]))=={0,64}
    assert np.all(pixels[~mask,3]==0)
    for fmt in ['png','tif']:
        paths=save_masks(document,tmp_path/fmt,fmt,color_mode='instance')
        result=np.asarray(Image.open(paths[0]));assert set(np.unique(result))=={0,1}
        assert np.array_equal(result>0,mask)
    with pytest.raises(ValueError):save_masks(document,tmp_path,'bmp',transparent=True)
    with pytest.raises(ValueError):save_masks(document,tmp_path,'bmp',color_mode='instance')

def test_float_and_16bit_source_not_modified_by_save(document,tmp_path):
    before=document.frame.raw.copy();save_masks(document,tmp_path,'bmp',overlay=True)
    assert np.array_equal(before,document.frame.raw)

def test_ome_tiff_stack_calibration_and_data_type(tmp_path):
    raw=np.arange(3*20*30,dtype=np.uint16).reshape(3,20,30)
    path=tmp_path/'stack.ome.tif'
    tifffile.imwrite(path,raw,ome=True,metadata={'axes':'ZYX','PhysicalSizeX':.2,'PhysicalSizeXUnit':'nm','PhysicalSizeY':.3,'PhysicalSizeYUnit':'nm'},photometric='minisblack')
    frames=load_file(path);assert len(frames)==3
    for i,frame in enumerate(frames):
        assert frame.raw.dtype==np.uint16 and np.array_equal(frame.raw,raw[i])
        assert frame.calibration.valid
        assert frame.calibration.area(2500)==pytest.approx(150)
    assert len({f.key for f in frames})==3

def test_arbitrary_tiff_dpi_is_not_microscope_calibration(tmp_path):
    path=tmp_path/'photo.tif';tifffile.imwrite(path,np.zeros((20,30),np.uint8),resolution=(96,96),resolutionunit='INCH')
    assert not load_file(path)[0].calibration.valid

def test_imagej_and_raw_rgb_open(tmp_path):
    path=tmp_path/'imagej.tif';raw=np.zeros((20,30),np.uint16)
    tifffile.imwrite(path,raw,imagej=True,resolution=(5,4),metadata={'unit':'nm'})
    cal=load_file(path)[0].calibration;assert cal.valid and cal.pixel_size_x==pytest.approx(.2) and cal.pixel_size_y==pytest.approx(.25)
    for ext in ['png','jpg','bmp','webp']:
        p=tmp_path/('color.'+ext);Image.fromarray(np.zeros((30,40,3),np.uint8)).save(p)
        assert load_file(p)[0].raw.shape==(30,40,3)

def test_multi_file_errors_do_not_discard_valid_images(tmp_path):
    image=tmp_path/'ok.png';Image.fromarray(np.zeros((10,12),np.uint8)).save(image)
    broken=tmp_path/'broken.png';broken.write_bytes(b'not an image')
    result=load_files([image,broken]);assert len(result.frames)==1 and len(result.warnings)==1

def test_cleaned_tiff_preserves_dtype_calibration_and_footprint(document,tmp_path):
    document.working=document.frame.raw.copy();document.working[3:8,3:8]=17;document.modified[3:8,3:8]=True
    path=save_cleaned(document,tmp_path/'cleaned.tif');assert np.array_equal(tifffile.imread(path),document.working)
    frame=load_file(path)[0];assert frame.calibration.valid and frame.calibration.pixel_size_x==.2
    history=json.loads(path.with_suffix('.tif.cleaning.json').read_text());assert np.array_equal(decode_coco_rle(history['modified_region']),document.modified)

def test_csv_contains_units_and_object_ids(document,tmp_path):
    rows,_=measurements(document);path=tmp_path/'stats.csv';write_measurement_csv(rows,path)
    text=path.read_text('utf-8-sig');assert 'physical_area' in text and document.objects[0].id in text

