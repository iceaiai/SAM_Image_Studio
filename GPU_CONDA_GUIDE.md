# GPU setup in a dedicated Conda environment

This release keeps GPU execution inside Conda. The default CPU installation does
not require Conda. The setup reads every NVIDIA device reported by nvidia-smi,
its architecture, driver and available CUDA runtime capability. It does not
install drivers. AMD/Intel devices use the CPU path in this release.

## 1. Install and open Conda

Install Miniforge or another Conda distribution from its official source. Open
its Conda prompt. Change to the extracted SAM_Image_Studio folder. Use a writable
folder and preserve the complete release tree.

```text
conda --version
cd C:\path\to\SAM_Image_Studio
conda run -n base python scripts/install_conda_gpu.py --inspect
```

On Linux/WSL2 use the corresponding Linux path. If Python is already available
in the active prompt, the `conda run -n base` prefix is optional for setup.

## 2. Inspect the plan and create the environment

```text
conda run -n base python scripts/install_conda_gpu.py --name sam-image-studio-gpu --dry-run
conda run -n base python scripts/install_conda_gpu.py --name sam-image-studio-gpu
```

On Windows, `Install_GPU_Conda.bat` runs the same setup for the default name.
The outer command creates a new environment containing Python 3.12 and pip,
then runs installation inside it. An existing name is not silently replaced.

The installer selects PyTorch 2.7.1 / torchvision 0.22.1 from CUDA 12.8, 12.6
or 11.8 wheel indexes according to the detected driver/architecture. New GPU
architectures needing CUDA 12.8 are rejected when the driver is too old.
Unsupported/undetected hardware produces a reason and leaves the CPU option
available. A driver-reported CUDA version is its maximum supported runtime,
not proof that inference or an independently installed CUDA toolkit works.

## 3. Activate and run

```text
conda activate sam-image-studio-gpu
python -m pip check
python -m samstudio.selftest --device cuda
python -m samstudio
```

Select NVIDIA CUDA (Conda) or Automatic device in Model manager. Automatic
selection uses the visible CUDA device with the largest reported total memory
when a CUDA-enabled Conda environment is active; otherwise it uses CPU.
Start_GUI_GPU.bat targets the default environment. For another environment name,
activate that name and use `python -m samstudio`.

## Manual environment creation

```text
conda create -n sam-image-studio-gpu python=3.12 pip
conda activate sam-image-studio-gpu
python scripts/install_conda_gpu.py --current
python -m samstudio
```

Use a dedicated environment, not Conda base. The general CPU installer refuses
`--backend cuda`; it redirects users to this Conda flow. The model loader also
rejects CUDA outside Conda.

## Optional native SAM3

The native SAM3 recipe targets Linux/WSL2 Conda and a driver supporting CUDA
12.6 or later. Native Windows SAM3 is not claimed as validated. In Linux/WSL2:

```text
python scripts/install_conda_gpu.py --name sam-image-studio-sam3 --sam3
conda activate sam-image-studio-sam3
hf auth login
python -m samstudio
```

Request and obtain model access from https://huggingface.co/facebook/sam3 before
downloading gated weights. Authentication is a separate user action. Select a
compatible authorized checkpoint or allow the native model loader to download
it after access is available. SAM3 CPU is not enabled as a verified backend.

The optional recipe uses a NumPy 1.26-compatible TIFF/codec set, separately from
the default NumPy 2 CPU/SAM1/2 recipe. Its complete Linux dependency graph is
resolved with PyTorch 2.7.1 constraints. This checks metadata compatibility,
not CUDA execution or full SAM3 inference. Do not upgrade that environment's
NumPy/TIFF/codec stack independently without regression checks.

## Local acceptance

After installation, load actual compatible weights and test point/shape preview,
whole-image positive/negative exemplars, acceptance, save/reopen, text prompts,
cleaning, statistics and PDF help. The installer self-test runs a matrix product and torchvision NMS on CUDA,
synchronizes the device, checks native imports/recovery and constructs the GUI; model accuracy and memory/performance still depend on
actual hardware, checkpoints and images.

The release validation machine has no NVIDIA GPU. Driver detection, rejection
paths and Conda command generation were tested with explicit synthetic hardware
reports. Windows dependency metadata and optional Linux SAM3 dependency metadata
were resolved. CUDA kernels, Windows execution and real SAM3 weights were not
run here. Consult TEST_REPORT.md for the recorded boundaries.

## Remove only the GPU environment

Close the GUI, then:

```text
conda deactivate
conda env remove -n sam-image-studio-gpu
```

Use the actual environment name. Images, annotation projects, exports and model
caches are separate and are not removed by this command.

Official references:

- https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html
- https://pytorch.org/get-started/previous-versions/
- https://github.com/facebookresearch/sam3


## SAM3.1 multiplex backend

SAM3.1 is available in Model manager as its own family, GPU only. Use the same --sam3 dedicated Linux/WSL2 Conda installer. The pinned official SAM3 source commit 7f473cfd983d5eb43040ff608f66bff0d7bdcb53 includes the official SAM3.1 multiplex builder. Requirements constrain PyTorch 2.7.1 / torchvision 0.22.1 and a NumPy 1.26-compatible restoration graph. SAM3.1 is not a CPU option. Native Windows users should use WSL2 for this optional backend.

Request approved access at https://huggingface.co/facebook/sam3.1 and authenticate locally with the Hugging Face CLI, or select your existing sam3.1_multiplex.pt. The SAM3 sam3.pt checkpoint is a different architecture. Never rename one to substitute for the other. Device=Automatic chooses the CUDA device with most total VRAM among available devices only inside Conda. The installer detects NVIDIA driver/build compatibility; it cannot guarantee enough free VRAM for a model or dataset. This build disables FA3, compilation and warm-up in the multiplex factory.

Local acceptance: select SAM3.1 and CUDA/Automatic, load the actual weights, open a small image, add one positive area example, then a negative example and another positive case. Run text as well, accept/reopen masks, cancel a preview and check GPU memory after repeated runs. Record device/driver, environment and checkpoint details with results. The supplied CPU validation executes contract checks, not these hardware tests. Model access/download and local checkpoint compatibility are checked only when loading.

The same environment supplies Excel lookup, SPORCO, BM3D and CAREamics. A zarr 3.0.10 pin keeps the SAM3 NumPy<2 graph compatible; the CPU environment uses a current NumPy2-compatible Zarr. Do not replace CPU lock files in place with SAM3 requirements.
