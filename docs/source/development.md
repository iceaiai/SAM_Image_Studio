# Development and documentation

## Application development

Install the CPU or dedicated GPU environment first. Activate it, then install
the supplied development requirements:

```sh
python -m pip install -r packaging/requirements/dev.txt
python -m pip check
python -m samstudio.selftest --device cpu
python -m pytest -q tests/test_v141_processing_workspace.py tests/test_v141_segmentation_plugins_gpu.py
```

Use `--device cuda` for the self-test only in a working dedicated GPU Conda
environment. The two selected test files cover processing, workspace,
segmentation, plugins, and hardware planning; synthetic GPU reports exercise
planning and rejection paths without executing CUDA kernels.

Run the broader suite with `python -m pytest -q`. Genuine-model and microscopy
tests can skip without their external fixtures. Report passed, failed, and
skipped outcomes separately; a passing subset is not full model validation.
On headless Linux, use `QT_QPA_PLATFORM=offscreen` for Qt tests.

## Full model/reader validation

The release documents these commands:

```sh
python scripts/fetch_validation_assets.py --models --text --directory /local/validation_assets
python scripts/run_full_validation.py --assets /local/validation_assets --output docs/validation/local_full_results.xml
```

The full runner requires actual SAM1/SAM2.1, LaMa, microscopy reader fixtures,
and the pinned Grounding DINO cache. It rejects skipped tests.

```{warning}
The supplied 1.4.2 archive does **not** contain
`docs/validation/external_assets.json`, which `fetch_validation_assets.py` reads.
Consequently, the fetch command cannot complete from this distribution as-is.
Obtain the authoritative manifest with expected asset hashes from the release
maintainer before using that helper. Do not invent hashes or disable checks.
If genuine fixtures are already available, provide their directory to the full
runner and ensure its separate text-model cache requirement is satisfied.
```

The uploaded ZIP's original `TEST_REPORT.md` and `validation/` (now archived under `docs/`) describe the original
release's checks. They are historical artifacts, not results from a current
checkout or this documentation build. Real CUDA and SAM3/SAM3.1 checks remain
hardware/access dependent.

## Current 1.4.3 checks

See [current validation](https://github.com/iceaiai/SAM_Image_Studio/blob/main/docs/validation/ONNX_VALIDATION_v143.md)
for actual runtime/model tests and their scope. The historical import results below
refer only to the earlier checkout.

## Repository import checks

During the initial repository import, the CPU installer completed on headless
Linux with Python 3.12.14 and PyTorch 2.7.1+cpu. Dependency consistency, native
PyTorch/torchvision operations, exact COCO recovery, and Qt window construction
passed. The two selected regression files above produced **78 passed and
2 skipped**; the skipped cases require genuine SAM checkpoints.

The Sphinx HTML build completed with warnings treated as errors. Its 49 HTML
pages, local links, anchors, and supplied-file downloads were checked. No NVIDIA
device/Conda environment was available, and no real model inference, full
external-asset suite, native Windows execution, or hosted documentation
deployment was validated during that import.

## Build the Sphinx documentation

From the repository root, use a separate Python 3.12 environment. On Linux:

```sh
python3.12 -m venv .docs-venv
.docs-venv/bin/python -m pip install -r docs/requirements.txt
.docs-venv/bin/python -m sphinx -W --keep-going -b html docs/source docs/_build/html
```

On Windows PowerShell:

```powershell
py -3.12 -m venv .docs-venv
.\.docs-venv\Scripts\python.exe -m pip install -r docs/requirements.txt
.\.docs-venv\Scripts\python.exe -m sphinx -W --keep-going -b html docs/source docs/_build/html
```

Open the generated `docs/_build/html/index.html` locally. `-W` treats warnings
as failures. AutoAPI generates a reference from `samstudio/` without importing
the application, so desktop/model dependencies are unnecessary for this build.

Check external links separately when Internet access is available:

```sh
python -m sphinx -b linkcheck docs/source docs/_build/linkcheck
```

External link availability and access policies are separate from the HTML
build. The notebook is offered as a download and is not executed by Sphinx.

## Continuous integration and hosting

`.github/workflows/docs.yml` builds HTML with warnings treated as errors on
pushes and pull requests, uploads a workflow artifact, and updates the static
GitHub Pages branch on `main`. `.readthedocs.yaml` remains an optional alternative.
See [website publishing](developer/publishing.md) for local publication and
hosting prerequisites. A local build alone does not establish a live site.

## Edit the right source

Edit `docs/source/` for installation, onboarding, and architecture pages.
The full manual pages include `docs/USER_MANUAL.md`, `docs/FOR_DEVELOPER.md`,
and `docs/DENOISING_PARAMETERS.md` from the supplied source archive using MyST.
Changes to code are picked up by AutoAPI on the next build. Keep
`samstudio.__version__` authoritative for the displayed version.

Preserve `uploads/` as the original supplied artifacts. The GUI's packaged
help PDFs under `samstudio/resources/` remain the release's original resources;
they are not regenerated from Sphinx by this workflow.
