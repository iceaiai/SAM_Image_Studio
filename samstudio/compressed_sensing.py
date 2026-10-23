"""Notebook-compatible sampled reconstruction and relaxed full-image denoising."""
from __future__ import annotations
import numpy as np
from scipy import ndimage
from scipy.fft import dctn, idctn


def sampling_mask(shape, fraction=.10, method='random', seed=7):
    h, w = shape; count = max(1, round(float(fraction) * h * w))
    mask = np.zeros(h * w, bool)
    if method == 'random':
        mask[np.random.default_rng(seed).choice(h*w, count, replace=False)] = True
    elif method == 'grid':
        rows = max(1, round(np.sqrt(count*h/w))); cols = max(1, round(count/rows))
        mask.reshape(h, w)[np.ix_(np.linspace(0,h-1,rows,dtype=int), np.linspace(0,w-1,cols,dtype=int))] = True
    else:
        raise ValueError('Sampling method must be random or grid.')
    return mask.reshape(h, w)


def fidelity_update(residual, loss, delta):
    if loss == 'l2':return residual
    if loss == 'l1':return delta*np.sign(residual)
    if loss == 'huber':return np.clip(residual, -delta, delta)
    raise ValueError('Data loss must be l2, l1 or huber.')


def iterative_restore(plane, method, p, progress=None, cancel=None):
    """Process one [0,1] plane. Reconstruction uses exact notebook updates."""
    import cv2
    original_shape = plane.shape
    observed = np.asarray(plane, np.float32)
    limit = p['max_side']
    if limit and max(observed.shape) > limit:
        factor = limit/max(observed.shape)
        observed = cv2.resize(observed, (max(1,round(observed.shape[1]*factor)),max(1,round(observed.shape[0]*factor))), interpolation=cv2.INTER_AREA)
    reconstruct = p['task']=='reconstruct'
    mask = sampling_mask(observed.shape, p['sample_fraction'], p['sampling_method'], p['random_seed']) if reconstruct else np.ones(observed.shape,bool)
    if reconstruct and p['initialization']=='nearest':
        indices=ndimage.distance_transform_edt(~mask,return_distances=False,return_indices=True)
        estimate=observed[indices[0],indices[1]].copy()
    elif reconstruct:
        estimate=np.where(mask,observed,0).astype(np.float32)
    else:
        estimate=observed.copy()
    keep_count=max(1,round(p.get('sparsity_fraction',.08)*observed.size))
    for iteration in range(p['iterations']):
        if cancel and cancel.is_set():raise InterruptedError('Iterative restoration cancelled.')
        if progress and (iteration==0 or (iteration+1)%5==0):progress(f'{method}: iteration {iteration+1}/{p["iterations"]}')
        if method=='DCT sparsity':
            coefficients=dctn(estimate,axes=(-2,-1),norm='ortho')
            threshold=np.partition(np.abs(coefficients).ravel(),-keep_count)[-keep_count]
            proposal=idctn(coefficients*(np.abs(coefficients)>=threshold),axes=(-2,-1),norm='ortho')
        else:
            gx=np.diff(estimate,axis=-1,append=estimate[...,-1:])
            gy=np.diff(estimate,axis=-2,append=estimate[...,-1:,:])
            magnitude=np.sqrt(gx**2+gy**2+p['gradient_epsilon'])
            dx,dy=gx/magnitude,gy/magnitude
            divergence=dx.copy();divergence[...,1:]-=dx[...,:-1]
            divergence+=dy;divergence[...,1:,:]-=dy[...,:-1,:]
            proposal=np.clip(estimate+p['tv_step']*divergence,0,1)
        residual=observed[mask]-proposal[mask]
        strength=1. if reconstruct else p['fidelity_step']
        proposal[mask]+=strength*fidelity_update(residual,p['data_loss'],p['huber_delta'])
        estimate=np.clip(proposal,0,1)
    if estimate.shape!=original_shape:
        estimate=cv2.resize(estimate,(original_shape[1],original_shape[0]),interpolation=cv2.INTER_LINEAR)
    return estimate
