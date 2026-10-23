"""Contracts for native SAM3 shared features and selected-object exemplars."""
from types import SimpleNamespace
import numpy as np
import pytest
from samstudio.inference import CATALOG, InferenceEngine
from samstudio.domain import pack_mask, unpack_mask


def test_sam3_instance_and_roi_use_parent_shared_features_and_cache():
    engine=InferenceEngine();engine.spec=next(s for s in CATALOG if s.family=='SAM3')
    calls=[];shape=(24,32);mask=np.zeros(shape,bool);mask[4:16,6:20]=True
    def forbidden(*a,**k):raise AssertionError('Tracker has no own backbone; never call set_image')
    engine.predictor=SimpleNamespace(set_image=forbidden)
    def encode(image):
        calls.append(('encode',image.size))
        return {'backbone_out':{'shared':True},'original_height':image.height,'original_width':image.width}
    def predict(state,**options):
        assert state['backbone_out']=={'shared':True}
        calls.append(('predict',options))
        return np.stack([mask,np.zeros(shape,bool)]),np.array([.95,.1]),None
    engine.processor=SimpleNamespace(set_image=encode)
    engine.model=SimpleNamespace(predict_inst=predict)
    rgb=np.zeros((*shape,3),np.uint8)
    roi=np.zeros(shape,bool);roi[3:12,4:17]=True
    result=engine.infer(rgb,roi=roi,whole=False,min_area=1)
    assert len(result)==1 and np.array_equal(result[0],mask&roi)
    engine.predict(rgb,points=[[8,8,1]])
    assert sum(c[0]=='encode' for c in calls)==1
    rgb[0,0]=1;engine.predict(rgb,box=[2,2,22,20])
    assert sum(c[0]=='encode' for c in calls)==2
    assert calls[0]==('encode',(32,24))


def test_selected_annotation_becomes_exact_whole_image_example(window,document):
    from test_v141_processing_workspace import mount
    mount(window,document)
    window.engine=SimpleNamespace(spec=SimpleNamespace(family='SAM3.1'),ready=False)
    window.canvas.set_selected([document.objects[0].id])
    examples=window._whole_image_examples(document)
    assert len(examples)==1 and examples[0]['kind']=='mask'
    assert np.array_equal(unpack_mask(examples[0]['mask'],document.frame.shape),document.objects[0].mask)
    assert examples[0]['object_id']==document.objects[0].id


def test_selected_mask_uses_public_sam_image_embedding():
    from samstudio.exemplars import _embedding
    import torch
    called=[]
    def features():called.append(True);return torch.ones((1,4,3,3))
    engine=SimpleNamespace(predictor=SimpleNamespace(get_image_embedding=features))
    embedding=_embedding(engine,np.ones((12,12),bool))
    assert called==[True] and np.allclose(embedding,np.full(4,.5))


def test_sam31_selected_mask_is_native_concept_box(monkeypatch):
    from samstudio.sam31_backend import Sam31Backend
    backend=Sam31Backend(None,'cuda');calls=[]
    backend.request=lambda rgb,payload,cancel=None:(calls.append(payload) or ([],[]))
    rgb=np.zeros((40,60,3),np.uint8);mask=np.zeros((40,60),bool);mask[10:20,15:30]=True
    backend.concepts(rgb,examples=[{'kind':'mask','mask':pack_mask(mask),'label':1}])
    assert np.allclose(calls[0]['bounding_boxes'],[[.25,.25,.25,.25]])
    assert calls[0]['bounding_box_labels']==[1]


@pytest.mark.parametrize('family',['SAM2.1','SAM3','SAM3.1','SAM3 ONNX'])
def test_text_label_and_placeholder_follow_loaded_family(window,document,family):
    from test_v141_processing_workspace import mount
    mount(window,document)
    window.engine=SimpleNamespace(spec=next(s for s in CATALOG if s.family==family),ready=True,device='cpu')
    window._refresh_controls()
    assert family in window.text_prompt.placeholderText()
    assert family in window.text_prompt_label.text()
    assert window.text_prompt_action.isVisible()
    window.engine.spec=next(s for s in CATALOG if s.family=='SAM1')
    window._refresh_controls()
    assert not window.text_prompt_action.isVisible() and not window.text_prompt_label_action.isVisible()
