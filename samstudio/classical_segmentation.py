"""Configurable Otsu foreground extraction and marker-controlled watershed."""
from __future__ import annotations
import numpy as np
from scipy import ndimage as ndi
from skimage import filters, morphology, segmentation, feature
from .denoise_config import P

WATERSHED_PARAMETERS={
    'polarity':P('auto',choices=['auto','bright','dark'],help='Which side of the Otsu threshold contains objects. Auto estimates background from the image border.',recommended='bright for bright STEM particles; dark for dark TEM particles. Override auto if it selects gaps/background.'),
    'gaussian_sigma':P(1.5,0.,20.,.5,help='Gaussian smoothing sigma in image pixels before Otsu thresholding.',recommended='Start 1-2; increase gently for noisy boundaries.'),
    'threshold_offset':P(0.,-.5,.5,.01,help='Offset added to Otsu threshold, as a fraction of the observed intensity range.',recommended='0 initially. Positive offsets shrink bright foreground and expand dark foreground.'),
    'minimum_area':P(20,1,10000000,10,help='Minimum foreground component and final object area, in image pixels.',recommended='Set below the smallest real particle, above isolated noise.'),
    'opening_radius':P(0,0,30,1,help='Optional binary opening disk radius, in pixels. Zero disables opening.',recommended='0-2; strong opening removes thin/small structures.'),
    'fill_holes':P(True,help='Fill holes in the foreground before distance-transform splitting.',recommended='True for solid particles; false when cavities are meaningful.'),
    'seed_distance':P(12,1,512,1,help='Minimum separation between distance-transform seed maxima, in pixels.',recommended='Increase to reduce over-splitting; decrease to separate nearby small particles.'),
    'seed_height':P(2.,0.,256.,.5,help='Minimum distance to background for an eligible seed, in pixels.',recommended='2 initially; keep below the radius of the smallest target.'),
    'distance_sigma':P(1.,0.,10.,.5,help='Smoothing sigma for the distance map before finding seeds.',recommended='0.5-2 to reduce noisy extra seeds.'),
    'compactness':P(0.,0.,1.,.001,help='Watershed compactness penalty. Zero follows the distance map without a shape prior.',recommended='0 initially; compare 0.001-0.01 for approximately compact particles.'),
    'watershed_line':P(False,help='Leave a one-pixel boundary between touching labels.',recommended='False for complete instance masks; true for visibly separated boundaries.'),
    'maximum_objects':P(300,1,3000,50,help='Maximum masks returned to preview, largest first. Each full-size mask uses memory.',recommended='300 initially. Increase only when needed and sufficient RAM is available.'),
}


def watershed_masks(raw, values=None, roi=None, progress=None, cancel=None):
    from .inference import check_cancel
    from .processing import display_rgb
    p={k:s['default'] for k,s in WATERSHED_PARAMETERS.items()};p.update(values or {})
    if set(p)!=set(WATERSHED_PARAMETERS):raise ValueError('Unknown watershed parameter.')
    for key,s in WATERSHED_PARAMETERS.items():
        v=p[key]
        if 'choices' in s and v not in s['choices']:raise ValueError('Invalid '+key)
        if 'min' in s and (not np.isfinite(v) or not s['min']<=v<=s['max']):raise ValueError('Invalid '+key)
    rgb=display_rgb(raw);plane=rgb.mean(axis=2).astype(np.float32)/255
    allowed=np.ones(plane.shape,bool) if roi is None else np.asarray(roi,bool)
    if allowed.shape!=plane.shape or not allowed.any():raise ValueError('Choose a nonempty watershed region.')
    check_cancel(cancel)
    if progress:progress('Otsu: smoothing and finding foreground…')
    smooth=ndi.gaussian_filter(plane,p['gaussian_sigma']) if p['gaussian_sigma'] else plane
    if np.ptp(smooth[allowed])<1e-7:return [],{'reason':'Image/ROI has no usable intensity contrast.','count':0}
    threshold=float(filters.threshold_otsu(smooth[allowed]))+p['threshold_offset']
    polarity=p['polarity']
    if polarity=='auto':
        border=np.zeros(allowed.shape,bool);border[[0,-1],:]=True;border[:,[0,-1]]=True
        samples=smooth[border&allowed]
        background=float(np.median(samples)) if samples.size else float(np.median(smooth[allowed]))
        polarity='bright' if background<threshold else 'dark'
    foreground=((smooth>threshold) if polarity=='bright' else (smooth<threshold))&allowed
    foreground=morphology.remove_small_objects(foreground,max_size=max(0,int(p['minimum_area'])-1))
    if p['opening_radius']:foreground=morphology.binary_opening(foreground,morphology.disk(int(p['opening_radius'])))
    if p['fill_holes']:foreground=ndi.binary_fill_holes(foreground)&allowed
    check_cancel(cancel)
    if progress:progress('Watershed: distance map and instance seeds…')
    distance=ndi.distance_transform_edt(foreground)
    seeds=ndi.gaussian_filter(distance,p['distance_sigma']) if p['distance_sigma'] else distance
    peaks=feature.peak_local_max(seeds,min_distance=int(p['seed_distance']),threshold_abs=p['seed_height'],exclude_border=False,labels=foreground.astype(np.uint8))
    markers=np.zeros(plane.shape,np.int32)
    for i,(y,x) in enumerate(peaks,1):markers[y,x]=i
    labels=segmentation.watershed(-distance,markers,mask=foreground,compactness=p['compactness'],watershed_line=p['watershed_line'])
    check_cancel(cancel)
    counts=np.bincount(labels.ravel());ids=np.flatnonzero(counts>=p['minimum_area']);ids=ids[ids!=0]
    ids=sorted(ids,key=lambda i:int(counts[i]),reverse=True)[:int(p['maximum_objects'])]
    # Guard excessive preview allocations on large microscopy frames.
    if len(ids)*plane.size>1_500_000_000:raise ValueError('Preview masks would exceed 1.5 GB. Reduce maximum objects or use a smaller ROI/image.')
    masks=[labels==i for i in ids]
    return masks,{'polarity':polarity,'otsu_threshold':threshold,'seed_count':len(peaks),'count':len(masks),'parameters':p}
