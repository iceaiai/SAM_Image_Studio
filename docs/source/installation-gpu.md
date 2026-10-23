# GPU installation and updates

This page is readable both on GitHub and on the Sphinx website. The
[complete GPU guide](https://github.com/iceaiai/SAM_Image_Studio/blob/main/GPU/INSTALLATION.md)
contains the full prerequisites, diagnostics and model-access details.

## 1. Obtain the complete project first

Choose one route before creating an environment:

- **ZIP:** use the [CPU version download list](downloads.md), download v1.4.3
  and extract every file. The same source bundle includes `GPU/`.
  Open the extracted project folder containing `pyproject.toml`, `samstudio/` and `GPU/`.
- **Git:** run these shared commands in your chosen parent folder:

```sh
git clone https://github.com/iceaiai/SAM_Image_Studio.git
cd SAM_Image_Studio
```

ZIP users do not need to clone again. For native SAM3.1, run installation in
Linux/WSL2 using Linux Conda; obtain the source there or make the extracted
folder accessible to Ubuntu. Native Windows supports SAM1/2 and SAM3 ONNX.

## 2. Select the route and install

Use **64-bit Python 3.12**. Run from the complete project root obtained above.

**Windows or Linux: SAM1/2 and SAM3 ONNX**

```sh
conda create -n sam-image-studio-gpu python=3.12 pip -y
conda activate sam-image-studio-gpu
python GPU/install.py --current
python -m samstudio
```

**Linux/WSL2: additionally native SAM3 and SAM3.1**

```sh
conda create -n sam-image-studio-sam3 python=3.12 pip -y
conda activate sam-image-studio-sam3
python GPU/install.py --current --sam3
python -m samstudio
```

The installer handles driver-aware Torch selection, application dependencies,
ONNX runtime, compatible setuptools and missing Ubuntu Qt libraries, then runs
checks. Ubuntu may request your sudo password for missing system libraries.
Application packages are installed only into the dedicated environment.
A supported NVIDIA driver and, for WSL GUI use, working WSLg are prerequisites.

## 3. Load the selected model

In **Load model…**, choose the family and NVIDIA CUDA device. SAM3/3.1 need
approved access to their distinct authentic weights. Paste an approved read
token in the optional masked field or reuse local Hugging Face login. The GUI
field is not saved. SAM3 ONNX downloads public text-only weights without HF login.

See [SAM3.1 text/shape prompts](segmentation/sam31.md) and
[public ONNX text segmentation](segmentation/sam3-onnx.md).

## 4. Update an existing installation

Close the GUI, download/extract or pull the new complete source, then enter
its project root. Reuse the existing environment instead of recreating it:

```sh
conda activate sam-image-studio-sam3
python GPU/install.py --current --sam3
python -m samstudio
```

For the ordinary GPU environment activate `sam-image-studio-gpu` and omit
`--sam3`. No routine uninstall is needed. Preserve projects, model caches and
local login separately from downloaded source folders.

For failures, follow [troubleshooting](troubleshooting.md) and the
[complete GPU guide](https://github.com/iceaiai/SAM_Image_Studio/blob/main/GPU/INSTALLATION.md).
