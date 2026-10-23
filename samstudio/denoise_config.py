"""Public processing controls and the explanations used by GUI and manuals."""
from __future__ import annotations
import copy, html


def P(default, low=None, high=None, step=1, *, choices=None, help='', recommended=''):
    p={'default':default,'help':help,'recommended':recommended}
    if low is not None:p.update(min=low,max=high,step=step)
    if choices is not None:p['choices']=list(choices)
    return p


METHODS={
 'TV restoration':{
  'weight':P(.08,.0001,2.,.01,help='Chambolle TV regularization weight on normalized intensities. Larger weights smooth more. This is not the notebook TV iteration step.',recommended='Start 0.03-0.12; compare particle boundaries and texture.'),
  'iterations':P(100,1,2000,1,help='Maximum Chambolle iterations; convergence may stop earlier.',recommended='100; increase to 200 if convergence is incomplete.'),
  'tolerance':P(.0002,.000001,.1,.0001,help='Relative change stopping tolerance passed as eps.',recommended='0.0002; smaller values take longer.')},
 'TV Bregman restoration':{
  'weight':P(5.,.01,100.,.5,help='Split-Bregman fidelity weight. Its convention is inverse to denoising strength: smaller values smooth more. It is not interchangeable with Chambolle weight.',recommended='Start 2-10, default 5.'),
  'iterations':P(100,1,2000,1,help='Maximum Split-Bregman iterations.',recommended='100-200.'),
  'tolerance':P(.001,.000001,.1,.0001,help='Absolute change tolerance (eps).',recommended='0.001.'),
  'isotropic':P(True,help='Use isotropic TV; false uses directional anisotropic TV.',recommended='True for general particle outlines.')},
 'Wavelet sparse restoration':{
  'sigma':P(.04,0.,1.,.005,help='Gaussian noise standard deviation in normalized intensity units; ignored when estimate_sigma is enabled.',recommended='Estimate sigma first; otherwise try 0.01-0.08.'),
  'estimate_sigma':P(False,help='Estimate Gaussian sigma from high-frequency wavelet coefficients.',recommended='Enable for a first comparison when noise level is unknown.'),
  'levels':P(2,1,6,1,help='Requested decomposition depth, capped by image size and wavelet support.',recommended='1-3; default 2.'),
  'wavelet':P('db2',choices=['db2','haar','sym4','coif1'],help='PyWavelets wavelet family.',recommended='db2 or sym4; Haar is a simple edge-oriented baseline.'),
  'threshold_rule':P('BayesShrink',choices=['BayesShrink','VisuShrink'],help='Adaptive BayesShrink or universal VisuShrink threshold.',recommended='BayesShrink. VisuShrink often smooths more.'),
  'threshold_mode':P('soft',choices=['soft','hard'],help='Soft shrinks retained coefficients; hard only removes coefficients below threshold.',recommended='Soft for a conservative baseline; inspect ringing with hard.')},
 'Non-local means':{
  'strength':P(.08,.001,1.,.005,help='Filter bandwidth h in normalized intensity units. Larger values combine less-similar patches.',recommended='About 0.8-1.2 times a credible Gaussian sigma; compare 0.02-0.10.'),
  'sigma':P(.03,0.,1.,.005,help='Gaussian noise sigma used for patch-distance correction; zero disables this correction.',recommended='Use a measured/estimated value, typically 0.01-0.08.'),
  'patch_size':P(5,1,15,2,help='Odd square patch side in pixels.',recommended='3, 5 or 7; default 5.'),
  'search_distance':P(6,1,25,1,help='Search radius in pixels; comparisons cover a (2r+1) square neighborhood.',recommended='6-11 for repeated local structures.'),
  'fast_mode':P(True,help='Use scikit-image fast NLM; false uses the slower reference approach.',recommended='True for interactive work.')},
 'Bilateral denoise':{
  'sigma_color':P(.05,.001,1.,.005,help='Intensity similarity scale on normalized pixels.',recommended='0.02-0.10; smaller values preserve stronger edges.'),
  'sigma_spatial':P(3.,.1,20.,.5,help='Spatial Gaussian sigma in image pixels.',recommended='1-5; default 3.')},
 'Median denoise':{
  'kernel_size':P(3,1,31,2,help='Odd median window side in pixels. A kernel of 1 leaves the image unchanged.',recommended='3; use 5 only after checking small-particle loss.')},
 'DCT sparsity':{},
 'TV iterative (notebook)':{},
 'Sparse dictionary learning':{
  'patch_size':P(8,3,24,1,help='Square image patch side in pixels.',recommended='6-12; default 8.'),
  'dictionary_atoms':P(64,4,512,4,help='Number of dictionary columns. Larger dictionaries represent more patterns and can fit noise.',recommended='64-128 for 8x8 patches.'),
  'training_patches':P(2048,32,20000,32,help='Maximum randomly selected, mean-centered training patches.',recommended='1024-4096, with at least as many patches as atoms.'),
  'dictionary_iterations':P(10,1,100,1,help='Alternating SPORCO dictionary-learning iterations.',recommended='10-30; start with 10.'),
  'coding_iterations':P(30,1,500,1,help='Maximum ADMM iterations per sparse coding/update solve.',recommended='30-100.'),
  'regularization':P(.05,.0001,1.,.005,help='L1 coefficient penalty lambda for 0.5*||D*X-S||^2 + lambda*||X||_1.',recommended='0.02-0.10 after intensity normalization.'),
  'patch_stride':P(4,1,24,1,help='Inference patch spacing; it must not exceed patch_size. Edge patches are included.',recommended='Half the patch side; use 1 for more overlap at higher cost.'),
  'inference_batch':P(256,16,2048,16,help='Patches sparse-coded together. Controls working memory.',recommended='128-512.'),
  'random_seed':P(7,0,2147483647,1,help='Seed for initial dictionary and training-patch sampling.',recommended='7 for repeatable comparisons.')},
 'BM3D':{
  'sigma':P(.04,.0001,.5,.005,help='Gaussian noise standard deviation in normalized intensity units.',recommended='Estimate the noise; initially compare 0.01-0.08.'),
  'profile':P('np',choices=['np','lc'],help='Official bm3d normal profile or low-complexity profile.',recommended='np for the main comparison; lc for faster previews.'),
  'stage':P('all',choices=['all','hard'],help='Both hard-threshold/Wiener stages, or hard-threshold stage only.',recommended='all for final output.'),
  'num_threads':P(1,1,32,1,help='Native BM3D worker threads.',recommended='1-4; avoid oversubscribing other processing.')},
 'Noise2Void':{},
 'N2V2':{},
 'Gaussian smooth':{
  'kernel_size':P(5,1,101,2,help='Odd Gaussian window side in pixels.',recommended='3-7; default 5.'),
  'sigma':P(1.,.01,30.,.1,help='Spatial Gaussian sigma in pixels.',recommended='0.5-1.5; default 1.')},
 'Gaussian noise':{
  'sigma':P(.03,0.,1.,.005,help='Added Gaussian standard deviation in normalized intensity units.',recommended='0.01-0.05 for a controlled comparison.'),
  'seed':P(0,0,2147483647,1,help='Random generator seed.',recommended='Keep fixed when comparing denoisers.')},
 'Poisson noise':{
  'peak_counts':P(50.,1.,1000000.,5.,help='Synthetic Poisson counts at normalized intensity 1; lower counts mean more relative noise.',recommended='20-200 for demonstrations; this is not detector calibration.'),
  'seed':P(0,0,2147483647,1,help='Random generator seed.',recommended='Keep fixed for comparisons.')},
 'Salt and pepper noise':{
  'amount':P(.01,0.,1.,.005,help='Fraction of pixels replaced by minimum/maximum normalized intensity.',recommended='0.001-0.02.'),
  'seed':P(0,0,2147483647,1,help='Random generator seed.',recommended='Keep fixed for comparisons.')},
}
ITERATIVE={
 'task':P('denoise',choices=['denoise','reconstruct'],help='Denoise uses every input pixel with relaxed fidelity. Reconstruct simulates missing pixels using a sampling mask and hard notebook data consistency.',recommended='denoise for ordinary complete SEM/TEM images; reconstruct for sampling experiments.'),
 'iterations':P(40,1,1000,1,help='Number of prior/fidelity iterations.',recommended='40 as in the notebook; compare 20-100.'),
 'data_loss':P('l2',choices=['l2','l1','huber'],help='L2 uses residual; L1 uses delta*sign(residual); Huber clips residual to +/-delta.',recommended='l2 initially; compare huber for occasional large residuals.'),
 'fidelity_step':P(.20,0.,.99,.05,help='Denoise-only relaxation strength. The prior proposal is pulled partway toward the noisy input, not restored exactly.',recommended='0.1-0.4. Higher values retain more input noise; never 1 in denoise mode.'),
 'huber_delta':P(.05,.000001,1.,.005,help='Normalized residual update scale for L1 and Huber; ignored for L2.',recommended='0.05 as in the notebook; compare 0.01-0.10.'),
 'sample_fraction':P(.10,.001,1.,.01,help='Reconstruct-only fraction of observed pixel positions. Random sampling is without replacement. At 1 with L2, reconstruction returns the input.',recommended='0.10 for notebook comparison; this is not a denoising strength.'),
 'sampling_method':P('random',choices=['random','grid'],help='Reconstruct-only random positions or a regular grid; a single mask is shared by RGB channels.',recommended='random for the notebook preset.'),
 'random_seed':P(7,0,2147483647,1,help='Seed for reconstruct-mode sample positions.',recommended='7 for the notebook preset.'),
 'initialization':P('nearest',choices=['nearest','zeros'],help='Reconstruct-only missing-pixel initialization. Denoise always starts from the observed image.',recommended='nearest, matching the notebook.'),
 'max_side':P(0,0,4096,1,help='Optional processing resolution cap. 0 uses the native grid. A smaller cap downsamples before processing and interpolates the result back to the original grid.',recommended='0 for native-resolution SEM/TEM; 256 only for a notebook-resolution comparison.')}
METHODS['DCT sparsity']=copy.deepcopy(ITERATIVE)
METHODS['DCT sparsity']['sparsity_fraction']=P(.08,.001,1.,.01,help='Retained fraction of full-image 2D DCT coefficients. The hard threshold is recalculated each iteration; threshold ties can retain additional coefficients.',recommended='0.08 as in the notebook; compare 0.04-0.20. Inspect ringing and weak details.')
METHODS['TV iterative (notebook)']=copy.deepcopy(ITERATIVE)
METHODS['TV iterative (notebook)'].update({
 'tv_step':P(.01,.0001,.24,.01,help='Gradient-divergence iteration step; this is not a TV regularization lambda or Chambolle weight.',recommended='0.01 for denoising (compare 0.005-0.02). The reconstruction preset uses notebook step 0.08; large steps can oscillate.'),
 'gradient_epsilon':P(.000001,.000000001,.01,.000001,help='Positive value added inside sqrt(gx^2+gy^2+epsilon). Forward differences repeat the last row/column.',recommended='0.000001 as in the notebook.')})
N2V={
 'run_mode':P('train',choices=['train','predict'],help='Train a blind-spot model on noisy input, or load a previously saved CAREamics model.',recommended='train for a new image; predict only with a compatible trained model.'),
 'model_path':P('',help='CAREamics checkpoint path for predict mode. For RGB use a training-output directory with channel_0, channel_1 and channel_2 models.',recommended='Use the checkpoint/directory reported after training.'),
 'output_directory':P('',help='Optional directory for trained models. Empty uses the application model cache; RGB channels receive separate subdirectories.',recommended='Keep trained models outside source-image folders.'),
 'device':P('cpu',choices=['cpu','cuda','auto'],help='Training/inference device. CUDA is permitted only inside Conda; auto selects CUDA there when available.',recommended='cpu for a small trial; use a dedicated Conda GPU environment for larger runs.'),
 'epochs':P(30,1,1000,1,help='Maximum training epochs.',recommended='30-100 after a small interface trial; inspect validation behavior.'),
 'steps_per_epoch':P(20,1,2000,1,help='Training batches per epoch.',recommended='20-100; increasing this increases time and exposure to patches.'),
 'patch_size':P(64,16,512,4,help='Training patch side; must fit the image and be divisible by 2^depth.',recommended='64 or 128; use 32 for a small test.'),
 'batch_size':P(8,1,64,1,help='Training patches per batch.',recommended='4-16; reduce on limited GPU memory.'),
 'learning_rate':P(.0003,.000001,.01,.0001,help='Adam learning rate.',recommended='0.0001-0.001, default 0.0003.'),
 'masked_pixel_percentage':P(.2,.01,10.,.1,help='Percentage of training pixel positions masked for blind-spot loss; 0.2 means 0.2%, not 20%.',recommended='0.2-1.5; default follows CAREamics 0.2.'),
 'roi_size':P(11,3,31,2,help='Odd neighborhood side for blind-spot pixel replacement.',recommended='5-11; default 11.'),
 'depth':P(2,1,4,1,help='U-Net downsampling depth.',recommended='2 for a first trial; 3 for larger patches/data.'),
 'initial_filters':P(16,8,64,8,help='Initial U-Net channel count.',recommended='16-32.'),
 'validation_patches':P(8,1,128,1,help='Held-out validation patch count when the input is split automatically.',recommended='8-32. Same-image validation is not an independent microscopy accuracy study.'),
 'tile_size':P(256,32,2048,16,help='Prediction tile side, padded for small images.',recommended='256; larger tiles need more memory.'),
 'tile_overlap':P(32,0,256,4,help='Even-sized overlapping prediction context; must be smaller than half the tile side.',recommended='32 for tile 256.'),
 'random_seed':P(7,0,2147483647,1,help='Seed for training/patch selection. Backend/device differences can still affect numerical reproducibility.',recommended='7 for comparisons.')}
METHODS['Noise2Void']=copy.deepcopy(N2V);METHODS['N2V2']=copy.deepcopy(N2V)
DENOISE_METHODS=[name for name in METHODS if name not in ('Gaussian smooth','Gaussian noise','Poisson noise','Salt and pepper noise')]
LEARNING_METHODS={'Noise2Void','N2V2'}
METHOD_SUMMARY={
 'DCT sparsity':'Global per-channel 2D DCT with orthonormal normalization and iterative hard thresholding. No block DCT. Denoise uses relaxed fidelity; reconstruction reproduces the notebook update.',
 'TV iterative (notebook)':'Forward-difference isotropic TV gradient/divergence iteration from the notebook. Its step is distinct from the weight in Chambolle TV. Full sampling with hard L2 is a reconstruction identity, so denoise uses relaxation.',
 'Sparse dictionary learning':'SPORCO patch dictionary learning and L1 sparse coding, with patch means restored and overlapping patches averaged. Overtraining can fit noise or alter lattice features.',
 'BM3D':'Official bm3d collaborative patch filtering. Sigma assumes approximately additive Gaussian noise. The upstream backend has academic/non-commercial license terms; see the parameter guide and package license.',
 'Noise2Void':'Official CAREamics Noise2Void self-supervised blind-spot training/inference. Needs neither clean targets nor bundled pretrained weights. Pixelwise-independent noise assumptions can fail for SEM/TEM stripes or correlated noise.',
 'N2V2':'Official CAREamics N2V2 configuration, including its model/masking improvements. Training is a substantive operation; preview results require validation against microscopy features, not only training loss.'}


def parameter_html(method, key=None):
    spec=METHODS.get(method,{})
    text='<h2>'+html.escape(method)+'</h2><p>'+html.escape(METHOD_SUMMARY.get(method,'Spatial processing on normalized intensities. Inspect the preview before Apply.'))+'</p>'
    for name,p in spec.items():
        if key is not None and name!=key:continue
        text+='<h3>'+html.escape(name.replace('_',' '))+'</h3><p>'+html.escape(p['help'])+'</p><p><b>Default:</b> '+html.escape(str(p['default']))
        if 'choices' in p:text+='; <b>Options:</b> '+html.escape(', '.join(map(str,p['choices'])))
        elif 'min' in p:text+='; <b>Range:</b> '+str(p['min'])+' to '+str(p['max'])
        text+='</p><p><b>Suggested start:</b> '+html.escape(p['recommended'])+'</p>'
    return text
