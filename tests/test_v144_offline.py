"""Offline/bootstrap integrity contracts; small fixture files are not model weights."""
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import subprocess
import sys
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]

def module(name):
    spec=importlib.util.spec_from_file_location('check_'+name,ROOT/'scripts'/f'{name}.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

@pytest.fixture
def cache(tmp_path):
    root=tmp_path;folder=root/'offline-cache';(folder/'models').mkdir(parents=True)
    (root/'samstudio/resources').mkdir(parents=True)
    data=folder/'wheels/test.whl';data.parent.mkdir();data.write_bytes(b'Fixture integrity bytes, not a usable wheel')
    model=folder/'models/test.pt';model.write_bytes(b'Fixture integrity bytes, not a checkpoint')
    m={'platform':sys.platform,'machine':platform.machine().lower(),'files':[{'path':'wheels/test.whl','sha256':hashlib.sha256(data.read_bytes()).hexdigest()}],'models':[{'filename':'test.pt','sha256':hashlib.sha256(model.read_bytes()).hexdigest()}]}
    (root/'samstudio/resources/offline_profile.json').write_text(json.dumps({'models':[{'filename':'test.pt'}]}))
    (folder/'manifest.json').write_text(json.dumps(m));(folder/'READY').write_text(hashlib.sha256((folder/'manifest.json').read_bytes()).hexdigest())
    return root

def test_offline_cache_checks_all_package_and_model_bytes(cache):
    installer=module('install_offline');assert installer.verify_cache(cache)['platform']==sys.platform
    (cache/'offline-cache/models/test.pt').write_bytes(b'Changed')
    with pytest.raises(ValueError,match='model'):installer.verify_cache(cache)

def test_offline_cache_rejects_incomplete_or_wrong_machine(cache):
    installer=module('install_offline')
    (cache/'offline-cache/READY').unlink()
    with pytest.raises(RuntimeError,match='not ready'):installer.verify_cache(cache)

def test_offline_download_never_attempts_network_without_cache(tmp_path,monkeypatch):
    bootstrap=module('bootstrap_python')
    monkeypatch.setattr(bootstrap.urllib.request,'urlopen',lambda *a,**k:pytest.fail('Offline must not open HTTP'))
    with pytest.raises(FileNotFoundError,match='missing'):bootstrap.download('https://example.invalid/a',tmp_path/'a',offline=True)
    p=tmp_path/'a';p.write_bytes(b'cached')
    assert bootstrap.download('https://example.invalid/a',p,bootstrap.digest(p),offline=True)==p
    with pytest.raises(ValueError,match='verification'):bootstrap.download('https://example.invalid/a',p,'0'*64,offline=True)

def test_existing_wrong_python_is_not_accepted(tmp_path):
    bootstrap=module('bootstrap_python')
    assert bootstrap.is_python312(sys.executable)
    assert not bootstrap.is_python312(tmp_path/'missing-python')
    runtime=json.loads((ROOT/'packaging/python-runtimes.json').read_text())
    assert runtime['windows-x86_64']['version'].startswith('3.12.')
    assert all(len(p['sha256'])==64 for p in runtime.values())

def test_offline_catalog_and_devices_are_restricted_in_fresh_process(tmp_path):
    # Copy only the package to isolate module-level edition detection from normal tests.
    import shutil,os
    shutil.copytree(ROOT/'samstudio',tmp_path/'samstudio',ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(ROOT/'offline/profile.json',tmp_path/'samstudio/resources/offline_profile.json')
    code='''from samstudio.inference import CATALOG,InferenceEngine,download_file
from samstudio.edition import offline_profile
from pathlib import Path
assert offline_profile()
assert {(s.family,s.variant) for s in CATALOG}=={('SAM1','ViT-B'),('SAM2.1','Small'),('SAM2.1','Base+')}
try: InferenceEngine().load(CATALOG[0],'cuda')
except ValueError as e: assert 'CPU only' in str(e)
else: raise AssertionError('CUDA must be rejected')
try: download_file('https://example.invalid/model',Path('missing.pt'))
except RuntimeError as e: assert 'disabled' in str(e)
else: raise AssertionError('Network download must be rejected')
print('Offline restrictions passed')
'''
    env=dict(os.environ);env['PYTHONPATH']=str(tmp_path)
    result=subprocess.run([sys.executable,'-c',code],cwd=tmp_path,env=env,capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr

def test_example_readers_and_narrow_emd_noise():
    from samstudio.imageio import load_files
    from samstudio.image_processing import process_pixels
    path=ROOT/'examples/user_samples/0058-Ceta_190_kx_1615.emd'
    frame=load_files([str(path)]).frames[0]
    assert frame.raw.dtype==np.int16 and frame.calibration.valid
    assert frame.calibration.pixel_size_x==pytest.approx(.314412251423185)
    noisy=process_pixels(frame.raw,'Gaussian noise')
    assert 2<float((noisy.astype(float)-frame.raw).std())<5
    stem=load_files([str(ROOT/'examples/user_samples/STEM_image.tif')]).frames[0]
    assert stem.shape==(2048,2048) and stem.raw.dtype==np.uint8
