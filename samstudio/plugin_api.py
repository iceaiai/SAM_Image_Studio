"""Plugin API v1. Plugins are ordinary trusted local Python code, not sandboxed."""
from __future__ import annotations
import copy,importlib.util,json,re,shutil,uuid,sys
from dataclasses import dataclass
from pathlib import Path
import numpy as np
from .domain import atomic_write
from .image_processing import processing_target,apply_processing

@dataclass
class ProcessingContext:
    image: np.ndarray
    target: np.ndarray
    parameters: dict
    calibration: dict
    objects: list
    progress: object
    cancel: object
    def check_cancelled(self):
        if self.cancel.is_set():raise InterruptedError('Plugin cancelled.')

class PluginAPI:
    version=1
    def __init__(self,window=None):self.window=window;self.processors={};self.actions={}
    @property
    def document(self):return self.window.document if self.window else None
    def add_image_processor(self,name,function,parameters=None):
        if not isinstance(name,str) or not name.strip() or name in self.processors:raise ValueError('Processor names must be nonempty and unique.')
        if not callable(function):raise ValueError('Processor function must be callable.')
        params=copy.deepcopy(parameters or {})
        if not isinstance(params,dict):raise ValueError('parameters must be an object.')
        json.dumps(params,allow_nan=False)
        self.processors[name]={'function':function,'parameters':params}
    def add_action(self,name,function):
        if not isinstance(name,str) or not name.strip() or name in self.actions or not callable(function):raise ValueError('Invalid or duplicate plugin action.')
        self.actions[name]=function
    def commit(self,label,mutation):
        if not self.window:raise ValueError('GUI access is unavailable in this test context.')
        return self.window._commit(label,mutation)

class PluginManager:
    def __init__(self,directory,window=None):
        self.directory=Path(directory);self.directory.mkdir(parents=True,exist_ok=True);self.window=window;self.loaded={}
    def manifests(self):
        return sorted(self.directory.glob('*/plugin.json'))
    def install(self,folder):
        folder=Path(folder).resolve();manifest=json.loads((folder/'plugin.json').read_text('utf-8'));ident=manifest.get('id','')
        if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_.-]{0,79}',ident):raise ValueError('Use a short alphanumeric plugin ID.')
        if manifest.get('api_version')!=1:raise ValueError('This app supports plugin API version 1.')
        module=Path(manifest.get('module','plugin.py'))
        if module.is_absolute() or '..' in module.parts or not (folder/module).is_file():raise ValueError('The plugin module must be a local file inside its folder.')
        target=self.directory/ident
        if target.exists():raise ValueError('This plugin ID is installed. Remove it in the plugin manager before installing a replacement.')
        files=list(folder.rglob('*'))
        if any(p.is_symlink() for p in files):raise ValueError('Plugin folders may not contain symbolic links.')
        if sum(p.stat().st_size for p in files if p.is_file())>512*1024*1024:raise ValueError('Keep checkpoints outside the plugin folder; maximum plugin source size is 512 MiB.')
        shutil.copytree(folder,target,ignore=shutil.ignore_patterns('__pycache__','.venv','*.pyc','.git'))
        return ident
    def load(self,ident):
        folder=self.directory/ident;manifest=json.loads((folder/'plugin.json').read_text('utf-8'))
        if manifest.get('id')!=ident or manifest.get('api_version')!=1:raise ValueError('Invalid plugin manifest.')
        relative=Path(manifest.get('module','plugin.py'))
        if relative.is_absolute() or '..' in relative.parts:raise ValueError('Invalid plugin module path.')
        path=folder/relative
        spec=importlib.util.spec_from_file_location('samstudio_user_'+uuid.uuid4().hex,path,submodule_search_locations=[str(folder)])
        module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module
        try:spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(spec.name,None);raise
        api=PluginAPI(self.window);module.register(api)
        self.loaded[ident]={'manifest':manifest,'api':api,'module':module}
        return api
    def remove(self,ident):
        if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_.-]{0,79}',ident):raise ValueError('Invalid plugin ID.')
        target=self.directory/ident
        if target.parent.resolve()!=self.directory.resolve():raise ValueError('Invalid plugin path.')
        self.loaded.pop(ident,None)
        if target.exists():shutil.rmtree(target)

def run_processor(function,context):
    context.check_cancelled();result=np.asarray(function(context))
    if result.shape!=context.image.shape:raise ValueError('Plugin output dimensions/channels do not match the image.')
    if result.dtype!=context.image.dtype:raise ValueError('Plugin output must preserve the input data type.')
    if not np.isfinite(result).all():raise ValueError('Plugin output contains nonfinite pixels.')
    result=result.copy();result[~context.target]=context.image[~context.target]
    if context.image.ndim==3 and context.image.shape[2]==4:result[...,3]=context.image[...,3]
    context.check_cancelled();return result
