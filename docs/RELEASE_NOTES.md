# SAM Image Studio 1.4.4

- Add model-free Otsu + watershed, exact-region preview, documented parameters and mask acceptance.
- Scale Gaussian/Poisson noise to observed image signal by default; add residuals to original data and compare previews on a shared intensity scale.
- Default newly opened images to original inference input; retain per-image session choice, and add undoable Forget processed image.
- Show persistent ONNX preview counts and raw/filter diagnostics. Real EMD `black dots` displays 52 previews; STEM `white dots` displays 16, while `particles` yields zero.
- Add exact pre-rotation snapshot reset, Select all/Deselect all in three panels, and real LaMa mask/context/resize/blend controls.
- Automatically select/bootstrap project-local Python 3.12 on Windows/Linux x86-64.
- Add a source-sized offline CPU edition: prepare complete packages/runtime/checkpoints online, then install with the normal CPU helper offline. Restrict to SAM1 ViT-B and SAM2.1 Small/Base+.
- Include supplied EMD/TIFF originals and illustrated workflows. Original historical uploads remain unchanged.

Validation: 484 passed, 35 external-asset checks skipped; genuine ONNX CPU Qt/ROI/native-project tests; fresh 126-wheel no-network dependency install and CPU self-test. Full checkpoint/OS-package offline preparation was blocked by cloud host restrictions; native Windows and CUDA execution were not run. See `validation/VALIDATION_v144.md`.

---

# SAM Image Studio 1.4.3

## Installation and repository organization

CPU helpers are now under `packaging/`; GPU README, install/update instructions,
installer and optional requirements are under `GPU/`. The existing
`scripts/install_conda_gpu.py` remains a compatibility entry point. Shared
requirements live under `packaging/requirements/`. Original validation reports
moved to `docs/validation/`; original artifacts and archive checksums remain in
`uploads/`. Runtime package/import paths remain unchanged.

Ubuntu/WSL installers detect and install missing Qt/font/XCB libraries, including
libxcb-shape. WSLg startup selects X11 without overriding explicit Qt platform
choices. Native SAM3 requirements retain setuptools 80.9.0 for pkg_resources.
Existing dedicated environments update in place; no routine uninstall is needed.

## Model and prompt workflows

- SAM3 ONNX text segmentation uses the public verified six-file ViT-H export.
  Supports CPU/CUDA runtime selection, text aliases, exact ROI limits, filters,
  preview and native project recovery. Native point/shape concepts and automatic
  grids are not exposed by this text-only export.
- SAM3/3.1 Model manager accepts a masked optional Hugging Face read token for
  downloads. The field is not saved; existing local login or local matching
  checkpoints remain supported. Model access approval is still required.
- Native SAM3 instance/ROI predictions now share processor image features through
  the parent's predict_inst API; they no longer call an interactive tracker with
  no backbone. Text control labels/placeholders follow the loaded model family.
- Whole-image examples can use selected accepted masks. SAM1/2 pool public
  predictor image embeddings; SAM3/3.1 use native concept prompts. Single object
  stays separate from exact ROI clipping because their output boundaries differ.

## Illustrated website and validation

Sphinx guides follow workspace, menus, toolbar controls and modes. New figures
cover data cleaning, three prompted Seg scopes, compressed sensing and DCT/TV
parameter comparisons. Synthetic schematics are labeled; real ONNX screenshots
use public synthetic input. Original v1.4.2 manuals remain historical references.

Current full regression: 460 passed, 35 external-asset checks skipped. Genuine
SAM3 ONNX CPU CLI and Qt text/alias/ROI/accept/reopen checks passed, as did CPU
installation self-test and strict Sphinx build. CUDA/native Windows/native
SAM3.1 inference were not run in this cloud. See `validation/ONNX_VALIDATION_v143.md`.

---

# SAM Image Studio 1.4.2

## Calibration and segmentation

Excel pixel-size lookup reads converted_image_name and converted_size, matches filenames without their extension and applies physical calibration to current/later images. Unit selection, invalid/conflicting-row checks, rotated-coordinate calibration, autosave and Undo are supported.

Point/dot segmentation uses whole-image exemplar search. Single object and Inside ROI only are hidden and disabled for this tool, and return with area tools.

SAM3.1 is a distinct GPU-only family using the official multiplex predictor and sam3.1_multiplex.pt weights. It supports point-derived/area examples and text through lossless single-frame sessions. The dedicated Linux/WSL2 Conda installer supplies the optional backend. Actual CUDA/SAM3.1 inference requires local hardware validation.

## Restoration and parameter guidance

Processing adds global DCT sparsity and explicit notebook TV with separate reconstruction/denoising tasks. The notebook preset preserves random 10% sampling, seed 7, nearest initialization and 40 iterations. Ordinary denoising uses relaxed data consistency, so full images are not restored unchanged by hard L2 constraints. The TV denoise step starts at 0.01; the reconstruction preset retains notebook step 0.08.

SPORCO dictionary learning, official BM3D and actual CAREamics Noise2Void/N2V2 training/prediction join the configurable TV, wavelet, NLM, bilateral and median methods. Tiny BM3D inputs receive safe reflected context. Each parameter has a default, allowed range/options, explanation and suggested starting values. Defaults reload on each dialog open/method change. The complete Denoising Parameters PDF is available from Help.

Neural models save per channel and can be reloaded. Model files remain after image preview cancellation or image Undo. BM3D/BM4D retain their upstream academic/non-commercial license terms. No pretrained model weights are bundled.

## Workflow and validation

The v1.4 annotation, Objects/Groups/Image files panels, COCO export, reversible cleaning, manual/edit tools, calibrated statistics, transforms and savepoints remain in use. Whole-image positive/negative examples, text Run, automatic grid, protected crops, workspace recovery and the plugin API are retained. Developer plugin/U-Net implementation instructions remain in the separate For Developer manual.

The CPU installer installs its specified PyTorch build before restoration dependencies. The Windows packaging recipe includes all three PDFs and BM4D native data. TEST_REPORT.md records the complete test run, installed-package acceptance, version/asset evidence and unverified platforms. Source comparison and patch are included under validation.
