"""Real SPORCO dictionary learning and the official BM3D backend."""
from __future__ import annotations
import numpy as np


def check(cancel):
    if cancel and cancel.is_set():raise InterruptedError('Denoising cancelled.')


def dictionary_denoise(plane,p,progress=None,cancel=None):
    from sporco.dictlrn import bpdndl
    from sporco.admm import bpdn
    n=p['patch_size'];h,w=plane.shape
    if min(h,w)<n:raise ValueError('Dictionary patch size must fit the image.')
    if p['patch_stride']>n:raise ValueError('Patch stride must not exceed patch size.')
    if p['training_patches']<p['dictionary_atoms']:raise ValueError('Use at least as many training patches as dictionary atoms.')
    ys=list(range(0,h-n+1,p['patch_stride']));xs=list(range(0,w-n+1,p['patch_stride']))
    if ys[-1]!=h-n:ys.append(h-n)
    if xs[-1]!=w-n:xs.append(w-n)
    locations=[(y,x) for y in ys for x in xs]
    rng=np.random.default_rng(p['random_seed'])
    chosen=rng.choice(len(locations),min(p['training_patches'],len(locations)),replace=False)
    patches=np.stack([plane[y:y+n,x:x+n].ravel() for y,x in (locations[int(i)] for i in chosen)],axis=1).astype(np.float32)
    patches-=patches.mean(axis=0,keepdims=True)
    initial=rng.standard_normal((n*n,p['dictionary_atoms'])).astype(np.float32)
    initial-=initial.mean(axis=0,keepdims=True)
    initial/=np.maximum(np.linalg.norm(initial,axis=0,keepdims=True),1e-8)
    iteration=[0]
    def callback(solver):
        check(cancel);iteration[0]+=1
        if progress:progress(f'Dictionary learning: {iteration[0]}/{p["dictionary_iterations"]}')
        return False
    options=bpdndl.BPDNDictLearn.Options({'Verbose':False,'MaxMainIter':p['dictionary_iterations'],'Callback':callback,
        'BPDN':{'MaxMainIter':p['coding_iterations'],'RelStopTol':1e-3},
        'CMOD':{'MaxMainIter':p['coding_iterations'],'RelStopTol':1e-3,'ZeroMean':True}})
    learner=bpdndl.BPDNDictLearn(initial,patches,p['regularization'],options)
    check(cancel);learner.solve();dictionary=learner.getdict()
    output=np.zeros((h,w),float);weights=np.zeros((h,w),float)
    for start in range(0,len(locations),p['inference_batch']):
        check(cancel);batch=locations[start:start+p['inference_batch']]
        values=np.stack([plane[y:y+n,x:x+n].ravel() for y,x in batch],axis=1).astype(np.float32)
        means=values.mean(axis=0,keepdims=True)
        solver=bpdn.BPDN(dictionary,values-means,p['regularization'],bpdn.BPDN.Options({'Verbose':False,'MaxMainIter':p['coding_iterations'],'RelStopTol':1e-3}))
        restored=dictionary@solver.solve()+means
        for i,(y,x) in enumerate(batch):output[y:y+n,x:x+n]+=restored[:,i].reshape(n,n);weights[y:y+n,x:x+n]+=1
        if progress:progress(f'Sparse coding: {min(start+len(batch),len(locations))}/{len(locations)} patches')
    check(cancel)
    return output/np.maximum(weights,1)


def bm3d_denoise(plane,p,progress=None,cancel=None):
    import bm3d
    check(cancel)
    profile=bm3d.BM3DProfile() if p['profile']=='np' else bm3d.BM3DProfileLC()
    profile.num_threads=p['num_threads']
    stage=bm3d.BM3DStages.ALL_STAGES if p['stage']=='all' else bm3d.BM3DStages.HARD_THRESHOLDING
    if progress:progress('Running BM3D '+p['profile']+' profile…')
    h,w=plane.shape
    # The native backend can crash on a block-sized 8x8 image. Give it safe
    # spatial context for tiny inputs, then remove only the added padding.
    safe=np.pad(np.asarray(plane,float),((0,max(0,32-h)),(0,max(0,32-w))),mode='reflect')
    result=bm3d.bm3d(safe,sigma_psd=p['sigma'],profile=profile,stage_arg=stage)
    check(cancel)
    return np.asarray(result)[:h,:w]
