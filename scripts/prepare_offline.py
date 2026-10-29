"""Prepare the CPU offline bundle on an ONLINE computer with the same OS/architecture."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import venv

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from bootstrap_python import ensure_python,runtime_archive,download,digest


def run(command,cwd=ROOT):
    print('Running: '+' '.join(map(str,command)),flush=True)
    subprocess.run(list(map(str,command)),cwd=cwd,check=True)


def linux_packages(cache):
    if not sys.platform.startswith('linux'):return []
    spec=importlib.util.spec_from_file_location('qtdeps',ROOT/'scripts/install_linux_dependencies.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    packages=sorted(set(module.LIBRARIES.values())|{'fonts-dejavu-core'})
    if not shutil.which('apt-cache'):raise RuntimeError('Offline Linux system-library preparation currently supports Debian/Ubuntu apt. Prepare on the target distribution.')
    lists=cache/'apt-lists';(lists/'partial').mkdir(parents=True,exist_ok=True)
    apt_options=['-o','Dir::State::Lists='+str(lists),'-o','APT::Update::Error-Mode=any','-o','Acquire::Retries=0']
    run(['apt-get',*apt_options,'update'])
    destination=cache/'system';(destination/'partial').mkdir(parents=True,exist_ok=True)
    # Resolve for a clean target status so installed libraries on the online
    # machine are still included. Download-only never modifies host packages.
    status=cache/'empty-dpkg-status';status.write_text('')
    run(['apt-get',*apt_options,'-o','Debug::NoLocking=1','-o','Dir::State::status='+str(status),
         '-o','Dir::Cache::archives='+str(destination),'--download-only','--reinstall','--yes',
         '--no-install-recommends','install',*packages])
    return sorted(destination.glob('*.deb'))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--skip-system-packages',action='store_true',help='Advanced: target must already have all Qt system libraries.')
    args=p.parse_args()
    if not (ROOT/'samstudio/resources/offline_profile.json').is_file():raise RuntimeError('Download the offline CPU edition first. Its profile marker is required.')
    if sys.version_info[:2]!=(3,12):
        py=ensure_python(ROOT);return subprocess.call([str(py),str(Path(__file__)),*sys.argv[1:]],cwd=ROOT)
    cache=ROOT/'offline-cache';cache.mkdir(exist_ok=True)
    os.environ['PIP_NO_CACHE_DIR']='1';os.environ['PIP_DISABLE_PIP_VERSION_CHECK']='1'
    previous_models={}
    if (cache/"manifest.json").is_file():
        previous_models={m["filename"]:m["sha256"] for m in json.loads((cache/"manifest.json").read_text()).get("models",[])}
    # Never let an interrupted preparation leave a previous READY marker usable.
    (cache/'READY').unlink(missing_ok=True)
    runtime,spec=runtime_archive(ROOT)
    wheels=cache/'wheels';wheels.mkdir(exist_ok=True)
    prep=ROOT/'.offline-prep-env';marker=prep/'.samstudio-owned'
    if prep.exists() and not marker.is_file():raise RuntimeError('Preserve/rename the unowned .offline-prep-env folder first.')
    prep.mkdir(exist_ok=True);marker.write_text('Temporary app-owned offline preparation environment\n')
    venv.EnvBuilder(with_pip=True,clear=False).create(prep)
    py=prep/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    run([py,'-m','pip','install','pip==25.2','setuptools==80.9.0','wheel==0.45.1'])
    constraints=cache/'cpu-constraints.txt';constraints.write_text('torch==2.7.1+cpu\ntorchvision==0.22.1+cpu\n')
    for wheel in (ROOT/'vendor').glob('*.whl'):shutil.copy2(wheel,wheels/wheel.name)
    run([py,'-m','pip','download','--only-binary=:all:','--dest',wheels,'torch==2.7.1+cpu','torchvision==0.22.1+cpu','--index-url','https://download.pytorch.org/whl/cpu'])
    run([py,'-m','pip','download','--only-binary=:all:','--dest',wheels,'--find-links',wheels,'--constraint',constraints,'-r',ROOT/'packaging/requirements/cpu.lock.txt','pip==25.2','setuptools==80.9.0','wheel==0.45.1'])
    with tempfile.TemporaryDirectory(prefix='.offline-build-',dir=ROOT) as stage:
        stage=Path(stage);shutil.copytree(ROOT/'samstudio',stage/'samstudio',ignore=shutil.ignore_patterns('__pycache__'))
        for name in ['pyproject.toml','LICENSE']:shutil.copy2(ROOT/name,stage/name)
        run([py,'-m','pip','wheel','--no-deps','--no-build-isolation','--wheel-dir',wheels,stage])
    # Resolve once from local wheels so repeated preparation never installs two
    # cached versions of the same dependency into the offline environment.
    import tomllib
    version=tomllib.loads((ROOT/'pyproject.toml').read_text())['project']['version']
    report=cache/'resolved-packages.json'
    run([py,'-m','pip','install','--dry-run','--ignore-installed','--no-index','--find-links',wheels,'--constraint',constraints,'--report',report,'-r',ROOT/'packaging/requirements/cpu.lock.txt','sam-image-studio=='+version,'SAM-2==1.0','pip==25.2','setuptools==80.9.0','wheel==0.45.1'])
    from urllib.parse import urlsplit,unquote
    selected=[]
    for item in json.loads(report.read_text())['install']:
        name=Path(unquote(urlsplit(item['download_info']['url']).path)).name
        path=wheels/name
        if not path.is_file():raise RuntimeError('Resolved wheel missing: '+name)
        selected.append(path)
    report.write_text(json.dumps({'wheels':[{'filename':f.name,'sha256':digest(f)} for f in selected]},indent=2)+'\n')
    profile=json.loads((ROOT/'samstudio/resources/offline_profile.json').read_text());models=[]
    for model in profile['models']:
        path=download(model['url'],cache/'models'/model['filename'],model.get('sha256') or previous_models.get(model['filename']))
        if path.stat().st_size<1024*1024:raise ValueError('Downloaded checkpoint is unexpectedly small: '+path.name)
        models.append({'family':model['family'],'variant':model['variant'],'filename':path.name,'sha256':digest(path)})
    system=[] if args.skip_system_packages else linux_packages(cache)
    files=[runtime,*selected,*system]
    records=[{'path':str(f.relative_to(cache)).replace('\\','/'),'sha256':digest(f),'bytes':f.stat().st_size} for f in files]
    requirements=[]
    for f in sorted(selected):
        requirements.append('offline-cache/wheels/'+f.name+' --hash=sha256:'+digest(f))
    (cache/'requirements-hashed.txt').write_text('\n'.join(requirements)+'\n')
    records.append({'path':'requirements-hashed.txt','sha256':digest(cache/'requirements-hashed.txt'),'bytes':(cache/'requirements-hashed.txt').stat().st_size})
    os_release=platform.freedesktop_os_release() if sys.platform.startswith('linux') else {}
    manifest={'schema':1,'python':'3.12','platform':sys.platform,'machine':platform.machine().lower(),'linux_distribution':{k:os_release[k] for k in ['ID','VERSION_ID'] if k in os_release},'models':models,'files':records,'system_packages_included':bool(system)}
    (cache/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (cache/'READY').write_text(digest(cache/'manifest.json')+'\n')
    shutil.rmtree(prep)
    print('Offline preparation complete. Copy the ENTIRE source folder, including offline-cache, to a computer with the same OS/architecture. Then use the normal CPU installer. No existing virtual environment needs to be copied.',flush=True)
    return 0
if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,RuntimeError,subprocess.CalledProcessError) as error:
        print('Offline preparation stopped: '+str(error)+'\nCompleted cached files are retained. Fix the reported network/package problem and rerun the same preparation helper.',file=sys.stderr);raise SystemExit(1)
