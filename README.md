# SAM Image Studio

Desktop microscopy annotation, SAM segmentation, reversible data cleaning and
compressed-sensing restoration, with calibrated measurements and editable projects.

**[Documentation website](https://iceaiai.github.io/SAM_Image_Studio/)** ·
[Installation](https://iceaiai.github.io/SAM_Image_Studio/installation.html) ·
[Cleaning](https://iceaiai.github.io/SAM_Image_Studio/features/cleaning.html) ·
[Segmentation modes](https://iceaiai.github.io/SAM_Image_Studio/segmentation/scopes.html) ·
[SAM3.1 text and shapes](https://iceaiai.github.io/SAM_Image_Studio/segmentation/sam31.html) ·
[Compressed sensing](https://iceaiai.github.io/SAM_Image_Studio/features/compressed-sensing.html)

Version **1.4.3** adds public SAM3 ONNX text segmentation, optional model-manager
Hugging Face token entry, automatic Ubuntu/WSL Qt dependency setup, and organized
installation files. Original v1.4.2 uploads remain unchanged.

## Install and start on CPU

Use **64-bit Python 3.12**. Clone or extract the complete project into a writable folder.

```sh
git clone https://github.com/iceaiai/SAM_Image_Studio.git
cd SAM_Image_Studio
```

- **Windows:** double-click [`packaging/Install_CPU.bat`](packaging/Install_CPU.bat),
  then [`packaging/Start_GUI.bat`](packaging/Start_GUI.bat).
- **Linux:** run `bash packaging/install_cpu.sh`, then `bash packaging/start_gui.sh`.

The installer creates an isolated `.venv`, installs verified dependencies and the
CPU ONNX runtime, and runs checks. Ubuntu/WSL missing Qt libraries are installed
automatically; an administrator password may be required. Model weights download
separately when you choose **Load model…**.

## GPU installation, launch and updates

All GPU setup entry points, dependency files and instructions are in **[GPU/](GPU/README.md)**.
Use a dedicated Anaconda/Conda environment. Native SAM3.1 requires Linux/WSL2;
SAM1/2 and SAM3 ONNX also have a native Windows GPU installation path.
Routine updates reuse the environment; uninstalling is unnecessary.

## What can it do?

| Task | Workflow |
| --- | --- |
| Annotate | Draw/edit points and shapes; organize objects into groups; Undo/Redo. |
| Segment | SAM1/2 point/box segmentation; SAM2 text detection → masks; SAM3 ONNX text; optional native SAM3/3.1 concepts. |
| Control output | Whole-image exemplar search, single object, exact ROI/inverse-region limits, protected annotations and review before acceptance. |
| Clean data | Remove contamination, fill from neighbors or manual background patches, and restore retained original pixels. |
| Restore pixels | TV, wavelets, DCT, sampled compressed-sensing reconstruction, BM3D, dictionary learning, and N2V/N2V2. |
| Measure/export | Physical calibration, object statistics, COCO/YOLO/masks/overlays, native editable `.sam.json` projects. |

For text segmentation without Hugging Face login, choose **SAM3 ONNX** and enter
`black dots` (or `white dots` for the bundled bright-particle example). The public
export downloads about **3.53 GiB** and supports text, aliases and application ROI
clipping. Native point/shape concepts use the separate SAM3.1 backend. See the
[ONNX guide](https://iceaiai.github.io/SAM_Image_Studio/segmentation/sam3-onnx.html).

## Repository map

| Folder | Contents |
| --- | --- |
| [`GPU/`](GPU/) | GPU README, installation/update guide, installer, launchers and optional GPU requirements. |
| [`packaging/`](packaging/) | CPU launch/install/uninstall helpers, shared requirement files and Windows build recipe. |
| [`samstudio/`](samstudio/) | Application package; keep this location for Python imports. |
| [`docs/`](docs/) | Sphinx site source, illustrated guides, original manuals, release notes and validation records. |
| [`examples/`](examples/) | Public synthetic demo and plugin example. |
| [`scripts/`](scripts/) | Shared setup, diagnostics, validation and website publishing helpers. |
| [`tests/`](tests/) | Regression tests. |
| [`uploads/`](uploads/) | Five original uploads, their digests, original archive manifest and historical wheel. |
| [`vendor/`](vendor/) / [`third_party/`](third_party/) | Verified bundled SAM2 wheel and upstream notices/licenses. |

`pyproject.toml`, `README.md`, `LICENSE` and hosting configuration stay at the root
for packaging, GitHub and documentation tools. Source images, tokens and downloaded
model weights should stay outside Git.

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
Current validation is recorded in [`docs/validation/ONNX_VALIDATION_v143.md`](docs/validation/ONNX_VALIDATION_v143.md).
CPU ONNX inference has been exercised with real weights; this cloud environment
has no GPU, so no new CUDA performance or native Windows validation is claimed.

Application code is [MIT licensed](LICENSE). Model weights and third-party packages
have their own terms; see [notices](third_party/NOTICE.md). Public download does not
remove SAM model license obligations. The original PDFs/notebook remain unchanged.
