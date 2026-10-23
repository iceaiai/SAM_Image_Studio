import os
from pathlib import Path
import pytest
from samstudio.imageio import load_file

pytestmark=pytest.mark.microscopy
ROOT=Path(os.environ.get("SAM_STUDIO_TEST_FIXTURES","not_provided"))


@pytest.mark.parametrize("filename,count,shape,unit",[
    ("test_STEM_image.dm3",1,(68,68),"nm"),
    ("test-2.dm4",1,(2,2),None),
    ("multi_signal.dm3",1,(512,512),"nm"),
    ("example_image.emd",1,(3,3),None),
    ("fei_example_tem_stack.emd",2,(3,3),"pm"),
])
def test_real_microscopy_files(filename,count,shape,unit):
    path=ROOT/filename
    if not path.is_file():pytest.skip("Provide RosettaSciIO public reader fixtures.")
    frames=load_file(path)
    assert len(frames)==count and len({f.key for f in frames})==count
    for frame in frames:
        assert frame.shape==shape
        assert frame.calibration.valid==(unit is not None)
        if unit:
            assert frame.calibration.length_unit==unit
            assert frame.calibration.pixel_size_x>0 and frame.calibration.pixel_size_y>0
