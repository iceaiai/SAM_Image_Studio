# SAM Image Studio 1.4.2 - validation report

Date: October 22, 2026

## Result

The final complete run passed **474 tests**, including **63 v1.4.2 feature cases**, with **0 failures, 0 errors and 0 skips**, in 235.232 seconds. The feature XML is a subset of this same complete run. The extra method/dtype cases in the earlier processing regression also execute the newly added non-neural methods.

Source comes from the verified v1.4.1 archive based on the original v1.4 release. The v1.4 object/group/annotation and COCO workflow is retained. The COCO exporter is byte-identical to v1.4.1. Excel lookup is an independent calibration feature; no expanded COCO editor is added.

## Environment and inventory

Linux x86-64, Python 3.12.14, PySide6 6.8.3 offscreen, PyTorch 2.7.1+cpu, torchvision 0.22.1+cpu, NumPy 2.3.5, SciPy 1.17.0, scikit-image 0.26.0. Actual backends: openpyxl 3.1.5, SPORCO 0.2.2.post1, bm3d 4.0.3 / bm4d 4.2.5 and CAREamics 0.3.5. Installed versions and the test-host virtual PID compatibility adjustment are documented under validation. No application/algorithm implementation was replaced by that host adjustment.

| Module | Passed |
| --- | ---: |
| test_core | 27 |
| test_exports_io | 40 |
| test_extra_regressions | 8 |
| test_gui | 18 |
| test_gui_fill_and_export | 5 |
| test_install_safety | 3 |
| test_microscopy_readers | 5 |
| test_real_models | 28 |
| test_recovery_download | 8 |
| test_v11_regressions | 28 |
| test_v12_regressions | 51 |
| test_v13_features | 52 |
| test_v141_processing_workspace | 46 |
| test_v141_segmentation_plugins_gpu | 34 |
| test_v142_calibration_denoise | 57 |
| test_v142_sam31 | 6 |
| test_v14_features | 58 |
| Total | 474 |

## Excel and Point scope

Real .xlsx files verify path/extension/case-insensitive converted_image_name matching, numeric converted_size, invalid/formula/conflicting rows and consistent duplicates. GUI import applies to current documents and later opens, autosaves and restores calibration. Two rotations verify the physical basis/origin against composed affine coordinates while masks remain exact. The lookup can be forgotten without clearing assigned sizes.

Point/dot hides and disables Single object and Inside ROI only, including programmatic attempts to select those scopes. Area tools re-enable them. Existing native single-object GUI regression scenarios use area scopes; Point live-edit/coalescing tests exercise whole-image exemplar routing. Genuine model checks retain zoomed image-pixel prompting, pre-load prompts followed by live clicks and exact cleaning/native recovery.

## Numerical restoration and actual neural backends

DCT and iterative TV reconstruction are compared byte-for-byte with an independent direct translation of the supplied notebook for L2, L1 and Huber updates. Random sampling, nearest initialization, full-image orthonormal DCT/hard threshold and explicit TV differences/divergence are retained. Full-sampling hard L2 reconstruction is checked as an identity, while denoise mode changes noisy input using relaxed consistency. Native-resolution processing is default; the optional notebook cap downsamples and interpolates back as documented.

DCT, iterative TV, real SPORCO and real BM3D reduce MSE for a fixed synthetic Gaussian-noise particle phantom with the tested settings. This is a limited numerical check, not a SEM/TEM accuracy claim. The explicit TV denoise step defaults to 0.01 after 0.08 showed oscillation; the reconstruction preset retains the supplied 0.08. Chambolle/Bregman weights remain separate parameters.

All non-neural methods execute on uint16 and float32 with exact outside-target preservation. RGBA alpha/seeded noise and invalid values are checked. Tiny BM3D images receive reflected context to at least 32x32 before native filtering and crop back; 1x1, 8x8 and 5x19 regressions remain finite and within 1e-4 of a constant input (native filtering is not an exact constant identity).

Both Noise2Void and N2V2 use actual CAREamics training, checkpoint save and reload, with identical prediction after reload in the tested CPU case. These use one epoch and one step on a 64x64 image, verifying the real interface rather than scientific convergence. Variant mismatches and cancellation are covered. The GUI runs actual DCT and Noise2Void worker-to-preview-to-Apply/Undo checks; training files intentionally persist after image Undo. Every exposed method parameter has a default, description and recommended starting value. Dialog mode relevance, defaults and the notebook preset are checked.

## Genuine segmentation and installed-package acceptance

The suite executes genuine SAM1 ViT-B, SAM2.1 Tiny, Grounding DINO Tiny, LaMa and real microscopy reader fixtures. Whole-image positive/negative exemplar tests find three particles outside/within a positive rectangle while excluding a negative instance. Existing editing, rotation, statistics, export, plugins and native recovery regressions remain in the complete run.

All **34 application modules** and all **three PDF resources** match source, wheel and installed site-packages byte-for-byte. Dependency checking reports no broken requirements. Separate cold SAM1 and SAM2.1 GUI processes load actual checkpoints, process later prompts, accept/reopen masks and render/resize histograms with no errors.

Extended acceptance imports from site-packages outside the source tree and verifies actual SAM2.1 whole-image retrieval (3 masks), the text Run button and alias (3 real text masks), Gaussian processing Apply/Undo, the supplied TorchScript U-Net plugin interface, retained crop/native recovery, workspace removal and startup No. It also executes installed DCT, TV, SPORCO, BM3D and both CAREamics train/save/reload variants, Excel calibration/native recovery and the Point scope guard. The native GUI heartbeat fired 1869 times and reported errors were empty. The U-Net plugin checkpoint is untrained and only verifies integration.

## SAM3.1, GPU, Windows and limits

SAM3.1 has a distinct model catalog entry, official sam3.1_multiplex.pt download and multiplex factory adapter. It uses lossless PNG single-frame sessions, native point instance seeds and combined positive/negative concept boxes in normalized top-left XYWH coordinates. API tests verify the factory, selected device, text/geometry, cleanup after native failure and CPU rejection. These tests use explicit API doubles and do not execute SAM3.1 weights or GPU kernels.

The machine has no NVIDIA GPU. Actual CUDA execution, Conda creation and approved SAM3/SAM3.1 checkpoints are **not verified**. They require the local acceptance steps in GPU_CONDA_GUIDE.md. Native SAM3/SAM3.1 are GPU-only in this application. No CPU fallback or renamed SAM3 weights are claimed for SAM3.1. Device/driver selection and Conda command planning have synthetic-contract coverage; this does not establish every GPU's compatibility or available VRAM.

The optional Linux SAM3/SAM3.1 dependency graph resolves with PyTorch 2.7.1, torchvision 0.22.1, NumPy 1.26.4, CAREamics 0.3.5 and Zarr 3.0.10. Windows x86-64 Python 3.12 application metadata resolves using the target-platform resolver, including new backends. The Windows build recipe evaluates with real collection helpers, includes all 3 PDFs and the bm4d Windows native library. A native Windows EXE is **not built or tested** here. macOS, larger/original SAM2 models and full microscopy training quality remain unverified.

BM3D/BM4D use upstream academic/non-commercial license terms. No pretrained model weights, environments or external microscopy fixtures are shipped. Blocking native solver calls may finish before Cancel is delivered. CAREamics short-run warnings about worker count/log intervals/checkpoint callback location and a pycocotools NumPy deprecation are upstream warnings; tested output/recovery checks pass.

## Documentation and reproducibility

The English User Manual has 22 pages, For Developer 13 pages and Denoising Parameters 27 pages. All 62 pages were rendered and visually inspected; native Qt PDF help loads all three. The parameter guide covers all methods, defaults, ranges/options, practical starting values, reconstruction versus denoising, normalization, blind-spot training/model files, limits and official references. Plugin/U-Net implementation instructions remain in the separate developer guide.

```text
python -m pip install -r requirements-dev.txt
python scripts/fetch_validation_assets.py --models --text --directory /local/validation_assets
python scripts/run_full_validation.py --assets /local/validation_assets --output validation/local_full_results.xml
```

The full runner rejects missing assets and skipped tests. A plain pytest without external assets can skip integrations. Preserve validation/*.xml, installed acceptance JSON, source/asset digests and the baseline patch for review. Defined tests do not establish that every image, library version or hardware configuration is defect-free.
