"""CAREamics Noise2Void/N2V2 training and inference on independent image planes."""
from __future__ import annotations
import json, os, uuid
from pathlib import Path
import numpy as np


def prepare_model_directory(parameters):
    p=dict(parameters)
    if p['run_mode']=='train' and not p['output_directory']:
        from .inference import data_directory
        p['output_directory']=str(data_directory()/'denoise_models'/uuid.uuid4().hex)
    return p


def neural_denoise(plane,method,p,channel=0,progress=None,cancel=None):
    from .inference import initialize_torch_runtime
    torch=initialize_torch_runtime()
    from careamics import CAREamist
    from careamics.config.factories import create_advanced_n2v_config
    from lightning.pytorch.callbacks import Callback
    device=p['device']
    if device=='auto':device='cuda' if os.environ.get('CONDA_PREFIX') and torch.cuda.is_available() else 'cpu'
    if device=='cuda' and not os.environ.get('CONDA_PREFIX'):raise ValueError('GPU denoising requires a dedicated Conda environment.')
    if device=='cuda' and not torch.cuda.is_available():raise ValueError('CUDA is unavailable for denoising.')
    if cancel and cancel.is_set():raise InterruptedError('Blind-spot denoising cancelled.')
    class Monitor(Callback):
        def on_train_batch_end(self,trainer,*args,**kwargs):
            if cancel and cancel.is_set():raise InterruptedError('Blind-spot training cancelled.')
            if progress:progress(f'{method}: channel {channel+1}, epoch {trainer.current_epoch+1}/{p["epochs"]}, step {trainer.global_step}')
        def on_predict_batch_end(self,*args,**kwargs):
            if cancel and cancel.is_set():raise InterruptedError('Blind-spot prediction cancelled.')
    data=np.ascontiguousarray(plane,dtype=np.float32)
    if p['run_mode']=='train':
        if min(data.shape)<p['patch_size']:raise ValueError('The training patch must fit the image. Reduce patch_size.')
        root=Path(p['output_directory']).expanduser().resolve()/f'channel_{channel}'
        if (root/'samstudio_model.json').exists():raise ValueError('This output directory already contains a model for this channel. Choose a fresh directory or Predict mode.')
        root.mkdir(parents=True,exist_ok=True)
        config=create_advanced_n2v_config(
            experiment_name='samstudio_n2v2' if method=='N2V2' else 'samstudio_n2v',
            data_type='array',axes='YX',patch_size=(p['patch_size'],)*2,batch_size=p['batch_size'],
            num_epochs=p['epochs'],num_steps=p['steps_per_epoch'],n_val_patches=p['validation_patches'],
            use_n2v2=method=='N2V2',roi_size=p['roi_size'],masked_pixel_percentage=p['masked_pixel_percentage'],
            num_workers=0,normalization='mean_std',seed=p['random_seed'],
            model_params={'depth':p['depth'],'num_channels_init':p['initial_filters'],'use_batch_norm':False},
            optimizer_params={'lr':p['learning_rate']},logger='none',
            checkpoint_params={'every_n_epochs':1,'save_top_k':0,'save_last':True},
            trainer_params={'accelerator':'gpu' if device=='cuda' else 'cpu','devices':1,
                            'num_sanity_val_steps':0,'enable_model_summary':False,'enable_progress_bar':False})
        restorer=CAREamist(config,work_dir=root,callbacks=[Monitor()],enable_progress_bar=False)
        restorer.train(train_data=data)
        checkpoint=root/'samstudio_model.ckpt'
        restorer.trainer.save_checkpoint(str(checkpoint))
        prediction_checkpoint=checkpoint
        (root/'samstudio_model.json').write_text(json.dumps({'method':method,'checkpoint':checkpoint.name,
            'channel':channel,'input':'float32 normalized spatial plane; CAREamics per-image mean/std',
            'parameters':p,'trained':True},indent=2)+'\n')
        if progress:progress('Trained '+method+' model: '+str(checkpoint))
    else:
        path=Path(p['model_path']).expanduser()
        if path.is_dir():
            root=path/f'channel_{channel}' if (path/f'channel_{channel}').is_dir() else path
            metadata=root/'samstudio_model.json'
            if not metadata.is_file():raise ValueError('Select a CAREamics .ckpt or a saved SAM Studio model directory.')
            record=json.loads(metadata.read_text())
            if record['method']!=method:raise ValueError('The saved model variant does not match the selected Noise2Void/N2V2 method.')
            path=root/record['checkpoint']
        if not path.is_file():raise ValueError('Select an existing trained CAREamics checkpoint.')
        prediction_checkpoint=path
        restorer=CAREamist(checkpoint_path=path,work_dir=path.parent,callbacks=[Monitor()],enable_progress_bar=False)
        if bool(restorer.config.algorithm_config.model.n2v2)!=(method=='N2V2'):raise ValueError('The checkpoint variant does not match Noise2Void/N2V2.')
        # Rebuild its runtime Trainer with the requested device; the loaded configuration
        # records model/data settings, while this explicit selection controls execution.
        import lightning.pytorch as pl
        restorer.trainer=pl.Trainer(accelerator='gpu' if device=='cuda' else 'cpu',devices=1,
            callbacks=[Monitor()],logger=False,enable_progress_bar=False,enable_model_summary=False)
    if cancel and cancel.is_set():raise InterruptedError('Blind-spot denoising cancelled.')
    arrays,_=restorer.predict(data,axes='YX',data_type='array',batch_size=1,
        tile_size=(p['tile_size'],)*2,tile_overlap=(p['tile_overlap'],)*2,num_workers=0,checkpoint=str(prediction_checkpoint))
    if len(arrays)!=1:raise ValueError('The blind-spot backend returned an unexpected number of images.')
    result=np.asarray(arrays[0],dtype=np.float32).reshape(data.shape)
    if not np.isfinite(result).all():raise ValueError('The trained model returned nonfinite pixels.')
    if cancel and cancel.is_set():raise InterruptedError('Blind-spot denoising cancelled.')
    return result
