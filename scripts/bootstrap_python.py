"""Select Python 3.12 or prepare a verified project-local runtime. Standard library only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()

def download(url,path,sha256=None,offline=False):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_file():
        if not sha256 or digest(path)==sha256:return path
        raise ValueError('Cached file failed verification: '+path.name)
    if offline:raise FileNotFoundError('Offline cache is missing '+path.name+'. Run Prepare Offline while online first.')
    temp=path.with_name(path.name+'.part')
    print('Downloading '+path.name,flush=True)
    request=urllib.request.Request(url,headers={'User-Agent':'SAMImageStudio-installer'})
    with urllib.request.urlopen(request,timeout=60) as response,temp.open('wb') as out:shutil.copyfileobj(response,out,1024*1024)
    if sha256 and digest(temp)!=sha256:
        temp.unlink();raise ValueError('Download failed SHA-256 verification: '+path.name)
    temp.replace(path);return path

def runtime_spec():
    arch=platform.machine().lower()
    if arch not in ('x86_64','amd64'):raise RuntimeError('Automatic Python runtime preparation supports x86-64. Supply 64-bit Python 3.12 for this architecture.')
    if os.name!='nt' and not sys.platform.startswith('linux'):raise RuntimeError('Automatic runtime download is supported on Windows/Linux x86-64. Supply Python 3.12 on this platform.')
    key=('windows' if os.name=='nt' else 'linux')+'-x86_64'
    return key,json.loads((ROOT/'packaging/python-runtimes.json').read_text())[key]

def runtime_archive(root=ROOT,offline=False,cache=None):
    key,spec=runtime_spec();cache=Path(cache) if cache else Path(root)/'offline-cache/runtime'
    return download(spec['url'],cache/spec['filename'],spec['sha256'],offline),spec

def is_python312(path):
    if not path:return False
    try:
        p=subprocess.run([str(path),'-c','import sys,struct; assert sys.version_info[:2]==(3,12) and struct.calcsize("P")==8'],capture_output=True,timeout=20)
        return p.returncode==0
    except (OSError,subprocess.SubprocessError):return False

def ensure_python(root=ROOT,offline=False,managed=False):
    root=Path(root);directory=root/'.python312'
    local=directory/('python.exe' if os.name=='nt' else 'bin/python3.12')
    if is_python312(local):return local
    if not managed:
        for candidate in [sys.executable,shutil.which('python3.12'),shutil.which('python')]:
            if is_python312(candidate):return Path(candidate)
    if directory.exists():raise ValueError('A pre-existing .python312 folder is not a working supported runtime; preserve/rename it before retrying.')
    archive,spec=runtime_archive(root,offline,root/('offline-cache/runtime' if offline or (root/'samstudio/resources/offline_profile.json').is_file() else '.install-cache/runtime'))
    with tempfile.TemporaryDirectory(prefix='samstudio-python-',dir=root) as stage:
        stage=Path(stage)
        if os.name=='nt':
            with zipfile.ZipFile(archive) as z:
                for member in z.namelist():
                    if Path(member).is_absolute() or '..' in Path(member).parts:raise ValueError('Unsafe runtime archive member.')
                z.extractall(stage)
        else:
            with tarfile.open(archive) as t:
                # data_filter is available in the supported modern bootstrap Pythons.
                if hasattr(tarfile,'data_filter'):
                    t.extractall(stage,filter='data')
                else:
                    # Support older system Pythons without accepting traversal,
                    # device nodes, FIFOs, or links leaving the fresh staging root.
                    import posixpath
                    for member in t.getmembers():
                        name=posixpath.normpath(member.name)
                        if name.startswith('/') or name=='..' or name.startswith('../') or member.isdev() or member.isfifo():raise ValueError('Unsafe runtime archive member.')
                        if member.issym() or member.islnk():
                            base=posixpath.dirname(name) if member.issym() else ''
                            target=posixpath.normpath(posixpath.join(base,member.linkname))
                            if target.startswith('/') or target=='..' or target.startswith('../'):raise ValueError('Unsafe runtime archive link.')
                    t.extractall(stage)
        shutil.move(str(stage/spec['archive_root']),str(directory))
    (directory/'.samstudio-owned').write_text('Project-local verified CPython runtime\n')
    if not is_python312(local):raise RuntimeError('Prepared Python 3.12 failed its architecture/version check.')
    return local

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--offline',action='store_true');p.add_argument('--managed',action='store_true');p.add_argument('--run',nargs=argparse.REMAINDER)
    a=p.parse_args();py=ensure_python(offline=a.offline,managed=a.managed)
    if not a.run:print(py);return 0
    return subprocess.call([str(py),*a.run],cwd=ROOT)
if __name__=='__main__':raise SystemExit(main())
