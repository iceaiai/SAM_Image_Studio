# SAM Image Studio

Desktop microscopy annotation and SAM segmentation with calibrated measurements,
reversible image restoration, and local plugins. CPU and NVIDIA GPU support.

This repository contains the complete **1.4.2** application source extracted
from the supplied CPU release, all five original uploads, and Sphinx
documentation based on the code and user/developer manuals.

**[Documentation website](https://iceaiai.github.io/SAM_Image_Studio/)** ·
[Installation and updates](https://iceaiai.github.io/SAM_Image_Studio/installation.html) ·
[Image workflows](https://iceaiai.github.io/SAM_Image_Studio/features/index.html) ·
[SAM3.1 text and shape prompts](https://iceaiai.github.io/SAM_Image_Studio/segmentation/sam31.html) ·
[Buttons, menus and modes](https://iceaiai.github.io/SAM_Image_Studio/documentation/index.html)

## Features

- Manual annotation, editable masks/shapes, groups, Undo/Redo, and native
  `.sam.json` saving and recovery.
- SAM1 and SAM2/2.1 segmentation on CPU or NVIDIA GPU; whole-image positive and
  negative exemplars, single-object/ROI workflows, and reviewed mask acceptance.
- SAM2/2.1 text-to-box segmentation, plus optional GPU-only SAM3/SAM3.1 backends.
- Microscopy readers, Excel pixel-size lookup, calibrated statistics,
  COCO/YOLO/mask/overlay exports, and separate acquired/derived pixels.
- Reversible cleaning and configurable TV, wavelet, DCT, non-local means,
  SPORCO, BM3D, and CAREamics Noise2Void/N2V2 processing.
- Local plugin API v1 and a tiled TorchScript U-Net interface example.

## CPU installation

Use **64-bit Python 3.12** and a writable folder containing the full repository:

```sh
git clone https://github.com/iceaiai/SAM_Image_Studio.git
cd SAM_Image_Studio
```

On **Windows**, run `Install_CPU.bat`, then `Start_GUI.bat`.
`Install_Python_3_12.bat` helps install Python when needed.

On **Linux**, with `python3` pointing to Python 3.12:

```sh
bash install_cpu.sh
bash start_gui.sh
```

The installer creates an app-owned `.venv`, installs the pinned CPU dependencies
and verified bundled SAM2 wheel, runs `pip check`, and runs the application
self-test. For an already activated dedicated Python 3.12 virtual or Conda
environment:

```sh
python scripts/install_environment.py --backend cpu --current
python -m samstudio
```

SAM1/SAM2.1 weights download separately through Model manager or can be selected
locally. No model weights or pretrained U-Net denoising weights are bundled.

## NVIDIA GPU installation

GPU execution requires a **dedicated non-base Conda environment** and a
compatible NVIDIA driver. From a Conda prompt in the repository root:

```sh
conda run -n base python scripts/install_conda_gpu.py --inspect
conda run -n base python scripts/install_conda_gpu.py --name sam-image-studio-gpu --dry-run
conda run -n base python scripts/install_conda_gpu.py --name sam-image-studio-gpu
conda activate sam-image-studio-gpu
python -m pip check
python -m samstudio.selftest --device cuda
python -m samstudio
```

On Windows, `Install_GPU_Conda.bat` and `Start_GUI_GPU.bat` target the same
default environment. The planner chooses PyTorch 2.7.1 / torchvision 0.22.1
CUDA 12.8, 12.6, or 11.8 wheels according to detected hardware and driver
capability. It does not install NVIDIA drivers. AMD/Intel GPUs use the CPU path.

Optional **SAM3/SAM3.1** uses Linux/WSL2 Conda, the installer's `--sam3` flag,
a driver supporting CUDA 12.6+, and separately approved access to matching
weights. These backends are not enabled on CPU. See the
[installation guide](docs/source/installation.md) and
[GPU Conda guide](GPU_CONDA_GUIDE.md) for details and validation boundaries.
CUDA planning tests do not establish real GPU inference.

## First use

1. Open an image, such as `examples/synthetic_particles.ome.tif`.
2. Check calibration and create a group.
3. Load SAM2.1 Tiny or SAM1 ViT-B on CPU in Model manager.
4. Switch to Segment, choose **Prompt project, whole image**, and add positive
   and negative examples. Inspect the preview, then **Accept masks**.
5. Retain native `.sam.json` projects for editing/recovery; export COCO, YOLO,
   masks, overlays, or derived images as needed.

Choose an area tool for **Single object** or **Inside ROI only**; Point uses
whole-image exemplars. Processing and cleaning use Preview/Apply and Undo.
The [quickstart](docs/source/quickstart.md) and
[user manual](docs/USER_MANUAL.md) cover the complete workflow.

## Sphinx documentation

Documentation includes CPU/GPU installation, a quickstart, full user/developer
and denoising manuals, architecture, validation, notebook guidance, original
file downloads, and a Python API reference generated statically from source.
It builds without installing Qt, PyTorch, or model weights:

```sh
python3.12 -m venv .docs-venv
.docs-venv/bin/python -m pip install -r docs/requirements.txt
.docs-venv/bin/python -m sphinx -W --keep-going -b html docs/source docs/_build/html
```

Open `docs/_build/html/index.html` locally. Windows commands and editing details
are in [development and documentation](docs/source/development.md).
The Sphinx website uses the PyData Sphinx Theme, with installation, image
workflows, a control-by-control reference and a dedicated SAM3.1 prompting
guide. GitHub Actions builds the HTML, saves an artifact and updates the
prebuilt `gh-pages` branch on `main`. Pages serves that static branch.
For local publication and hosting prerequisites, see
[website publishing](docs/source/developer/publishing.md).
`.readthedocs.yaml` supports optional Read the Docs hosting.

## Original uploads and repository layout

| Location | Contents |
| --- | --- |
| [`uploads/`](uploads/) | Original CPU ZIP, three supplied PDF manuals, notebook, and SHA-256 digests |
| [`samstudio/`](samstudio/) | Editable application source and packaged PDF help |
| [`scripts/`](scripts/) | Installers, diagnostics, and validation helpers |
| [`docs/source/`](docs/source/) | Sphinx pages and configuration |
| [`docs/`](docs/) | Release Markdown/PDF manuals and screenshots |
| [`examples/`](examples/) | Demo images and U-Net plugin example |
| [`tests/`](tests/) | Application regression tests |
| [`validation/`](validation/) | Original release evidence, separate from current test results |
| [`vendor/`](vendor/) and [`dist/`](dist/) | Bundled dependency wheels and original app wheel |

The notebook targets Google Colab and uses external `gduscher/MLSTEM2026`
workshop images; it is preserved unchanged. See
[notebook guidance](docs/source/notebook.md). The separately supplied PDFs
differ from the earlier PDFs inside the ZIP; both versions are retained.

`FILE_MANIFEST_SHA256.json` describes the **original ZIP contents**, including
its original README. It is not a checksum manifest for this expanded Git tree.
See [provenance](docs/source/provenance.md).

## Validation and licenses

Use the installed environment for `python -m samstudio.selftest --device cpu`
and the existing regression suite. Headless Linux diagnostics use
`QT_QPA_PLATFORM=offscreen`. Real model/reader validation requires external
assets; this archive omits `validation/external_assets.json`, needed by its
asset-fetch helper. See [development](docs/source/development.md) before running
full validation. Bundled reports describe the original release's checks and
do not certify a new machine's CUDA or Windows execution.

Application source is supplied under [MIT](LICENSE). Third-party dependencies
and model checkpoints have separate terms; see [notices](third_party/NOTICE.md).
BM3D/bm4d have upstream academic/non-commercial terms. The application license
does not automatically apply to the notebook, workshop assets, or model weights.
