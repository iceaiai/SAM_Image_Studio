"""Read-only GPU detection and explicit Conda-only CUDA installation planning."""
from __future__ import annotations
import csv,json,os,re,shutil,subprocess,sys
from pathlib import Path

def detect_gpus(run=subprocess.run):
    executable=shutil.which('nvidia-smi')
    if not executable and os.name=='nt':
        candidate=Path(os.environ.get('WINDIR','C:/Windows'))/'System32/nvidia-smi.exe'
        if candidate.exists():executable=str(candidate)
    report={'gpus':[],'cuda_runtime_max':None,'conda_environment':bool(os.environ.get('CONDA_PREFIX')),'platform':sys.platform,'detected':False}
    if not executable:
        report['reason']='No NVIDIA driver utility found. CPU remains available; AMD/Intel GPUs do not use this CUDA installer.';return report
    try:
        query=run([executable,'--query-gpu=index,name,driver_version,memory.total,compute_cap','--format=csv,noheader,nounits'],capture_output=True,text=True,check=True,timeout=15)
        for row in csv.reader(query.stdout.splitlines()):
            if len(row)<5:continue
            index,name,driver,memory,cap=(x.strip() for x in row[:5])
            report['gpus'].append({'index':int(index),'name':name,'driver_version':driver,'memory_mib':float(memory),'compute_capability':cap})
        info=run([executable],capture_output=True,text=True,check=True,timeout=15)
        match=re.search(r'CUDA Version:\s*([0-9.]+)',info.stdout)
        if match:report['cuda_runtime_max']=match.group(1)
        report['detected']=bool(report['gpus'])
        if not report['detected']:report['reason']='The NVIDIA utility reported no devices.'
    except (OSError,ValueError,subprocess.SubprocessError) as e:report['reason']='NVIDIA detection failed: '+str(e)
    return report

def cuda_index(report,sam3=False):
    if not report.get('gpus'):raise ValueError(report.get('reason','No NVIDIA GPU was detected.'))
    maximum=tuple(int(x) for x in str(report.get('cuda_runtime_max') or '0.0').split('.')[:2])
    if maximum>=(12,8):index='cu128'
    elif maximum>=(12,6):index='cu126'
    elif maximum>=(11,8) and not sam3:index='cu118'
    else:raise ValueError('Update the NVIDIA driver. SAM3 requires CUDA 12.6 or later; SAM1/2 require at least a driver supporting CUDA 11.8 for this release.')
    capabilities=[float(g.get('compute_capability',0)) for g in report['gpus']]
    if max(capabilities)<5.:raise ValueError('This NVIDIA GPU is too old for the supplied PyTorch builds.')
    if max(capabilities)>=10 and index!='cu128':raise ValueError('This GPU generation needs the CUDA 12.8 build and a compatible newer driver.')
    return index

def conda_gpu_plan(root,report,name='sam-image-studio-gpu',current=False,sam3=False,conda=None):
    root=Path(root).resolve()
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,63}',name):raise ValueError('Use a simple Conda environment name.')
    index=cuda_index(report,sam3)
    if sam3 and sys.platform=='win32':raise ValueError('Use Linux/WSL2 Conda for the native SAM3 backend. Native Windows Conda supports the SAM1/2 GPU setup.')
    if not current:
        executable=conda or shutil.which('conda')
        if not executable:raise ValueError('Install Miniforge/Conda, open its prompt, and run this command again.')
        second=[executable,'run','--no-capture-output','-n',name,'python',str(root/'scripts/install_conda_gpu.py'),'--current']
        if sam3:second.append('--sam3')
        return [[executable,'create','--yes','--name',name,'python=3.12','pip'],second]
    if not os.environ.get('CONDA_PREFIX') or Path(os.environ['CONDA_PREFIX']).name.lower() in ('base','anaconda3','miniconda3','miniforge3'):
        raise ValueError('Activate a dedicated non-base Conda environment before GPU installation.')
    py=sys.executable
    requirements='requirements-sam3-experimental.txt' if sam3 else 'requirements.lock.txt'
    commands=[
        [py,'-m','pip','install','--upgrade','pip>=24.3','setuptools>=75','wheel'],
        [py,'-m','pip','install','torch==2.7.1','torchvision==0.22.1','--index-url','https://download.pytorch.org/whl/'+index],
        [py,'-m','pip','install','--find-links',str(root/'vendor'),'-r',str(root/requirements)],
        [py,'-m','pip','install','--no-deps',str(root/'vendor/sam_2-1.0-py3-none-any.whl')],
        [py,'-m','pip','install','--no-deps',str(root)],
        [py,'-m','pip','check'],
        [py,'-m','samstudio.selftest','--device','cuda'],
    ]
    return commands

def automatic_device():
    import torch
    if not os.environ.get('CONDA_PREFIX') or not torch.cuda.is_available():return 'cpu'
    devices=[(torch.cuda.get_device_properties(i).total_memory,i) for i in range(torch.cuda.device_count())]
    return 'cuda:'+str(max(devices)[1]) if devices else 'cpu'
