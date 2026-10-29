"""Dtype-preserving spatial restoration, synthetic noise and retained crop patches."""
from __future__ import annotations
import copy,math,uuid
import numpy as np
from .domain import pack_array,unpack_array,pack_mask,unpack_mask
from .processing import cast_like,bounding_box

from .denoise_config import METHODS


def add_signal_noise(raw, method, params, target):
    """Add residual noise in signal units, without replacing a narrow signal by dtype-scale noise."""
    a=np.asarray(raw);output=a.copy();rng=np.random.default_rng(params['seed'])
    channels=[None] if a.ndim==2 else range(min(3,a.shape[-1]))
    for channel in channels:
        source=a if channel is None else a[...,channel]
        values=source.astype(np.float64)
        mode=params.get('scale','image_range')
        if mode=='dtype_range' and a.dtype.kind in 'iu':
            info=np.iinfo(a.dtype);low=float(info.min);span=float(info.max)-low
        elif mode=='data_units':low=0.;span=1.
        else:
            low,high=np.percentile(values,[.5,99.5]);span=float(high-low)
            if span<=0:low=min(0.,float(low));span=max(1.,abs(float(values.flat[0])))
        if method=='Gaussian noise':
            result=values+rng.normal(0,float(params['sigma'])*span,values.shape)
        else:
            rate=np.maximum((values-low)/span,0)*params['peak_counts']
            residual=(rng.poisson(rate)-rate)/params['peak_counts']
            result=values+params['strength']*span*residual
        dest=output if channel is None else output[...,channel]
        dest[target]=cast_like(result[target],a.dtype)
    return output


def parameters(method,values=None):
    if method not in METHODS:raise ValueError('Unknown processing method.')
    spec=METHODS[method];result={k:v['default'] for k,v in spec.items()}
    for key,value in (values or {}).items():
        if key not in spec:raise ValueError('Unknown parameter: '+key)
        definition=spec[key];default=definition['default']
        if 'choices' in definition:
            if value not in definition['choices']:raise ValueError(key+' has an unsupported option.')
        elif isinstance(default,bool):
            if not isinstance(value,(bool,np.bool_)):raise ValueError(key+' must be true or false.')
        elif isinstance(default,(int,float)):
            if isinstance(value,bool) or not isinstance(value,(int,float,np.number)) or not math.isfinite(float(value)) or not definition['min']<=value<=definition['max']:raise ValueError(f'{key} must be between {definition["min"]} and {definition["max"]}.')
            if isinstance(default,int) and int(value)!=value:raise ValueError(key+' must be an integer.')
            value=int(value) if isinstance(default,int) else float(value)
        elif not isinstance(value,str):raise ValueError(key+' must be text.')
        result[key]=value
    for key in ('kernel_size','roi_size'):
        if key in result and result[key]%2!=1:raise ValueError(key+' must be an odd integer.')
    if method=='Non-local means' and result['patch_size']%2!=1:raise ValueError('patch_size must be odd for NLM.')
    if method in ('Noise2Void','N2V2'):
        if result['run_mode']=='train' and result['patch_size']**2*result['masked_pixel_percentage']/100<1:raise ValueError('Increase patch_size or masked_pixel_percentage: at least one masked pixel per patch is required.')
        if result['patch_size']%(2**result['depth']):raise ValueError('Patch size must be divisible by 2^depth.')
        if result['tile_size']%(2**result['depth']):raise ValueError('Prediction tile size must be divisible by 2^depth.')
        if result['tile_overlap']%2:raise ValueError('Tile overlap must be an even integer.')
        if result['tile_overlap']>=result['tile_size']/2:raise ValueError('Tile overlap must be less than half the tile size.')
        if result['run_mode']=='predict' and not result['model_path']:raise ValueError('Choose a trained model path in Predict mode.')
    return result


def process_pixels(raw,method,values=None,target=None,progress=None,cancel=None):
    import cv2
    from skimage import restoration
    a=np.asarray(raw)
    if a.dtype.kind not in 'buif' or not np.isfinite(a).all():raise ValueError('Processing requires finite real-valued pixels.')
    p=parameters(method,values)
    if a.ndim not in (2,3) or a.ndim==3 and a.shape[2] not in (3,4):raise ValueError('Expected grayscale, RGB or RGBA pixels.')
    mask=np.ones(a.shape[:2],bool) if target is None else np.asarray(target,bool)
    if mask.shape!=a.shape[:2] or not mask.any():raise ValueError('Choose a nonempty processing region.')
    if method in ('Gaussian noise','Poisson noise'):
        if cancel and cancel.is_set():raise InterruptedError('Processing cancelled.')
        return add_signal_noise(a,method,p,mask)
    work=a[...,:3] if a.ndim==3 else a
    if a.dtype.kind in 'bu':low=0.;high=1. if a.dtype.kind=='b' else float(np.iinfo(a.dtype).max)
    elif a.dtype.kind=='i':low=float(np.iinfo(a.dtype).min);high=float(np.iinfo(a.dtype).max)
    else:low,high=(0.,1.) if work.min()>=0 and work.max()<=1 else (float(work.min()),float(work.max()))
    span=high-low if high>low else 1.
    unit=np.clip((work.astype(float)-low)/span,0,1)
    if method in ('Noise2Void','N2V2'):
        from .neural_denoising import prepare_model_directory
        p=prepare_model_directory(p)
    channels=[unit] if a.ndim==2 else [unit[...,c] for c in range(3)]
    outputs=[];rng=np.random.default_rng(p.get('seed',0))
    for index,x in enumerate(channels):
        if cancel and cancel.is_set():raise InterruptedError('Processing cancelled.')
        if progress:progress(f'{method}: channel {index+1}/{len(channels)}')
        if method=='TV restoration':y=restoration.denoise_tv_chambolle(x,weight=p['weight'],eps=p['tolerance'],max_num_iter=p['iterations'])
        elif method=='TV Bregman restoration':y=restoration.denoise_tv_bregman(x,weight=p['weight'],max_num_iter=p['iterations'],eps=p['tolerance'],isotropic=p['isotropic'])
        elif method=='Wavelet sparse restoration':
            import pywt
            levels=min(p['levels'],pywt.dwtn_max_level(x.shape,p['wavelet']))
            if levels<1:raise ValueError('The image is too small for a db2 wavelet decomposition.')
            sigma=float(restoration.estimate_sigma(x,channel_axis=None)) if p['estimate_sigma'] else p['sigma']
            y=restoration.denoise_wavelet(x,sigma=sigma,wavelet=p['wavelet'],wavelet_levels=levels,method=p['threshold_rule'],mode=p['threshold_mode'],rescale_sigma=True)
        elif method=='Non-local means':y=restoration.denoise_nl_means(x,h=p['strength'],sigma=p['sigma'],patch_size=p['patch_size'],patch_distance=p['search_distance'],fast_mode=p['fast_mode'],preserve_range=True)
        elif method=='Bilateral denoise':y=restoration.denoise_bilateral(x,sigma_color=p['sigma_color'],sigma_spatial=p['sigma_spatial'],channel_axis=None)
        elif method=='Median denoise':
            from scipy.ndimage import median_filter
            y=median_filter(x,size=p['kernel_size'],mode='reflect')
        elif method=='Gaussian smooth':y=cv2.GaussianBlur(x,(p['kernel_size'],)*2,p['sigma'],borderType=cv2.BORDER_REFLECT_101)
        elif method in ('DCT sparsity','TV iterative (notebook)'):
            from .compressed_sensing import iterative_restore
            y=iterative_restore(x,method,p,progress,cancel)
        elif method=='Sparse dictionary learning':
            from .sparse_denoising import dictionary_denoise
            y=dictionary_denoise(x,p,progress,cancel)
        elif method=='BM3D':
            from .sparse_denoising import bm3d_denoise
            y=bm3d_denoise(x,p,progress,cancel)
        elif method in ('Noise2Void','N2V2'):
            from .neural_denoising import neural_denoise
            y=neural_denoise(x,method,p,index,progress,cancel)
        elif method=='Gaussian noise':y=x+rng.normal(0,p['sigma'],x.shape)
        elif method=='Poisson noise':y=rng.poisson(np.clip(x,0,1)*p['peak_counts'])/p['peak_counts']
        else:
            y=x.copy();draw=rng.random(x.shape);y[draw<p['amount']/2]=0;y[(draw>=p['amount']/2)&(draw<p['amount'])]=1
        outputs.append(y)
    processed=outputs[0] if a.ndim==2 else np.stack(outputs,axis=-1)
    restored=cast_like(np.clip(processed,0,1)*span+low,a.dtype)
    output=a.copy()
    if a.ndim==3:output[...,:3][mask]=restored[mask]
    else:output[mask]=restored[mask]
    if cancel and cancel.is_set():raise InterruptedError('Processing cancelled.')
    return output

def processing_target(doc,selected=None):
    target=np.ones(doc.frame.shape,bool) if selected is None else np.asarray(selected,bool).copy()
    if target.shape!=doc.frame.shape:raise ValueError('Processing region dimensions do not match.')
    target&=~doc.removed
    for crop in doc.detached_crops:
        if crop.get('protected') and not crop.get('pasted'):
            x,y,w,h=crop['bbox'];target[y:y+h,x:x+w]=False
    if not target.any():raise ValueError('No unprotected pixels remain. Restore/fill removed regions or release retained crops.')
    return target

def apply_processing(doc,result,target,method,params):
    obj=doc.apply_image_smoothing(result,target,method,params)
    obj.name=method+' '+str(obj.cleaning['sequence']).zfill(3)
    doc.cleaning_history[-1]['operation']='image_processing'
    return obj

def retain_crop(doc,mask,name=None,protect=True,padding=3):
    if isinstance(padding,bool) or int(padding)!=padding or not 0<=padding<=100:raise ValueError('Crop padding must be 0 to 100 pixels.')
    mask=np.asarray(mask,bool)
    if mask.shape!=doc.frame.shape or not mask.any():raise ValueError('Select an area or one or more masks to crop.')
    x,y,w,h=bounding_box(mask);pad=int(padding);x2=min(doc.frame.shape[1],x+w+pad);y2=min(doc.frame.shape[0],y+h+pad);x=max(0,x-pad);y=max(0,y-pad)
    source=doc.working if doc.working is not None else doc.frame.raw
    record={'id':str(uuid.uuid4()),'name':name or f'Crop {len(doc.detached_crops)+1}', 'bbox':[x,y,x2-x,y2-y],
            'mask':pack_mask(mask[y:y2,x:x2]),'pixels':pack_array(source[y:y2,x:x2]),'protected':bool(protect),'pasted':False,
            'coordinate_shape':list(doc.frame.shape),'rotation_count':len(doc.rotation),'padding':pad}
    doc.detached_crops.append(record)
    return record

def paste_crop(doc,ident,mask_only=False):
    record=next(c for c in doc.detached_crops if c['id']==ident)
    if record['coordinate_shape']!=list(doc.frame.shape) or record['rotation_count']!=len(doc.rotation):raise ValueError('Crop coordinates no longer match the image.')
    pixels=unpack_array(record['pixels']);x,y,w,h=record['bbox'];target=np.zeros(doc.frame.shape,bool)
    target[y:y+h,x:x+w]=unpack_mask(record['mask']) if mask_only else True
    output=(doc.working if doc.working is not None else doc.frame.raw).copy()
    patch=output[y:y+h,x:x+w];local=target[y:y+h,x:x+w];patch[local]=pixels[local]
    # Pasting restores a filled pixel region, including any prior pending removal.
    if (target&doc.removed).any():doc.apply_cleaning_fill(output,target&doc.removed,'retained crop')
    apply_processing(doc,output,target,'Paste retained crop',{'crop_id':ident,'mask_only':bool(mask_only)})
    record['pasted']=True;record['protected']=False
    return output
