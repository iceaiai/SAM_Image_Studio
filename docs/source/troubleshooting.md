# Troubleshooting

## Installation stops

Check 64-bit Python 3.12, a writable complete source tree, available disk space,
and the first failing command. Re-run the installer after correcting that
prerequisite. Keep the CPU and optional SAM3 lockfiles separate.
Use the supported installer and `--find-links vendor` path rather than ignoring
dependencies, altering pins, or disabling TLS/checksum verification.

If a bundled artifact fails its checksum, re-extract the original archive and
verify it before installation. Preserve images, native projects, and any user
changes before replacing files. A missing package version in a configured
index is a dependency/index issue to diagnose, not a reason to silently claim
the documented installation worked.

## PowerShell cannot change into a folder containing spaces

For "A positional parameter cannot be found" after a `cd` command, quote the
entire path:

```powershell
Set-Location -LiteralPath 'C:\work\AI works\Desktop_SAM3\SAM_Image_Studio_v1.4.2_CPU\SAM_Image_Studio'
Test-Path .\scripts\install_conda_gpu.py
Test-Path .\pyproject.toml
```

Replace the example with your real folder. Both checks should return `True`
before running the installer. A `False` result means you are in the wrong
level of the extracted folder or the source tree is incomplete.

For native Windows GPU, use the SAM1/2 recipe. The SAM3.1 `--sam3` recipe must
run inside Linux/WSL2 with Linux Conda, not in Windows PowerShell. See
[GPU installation](installation.md#nvidia-gpu-with-conda).

## Qt cannot open a display

A normal launch requires a desktop display and the platform's Qt runtime
libraries. On headless Linux, use `QT_QPA_PLATFORM=offscreen` for diagnostics
and GUI tests; an offscreen process is not an interactive application preview.
If Qt reports a missing shared library, install that library through the
system's supported package manager, preserving package verification.

## GPU detection or model loading fails

Run `python scripts/install_conda_gpu.py --inspect` from the repository root.
No `nvidia-smi`, no visible NVIDIA devices, or an old driver prevents this CUDA
path. The installer neither installs drivers nor treats AMD/Intel GPUs as CUDA.
Use CPU where appropriate. CUDA execution requires a dedicated Conda environment.

Run `python -m samstudio.selftest --device cuda` in the GPU environment, then
load matching real weights for a model acceptance check. Detection and synthetic
planner tests do not verify kernels, available VRAM, or model performance.
SAM3/3.1 require Linux/WSL2, approved access, and the correct distinct checkpoint.

## Prompts do not create the expected result

- Confirm that a model is loaded and **Segment** mode is active.
- Choose an area tool for **Single object** or **Inside ROI only**. **Point**
  uses **Prompt project, whole image**.
- Use **Run text segmentation** for text; SAM1 does not offer that path.
- A zero-mask automatic-grid result is a visible result. Review grid density,
  minimum score/area, and image suitability.
- Previews require **Accept masks**. Review positive and negative examples
  and compare with acquired image content.

## Saving or recovery fails

Choose a writable project folder and retain native `.sam.json` files.
Removing an image entry does not delete its source or saved project. The app
normally writes rotating `samstudio.log` files in its data directory;
`SAM_STUDIO_DATA_DIR` can select another writable location. Exports do not
replace full native editing/recovery records.

## A plugin or restoration operation fails

Install plugin dependencies in the active environment, then run `pip check`.
Check the processor's shape, dtype, finite-value, target-mask and cancellation
contract. Keep GUI calls on the GUI thread. Remove/disable an incompatible
plugin through its manager; dependencies are not installed automatically.

For CAREamics, validate image size, patch size/depth, device, and output paths.
Training saves model files before Apply, and image Undo does not delete those
files. For BM3D/bm4d, review the upstream package's applicable license terms.

## Full validation cannot download fixtures

This release archive omits `validation/external_assets.json`, required by its
asset-fetch helper. Obtain the authoritative manifest from the maintainer, or
use existing genuine assets with the full runner. See
[development and validation](development.md). Do not describe skipped
integration tests or old bundled XML reports as a current full validation run.
