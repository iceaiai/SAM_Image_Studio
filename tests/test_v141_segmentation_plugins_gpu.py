import copy,importlib.util,json,os,threading
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from samstudio.exemplars import infer_examples
from samstudio.plugin_api import PluginManager,ProcessingContext,run_processor
from samstudio.hardware import cuda_index,conda_gpu_plan,detect_gpus

class ExampleEngine:
    ready=True
    def __init__(self):
        self.spec=SimpleNamespace(family='SAM2.1');self.predictor=SimpleNamespace();self.last_proposal_scores=[];self.calls=0
        self.masks=[]
        for y,x in [(10,10),(10,50),(45,10),(45,50)]:
            mask=np.zeros((80,90),bool);mask[y:y+15,x:x+15]=True;self.masks.append(mask)
    def predict(self,rgb,points=None,box=None,progress=None,cancel=None):
        if points:x,y,_=points[0]
        else:x,y=box[:2]
        mask=next((m for m in self.masks if m[min(79,int(y)),min(89,int(x))]),self.masks[0])
        return mask.copy(),.99
    def infer(self,rgb,**kwargs):self.calls+=1;self.last_proposal_scores=[.99]*4;return [m.copy() for m in self.masks]

def sample():
    engine=ExampleEngine();rgb=np.full((80,90,3),30,np.uint8)
    for i,m in enumerate(engine.masks):rgb[m]=230 if i<3 else 90
    return engine,rgb

def test_whole_image_examples_find_other_objects_and_negative_cases():
    engine,rgb=sample();masks=infer_examples(engine,rgb,points=[[15,15,1],[55,50,0]])
    assert len(masks)==3 and all(not(m&engine.masks[3]).any() for m in masks)
    assert all(any(np.array_equal(a,b) for b in masks) for a in engine.masks[:3])
    assert len(engine.last_proposal_scores)==3

def test_whole_image_examples_protect_accepted_objects_and_cache_candidates():
    engine,rgb=sample();first=infer_examples(engine,rgb,[[15,15,1]])
    second=infer_examples(engine,rgb,[[15,15,1],[55,50,0]],protected=engine.masks[1])
    assert engine.calls==1 and len(second)==2 and not any((m&engine.masks[1]).any() for m in second)
    engine.predictor=SimpleNamespace()  # A newly loaded backend must not reuse old model proposals.
    infer_examples(engine,rgb,[[15,15,1]])
    assert engine.calls==2

@pytest.mark.parametrize('kind,points',[('rectangle',[[9,9],[26,26]]),('polygon',[[9,9],[26,9],[26,26],[9,26]]),('ellipse',[[8,8],[28,28]]),('circle',[[8,8],[28,28]])])
def test_positive_shapes_are_examples_not_result_clips(kind,points):
    engine,rgb=sample();masks=infer_examples(engine,rgb,examples=[{'kind':kind,'points':points,'label':1}])
    assert len(masks)>=3 and any(m[15,55] for m in masks)

def test_exemplar_cancellation():
    engine,rgb=sample();cancel=threading.Event();cancel.set()
    with pytest.raises(InterruptedError):infer_examples(engine,rgb,[[15,15,1]],cancel=cancel)

def mount(window,document):
    from test_v141_processing_workspace import mount as attach
    return attach(window,document)

def test_point_tool_hides_roi_and_single_choices(window,document):
    mount(window,document);window.mode.setCurrentText('Segment');window.tool_actions['rectangle'].trigger();window.scope.setCurrentIndex(window.scope.findData('roi'));window.tool_actions['point'].trigger()
    assert window.scope.currentData()=='prompt' and not window.scope.model().item(window.scope.findData('roi')).isEnabled()
    window.tool_actions['ellipse'].trigger();assert window.scope.model().item(window.scope.findData('roi')).isEnabled()

def test_auto_grid_selection_starts_and_ignores_text(window,document,qtbot):
    mount(window,document);engine=SimpleNamespace(ready=True,spec=SimpleNamespace(family='SAM2.1',label='test'),device='cpu',last_proposal_scores=[])
    calls=[]
    def infer(rgb,*args,**kwargs):calls.append(kwargs);return []
    engine.infer=infer;window.engine=engine;window.mode.setCurrentText('Segment');window.text_prompt.setText('particle')
    window.scope.setCurrentIndex(window.scope.findData('automatic'));qtbot.waitUntil(lambda:bool(calls),timeout=4000);qtbot.waitUntil(lambda:not window.busy,timeout=4000)
    assert calls[0]['whole'] is True and calls[0]['text_prompt']==''

def test_text_run_button_available_and_executes_without_drawing(window,document,qtbot):
    mount(window,document);calls=[]
    window.engine=SimpleNamespace(ready=True,spec=SimpleNamespace(family='SAM2.1',label='test'),device='cpu')
    window.text_prompt.setText('big dots');window._refresh();window.run_inference=lambda *a,**k:calls.append(True)
    qtbot.mouseClick(window.text_run_button, __import__('PySide6.QtCore',fromlist=['Qt']).Qt.MouseButton.LeftButton)
    assert calls and window.mode.currentText()=='Segment'

def test_multiple_shapes_positive_negative_persist_before_accept(window,document):
    mount(window,document);window.mode.setCurrentText('Segment');window.auto_checkbox.setChecked(False)
    window._shape_completed('rectangle',[[10,10],[30,30]])
    window.example_polarity.setCurrentIndex(1);window._shape_completed('ellipse',[[60,60],[80,80]])
    assert len(document.draft['examples'])==2 and [e['label'] for e in document.draft['examples']]==[1,0]
    restored=type(document)(document.frame);assert window.stores[document.frame.key].load(restored)[0]
    assert restored.draft['examples']==document.draft['examples']
    window.cancel_operation();assert not document.draft['examples']

def context(raw=None):
    raw=np.full((31,37),20000,np.uint16) if raw is None else raw
    target=np.zeros(raw.shape[:2],bool);target[4:-4,4:-4]=True
    return ProcessingContext(raw,target,{}, {},[],lambda m:None,threading.Event())

def test_plugin_install_registration_run_dtype_and_outside_pixels(tmp_path):
    folder=tmp_path/'source';folder.mkdir();(folder/'plugin.json').write_text(json.dumps({'id':'test.local','api_version':1,'module':'plugin.py'}));(folder/'plugin.py').write_text('def register(api):\n    api.add_image_processor("Darken", lambda ctx: ctx.image // 2)\n')
    manager=PluginManager(tmp_path/'installed');ident=manager.install(folder);api=manager.load(ident);ctx=context();result=run_processor(api.processors['Darken']['function'],ctx)
    assert np.array_equal(result[~ctx.target],ctx.image[~ctx.target]) and np.all(result[ctx.target]==10000)
    manager.remove(ident);assert not (tmp_path/'installed'/ident).exists()

@pytest.mark.parametrize('bad',[lambda c:c.image.astype(float),lambda c:c.image[:-1],lambda c:np.full(c.image.shape,np.nan)])
def test_invalid_plugin_results_rejected(bad):
    with pytest.raises(ValueError):run_processor(bad,context())

def test_plugin_cancel_and_register_failure_isolation(tmp_path):
    ctx=context();ctx.cancel.set()
    with pytest.raises(InterruptedError):run_processor(lambda c:c.image,ctx)
    folder=tmp_path/'source';folder.mkdir();(folder/'plugin.json').write_text(json.dumps({'id':'bad.plugin','api_version':1,'module':'plugin.py'}));(folder/'plugin.py').write_text('def register(api):\n    raise ValueError("plugin failed")\n')
    manager=PluginManager(tmp_path/'installed');manager.install(folder)
    with pytest.raises(ValueError,match='plugin failed'):manager.load('bad.plugin')
    assert not manager.loaded


def test_unet_plugin_runs_real_torchscript_tiling(tmp_path):
    import torch
    root=Path(__file__).resolve().parents[1]/'examples/plugins/unet_denoiser'
    spec=importlib.util.spec_from_file_location('tiny_unet',root/'model_example.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    torch.manual_seed(7);model=module.TinyUNet().eval();checkpoint=tmp_path/'test_untrained.pt';torch.jit.script(model).save(str(checkpoint))
    manager=PluginManager(tmp_path/'installed');ident=manager.install(root);api=manager.load(ident);ctx=context();ctx.parameters={'checkpoint':str(checkpoint),'device':'cpu','tile_size':16,'overlap':4}
    result=run_processor(api.processors['U-Net denoise']['function'],ctx)
    assert result.dtype==ctx.image.dtype and result.shape==ctx.image.shape and np.array_equal(result[~ctx.target],ctx.image[~ctx.target])
    assert not np.array_equal(result[ctx.target],ctx.image[ctx.target])

@pytest.mark.parametrize('maximum,cap,expected',[('12.8','12.0','cu128'),('12.6','8.6','cu126'),('12.4','7.5','cu118'),('11.8','7.0','cu118')])
def test_detected_runtime_and_architecture_choose_matching_cuda(maximum,cap,expected):
    report={'gpus':[{'index':0,'compute_capability':cap}],'cuda_runtime_max':maximum}
    assert cuda_index(report)==expected
    plan=conda_gpu_plan(Path('.'),report,name='test-gpu',conda='conda')
    assert plan[0][:5]==['conda','create','--yes','--name','test-gpu'] and 'run' in plan[1]

@pytest.mark.parametrize('maximum,cap,sam3',[('12.6','12.0',False),('11.7','7.5',False),('12.4','8.6',True),('12.8','3.5',False)])
def test_incompatible_gpu_setup_rejected(maximum,cap,sam3):
    with pytest.raises(ValueError):cuda_index({'gpus':[{'compute_capability':cap}],'cuda_runtime_max':maximum},sam3)


def test_gpu_install_commands_are_conda_only(monkeypatch):
    report={'gpus':[{'compute_capability':'8.6'}],'cuda_runtime_max':'12.6'}
    monkeypatch.delenv('CONDA_PREFIX',raising=False)
    with pytest.raises(ValueError,match='Conda'):conda_gpu_plan('.',report,current=True)
    monkeypatch.setenv('CONDA_PREFIX','/opt/conda/envs/sam-studio-gpu');commands=conda_gpu_plan('.',report,current=True)
    assert any('https://download.pytorch.org/whl/cu126' in c for c in commands)
    assert commands[-1][-2:]==['--device','cuda']


def test_actual_cpu_detection_does_not_claim_gpu():
    report=detect_gpus()
    if not report['detected']:
        with pytest.raises(ValueError):cuda_index(report)


@pytest.mark.parametrize('conda, expected', [(False, 'Conda environment'), (True, 'CUDA is unavailable')])
def test_gpu_install_selftest_rejects_invalid_execution_environment(tmp_path, conda, expected):
    import subprocess, sys
    env=dict(os.environ);env['CUDA_VISIBLE_DEVICES']=''
    if conda:env['CONDA_PREFIX']=str(tmp_path/'synthetic-conda-env')
    else:env.pop('CONDA_PREFIX',None)
    report=tmp_path/'gpu-selftest.json'
    process=subprocess.run([sys.executable,'-m','samstudio.selftest','--device','cuda','--report',str(report)],env=env,capture_output=True,text=True,timeout=60)
    result=json.loads(report.read_text())
    assert process.returncode==1 and result['status']=='failed' and expected in result['error']

@pytest.mark.parametrize('family,variant',[('SAM1','ViT-B'),('SAM2.1','Tiny')])
@pytest.mark.integration
def test_genuine_sam_whole_image_retrieval_from_shape_and_negative_point(family,variant,tmp_path):
    import cv2
    from samstudio.inference import InferenceEngine,CATALOG
    from samstudio.exemplars import descriptor
    spec=next(s for s in CATALOG if s.family==family and s.variant==variant)
    weights=Path(os.environ.get('SAM_STUDIO_TEST_WEIGHTS','not_provided'))/spec.filename
    if not weights.is_file():pytest.skip('Provide genuine SAM checkpoint assets.')
    rgb=np.full((192,192,3),50,np.uint8)
    for p in [(45,45),(140,45),(45,140),(140,140)]:cv2.circle(rgb,p,18,(220,220,220),-1)
    engine=InferenceEngine();engine.load(spec,'cpu',weights)
    masks=infer_examples(engine,rgb,points=[[140,140,0]],examples=[{'kind':'rectangle','points':[[25,25],[65,65]],'label':1}],grid=4,min_score=.5,min_area=20,max_objects=20,similarity_threshold=.60)
    assert len(masks)>=2 and any(m[45,140] or m[140,45] for m in masks)
    assert not any(m[140,140] for m in masks)
    assert descriptor(engine,rgb,masks[0])['embedding'] is not None
    report={'family':family,'positive_shape':'rectangle','negative_point':[140,140],'whole_image_result_count':len(masks),'other_instances_outside_prompt':True,'negative_instance_excluded':True,'pooled_sam_features':True}
    target=Path(os.environ.get('SAM_STUDIO_TEST_REPORT',tmp_path/'models.json')).parent/f'v15_examples_{family.replace(".","_")}.json';target.write_text(json.dumps(report,indent=2))


def test_new_shape_examples_while_running_are_coalesced(window,document,qtbot):
    mount(window,document);window.engine=SimpleNamespace(ready=True,spec=SimpleNamespace(family='SAM2.1',label='test'),device='cpu',last_proposal_scores=[])
    window.mode.setCurrentText('Segment');entered=threading.Event();release=threading.Event();calls=[]
    def infer(engine,rgb,points,examples,protected,progress,cancel,text,options):
        calls.append(copy.deepcopy(examples))
        if len(calls)==1:entered.set();release.wait(5)
        mask=np.zeros(document.frame.shape,bool);mask[70:80,80:90]=True;return [mask]
    window._example_inference=infer
    window._shape_completed('rectangle',[[10,10],[30,30]]);window.preview_timer.stop();window.run_inference();qtbot.waitUntil(entered.is_set,timeout=3000)
    window.example_polarity.setCurrentIndex(1);window._shape_completed('ellipse',[[60,60],[80,80]]);release.set()
    qtbot.waitUntil(lambda:len(calls)==2 and not window.busy and bool(window.canvas.preview_masks),timeout=6000)
    assert len(calls[-1])==2 and calls[-1][-1]['label']==0 and not window.errors


def test_sam3_native_contract_uses_normalized_positive_and_negative_boxes():
    import torch
    engine,rgb=sample();engine.spec.family='SAM3';engine._lock=threading.RLock();calls=[]
    class Processor:
        def set_image(self,image):return {}
        def add_geometric_prompt(self,box,label,state):
            calls.append((box,label));return {'masks':torch.tensor(np.asarray(engine.masks[:3])),'scores':torch.tensor([.9]*3)}
    engine.processor=Processor()
    masks=infer_examples(engine,rgb,[[15,15,1],[55,50,0]])
    assert len(masks)==3 and [label for box,label in calls]==[True,False]
    assert all(0<=v<=1 for box,label in calls for v in box)


def test_plugin_relative_modules_supported(tmp_path):
    folder=tmp_path/'source';folder.mkdir();(folder/'plugin.json').write_text(json.dumps({'id':'test.relative','api_version':1,'module':'plugin.py'}));(folder/'helper.py').write_text('def process(ctx):\n    return ctx.image.copy()\n');(folder/'plugin.py').write_text('from .helper import process\ndef register(api):\n    api.add_image_processor("Relative",process)\n')
    manager=PluginManager(tmp_path/'installed');ident=manager.install(folder);api=manager.load(ident);ctx=context();assert np.array_equal(run_processor(api.processors['Relative']['function'],ctx),ctx.image)
