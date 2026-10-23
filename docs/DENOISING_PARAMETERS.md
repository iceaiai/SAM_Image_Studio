# SAM Image Studio 1.4.2 - Denoising Parameter Guide

## Workflow and physical interpretation

Choose Processing > Denoise, select a method and review the controls. Each parameter has an in-dialog ? explanation. The side panel and this guide contain all exposed controls, defaults and suggested values. These are starting points for comparisons, not specimen-specific optimal settings. Defaults reload on each open or method change. Preview first; Apply creates a reversible image record. Keep the acquired source for comparison and save the native .sam.json for exact editable recovery.

Use whole image or selected region/object masks. Algorithms see the current full image as context, and final compositing changes only the target. Protected retained crop rectangles and pending removed pixels are excluded from Apply. Selecting a target does not train a neural model only inside that mask: training uses the full selected input image plane. To train only on a patch, export/open that patch first. Choose original pixels to process the uncleaned image in its current orientation.

Unsigned integers normalize to their full dtype range, signed integers to their full type range. Floating inputs already within [0,1] keep [0,1]; other finite floats normalize using observed min/max. All algorithm sigma/threshold/fidelity values refer to these normalized units. For example, sigma 0.04 means approximately 10.2 counts for uint8, or 2621.4 for uint16. If a uint16 detector only uses 0-4095, scale sigma by the full 65535 range or convert deliberately before processing; display brightness is not the processing normalization. Outputs clip to [0,1], then convert to the original type with integer rounding. RGB channels are independent spatial planes. Alpha and outside-target pixels remain exact. No automatic change to acquired image dimensions occurs.

For a first comparison, estimate noise in a plausibly uniform area, preserve a crop of fine details and try wavelet, NLM and TV. Repeated particles can benefit from patch methods. Gaussian-noise assumptions may be poor for shot noise, stripes, scan drift, correlated artifacts or dose-dependent contrast. Check particle area, edges and lattice features against original pixels; low training loss alone does not establish correctness. Synthetic tests in the validation report are algorithm checks, not universal SEM/TEM accuracy claims.

## DCT and TV: reconstruction versus denoising

Reconstruct simulates a sampling experiment from the input: one spatial mask, shared across RGB channels, retains a fraction of observed positions. Random sampling uses np.random.default_rng(seed), without replacement, with max(1, round(fraction*H*W)) positions. Grid sampling approximates the requested fraction and may have a slightly different count. Missing values initialize by nearest observed neighbor using a Euclidean distance transform, or zero. The notebook comparison uses random 10%, seed 7, nearest initialization and 40 iterations.

DCT uses scipy.fft.dctn/idctn with norm='ortho', axes=(-2,-1), over each full channel plane. It retains coefficients whose absolute value is at least the kth largest threshold, where k=max(1,round(sparsity_fraction*H*W)); ties can retain more than k. The threshold is recomputed every iteration. It is global hard thresholding, with no blocks. After inverse DCT, update observed positions and clip to [0,1].

Iterative TV uses forward horizontal/vertical differences with repeated final columns/rows (zero final forward difference). magnitude=sqrt(gx*gx+gy*gy+gradient_epsilon). Divide each gradient by magnitude, take the backward divergence and form clip(estimate+tv_step*divergence,0,1). Then apply data consistency and clip again. There is no separate lambda. tv_step is not the weight of denoise_tv_chambolle. Large explicit steps can oscillate; denoise defaults to 0.01, while the notebook reconstruction preset retains 0.08.

At sampled positions residual=observed-proposal. L2 update is residual, L1 update is delta*sign(residual), Huber update is clip(residual,-delta,delta). These reproduce the supplied notebook update rules; they are not interchangeable generic optimizer loss implementations. In reconstruction the update strength is one. Full-sampling L2 therefore returns the input and is not a denoiser. In Denoise every pixel participates but the update is multiplied by fidelity_step < 1, retaining a prior contribution. With L2 this is proposal=(1-eta)*prior+eta*observed. Denoise initializes from observed pixels and ignores sampling/initialization controls.

The Notebook reconstruction preset also sets a max-side cap of 256, without enlarging small images. The original notebook converted to RGB/float32 and divided uint8 by 255. Here native grayscale/RGB/uint16 inputs preserve their channel/dtype contract; unsigned-byte RGB has the same normalization. A cap uses area downsampling and linear interpolation back onto the original grid. This is a resolution experiment, not a claim of recovering original high-frequency detail. Leave max_side at 0 for native resolution. For full-sampling identity checks use cap 0.

## How to read each parameter entry

Default is the value restored when the dialog opens or the method changes. Range/options are accepted by the GUI and validator; a legal endpoint is not necessarily a sensible specimen setting. Suggested start provides a practical comparison range. Iteration counts are maxima for convergent library solvers and fixed counts for notebook DCT/TV. Spatial sizes are image pixels regardless of display zoom. Intensity quantities use normalized units described above. Disabled fields are retained for switching modes but ignored by that mode. Restore defaults clears custom parameter values without applying an image operation.


## TV restoration

Use as a baseline for relatively uniform particle regions. Higher weight removes more variation but can flatten gradients and introduce staircase-like appearance. scikit-image Chambolle TV is different from the explicit notebook TV loop.

### weight

Default: 0.08. Allowed range: 0.0001 to 2.0.

Chambolle TV regularization weight on normalized intensities. Larger weights smooth more. This is not the notebook TV iteration step.

Suggested start: Start 0.03-0.12; compare particle boundaries and texture.

### iterations

Default: 100. Allowed range: 1 to 2000.

Maximum Chambolle iterations; convergence may stop earlier.

Suggested start: 100; increase to 200 if convergence is incomplete.

### tolerance

Default: 0.0002. Allowed range: 1e-06 to 0.1.

Relative change stopping tolerance passed as eps.

Suggested start: 0.0002; smaller values take longer.


## TV Bregman restoration

This alternate TV solver uses the inverse weight convention. Lower weight increases smoothing. Do not transfer Chambolle weight values numerically.

### weight

Default: 5.0. Allowed range: 0.01 to 100.0.

Split-Bregman fidelity weight. Its convention is inverse to denoising strength: smaller values smooth more. It is not interchangeable with Chambolle weight.

Suggested start: Start 2-10, default 5.

### iterations

Default: 100. Allowed range: 1 to 2000.

Maximum Split-Bregman iterations.

Suggested start: 100-200.

### tolerance

Default: 0.001. Allowed range: 1e-06 to 0.1.

Absolute change tolerance (eps).

Suggested start: 0.001.

### isotropic

Default: True. Options: true / false.

Use isotropic TV; false uses directional anisotropic TV.

Suggested start: True for general particle outlines.


## Wavelet sparse restoration

Small coefficients are shrunk using PyWavelets/scikit-image. Sigma estimation assumes a high-frequency noise component; fine lattice structure can inflate it. Requested levels are capped by wavelet support/image size; too-small images produce a clear error.

### sigma

Default: 0.04. Allowed range: 0.0 to 1.0.

Gaussian noise standard deviation in normalized intensity units; ignored when estimate_sigma is enabled.

Suggested start: Estimate sigma first; otherwise try 0.01-0.08.

### estimate_sigma

Default: False. Options: true / false.

Estimate Gaussian sigma from high-frequency wavelet coefficients.

Suggested start: Enable for a first comparison when noise level is unknown.

### levels

Default: 2. Allowed range: 1 to 6.

Requested decomposition depth, capped by image size and wavelet support.

Suggested start: 1-3; default 2.

### wavelet

Default: db2. Options: db2, haar, sym4, coif1.

PyWavelets wavelet family.

Suggested start: db2 or sym4; Haar is a simple edge-oriented baseline.

### threshold_rule

Default: BayesShrink. Options: BayesShrink, VisuShrink.

Adaptive BayesShrink or universal VisuShrink threshold.

Suggested start: BayesShrink. VisuShrink often smooths more.

### threshold_mode

Default: soft. Options: soft, hard.

Soft shrinks retained coefficients; hard only removes coefficients below threshold.

Suggested start: Soft for a conservative baseline; inspect ringing with hard.


## Non-local means

Repeated local appearance supplies averaging evidence. Stronger filtering can merge genuinely different weak structures. Search radius increases computation. Fast and reference modes can differ numerically.

### strength

Default: 0.08. Allowed range: 0.001 to 1.0.

Filter bandwidth h in normalized intensity units. Larger values combine less-similar patches.

Suggested start: About 0.8-1.2 times a credible Gaussian sigma; compare 0.02-0.10.

### sigma

Default: 0.03. Allowed range: 0.0 to 1.0.

Gaussian noise sigma used for patch-distance correction; zero disables this correction.

Suggested start: Use a measured/estimated value, typically 0.01-0.08.

### patch_size

Default: 5. Allowed range: 1 to 15.

Odd square patch side in pixels.

Suggested start: 3, 5 or 7; default 5.

### search_distance

Default: 6. Allowed range: 1 to 25.

Search radius in pixels; comparisons cover a (2r+1) square neighborhood.

Suggested start: 6-11 for repeated local structures.

### fast_mode

Default: True. Options: true / false.

Use scikit-image fast NLM; false uses the slower reference approach.

Suggested start: True for interactive work.


## Bilateral denoise

A fast spatial/intensity baseline. The per-channel implementation preserves the RGB contract but does not perform vector-color patch matching.

### sigma_color

Default: 0.05. Allowed range: 0.001 to 1.0.

Intensity similarity scale on normalized pixels.

Suggested start: 0.02-0.10; smaller values preserve stronger edges.

### sigma_spatial

Default: 3.0. Allowed range: 0.1 to 20.0.

Spatial Gaussian sigma in image pixels.

Suggested start: 1-5; default 3.


## Median denoise

Useful for sparse impulse artifacts; wide windows can remove small real particles. Kernel 1 is an intentional identity setting.

### kernel_size

Default: 3. Allowed range: 1 to 31.

Odd median window side in pixels. A kernel of 1 leaves the image unchanged.

Suggested start: 3; use 5 only after checking small-particle loss.


## DCT sparsity

Start with native resolution and compare sparsity fractions. Hard global thresholds can ring around sharp boundaries or erase weak structure. The mask in Reconstruct is generated from input pixels; this UI does not import a separate external missing-pixel mask.

### task

Default: denoise. Options: denoise, reconstruct.

Denoise uses every input pixel with relaxed fidelity. Reconstruct simulates missing pixels using a sampling mask and hard notebook data consistency.

Suggested start: denoise for ordinary complete SEM/TEM images; reconstruct for sampling experiments.

### iterations

Default: 40. Allowed range: 1 to 1000.

Number of prior/fidelity iterations.

Suggested start: 40 as in the notebook; compare 20-100.

### data_loss

Default: l2. Options: l2, l1, huber.

L2 uses residual; L1 uses delta*sign(residual); Huber clips residual to +/-delta.

Suggested start: l2 initially; compare huber for occasional large residuals.

### fidelity_step

Default: 0.2. Allowed range: 0.0 to 0.99.

Denoise-only relaxation strength. The prior proposal is pulled partway toward the noisy input, not restored exactly.

Suggested start: 0.1-0.4. Higher values retain more input noise; never 1 in denoise mode.

### huber_delta

Default: 0.05. Allowed range: 1e-06 to 1.0.

Normalized residual update scale for L1 and Huber; ignored for L2.

Suggested start: 0.05 as in the notebook; compare 0.01-0.10.

### sample_fraction

Default: 0.1. Allowed range: 0.001 to 1.0.

Reconstruct-only fraction of observed pixel positions. Random sampling is without replacement. At 1 with L2, reconstruction returns the input.

Suggested start: 0.10 for notebook comparison; this is not a denoising strength.

### sampling_method

Default: random. Options: random, grid.

Reconstruct-only random positions or a regular grid; a single mask is shared by RGB channels.

Suggested start: random for the notebook preset.

### random_seed

Default: 7. Allowed range: 0 to 2147483647.

Seed for reconstruct-mode sample positions.

Suggested start: 7 for the notebook preset.

### initialization

Default: nearest. Options: nearest, zeros.

Reconstruct-only missing-pixel initialization. Denoise always starts from the observed image.

Suggested start: nearest, matching the notebook.

### max_side

Default: 0. Allowed range: 0 to 4096.

Optional processing resolution cap. 0 uses the native grid. A smaller cap downsamples before processing and interpolates the result back to the original grid.

Suggested start: 0 for native-resolution SEM/TEM; 256 only for a notebook-resolution comparison.

### sparsity_fraction

Default: 0.08. Allowed range: 0.001 to 1.0.

Retained fraction of full-image 2D DCT coefficients. The hard threshold is recalculated each iteration; threshold ties can retain additional coefficients.

Suggested start: 0.08 as in the notebook; compare 0.04-0.20. Inspect ringing and weak details.


## TV iterative (notebook)

Use Denoise for complete SEM/TEM images. Step 0.01 is a conservative starting point; step 0.08 is retained in the notebook reconstruction preset. Repeated steps do not guarantee monotonic quality improvement.

### task

Default: denoise. Options: denoise, reconstruct.

Denoise uses every input pixel with relaxed fidelity. Reconstruct simulates missing pixels using a sampling mask and hard notebook data consistency.

Suggested start: denoise for ordinary complete SEM/TEM images; reconstruct for sampling experiments.

### iterations

Default: 40. Allowed range: 1 to 1000.

Number of prior/fidelity iterations.

Suggested start: 40 as in the notebook; compare 20-100.

### data_loss

Default: l2. Options: l2, l1, huber.

L2 uses residual; L1 uses delta*sign(residual); Huber clips residual to +/-delta.

Suggested start: l2 initially; compare huber for occasional large residuals.

### fidelity_step

Default: 0.2. Allowed range: 0.0 to 0.99.

Denoise-only relaxation strength. The prior proposal is pulled partway toward the noisy input, not restored exactly.

Suggested start: 0.1-0.4. Higher values retain more input noise; never 1 in denoise mode.

### huber_delta

Default: 0.05. Allowed range: 1e-06 to 1.0.

Normalized residual update scale for L1 and Huber; ignored for L2.

Suggested start: 0.05 as in the notebook; compare 0.01-0.10.

### sample_fraction

Default: 0.1. Allowed range: 0.001 to 1.0.

Reconstruct-only fraction of observed pixel positions. Random sampling is without replacement. At 1 with L2, reconstruction returns the input.

Suggested start: 0.10 for notebook comparison; this is not a denoising strength.

### sampling_method

Default: random. Options: random, grid.

Reconstruct-only random positions or a regular grid; a single mask is shared by RGB channels.

Suggested start: random for the notebook preset.

### random_seed

Default: 7. Allowed range: 0 to 2147483647.

Seed for reconstruct-mode sample positions.

Suggested start: 7 for the notebook preset.

### initialization

Default: nearest. Options: nearest, zeros.

Reconstruct-only missing-pixel initialization. Denoise always starts from the observed image.

Suggested start: nearest, matching the notebook.

### max_side

Default: 0. Allowed range: 0 to 4096.

Optional processing resolution cap. 0 uses the native grid. A smaller cap downsamples before processing and interpolates the result back to the original grid.

Suggested start: 0 for native-resolution SEM/TEM; 256 only for a notebook-resolution comparison.

### tv_step

Default: 0.01. Allowed range: 0.0001 to 0.24.

Gradient-divergence iteration step; this is not a TV regularization lambda or Chambolle weight.

Suggested start: 0.01 for denoising (compare 0.005-0.02). The reconstruction preset uses notebook step 0.08; large steps can oscillate.

### gradient_epsilon

Default: 1e-06. Allowed range: 1e-09 to 0.01.

Positive value added inside sqrt(gx^2+gy^2+epsilon). Forward differences repeat the last row/column.

Suggested start: 0.000001 as in the notebook.


## Sparse dictionary learning

A real SPORCO BPDNDictLearn dictionary is fit to seeded patches, using mean-centered data and zero-mean atoms. Inference solves BPDN with the same lambda, restores patch means, includes border patches and averages overlaps. Dictionary update/ADMM tolerances are fixed at 1e-3. Learned dictionaries currently belong to this operation and are not reused as saved neural checkpoints.

### patch_size

Default: 8. Allowed range: 3 to 24.

Square image patch side in pixels.

Suggested start: 6-12; default 8.

### dictionary_atoms

Default: 64. Allowed range: 4 to 512.

Number of dictionary columns. Larger dictionaries represent more patterns and can fit noise.

Suggested start: 64-128 for 8x8 patches.

### training_patches

Default: 2048. Allowed range: 32 to 20000.

Maximum randomly selected, mean-centered training patches.

Suggested start: 1024-4096, with at least as many patches as atoms.

### dictionary_iterations

Default: 10. Allowed range: 1 to 100.

Alternating SPORCO dictionary-learning iterations.

Suggested start: 10-30; start with 10.

### coding_iterations

Default: 30. Allowed range: 1 to 500.

Maximum ADMM iterations per sparse coding/update solve.

Suggested start: 30-100.

### regularization

Default: 0.05. Allowed range: 0.0001 to 1.0.

L1 coefficient penalty lambda for 0.5*||D*X-S||^2 + lambda*||X||_1.

Suggested start: 0.02-0.10 after intensity normalization.

### patch_stride

Default: 4. Allowed range: 1 to 24.

Inference patch spacing; it must not exceed patch_size. Edge patches are included.

Suggested start: Half the patch side; use 1 for more overlap at higher cost.

### inference_batch

Default: 256. Allowed range: 16 to 2048.

Patches sparse-coded together. Controls working memory.

Suggested start: 128-512.

### random_seed

Default: 7. Allowed range: 0 to 2147483647.

Seed for initial dictionary and training-patch sampling.

Suggested start: 7 for repeatable comparisons.


## BM3D

Official bm3d 4.0.3 / bm4d 4.2.5 native backend. Gaussian sigma is a standard deviation, not a variance. This backend has academic/non-commercial licensing; installing this application does not replace its upstream terms. See https://pypi.org/project/bm3d/ and the installed bm3d/bm4d licenses. Inputs smaller than 32 pixels on either axis receive reflected context to at least 32x32 before native filtering, then crop back to their original size. This avoids unsafe native block-size edge cases. Cancel becomes effective after the native filtering call returns.

### sigma

Default: 0.04. Allowed range: 0.0001 to 0.5.

Gaussian noise standard deviation in normalized intensity units.

Suggested start: Estimate the noise; initially compare 0.01-0.08.

### profile

Default: np. Options: np, lc.

Official bm3d normal profile or low-complexity profile.

Suggested start: np for the main comparison; lc for faster previews.

### stage

Default: all. Options: all, hard.

Both hard-threshold/Wiener stages, or hard-threshold stage only.

Suggested start: all for final output.

### num_threads

Default: 1. Allowed range: 1 to 32.

Native BM3D worker threads.

Suggested start: 1-4; avoid oversubscribing other processing.


## Noise2Void

CAREamics 0.3.5 blind-spot self-supervision assumes sufficiently independent noise across neighboring pixels. Correlated scan noise can be learned as signal. Train uses per-plane mean/std normalization internally, undone in prediction. The application disables batch normalization and multiprocessing workers, uses the backend Adam optimizer and default scheduler, and does not enable an experiment logger. Keep sufficient representative training data; one noisy image is a convenience, not a substitute for a dataset/held-out validation.

### run_mode

Default: train. Options: train, predict.

Train a blind-spot model on noisy input, or load a previously saved CAREamics model.

Suggested start: train for a new image; predict only with a compatible trained model.

### model_path

Default: (empty). Text or filesystem path.

CAREamics checkpoint path for predict mode. For RGB use a training-output directory with channel_0, channel_1 and channel_2 models.

Suggested start: Use the checkpoint/directory reported after training.

### output_directory

Default: (empty). Text or filesystem path.

Optional directory for trained models. Empty uses the application model cache; RGB channels receive separate subdirectories.

Suggested start: Keep trained models outside source-image folders.

### device

Default: cpu. Options: cpu, cuda, auto.

Training/inference device. CUDA is permitted only inside Conda; auto selects CUDA there when available.

Suggested start: cpu for a small trial; use a dedicated Conda GPU environment for larger runs.

### epochs

Default: 30. Allowed range: 1 to 1000.

Maximum training epochs.

Suggested start: 30-100 after a small interface trial; inspect validation behavior.

### steps_per_epoch

Default: 20. Allowed range: 1 to 2000.

Training batches per epoch.

Suggested start: 20-100; increasing this increases time and exposure to patches.

### patch_size

Default: 64. Allowed range: 16 to 512.

Training patch side; must fit the image and be divisible by 2^depth.

Suggested start: 64 or 128; use 32 for a small test.

### batch_size

Default: 8. Allowed range: 1 to 64.

Training patches per batch.

Suggested start: 4-16; reduce on limited GPU memory.

### learning_rate

Default: 0.0003. Allowed range: 1e-06 to 0.01.

Adam learning rate.

Suggested start: 0.0001-0.001, default 0.0003.

### masked_pixel_percentage

Default: 0.2. Allowed range: 0.01 to 10.0.

Percentage of training pixel positions masked for blind-spot loss; 0.2 means 0.2%, not 20%.

Suggested start: 0.2-1.5; default follows CAREamics 0.2.

### roi_size

Default: 11. Allowed range: 3 to 31.

Odd neighborhood side for blind-spot pixel replacement.

Suggested start: 5-11; default 11.

### depth

Default: 2. Allowed range: 1 to 4.

U-Net downsampling depth.

Suggested start: 2 for a first trial; 3 for larger patches/data.

### initial_filters

Default: 16. Allowed range: 8 to 64.

Initial U-Net channel count.

Suggested start: 16-32.

### validation_patches

Default: 8. Allowed range: 1 to 128.

Held-out validation patch count when the input is split automatically.

Suggested start: 8-32. Same-image validation is not an independent microscopy accuracy study.

### tile_size

Default: 256. Allowed range: 32 to 2048.

Prediction tile side, padded for small images.

Suggested start: 256; larger tiles need more memory.

### tile_overlap

Default: 32. Allowed range: 0 to 256.

Overlapping prediction context; must be smaller than half the tile side.

Suggested start: 32 for tile 256.

### random_seed

Default: 7. Allowed range: 0 to 2147483647.

Seed for training/patch selection. Backend/device differences can still affect numerical reproducibility.

Suggested start: 7 for comparisons.


## N2V2

Uses the official CAREamics use_n2v2=True factory, including its median masking strategy and N2V2 architecture path. It is not ordinary N2V with a changed label. The same parameter interpretation/model persistence rules apply. Same-image validation patches are not an independent image-level assessment.

### run_mode

Default: train. Options: train, predict.

Train a blind-spot model on noisy input, or load a previously saved CAREamics model.

Suggested start: train for a new image; predict only with a compatible trained model.

### model_path

Default: (empty). Text or filesystem path.

CAREamics checkpoint path for predict mode. For RGB use a training-output directory with channel_0, channel_1 and channel_2 models.

Suggested start: Use the checkpoint/directory reported after training.

### output_directory

Default: (empty). Text or filesystem path.

Optional directory for trained models. Empty uses the application model cache; RGB channels receive separate subdirectories.

Suggested start: Keep trained models outside source-image folders.

### device

Default: cpu. Options: cpu, cuda, auto.

Training/inference device. CUDA is permitted only inside Conda; auto selects CUDA there when available.

Suggested start: cpu for a small trial; use a dedicated Conda GPU environment for larger runs.

### epochs

Default: 30. Allowed range: 1 to 1000.

Maximum training epochs.

Suggested start: 30-100 after a small interface trial; inspect validation behavior.

### steps_per_epoch

Default: 20. Allowed range: 1 to 2000.

Training batches per epoch.

Suggested start: 20-100; increasing this increases time and exposure to patches.

### patch_size

Default: 64. Allowed range: 16 to 512.

Training patch side; must fit the image and be divisible by 2^depth.

Suggested start: 64 or 128; use 32 for a small test.

### batch_size

Default: 8. Allowed range: 1 to 64.

Training patches per batch.

Suggested start: 4-16; reduce on limited GPU memory.

### learning_rate

Default: 0.0003. Allowed range: 1e-06 to 0.01.

Adam learning rate.

Suggested start: 0.0001-0.001, default 0.0003.

### masked_pixel_percentage

Default: 0.2. Allowed range: 0.01 to 10.0.

Percentage of training pixel positions masked for blind-spot loss; 0.2 means 0.2%, not 20%.

Suggested start: 0.2-1.5; default follows CAREamics 0.2.

### roi_size

Default: 11. Allowed range: 3 to 31.

Odd neighborhood side for blind-spot pixel replacement.

Suggested start: 5-11; default 11.

### depth

Default: 2. Allowed range: 1 to 4.

U-Net downsampling depth.

Suggested start: 2 for a first trial; 3 for larger patches/data.

### initial_filters

Default: 16. Allowed range: 8 to 64.

Initial U-Net channel count.

Suggested start: 16-32.

### validation_patches

Default: 8. Allowed range: 1 to 128.

Held-out validation patch count when the input is split automatically.

Suggested start: 8-32. Same-image validation is not an independent microscopy accuracy study.

### tile_size

Default: 256. Allowed range: 32 to 2048.

Prediction tile side, padded for small images.

Suggested start: 256; larger tiles need more memory.

### tile_overlap

Default: 32. Allowed range: 0 to 256.

Overlapping prediction context; must be smaller than half the tile side.

Suggested start: 32 for tile 256.

### random_seed

Default: 7. Allowed range: 0 to 2147483647.

Seed for training/patch selection. Backend/device differences can still affect numerical reproducibility.

Suggested start: 7 for comparisons.


## Blind-spot training, models and resource constraints

Train fits a separate model for each grayscale/RGB plane. A chosen output folder contains channel_0 (and channel_1/channel_2 for RGB), the backend checkpoints, samstudio_model.ckpt and samstudio_model.json with method/parameters. Empty output_directory creates a unique application-data folder. A folder containing a completed model for the channel is not overwritten. Interrupted training can leave partial backend files; use a new folder when retrying. Prediction accepts a .ckpt or a saved root/channel folder; a saved manifest must match the selected method. An external checkpoint must be a compatible trusted CAREamics model, not an arbitrary U-Net .pt file. The separate plugin developer guide covers TorchScript U-Net integration.

Training patch side and prediction tile side must be divisible by 2^depth. The training patch must fit the image. At least one pixel per patch must be masked: patch_size^2 * masked_pixel_percentage/100 >= 1. With 0.2%, use at least a 32x32 patch. tile_overlap must be less than half the tile side; use even values for the backend tiler. Depth increases the receptive field and memory use; scale patch/tile sizes accordingly. In Predict mode train-only controls are disabled and the checkpoint architecture is used. Tiling values must also satisfy the loaded checkpoint architecture; native validation reports incompatible choices.

For a quick interface test, use a 64x64 image, patch 32, depth 1, filters 8, batch 2, validation patches 2, one epoch/one step, tile 32 and overlap 4. This tests train/save/load only; it does not produce validated denoising. For real comparisons start with patch 64-128, depth 2, filters 16-32, 30 epochs and 20 steps, and inspect validation/real details before increasing training. The defaults do not promise convergence. Use more representative data for scientific work and validate on held-out images or known measurements.

CPU training can be slow. device=auto chooses CUDA only when a dedicated Conda environment and CUDA are both available. Explicit cuda outside Conda or without CUDA fails clearly. A GPU choice does not install drivers. Cancellation is checked between training and prediction batches, and image changes occur only after Apply. Saved models remain when cancelling image preview or undoing image edits. The CPU release includes no pretrained N2V/N2V2 weights.

## Smoothing and synthetic noise controls

Processing > Smooth exposes Gaussian kernel_size (default 5, odd 1-101; start 3-7) and sigma (default 1.0, 0.01-30 spatial pixels; start 0.5-1.5). Processing > Add noise offers Gaussian sigma (default 0.03, 0-1; start 0.01-0.05), Poisson peak_counts (default 50, 1-1000000; start 20-200) and Salt-and-pepper amount (default 0.01, 0-1; start 0.001-0.02). Each noise method has seed (default 0, integer 0-2147483647); keep it fixed for comparisons. Poisson peak counts are a synthetic model, not microscope detector calibration. Alpha and outside-target pixels remain exact for these operations too.

## Official references and validation limits

scikit-image restoration API: https://scikit-image.org/docs/stable/api/skimage.restoration.html

SciPy DCT/IDCT API: https://docs.scipy.org/doc/scipy/reference/fft.html

PyWavelets: https://github.com/PyWavelets/pywt

SPORCO dictionary learning: https://sporco.readthedocs.io/en/latest/dictlrn/bpdndl.html

BM3D package, citations and license: https://pypi.org/project/bm3d/

CAREamics documentation and source: https://careamics.github.io/ ; https://github.com/CAREamics/careamics

The test report distinguishes CPU numerical execution, one-step blind-spot interface tests and native API contract checks. Actual NVIDIA CUDA and SAM3.1 checkpoint inference require target-hardware validation. Synthetic phantom improvement for selected settings is not a specimen-independent accuracy guarantee.
