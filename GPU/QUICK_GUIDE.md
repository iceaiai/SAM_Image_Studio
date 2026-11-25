# GPU quick installation guide

## 1. Obtain the complete project first

Get the **Standard ZIP** and extract it, or clone the repository using the commands below. The project root contains `GPU/install.py`, `samstudio/` and `pyproject.toml`. [Downloads](https://iceaiai.github.io/SAM_Image_Studio/downloads.html)

```sh
git clone https://github.com/iceaiai/SAM_Image_Studio.git
cd SAM_Image_Studio
```

Install Miniforge or Anaconda for your platform. Open its terminal, change to the project root and run `nvidia-smi` to check that the NVIDIA driver can see the GPU. For WSL2, run the commands inside the Linux distribution with Linux Conda and a working WSLg display.

## 2. Select the route and install

Use a dedicated Conda environment with **64-bit Python 3.12**. The installer checks the driver, selects the matching Torch and ONNX Runtime dependencies, prepares missing Ubuntu Qt libraries and runs installation checks. Installing Ubuntu system libraries can require your sudo password.

**Windows or Linux for SAM1/2 and SAM3 ONNX**

On Windows, open **Anaconda Prompt** from the Start menu. Use `cd /d` with the full path in double quotes. If extraction produced two folders with the same name, enter the inner folder that contains `GPU\install.py` and `pyproject.toml`. Replace the example path with your actual extracted folder.

```bat
cd /d "C:\Work\AI Projects\SAM_Image_Studio-1.4.5.1-docs\SAM_Image_Studio-1.4.5.1-docs"
dir GPU\install.py
nvidia-smi
conda env list
```

On Linux, use your initialized Conda terminal in the project root.

If `conda env list` shows your existing SAM Image Studio GPU environment, go to **4. Update an existing installation**. For a first installation, run these commands in order.

```sh
conda create -n sam-image-studio-gpu python=3.12 pip -y
conda activate sam-image-studio-gpu
python GPU/install.py --current
python -m samstudio
```

On Windows, `GPU\Install_GPU_Conda.bat` and `GPU\Start_GUI_GPU.bat` are shortcuts for the default environment.

**Linux/WSL2 for native SAM3 and SAM3.1**

These models require NVIDIA driver support for CUDA 12.6 or later. Some newer GPUs require a newer driver. For a first installation, run the following in a Linux Conda terminal. To reuse an existing native-model environment, go to **4. Update an existing installation**.

```sh
conda create -n sam-image-studio-sam3 python=3.12 pip -y
conda activate sam-image-studio-sam3
python GPU/install.py --current --sam3
python -m samstudio
```

## 3. Load the selected model

1. Open an image and choose **Load model…**. For ordinary GPU segmentation, try **SAM2.1 → Base+**. Set **Execution device** to **NVIDIA CUDA GPU (Conda)**.
2. For **SAM1/2**, choose a variant and download or select its matching checkpoint. For **SAM3 ONNX**, choose **ViT-H · text prompts** and let the app download the public files or browse to a verified local folder. ONNX CUDA uses CUDA 12.x and cuDNN 9. With the legacy CUDA 11.8 plan, use CPU for ONNX and CUDA for SAM1/2.
3. For **native SAM3 or SAM3.1**, get access to the chosen model on Hugging Face. Use a matching local checkpoint, an existing Hugging Face login, or paste an approved read token into the optional masked field. The app does not save that field. SAM3.1 uses `sam3.1_multiplex.pt`.
4. Click **Download / load** and wait for the loaded model status. In **Segment**, run a short text prompt for SAM3 ONNX, or draw a supported prompt for the selected native model. Check the preview before **Accept masks**. To check CUDA, run `python -m samstudio.selftest --device cuda` in the same environment. The preview checks that your specific model loads and runs.

## 4. Update an existing installation

Close the app and extract the new complete ZIP, or pull the update in your existing Git checkout. Enter the new project root. Your existing dedicated Conda environment can be used from the new source folder. Run `conda env list` to find its name and activate it. Use the commands below for the default GPU environment and substitute your environment's name if it differs.

```sh
conda activate sam-image-studio-gpu
python GPU/install.py --current
python -m samstudio
```

For the existing native SAM3/3.1 environment in Linux/WSL2, activate `sam-image-studio-sam3` and run `python GPU/install.py --current --sam3`, then `python -m samstudio`. The installer updates the application and checks the dependencies in the active environment. Reuse your compatible 64-bit Python 3.12 environment, model cache and saved projects.

## 5. Start again after installation

Open Anaconda Prompt or the Conda terminal used for installation, enter the same project root and activate your environment. Run `python -m samstudio`. Rerun the installer when updating to new source.

For driver checks, authentication, WSL startup and updates, see the [full GPU installation guide](https://github.com/iceaiai/SAM_Image_Studio/blob/main/GPU/INSTALLATION.md).
