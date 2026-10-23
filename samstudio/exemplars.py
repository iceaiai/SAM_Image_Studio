"""Whole-image exemplar retrieval for SAM1/2 and native concept prompts for SAM3.

SAM1/2 do not natively propagate a concept: candidate masks are proposed, then
ranked using pooled SAM features, observed intensity and simple shape features.
This application retrieval layer is explicitly recorded in mask provenance.
"""
from __future__ import annotations
import hashlib,math
import cv2
import numpy as np
from scipy.ndimage import distance_transform_edt
from .processing import shape_mask,bounding_box,filter_proposals
from .domain import unpack_mask

def _check(cancel):
    if cancel and cancel.is_set():raise InterruptedError('Exemplar preview cancelled.')

def _embedding(engine,mask):
    getter = getattr(engine.predictor, 'get_image_embedding', None)
    value = getter() if callable(getter) else getattr(engine.predictor,'features',None)
    if value is None:value=getattr(engine.predictor,'_features',{}).get('image_embed')
    if value is None:return None
    value=value.detach().float().cpu().numpy()
    if value.ndim==4:value=value[0]
    if value.ndim!=3:return None
    weights=cv2.resize(mask.astype(np.float32),(value.shape[2],value.shape[1]),interpolation=cv2.INTER_AREA)
    if weights.sum()<1e-7:return None
    pooled=(value*weights).sum(axis=(1,2))/weights.sum()
    norm=np.linalg.norm(pooled)
    return pooled/norm if norm>1e-8 else None

def descriptor(engine,rgb,mask):
    values=rgb[mask].astype(float)/255.
    if not len(values):raise ValueError('An exemplar mask is empty.')
    x,y,w,h=bounding_box(mask)
    return {'embedding':_embedding(engine,mask),'mean':values.mean(0),'std':values.std(0),
            'aspect':min(w,h)/max(w,h),'fill':float(mask.sum())/max(1,w*h)}

def similarity(a,b):
    appearance=math.exp(-float(np.linalg.norm(a['mean']-b['mean']))/.35-float(np.linalg.norm(a['std']-b['std']))/.5)
    geometry=max(0.,1.-(abs(a['aspect']-b['aspect'])+abs(a['fill']-b['fill']))/2)
    if a['embedding'] is not None and b['embedding'] is not None and a['embedding'].shape==b['embedding'].shape:
        return .6*max(0.,float(a['embedding']@b['embedding']))+.3*appearance+.1*geometry
    return .8*appearance+.2*geometry

def template_centers(rgb,mask,limit=24):
    """Supplement the fixed grid so small repeated particles are not missed."""
    x,y,w,h=bounding_box(mask);pad=max(2,int(min(w,h)*.2));x1=max(0,x-pad);y1=max(0,y-pad);x2=min(rgb.shape[1],x+w+pad);y2=min(rgb.shape[0],y+h+pad)
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY).astype(np.float32);patch=gray[y1:y2,x1:x2]
    if min(patch.shape)<3 or patch.std()<1e-4:return []
    result=[]
    for scale in (.7,1.,1.4):
        pw,ph=max(3,round(patch.shape[1]*scale)),max(3,round(patch.shape[0]*scale))
        if pw>gray.shape[1] or ph>gray.shape[0]:continue
        response=cv2.matchTemplate(gray,cv2.resize(patch,(pw,ph)),cv2.TM_CCOEFF_NORMED)
        for _ in range(limit):
            _,value,_,point=cv2.minMaxLoc(response)
            if value<.5:break
            px,py=point;result.append([px+pw/2,py+ph/2,1])
            radius=max(2,min(pw,ph)//3);response[max(0,py-radius):py+radius+1,max(0,px-radius):px+radius+1]=-1
    return result

def infer_examples(engine,rgb,points=None,examples=None,protected=None,grid=8,min_score=.70,min_area=8,max_objects=300,
                   progress=None,cancel=None,text_prompt='',similarity_threshold=.72,negative_margin=.025):
    if not engine.ready:raise ValueError('Load a model first.')
    shape=rgb.shape[:2];protected=np.zeros(shape,bool) if protected is None else np.asarray(protected,bool)
    if protected.shape!=shape:raise ValueError('Protected mask dimensions do not match.')
    if engine.spec.family=='SAM3 ONNX':
        if points or examples:
            raise ValueError('This SAM3 ONNX export is text-only. Clear exemplar prompts and enter text; choose Inside ROI only for an output region. Use SAM3.1 for native positive/negative shapes.')
        return engine.infer(rgb,protected=protected,whole=True,min_score=min_score,min_area=min_area,
                            max_objects=max_objects,progress=progress,cancel=cancel,text_prompt=text_prompt)
    if engine.spec.family=='SAM3.1':
        with engine._lock:
            candidates,scores=engine.predictor.concepts(rgb,points,examples,text_prompt,cancel)
        pairs=[(m,s) for m,s in zip(candidates,scores) if s>=min_score]
        candidates,scores=([p[0] for p in pairs],[p[1] for p in pairs])
        result=filter_proposals(candidates,protected,min_area=min_area)[:max_objects]
        engine.last_proposal_scores=[scores[int(np.argmax([float((m&c).sum())/max(1,float((m|c).sum())) for c in candidates]))] for m in result]
        return result
    seeds=[]
    for x,y,label in points or []:
        _check(cancel);mask,score=engine.predict(rgb,[[x,y,1]],progress=progress,cancel=cancel)
        seeds.append((mask,float(score),bool(label)))
    for example in examples or []:
        _check(cancel)
        if example['kind'] == 'mask':
            mask = unpack_mask(example['mask'], shape)
            if not mask.any():raise ValueError('A selected exemplar object is empty.')
            # Existing masks already describe the exemplar; pool SAM image
            # features over them rather than replacing them by a box prediction.
            if engine.spec.family in ('SAM1','SAM2','SAM2.1'):
                engine._set_image(np.ascontiguousarray(rgb, dtype=np.uint8), progress, cancel)
            seeds.append((mask, 1., bool(example.get('label',1))))
            continue
        region=shape_mask(example['kind'],example['points'],shape)
        if not region.any():raise ValueError('An example shape is empty.')
        x,y,w,h=bounding_box(region)
        yy,xx=np.unravel_index(np.argmax(distance_transform_edt(region)),shape)
        mask,score=engine.predict(rgb,[[float(xx),float(yy),1]],[x,y,x+w,y+h],progress,cancel)
        seeds.append((mask,float(score),bool(example.get('label',1))))
    if not any(label for _,_,label in seeds) and not text_prompt:raise ValueError('Add at least one positive example or a text prompt.')
    if engine.spec.family=='SAM3':
        import torch
        from PIL import Image
        with engine._lock,torch.inference_mode():
            state=engine.processor.set_image(Image.fromarray(rgb))
            if text_prompt:state=engine.processor.set_text_prompt(text_prompt,state)
            for mask,score,label in seeds:
                _check(cancel);x,y,w,h=bounding_box(mask)
                box=[(x+w/2)/shape[1],(y+h/2)/shape[0],w/shape[1],h/shape[0]]
                state=engine.processor.add_geometric_prompt(box,label,state)
            masks=state['masks'].detach().cpu().numpy().reshape(-1,*shape).astype(bool)
            scores=state['scores'].detach().float().cpu().numpy().reshape(-1).tolist()
        candidates=list(masks)
    else:
        positive=[descriptor(engine,rgb,m) for m,_,label in seeds if label]
        negative=[descriptor(engine,rgb,m) for m,_,label in seeds if not label]
        if text_prompt:
            candidates=engine.infer(rgb,protected=np.zeros(shape,bool),whole=True,text_prompt=text_prompt,progress=progress,cancel=cancel,min_area=min_area,max_objects=max_objects)
            scores=list(engine.last_proposal_scores)
        else:
            key=(id(engine.predictor),hashlib.sha256(rgb.tobytes()).hexdigest(),int(grid),float(min_score),int(min_area),int(max_objects))
            cache=getattr(engine,'_example_candidates',None)
            if not cache or cache[0]!=key:
                masks=engine.infer(rgb,protected=np.zeros(shape,bool),whole=True,grid=grid,min_score=min_score,min_area=min_area,max_objects=max_objects,progress=progress,cancel=cancel)
                cache=(key,[m.copy() for m in masks],list(engine.last_proposal_scores));engine._example_candidates=cache
            candidates,scores=list(cache[1]),list(cache[2])
        # Explicit exemplars and correlation seeds supplement sparse grid proposals.
        for mask,score,label in seeds:
            if label:
                candidates.append(mask);scores.append(score)
                for index,point in enumerate(template_centers(rgb,mask)):
                    _check(cancel)
                    if progress:progress(f'Checking small-object exemplar matches: {index+1}')
                    candidate,quality=engine.predict(rgb,[point],cancel=cancel)
                    if quality>=min_score and min_area<=candidate.sum()<np.prod(shape)*.85:candidates.append(candidate);scores.append(float(quality))
        chosen=[];qualities=[]
        for index,(mask,quality) in enumerate(zip(candidates,scores)):
            _check(cancel)
            if progress:progress(f'Comparing positive/negative exemplars: {index+1}/{len(candidates)}')
            desc=descriptor(engine,rgb,mask)
            pos=max((similarity(desc,d) for d in positive),default=1.)
            neg=max((similarity(desc,d) for d in negative),default=-1.)
            explicit=any(label and np.array_equal(mask,m) for m,_,label in seeds)
            excluded=any(not label and (mask&m).sum()/max(1,min(mask.sum(),m.sum()))>.5 for m,_,label in seeds)
            if not excluded and (explicit or pos>=similarity_threshold and pos+negative_margin>=neg):chosen.append(mask);qualities.append(quality)
        candidates,scores=chosen,qualities
    result=filter_proposals(candidates,protected,min_area=min_area)[:max_objects]
    engine.last_proposal_scores=[]
    for mask in result:
        overlaps=[float((mask&m).sum())/max(1,float((mask|m).sum())) for m in candidates]
        score=scores[int(np.argmax(overlaps))] if overlaps else None
        engine.last_proposal_scores.append(score)
    _check(cancel)
    return result
