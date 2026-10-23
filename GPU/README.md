# GPU edition: install, start and update

This folder collects GPU setup files. Run commands from the **repository root**,
the folder containing `pyproject.toml`, `samstudio/` and `GPU/`.

- **[Full GPU installation guide](INSTALLATION.md)**: Windows, WSL2, native SAM3.1,
  local authentication, updates and troubleshooting.
- `install.py`: hardware-aware installer; defaults to a new dedicated environment.
- `Install_GPU_Conda.bat` / `Start_GUI_GPU.bat`: native Windows helpers for the
  default `sam-image-studio-gpu` environment.
- `Start_GUI_SAM31.sh`: Linux/WSL launcher for `sam-image-studio-sam3` (run with bash).
- `requirements-sam3.txt`: native SAM3/3.1 Linux dependencies.
- `requirements-onnx.txt`: CUDA ONNX Runtime; installed automatically.

## Windows: SAM1/2 and public SAM3 ONNX

Open an Anaconda/Miniforge PowerShell prompt and substitute your project path:

```powershell
Set-Location -LiteralPath 'C:\work\AI works\SAM_Image_Studio'
Test-Path .\GPU\install.py
conda create -n sam-image-studio-gpu python=3.12 pip -y
conda activate sam-image-studio-gpu
python GPU/install.py --current
python -m samstudio
```

## Linux/WSL2: native SAM3.1 as well

Use Linux Conda **inside Ubuntu**, rather than the Windows Conda executable:

```bash
cd '/mnt/c/work/AI works/SAM_Image_Studio'
conda create -n sam-image-studio-sam3 python=3.12 pip -y
conda activate sam-image-studio-sam3
python GPU/install.py --current --sam3
python -m samstudio
```

Use your actual extracted path. The installer handles Ubuntu Qt libraries,
`pkg_resources` compatibility, CUDA wheel selection, ONNX runtime and self-tests.
It never installs application packages into `base`. WSL startup automatically
uses X11 when WSLg provides `DISPLAY`.

Select **SAM3.1** in Model manager. You can paste your own approved Hugging Face
read token into its masked optional field; leaving it empty reuses your local
login. This field is not saved. Alternatively select a local authentic
`sam3.1_multiplex.pt`. **SAM3 ONNX** downloads public text-only weights without a
Hugging Face token. It is a different backend from native SAM3.1.

## Update an existing environment

Close the GUI, update/extract the new **complete source**, enter its root, then:

```bash
conda activate sam-image-studio-sam3
python GPU/install.py --current --sam3
python -m samstudio
```

For the ordinary GPU environment, activate `sam-image-studio-gpu` and omit
`--sam3`. Do not rerun `conda create` for routine updates. Keep your projects,
weights and local token cache; no uninstall is required.

The [website](https://iceaiai.github.io/SAM_Image_Studio/) documents every menu,
button and prompting scope. Source implementation remains under `samstudio/`
so CPU and GPU use the same application and saved-project format.
