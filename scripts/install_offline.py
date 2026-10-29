"""Install the prepared CPU-only edition without package indexes or model downloads."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import venv

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from bootstrap_python import ensure_python,digest


def verify_cache(root=ROOT):
    root=Path(root);cache=root/'offline-cache';manifest_path=cache/'manifest.json'
    if not (cache/'READY').is_file() or not manifest_path.is_file():raise RuntimeError('Offline cache is not ready. Run Prepare Offline on an online computer first, then transfer the whole folder.')
    if (cache/'READY').read_text().strip()!=digest(manifest_path):raise ValueError('Offline preparation manifest failed verification.')
    m=json.loads(manifest_path.read_text())
    if m['platform']!=sys.platform or m['machine']!=platform.machine().lower():raise ValueError('Prepared OS/architecture does not match this computer. Prepare on a matching computer.')
    for item in m['files']:
        path=cache/item['path']
        if cache.resolve() not in path.resolve().parents:raise ValueError('Invalid offline manifest path.')
        if not path.is_file() or digest(path)!=item['sha256']:raise ValueError('Missing/corrupt offline file: '+item['path'])
    profile=json.loads((root/'samstudio/resources/offline_profile.json').read_text())
    if {i['filename'] for i in m['models']}!={i['filename'] for i in profile['models']}:raise ValueError('The prepared cache does not contain the complete offline model set.')
    for item in m['models']:
        path=cache/'models'/item['filename']
        if (cache/'models').resolve() not in path.resolve().parents:raise ValueError('Invalid offline model path.')
        if not path.is_file() or digest(path)!=item['sha256']:raise ValueError('Missing/corrupt offline model: '+item['filename'])
    return m


def install_system(m):
    if not sys.platform.startswith('linux'):return
    spec=importlib.util.spec_from_file_location('qtdeps',ROOT/'scripts/install_linux_dependencies.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    if not module.missing_packages():return
    local=platform.freedesktop_os_release()
    if not m.get('system_packages_included') or any(local.get(k)!=v for k,v in m['linux_distribution'].items()):raise RuntimeError('Missing Qt libraries and no matching distribution package cache. Prepare on the same Linux distribution, including system packages.')
    prefix=[] if os.geteuid()==0 else ['sudo']
    packages=sorted((ROOT/'offline-cache/system').glob('*.deb'))
    subprocess.run([*prefix,'apt-get','--no-download','--yes','install',*map(str,packages)],check=True)
    if module.missing_packages():raise RuntimeError('Qt libraries still cannot load. Ask the system administrator to inspect the cached package installation.')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--verify-only',action='store_true');a=p.parse_args()
    if not (ROOT/'samstudio/resources/offline_profile.json').is_file():raise RuntimeError('This is not the offline CPU source edition.')
    m=verify_cache()
    if a.verify_only:print('All prepared runtime/package/model checksums verified.');return 0
    if sys.version_info[:2]!=(3,12):
        py=ensure_python(ROOT,offline=True);return subprocess.call([str(py),str(Path(__file__))],cwd=ROOT)
    install_system(m)
    directory=ROOT/'.venv-offline';marker=directory/'.samstudio-owned'
    if directory.exists() and not marker.is_file():raise RuntimeError('Preserve/rename the unowned .venv-offline folder first.')
    directory.mkdir(exist_ok=True);marker.write_text('SAM Image Studio offline CPU environment\n')
    venv.EnvBuilder(with_pip=True,clear=False).create(directory)
    py=directory/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    env=dict(os.environ);env.update(PIP_NO_INDEX='1',PIP_DISABLE_PIP_VERSION_CHECK='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',SAM_STUDIO_OFFLINE_ROOT=str(ROOT))
    commands=[
        [py,'-m','pip','install','--no-index','--no-deps','--require-hashes','-r',ROOT/'offline-cache/requirements-hashed.txt'],
        [py,'-m','pip','check'],
        [py,'-m','samstudio.selftest','--device','cpu'],
    ]
    for command in commands:subprocess.run(list(map(str,command)),cwd=ROOT,env=env,check=True)
    print('Offline CPU installation verified. Use the normal Start_GUI helper. Model manager reads only the prepared SAM1/SAM2 models.')
    return 0
if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,RuntimeError,subprocess.CalledProcessError) as error:
        print('Offline installation stopped: '+str(error),file=sys.stderr);raise SystemExit(1)
