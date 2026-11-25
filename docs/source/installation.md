# Installation and updates

Install once, then reuse the environment for updates. Use the complete source
folder containing `pyproject.toml`, `samstudio/`, `packaging/` and `GPU/`.
All application environments use **64-bit Python 3.12**.

| What you want | Installation |
| --- | --- |
| CPU annotation, SAM1/2, public SAM3 ONNX text | CPU instructions below |
| NVIDIA GPU, SAM1/2 or public SAM3 ONNX | [GPU quick installation guide](installation-gpu.md) |
| Native SAM3.1 text and positive/negative shapes | [Linux/WSL2 GPU guide](installation-gpu.md) |
| Disconnected CPU, SAM1 + SAM2.1 Small/Base+ | [Offline source edition and preparation](installation-offline.md) |
| Website development only | [Documentation build](development.md#build-the-sphinx-documentation) |

SAM3 ONNX downloads public text-only weights without HF login. Native SAM3.1
has a separate installation and gated weights; it is not an ONNX mode switch.

## First for every route: download, extract or clone

CPU and GPU installations both need the complete project first. Choose **one**:

- **Download:** open the [CPU version download list](downloads.md), click
  **Standard ZIP** for the latest version, and extract the entire archive. The same source
  bundle includes optional GPU setup. Enter the extracted project folder containing
  `pyproject.toml`, `samstudio/`, `packaging/` and `GPU/`.
- **Clone:** open a terminal in your chosen parent folder and run:

```sh
git clone https://github.com/iceaiai/SAM_Image_Studio.git
cd SAM_Image_Studio
```

ZIP users do not need Git or another clone. For native SAM3.1, use Linux/WSL2
for the environment and installation commands. After obtaining the source,
continue with exactly one CPU or GPU route below.

## CPU: Windows

1. Download/extract the complete current source or clone it using the shared
   steps above. Open the extracted project folder containing `pyproject.toml`.
2. No separate Python installation is needed: the installer chooses a compatible
   64-bit Python 3.12 or prepares a verified project-local runtime automatically.
   An older/default Python does not receive the application packages.
3. Open **packaging** in that source folder.
4. Double-click **Install_CPU.bat** and wait for the installation self-test.
5. Double-click **Start_GUI.bat**.

For command-line installation, obtain/extract the source first, then enter its
root. The path below is a fictional example; substitute your chosen folder and
quote paths containing spaces:

```powershell
Set-Location -LiteralPath 'C:\Projects\Example Folder\SAM_Image_Studio'
Test-Path .\pyproject.toml
.\packaging\Install_CPU.bat
.\.venv\Scripts\python.exe -m samstudio
```

The installer creates an app-owned `.venv` at the repository root. It keeps
system Python and Conda base separate. Do not move only `samstudio/` out of the
source tree and then run installation helpers.

## CPU: Linux

First download/extract the complete current source or clone it using the shared
steps above. On Linux x86-64, the helper uses an existing Python 3.12 or prepares
a verified local runtime. A distribution-provided `python3` is needed to run the
bootstrap. Enter that project root:

```bash
cd '/path/with spaces/SAM_Image_Studio'
bash packaging/install_cpu.sh
bash packaging/start_gui.sh
```

Ubuntu/WSL Qt libraries are detected and installed automatically. A non-root
user may be asked for their Ubuntu `sudo` password. On another distribution,
an administrator must supply equivalent Qt system libraries if unavailable.
The Python installer supports macOS CPU setup where the pinned dependency
wheels are available; this release has not been acceptance-tested on macOS.

The automatic runtime is stored under `.python312/`, and packages stay inside
`.venv/`. Neither system Python nor Conda base is modified. Windows uses the PSF
Python NuGet distribution; Linux x86-64 uses python-build-standalone. Other CPU
architectures need an existing compatible Python 3.12.

For a disconnected machine, first download the **offline CPU** ZIP and complete
[online preparation](installation-offline.md) on a matching platform.

## Existing dedicated CPU environment

First download/extract or clone the complete current project and enter its
root as above. If using a dedicated Conda/virtual environment, activate its
Python 3.12 before running:

```sh
python scripts/install_environment.py --backend cpu --current
python -m samstudio
```

The installer supplies dependencies, the verified SAM2 wheel, app code, CPU
ONNX runtime, `pip check` and installation self-test. Model weights are loaded
separately. Do not install both CPU and GPU ONNX Runtime distributions together;
the provided helper selects the correct distribution for the environment.

## NVIDIA GPU with Conda

First download/extract or clone the complete current source using the common
steps above and enter its root. All GPU setup files live under `GPU/`.

On Windows, the GPU guide shows how to enter a quoted path in **Anaconda Prompt**
when ZIP extraction creates two nested folders with the same name.
[Windows folder and installer steps](installation-gpu.md#2-select-the-route-and-install)

For **SAM1/2 and SAM3 ONNX** on Windows or Linux, open an initialized Conda
terminal in that folder, then run:

```sh
conda create -n sam-image-studio-gpu python=3.12 pip -y
conda activate sam-image-studio-gpu
python GPU/install.py --current
python -m samstudio
```

For **native SAM3/SAM3.1**, obtain/extract the source inside Linux/WSL2 or where
Ubuntu can access it, enter its root in Ubuntu, and use Linux Conda:

```sh
conda create -n sam-image-studio-sam3 python=3.12 pip -y
conda activate sam-image-studio-sam3
python GPU/install.py --current --sam3
python -m samstudio
```

Create the environment only for a first installation. If you already installed
SAM Image Studio, activate the existing dedicated environment and use the
update commands. [GPU update guide](installation-gpu.md#4-update-an-existing-installation)

## Choose a model after installation

Use **Load model…**. SAM1/2 checkpoints download on demand. For SAM3 ONNX, choose
that family, leave the folder blank and allow about 3.53 GiB plus a small tokenizer
for first download. Later loads reuse verified local files. Text aliases and
ROI clipping work with this backend; native shape/point prompts do not.

For SAM3/3.1, choose the matching family and authentic weights. You can paste
an approved read token in the masked optional Model manager field or reuse
local HF login. See [SAM3.1 prompting](segmentation/sam31.md).

## Update without uninstalling

Close the GUI. Extract the complete new ZIP, or run `git pull --ff-only` in
your source checkout. Enter the folder containing `pyproject.toml`. Keep your
source images, `.sam.json` projects, exports and model cache.

| Existing installation | Update |
| --- | --- |
| **GPU with Conda** | Activate your existing environment by name, run `python GPU/install.py --current` from the updated source, then `python -m samstudio`. Include `--sam3` for the native SAM3/3.1 environment in Linux/WSL2. |
| **CPU in a dedicated environment** | Activate your existing 64-bit Python 3.12 environment and run `python scripts/install_environment.py --backend cpu --current`, then `python -m samstudio`. |
| **CPU with project-local `.venv`** | Rerun the CPU helper in an updated checkout to reuse its `.venv`. When extracting into a new folder, the helper prepares a local environment there. To reuse the old `.venv`, activate it from its original path and use the dedicated CPU commands. |
| **Offline CPU** | Reuse the downloaded cache files on a matching platform. Rerun offline preparation in the new source before running the normal installer on the target. See the [offline instructions](installation-offline.md). |

Version 1.4.3 automatically handles the Qt/font/XCB libraries and
`pkg_resources` compatibility encountered with the earlier v1.4.2 installation.
The installer performs these repairs; normal users need no per-library commands.

## Storage, network and diagnostics

The installation uses PyPI and official PyTorch indexes. Public ONNX files use
GitHub Releases; optional native/text models use Hugging Face and its download
hosts. Keep TLS and model checksum verification enabled.

Application state defaults to `%LOCALAPPDATA%/SAMImageStudio` on Windows and
`~/.local/share/sam-image-studio` on Linux; `SAM_STUDIO_DATA_DIR` overrides it.
Native projects use the folder selected through File. HF CLI login uses its
own local cache; app token-field input is not saved.

On a machine without a display, `QT_QPA_PLATFORM=offscreen` supports installation
self-tests. It does not open an interactive window or prove model inference.
See [troubleshooting](troubleshooting.md) if an installer check fails.

## Uninstall

Use `packaging/Uninstall.bat` or `bash packaging/uninstall.sh` for app-owned CPU
environments. Dedicated Conda environments are removed with `conda env remove`
after deactivation. User images, annotation projects and model caches are retained
by the supported uninstallers.
