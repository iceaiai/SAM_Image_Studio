"""Contract checks against the official multiplex API; no real GPU inference claim."""
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
import threading
import numpy as np
import pytest
from samstudio.inference import CATALOG,InferenceEngine
from samstudio.sam31_backend import Sam31Backend


def test_sam31_catalog_and_cpu_guard(monkeypatch):
    spec=next(s for s in CATALOG if s.family=='SAM3.1')
    assert spec.filename=='sam3.1_multiplex.pt' and spec.config=='sam3.1'
    with pytest.raises(ValueError,match='CUDA only'):InferenceEngine().load(spec,'cpu')


class Native:
    def __init__(self,fail=False):self.requests=[];self.paths=[];self.fail=fail
    def handle_request(self,r):
        self.requests.append(r)
        if r['type']=='start_session':
            path=Path(r['resource_path']);assert path.is_file() and path.suffix=='.png'
            self.paths.append(path);return {'session_id':'test'}
        if r['type']=='close_session':return {'success':True}
        if self.fail:raise RuntimeError('native failure')
        mask=np.zeros((1,40,80),bool);mask[:,10:20,20:40]=True
        return {'outputs':{'out_binary_masks':mask,'out_probs':np.array([.9]),'out_obj_ids':np.array([1])}}


def adapter(monkeypatch,fail=False):
    import torch
    monkeypatch.setattr(torch.cuda,'device',lambda *a:nullcontext())
    native=Native(fail);return Sam31Backend(native,'cuda:0'),native,np.zeros((40,80,3),np.uint8)


def test_sam31_combines_positive_negative_boxes_and_text(monkeypatch):
    backend,native,rgb=adapter(monkeypatch)
    backend.concepts(rgb,examples=[{'kind':'rectangle','points':[[8,4],[24,12]],'label':1},
        {'kind':'ellipse','points':[[40,20],[56,28]],'label':0}],text='particles')
    prompt=next(r for r in native.requests if r['type']=='add_prompt')
    assert prompt['text']=='particles' and prompt['bounding_box_labels']==[1,0]
    # The first two numbers are TOP LEFT, never the center used by SAM3 image API.
    assert prompt['bounding_boxes'][0][:2]==[.1,.1]
    assert len([r for r in native.requests if r['type']=='add_prompt'])==1
    assert native.requests[-1]['type']=='close_session' and all(not p.exists() for p in native.paths)


def test_sam31_point_seed_is_promoted_to_concept_and_excluded_box(monkeypatch):
    backend,native,rgb=adapter(monkeypatch)
    backend.concepts(rgb,points=[[25,15,1],[60,30,0]])
    prompts=[r for r in native.requests if r['type']=='add_prompt']
    assert prompts[0]['points']==[[25/80,15/40]] and prompts[0]['point_labels']==[1]
    assert prompts[0]['obj_id']==1 and prompts[0]['rel_coordinates']
    assert prompts[-1]['bounding_box_labels']==[1,0] and len(prompts[-1]['bounding_boxes'])==2
    assert len([r for r in native.requests if r['type']=='close_session'])==3


def test_sam31_native_failure_closes_session_and_deletes_image(monkeypatch):
    backend,native,rgb=adapter(monkeypatch,True)
    with pytest.raises(RuntimeError,match='native failure'):backend.predict(rgb,[[25,15,1]])
    assert native.requests[-1]['type']=='close_session' and all(not p.exists() for p in native.paths)


def test_sam31_engine_routes_native_text_and_examples(monkeypatch):
    from samstudio.exemplars import infer_examples
    backend,native,rgb=adapter(monkeypatch)
    engine=InferenceEngine();engine.spec=next(s for s in CATALOG if s.family=='SAM3.1');engine.predictor=backend
    masks=engine.infer(rgb,whole=True,text_prompt='particle',min_area=1)
    assert len(masks)==1 and engine.last_proposal_scores==[.9]
    protected=np.zeros((40,80),bool);protected[10:12]=True
    masks=infer_examples(engine,rgb,examples=[{'kind':'rectangle','points':[[8,4],[24,12]],'label':1}],protected=protected,min_area=1)
    assert len(masks)==1 and not (masks[0]&protected).any()


def test_sam31_load_uses_official_multiplex_factory_not_sam3_image(monkeypatch,tmp_path):
    import sys,types
    from samstudio import inference
    calls=[];native=Native()
    module=types.ModuleType('sam3.model_builder')
    module.build_sam3_multiplex_video_predictor=lambda **kwargs:(calls.append(kwargs) or native)
    monkeypatch.setitem(sys.modules,'sam3',types.ModuleType('sam3'))
    monkeypatch.setitem(sys.modules,'sam3.model_builder',module)
    monkeypatch.setenv('CONDA_PREFIX',str(tmp_path/'dedicated'))
    fake=SimpleNamespace(inference_mode=lambda:nullcontext(),cuda=SimpleNamespace(is_available=lambda:True,device=lambda d:nullcontext()))
    monkeypatch.setattr(inference,'initialize_torch_runtime',lambda:fake)
    checkpoint=tmp_path/'sam3.1_multiplex.pt';checkpoint.write_bytes(b'contract-only')
    engine=InferenceEngine();engine.load(next(s for s in CATALOG if s.family=='SAM3.1'),'cuda:1',checkpoint)
    assert engine.ready and isinstance(engine.predictor,Sam31Backend) and engine.device=='cuda:1'
    assert calls==[dict(checkpoint_path=str(checkpoint),use_fa3=False,compile=False,warm_up=False,async_loading_frames=False)]
