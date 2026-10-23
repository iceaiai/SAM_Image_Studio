# Installation

Run all commands from the repository root, the directory containing
`pyproject.toml`, `samstudio/`, and `scripts/`. Use a writable local folder and
**64-bit Python 3.12**: this release requires `>=3.12,<3.13`.

For **Anaconda GPU testing**, go to [NVIDIA GPU with Conda](#nvidia-gpu-with-conda)
and [optional SAM3/SAM3.1](#optional-sam3-and-sam31). After first installation,
use [Updating an existing Conda environment](#updating-an-existing-conda-environment).
The ordinary CPU route remains available for SAM1/SAM2.

```sh
git clone https://github.com/iceaiai/SAM_Image_Studio.git
cd SAM_Image_Studio
```

Alternatively, extract the original CPU ZIP from the [downloads](downloads.md)
page. It contains its own `SAM_Image_Studio/` top-level folder. Preserve the
complete tree, including `vendor/`, because the installer checks the bundled
SAM2 wheel's SHA-256 digest.

## Choose a backend

| Workflow | Environment | Models | Requirements |
| --- | --- | --- | --- |
| CPU | App-owned `.venv` or dedicated existing virtual/Conda environment | SAM1, SAM2/2.1 | Python 3.12; no NVIDIA hardware needed |
| NVIDIA GPU | Dedicated non-base Conda environment | SAM1, SAM2/2.1 | NVIDIA driver and compatible CUDA PyTorch wheels |
| Optional SAM3 / SAM3.1 | Separate Linux/WSL2 Conda environment | Matching SAM3 or SAM3.1 weights | Driver supporting CUDA 12.6+ and approved checkpoint access |

The installer does not install system NVIDIA drivers. AMD/Intel GPUs use the
CPU path in this release. Native Windows CUDA and real SAM3/SAM3.1 inference
require acceptance testing on the target hardware.

## CPU on Windows

1. Install 64-bit Python 3.12, if needed, using the official installer or
   `Install_Python_3_12.bat`.
2. Run `Install_CPU.bat` from the writable source/release folder.
3. Run `Start_GUI.bat`.

To install Python per user from PowerShell:

```powershell
winget install --exact --id Python.Python.3.12 --architecture x64 --scope user --source winget
```

Reopen the terminal and check `py -3.12 --version`. The batch launcher uses the
app-owned environment; no administrator shell is required for that per-user
Python installation.

## CPU on Linux

Check that `python3 --version` reports Python 3.12, then run:

```sh
bash install_cpu.sh
bash start_gui.sh
```

If `python3` is a different version but `python3.12` is installed, use the
installer explicitly:

```sh
python3.12 scripts/install_environment.py --backend cpu
bash start_gui.sh
```

The installer creates `.venv`, installs CPU PyTorch 2.7.1 and torchvision 0.22.1,
installs `requirements.lock.txt` and the bundled SAM2 wheel, installs the app,
runs `pip check`, and runs `samstudio.selftest --device cpu`. System Python
packages remain separate. If `.venv` already exists without the app's ownership
marker, the installer stops rather than replacing it.

## CPU in an existing dedicated environment

Activate a Python 3.12 virtual environment or create a CPU Conda environment:

```sh
conda create -n sam-image-studio-cpu python=3.12 pip
conda activate sam-image-studio-cpu
python scripts/install_environment.py --backend cpu --current
python -m samstudio
```

`--current` requires an activated virtual or Conda environment. When using it,
start with `python -m samstudio`; the default shell/batch launchers target the
app-owned `.venv` instead.

## NVIDIA GPU with Conda

Install Anaconda, Miniforge, or another Conda distribution from its official source. Open
its Conda prompt, change to this repository, and inspect the detected hardware
and installation plan:

### First choose the correct project folder

The working directory must be the **inner `SAM_Image_Studio` folder containing
`scripts/`, `samstudio/`, and `pyproject.toml`**. Do not run installer commands
from `C:\Users\yourname`, the parent ZIP extraction folder, or inside `scripts/`.
The CPU-named release archive also contains the GPU installer; you can use that
complete source tree for the dedicated GPU installation.

In **Anaconda PowerShell Prompt**, put paths containing spaces in quotes.
For example, replace this sample path with your actual extracted folder:

```powershell
Set-Location -LiteralPath 'C:\work\AI works\Desktop_SAM3\SAM_Image_Studio_v1.4.2_CPU\SAM_Image_Studio'
Test-Path .\scripts\install_conda_gpu.py
Test-Path .\pyproject.toml
```

Both checks must return **`True`**. An unquoted path such as `cd C:\work\AI works\...`
is split at the space, producing PowerShell's "A positional parameter cannot
be found" error. `cd 'C:\path with spaces\SAM_Image_Studio'` is also valid;
`Set-Location -LiteralPath` is explicit and avoids wildcard interpretation.

### First installation: native Windows SAM1/2 GPU

After the folder checks above, run:

```powershell
conda run -n base python scripts/install_conda_gpu.py --inspect
conda run -n base python scripts/install_conda_gpu.py --name sam-image-studio-gpu --dry-run
conda run -n base python scripts/install_conda_gpu.py --name sam-image-studio-gpu
conda activate sam-image-studio-gpu
python -m pip check
python -m samstudio.selftest --device cuda
python -m samstudio
```

This creates a **new** environment. `(base)` in the prompt is normal for the
first three outer commands; the app runs after activating the dedicated GPU
environment. If that name already exists and you are updating, use the
[existing-environment update steps](#updating-an-existing-conda-environment)
instead of recreating it.

On Linux, change to the corresponding project path first, then use the same
Conda commands for SAM1/2 GPU. For SAM3/SAM3.1 use the separate recipe below.

On Windows, `Install_GPU_Conda.bat` and `Start_GUI_GPU.bat` use this default
environment name. An existing Conda environment is not silently replaced.

The planner selects PyTorch 2.7.1 / torchvision 0.22.1 from `cu128`, `cu126`, or
`cu118` according to the driver's reported capability. GPUs with compute
capability 10 or newer require the CUDA 12.8 build; outdated drivers are
rejected. A driver-reported CUDA version is its maximum supported runtime,
not evidence of working CUDA inference or sufficient free VRAM.

Select **NVIDIA CUDA (Conda)** or **Automatic device** in Model manager.
Automatic chooses the visible CUDA device with most total memory inside Conda;
otherwise it uses CPU. This application rejects CUDA outside Conda and in the
GPU installer's base environment. Do not add GPU packages to the CPU `.venv`.

The CUDA self-test exercises a matrix product, torchvision NMS, recovery, and
GUI construction. Model inference still requires compatible checkpoints and a
representative preview/save/reopen test with actual images.

## Optional SAM3 and SAM3.1

Use Linux or WSL2, Conda, and a driver supporting CUDA 12.6 or later:

**Native Windows Anaconda is not the SAM3.1 installation path in this release.**
If you are at a `(base) PS C:\...>` prompt on Windows, the ordinary commands
above prepare SAM1/2 GPU. For SAM3.1, open a **Linux/WSL2 terminal** and use a
Linux Anaconda/Conda installation inside WSL2. Windows and WSL Conda
environments are separate; do not try to activate the Windows environment from
the Linux shell.

For the sample Windows folder above, the corresponding WSL path is:

```sh
cd '/mnt/c/work/AI works/Desktop_SAM3/SAM_Image_Studio_v1.4.2_CPU/SAM_Image_Studio'
test -f scripts/install_conda_gpu.py && test -f pyproject.toml
```

Keep the path quoted because it contains a space. Confirm that NVIDIA detection
works in WSL2 and that Linux Conda is available, then create the separate
SAM3/SAM3.1 environment:

```sh
conda run -n base python scripts/install_conda_gpu.py --inspect
conda run -n base python scripts/install_conda_gpu.py --name sam-image-studio-sam3 --sam3
conda activate sam-image-studio-sam3
python -m pip check
python -m samstudio.selftest --device cuda
hf auth login
python -m samstudio
```

Obtain access separately at <https://huggingface.co/facebook/sam3> or
<https://huggingface.co/facebook/sam3.1>. Select the matching model family and
authorized checkpoint in Model manager. `sam3.pt` and
`sam3.1_multiplex.pt` are different architectures and are not interchangeable.
SAM3 CPU and native Windows SAM3 are not enabled as verified installation paths.

`requirements-sam3-experimental.txt` pins the official SAM3 source commit and a
separate NumPy 1.26-compatible dependency graph. The default CPU recipe uses
NumPy 2. Do not merge these environments or independently upgrade their
NumPy/TIFF/codec dependencies. See the source release's
{download}`GPU guide <../../GPU_CONDA_GUIDE.md>` for the recorded validation limits.

## Updating an existing Conda environment

**A routine GPU application update does not require uninstalling Anaconda or
deleting the existing environment.** Close the GUI, obtain the new source
version, activate the same dedicated GPU environment, and run the installer
from the new version's directory.

For SAM3/SAM3.1:

```sh
conda activate sam-image-studio-sam3
git pull --ff-only
python scripts/install_conda_gpu.py --current --sam3
python -m samstudio
```

Replace the environment name with your actual name. If using a new release ZIP,
extract the complete new release to a fresh folder and change to it **instead
of** running `git pull`. The same `--current --sam3` command updates the app and
dependencies in the existing activated environment. Do not run the
environment-creation command with the existing name for routine updates.

For a SAM1/2-only GPU environment, use
`python scripts/install_conda_gpu.py --current` without `--sam3`.
For an existing CPU environment, use
`python scripts/install_environment.py --backend cpu --current`.

Installing only a requirements file does not update all of the application,
verified vendor wheel, or hardware-selected PyTorch installation steps. The
project installer performs those steps, checks dependency consistency, and
runs the self-test. Keep model weights/projects in their existing separate
locations and select weights matching the chosen architecture.

Create a **new parallel environment** when a release explicitly requires an
incompatible stack or dependency conflicts cannot be resolved. Keep the old
working environment until the new one passes your GPU/model acceptance checks.
That is a migration decision, not a requirement for every version update.

## Models, storage, and network

Model weights are **not bundled**. Model manager can download supported SAM1/2
weights separately, or use a matching local checkpoint. Text prompting for
SAM2/2.1 additionally downloads the pinned Grounding DINO model. No hosted API
key is needed for ordinary local CPU annotation. Gated SAM3/SAM3.1 weights need
the user's own approved access.

Installation uses PyPI (`pypi.org`, `files.pythonhosted.org`) and
`download.pytorch.org` and its official redirects. Model downloads use hosts
specified in `samstudio/inference.py`, including
`dl.fbaipublicfiles.com`; optional Hugging Face models also need
`huggingface.co` and the download destinations returned by that service.
Restricted cloud environments must allow the actual required destinations.
Keep TLS and artifact checksum verification enabled.

Application state/model caches normally live at
`%LOCALAPPDATA%/SAMImageStudio` on Windows or
`~/.local/share/sam-image-studio` on Linux. `SAM_STUDIO_DATA_DIR` overrides the
location. Choose a writable **project folder** for native `.sam.json` saves.

## Headless cloud checks

The app is a Qt desktop GUI. A local desktop needs a working display. On a
headless Linux machine, run installation diagnostics offscreen:

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m samstudio.selftest --device cpu
```

Offscreen checks construct the GUI and exercise persistence; they do not
provide an interactive desktop or verify GPU model inference.

## Uninstall

Close the GUI, then use `Uninstall.bat` or `bash uninstall.sh` for app-owned
local environments. For the dedicated GPU environment:

```sh
conda deactivate
conda env remove -n sam-image-studio-gpu
```

Use its actual name. Source images, annotation projects, exports, and model
caches are preserved by the supported uninstallers. See
[troubleshooting](troubleshooting.md) for recovery and dependency failures.
