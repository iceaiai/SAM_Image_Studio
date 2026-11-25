# SAM Image Studio

Desktop microscopy annotation, SAM segmentation, reversible data cleaning and
compressed-sensing restoration, with calibrated measurements and editable projects.

[CPU version downloads](https://iceaiai.github.io/SAM_Image_Studio/downloads.html) ·
**[Documentation website](https://iceaiai.github.io/SAM_Image_Studio/)** ·
[Installation](https://iceaiai.github.io/SAM_Image_Studio/installation.html) ·
[Cleaning](https://iceaiai.github.io/SAM_Image_Studio/features/cleaning.html) ·
[Segmentation modes](https://iceaiai.github.io/SAM_Image_Studio/segmentation/scopes.html) ·
[SAM3.1 text and shapes](https://iceaiai.github.io/SAM_Image_Studio/segmentation/sam31.html) ·
[Compressed sensing](https://iceaiai.github.io/SAM_Image_Studio/features/compressed-sensing.html) ·
[User Manual](https://iceaiai.github.io/SAM_Image_Studio/user-manual.html)

Version **1.4.5.2** fixes GPU detection on Windows systems whose NVIDIA driver
reports **CUDA UMD Version**. The standard ZIP includes the GPU Quick Guide and
the update steps for existing Conda environments.

## First: download or clone the complete project (CPU and GPU)

Choose **one** method below before following any CPU or GPU installation route.
You do not need Git if you download a ZIP.

| Version | Downloads | Main changes |
| --- | --- | --- |
| **1.4.5.2 — recommended** | [Standard ZIP](https://github.com/iceaiai/SAM_Image_Studio/archive/refs/tags/v1.4.5.2.zip) · [Offline CPU ZIP](https://github.com/iceaiai/SAM_Image_Studio/archive/refs/tags/v1.4.5.2-offline.zip) | Detects newer NVIDIA driver output containing **CUDA UMD Version**. |
| 1.4.5.1 | [Standard ZIP](https://github.com/iceaiai/SAM_Image_Studio/archive/refs/tags/v1.4.5.1-docs.zip) · [Offline CPU ZIP](https://github.com/iceaiai/SAM_Image_Studio/archive/refs/tags/v1.4.5.1-offline-docs.zip) | Adds keyboard deletion of mask pieces, segmentation review, measurement-colored histograms, and hand-drawn filament links. Fixes Mask pusher strokes when changing sides. |
| 1.4.5 | [Standard ZIP](https://github.com/iceaiai/SAM_Image_Studio/archive/refs/tags/v1.4.5.zip) · [Offline CPU ZIP](https://github.com/iceaiai/SAM_Image_Studio/archive/refs/tags/v1.4.5-offline.zip) | Adds two-column tools, mask-fragment cleanup, a circular mask pusher, batch vertex deletion, and adjustable polygon closure. |
| 1.4.4.2 | [Standard ZIP](https://github.com/iceaiai/SAM_Image_Studio/archive/refs/tags/v1.4.4.2.zip) · [Offline CPU ZIP](https://github.com/iceaiai/SAM_Image_Studio/archive/refs/tags/v1.4.4.2-offline.zip) | Adds calibrated line and curve rulers and fixes crashes in segmentation options, mask-color, and plot-group dialogs. |
| 1.4.4.1 | [Standard ZIP](https://github.com/iceaiai/SAM_Image_Studio/archive/refs/tags/v1.4.4.1.zip) · [Offline CPU ZIP](https://github.com/iceaiai/SAM_Image_Studio/archive/refs/tags/v1.4.4.1-offline.zip) | Adds segmentation size filters, editable scale bars, filament measurements, and shared colors for plot groups. |
| 1.4.3 | [Standard ZIP](https://github.com/iceaiai/SAM_Image_Studio/archive/refs/tags/v1.4.3.zip) | Adds public SAM3 ONNX text segmentation, updates CPU/GPU installers, and publishes illustrated guides. |
| 1.4.2 — First stable version | [CPU ZIP](https://raw.githubusercontent.com/iceaiai/SAM_Image_Studio/main/uploads/SAM_Image_Studio_v1.4.2_CPU.zip) | Includes calibrated segmentation, Excel pixel-size lookup, image restoration, and bundled manuals. |

The downloads page also lists the earlier CPU archives with their release summaries. [Show all versions](https://iceaiai.github.io/SAM_Image_Studio/downloads.html#earlier-cpu-versions)

Use the installation instructions included in the ZIP you download. For
1.4.2, run `Install_CPU.bat` or `bash install_cpu.sh` from its inner
`SAM_Image_Studio` folder. For an Offline CPU ZIP, [prepare the cache online](offline/README.md)
before installing offline.

These are source packages with an installation step. The current CPU installer
uses an existing compatible **64-bit Python 3.12**, or downloads a verified runtime
into the project folder; other Python installations remain available. The offline
ZIP is initially approximately the same size as the normal ZIP: its packages,
runtime and three checkpoints must be pre-downloaded before disconnecting.
The normal source bundle also contains the optional GPU setup files;
you do not need to download a second source package for GPU installation.

**Download route:** choose a ZIP, extract the entire archive, and open the
project folder containing `pyproject.toml` and `samstudio/`. Keep the folder contents
together. The standard 1.4.5.2 ZIP extracts to `SAM_Image_Studio-1.4.5.2/`.
It includes `GPU/QUICK_GUIDE.md` and the updated User Manual.

**Git alternative, shared by CPU and GPU:** open a terminal in the parent folder
where you want to keep the project, then run:

```sh
git clone https://github.com/iceaiai/SAM_Image_Studio.git
cd SAM_Image_Studio
```

After either route, continue below. See the [download list](https://iceaiai.github.io/SAM_Image_Studio/downloads.html)
for version details and installation steps.

## Install and start on CPU

First complete the download/extraction or Git steps above and enter the project root.

- **Windows:** double-click [`packaging/Install_CPU.bat`](packaging/Install_CPU.bat),
  then [`packaging/Start_GUI.bat`](packaging/Start_GUI.bat).
- **Linux:** run `bash packaging/install_cpu.sh`, then `bash packaging/start_gui.sh`.

The installer creates an isolated `.venv`, installs verified dependencies and the
CPU ONNX runtime, and runs checks. Ubuntu/WSL missing Qt libraries are installed
automatically; an administrator password may be required. Model weights download
separately when you choose **Load model…**.

## GPU installation, launch and updates

First download and extract the current complete source, or clone it using the
shared steps above, and enter its root. All GPU setup entry points, dependency
files and instructions are in the [GPU folder](GPU/README.md). Start with the
[GPU quick installation guide](GPU/QUICK_GUIDE.md).
Use a dedicated Anaconda/Conda environment. Native SAM3.1 requires Linux/WSL2;
SAM1/2 and SAM3 ONNX also have a native Windows GPU installation path.
For an existing GPU installation, activate its Conda environment in the new
source folder, run `python GPU/install.py --current` and launch with
`python -m samstudio`. Add `--sam3` to the installer command if you already use
the native SAM3/3.1 environment. [Update instructions](GPU/QUICK_GUIDE.md#4-update-an-existing-installation)

## What can it do?

| Task | Workflow |
| --- | --- |
| Annotate | Draw points and shapes, remove disconnected mask parts, push or carve boundaries, and undo edits. |
| Segment | SAM1/2 point/box segmentation; SAM2 text detection → masks; SAM3 ONNX text; optional native SAM3/3.1 concepts. |
| Control output | Whole-image exemplar search, single object, exact ROI/inverse-region limits, optional size bounds and review before acceptance. |
| Clean data | Remove contamination, fill from neighbors or manual background patches, and restore retained original pixels. |
| Restore pixels | TV, wavelets, DCT, sampled compressed-sensing reconstruction, BM3D, dictionary learning, and N2V/N2V2. |
| Measure/export | Line and curve distances, physical scale bars, filament centerline and width measurements, shared metric colors for named plot groups, object statistics and editable `.sam.json` projects. COCO, YOLO and mask exports are available. |

For text segmentation without Hugging Face login, choose **SAM3 ONNX** and enter
`black dots` (or `white dots` for the bundled bright-particle example). The public
export downloads about **3.53 GiB** and supports text, aliases and application ROI
clipping. Native point/shape concepts use the separate SAM3.1 backend. See the
[ONNX guide](https://iceaiai.github.io/SAM_Image_Studio/segmentation/sam3-onnx.html).

## Repository map

| Folder | Contents |
| --- | --- |
| [`GPU/`](GPU/) | GPU quick guide, detailed installation guide, installer, launchers and optional GPU requirements. |
| [`packaging/`](packaging/) | CPU launch/install/uninstall helpers, shared requirement files and Windows build recipe. |
| [`samstudio/`](samstudio/) | Application package; keep this location for Python imports. |
| [`docs/`](docs/) | Sphinx site source, illustrated guides, original manuals, release notes and validation records. |
| [`examples/`](examples/) | Synthetic demo, supplied EMD/TIFF microscopy examples and plugin example. |
| [`offline/`](offline/) | CPU offline preparation guide, model profile and entry points. |
| [`scripts/`](scripts/) | Shared setup, diagnostics, validation and website publishing helpers. |
| [`tests/`](tests/) | Regression tests. |
| [`uploads/`](uploads/) | Historical CPU archives and checksums, supplied manuals and notebook, and the 1.4.2 archive manifest and wheel. |
| [`vendor/`](vendor/) / [`third_party/`](third_party/) | Verified bundled SAM2 wheel and upstream notices/licenses. |

`pyproject.toml`, `README.md`, `LICENSE` and hosting configuration stay at the root
for packaging, GitHub and documentation tools. User projects, credentials and downloaded model weights stay outside Git; the
explicitly supplied public examples live under `examples/user_samples/`.

## Documentation and validation

Build the Sphinx website without Qt, Torch or model weights:

```sh
python3.12 -m venv .docs-venv
.docs-venv/bin/python -m pip install -r docs/requirements.txt
.docs-venv/bin/python -m sphinx -W --keep-going -b html docs/source docs/_build/html
```

See [development](docs/source/development.md) and
[website publishing](docs/source/developer/publishing.md). The website follows
installation → image workflows → menus/buttons/modes, with a source-generated API.
The 1.4.4 release validation is recorded in [`docs/validation/VALIDATION_v144.md`](docs/validation/VALIDATION_v144.md).
CPU ONNX inference has been exercised with real weights; this cloud environment
has no GPU, so no new CUDA performance or native Windows validation is claimed.

Application code is [MIT licensed](LICENSE). Model weights and third-party packages
have their own terms; see [notices](third_party/NOTICE.md). Public download does not
remove SAM model license obligations. The original PDFs/notebook remain unchanged.
