# Installation and updates

Install once, then reuse the environment for updates. Use the complete source
folder containing `pyproject.toml`, `samstudio/`, `packaging/` and `GPU/`.
All application environments use **64-bit Python 3.12**.

| What you want | Installation |
| --- | --- |
| CPU annotation, SAM1/2, public SAM3 ONNX text | CPU instructions below |
| NVIDIA GPU, SAM1/2 or public SAM3 ONNX | [GPU / Anaconda guide](installation-gpu.md) |
| Native SAM3.1 text and positive/negative shapes | [Linux/WSL2 GPU guide](installation-gpu.md) |
| Website development only | [Documentation build](development.md#build-the-sphinx-documentation) |

SAM3 ONNX downloads public text-only weights without HF login. Native SAM3.1
has a separate installation and gated weights; it is not an ONNX mode switch.

## CPU: Windows

1. Install Python 3.12 64-bit, if absent. The helper
   `packaging/Install_Python_3_12.bat` uses the official WinGet package.
2. Open the complete source folder, then open **packaging**.
3. Double-click **Install_CPU.bat** and wait for the installation self-test.
4. Double-click **Start_GUI.bat**.

For a command-line install, first enter your real project folder, quoting spaces:

```powershell
Set-Location -LiteralPath 'C:\work\AI works\SAM_Image_Studio'
Test-Path .\pyproject.toml
py -3.12 scripts/install_environment.py --backend cpu
.\.venv\Scripts\python.exe -m samstudio
```

The installer creates an app-owned `.venv` at the repository root. It keeps
system Python and Conda base separate. Do not move only `samstudio/` out of the
source tree and then run installation helpers.

## CPU: Linux

With Python 3.12 available, enter the repository root:

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

## Existing dedicated CPU environment

If using a dedicated Conda/virtual environment, activate its Python 3.12 first:

```sh
python scripts/install_environment.py --backend cpu --current
python -m samstudio
```

The installer supplies dependencies, the verified SAM2 wheel, app code, CPU
ONNX runtime, `pip check` and installation self-test. Model weights are loaded
separately. Do not install both CPU and GPU ONNX Runtime distributions together;
the provided helper selects the correct distribution for the environment.

## NVIDIA GPU with Conda

All GPU setup files live under `GPU/`. Follow the
[complete GPU installation and updates guide](installation-gpu.md), including
quoted PowerShell paths, WSL2, authentication and routine updates without
uninstalling. No application packages are installed into Conda base.

```{toctree}
:maxdepth: 1

installation-gpu
```

## Choose a model after installation

Use **Load model…**. SAM1/2 checkpoints download on demand. For SAM3 ONNX, choose
that family, leave the folder blank and allow about 3.53 GiB plus a small tokenizer
for first download. Later loads reuse verified local files. Text aliases and
ROI clipping work with this backend; native shape/point prompts do not.

For SAM3/3.1, choose the matching family and authentic weights. You can paste
an approved read token in the masked optional Model manager field or reuse
local HF login. See [SAM3.1 prompting](segmentation/sam31.md).

## Update without uninstalling

Close the GUI, update/extract the **complete** new source, and enter its root.
For the existing app-owned CPU environment, rerun its installer. For an activated
dedicated CPU environment, use `--current`. GPU uses `GPU/install.py --current`
and, for native SAM3.1, `--sam3`. Do not recreate the same Conda environment for
every update, and do not install only a requirements file as an app update.

Version 1.4.3 automatically handles the Qt/font/XCB libraries and
`pkg_resources` compatibility encountered with the earlier v1.4.2 installation.
The installer performs these repairs; normal users need no per-library commands.
Keep source images, `.sam.json` projects, exports and model caches separately.

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
