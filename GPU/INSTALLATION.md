# NVIDIA GPU with Anaconda / Conda

Choose the backend first. **SAM1/2 and SAM3 ONNX** have Windows and Linux GPU
installation paths. **Native SAM3 / SAM3.1** use Linux or WSL2 Ubuntu and their
separate optional dependency set. They require approved compatible weights.
SAM3 ONNX public text weights do not require Hugging Face login.

## 1. Open the correct terminal and project folder

On Windows, open **Anaconda PowerShell Prompt** or an initialized Conda prompt.
Quote paths containing spaces:

```powershell
Set-Location -LiteralPath 'C:\work\AI works\SAM_Image_Studio'
Test-Path .\GPU\install.py
Test-Path .\pyproject.toml
```

Replace the example path with your actual clone/extracted folder. Both checks
must return `True`. Do not enter only the outer archive directory.

For native SAM3.1, enter your existing WSL2 Ubuntu distribution first:

```powershell
wsl -d Ubuntu-22.04
```

Then use Linux paths and the Linux Conda installation:

```bash
cd '/mnt/c/work/AI works/SAM_Image_Studio'
test -f GPU/install.py && echo 'Project folder OK'
conda --version
nvidia-smi
```

The Windows NVIDIA driver must expose the GPU to WSL2. Installing Windows
Anaconda alone does not create a Linux Conda installation. Install Anaconda or
Miniforge for Linux inside WSL if `conda` is missing there. WSLg supplies the GUI
display; keep WSL updated through Windows when its display service is unavailable.

## 2. Create one dedicated environment

**Windows or Linux, SAM1/2 + SAM3 ONNX:**

```sh
conda create -n sam-image-studio-gpu python=3.12 pip -y
conda activate sam-image-studio-gpu
python GPU/install.py --current
```

**Linux/WSL2, additionally native SAM3/SAM3.1:**

```sh
conda create -n sam-image-studio-sam3 python=3.12 pip -y
conda activate sam-image-studio-sam3
python GPU/install.py --current --sam3
```

The creation command may run from a base Conda prompt; it creates a **separate**
environment. All application package installation happens after activation.
`--current` rejects base. There is no need to upgrade, remove or install app
packages in base.

Optional inspection before installation:

```sh
python GPU/install.py --inspect
python GPU/install.py --current --sam3 --dry-run
```

Omit `--sam3` for the ordinary GPU environment. An existing named environment
must use `--current`; the default automatic creation command is for new names.

## 3. What installation handles automatically

The installer detects the driver/GPU, selects compatible PyTorch 2.7.1 and
Torchvision 0.22.1 wheels (CUDA 12.8, 12.6 or 11.8 where supported), installs
application dependencies and the verified bundled SAM2 wheel, adds CUDA ONNX
Runtime, runs `pip check`, and executes the CUDA installation self-test.
The ONNX CUDA package needs CUDA 12.x/cuDNN 9. With a legacy CUDA 11.8 Torch
plan, the installer supplies CPU ONNX instead; SAM1/2 still use CUDA. Update
the driver and reinstall with a CUDA 12.x plan to use ONNX on GPU.

On Ubuntu/WSL, it detects and installs missing Qt display/font/XCB libraries
in one system-package step. A non-root user may need to enter their **Ubuntu
administrator password** for `sudo`. The SAM3 requirements pin a compatible
setuptools release for `pkg_resources`. The launcher selects X11 on WSLg when
`DISPLAY` is present. These repairs are built in; do not install each library
or edit environment variables by hand during a normal installation.

Driver installation, access approval for gated model weights, and GUI display
availability are external prerequisites. CUDA maximum shown by `nvidia-smi`
is driver capability; it need not equal the CUDA runtime bundled with Torch.
Native SAM3 requires driver support for CUDA 12.6 or newer in this release.

## 4. Start and load a model

From the same activated environment and project root:

```sh
python -m samstudio
```

Choose **Load model… → SAM3.1 → NVIDIA CUDA GPU (Conda)** for native SAM3.1.
The optional **Hugging Face token** field is masked and accepts paste. Use a
token belonging to the account approved for
[facebook/sam3.1](https://huggingface.co/facebook/sam3.1), with permission to read
that gated repository. The field is used for this download and is not saved
in projects, application settings or Git credentials. Leave it blank to use
your existing local Hugging Face login. A local matching checkpoint avoids a
download. `sam3.pt` and `sam3.1_multiplex.pt` are distinct, incompatible weights.

For **SAM3 ONNX**, select that family and leave the model-folder field blank
to download the public export. Native geometric prompts are unavailable in
this text-only export. See the
[ONNX guide](https://iceaiai.github.io/SAM_Image_Studio/segmentation/sam3-onnx.html).

If you prefer persistent local CLI login, `hf auth login` remains supported.
Token input is invisible: paste once with Ctrl+Shift+V or right-click, then
Enter. Answer **n** to adding a Git credential; `hf auth whoami` checks the
account. Login validity and model-access approval are separate checks.
Never put a token in a command argument, project, screenshot, chat or repository.

## 5. Validate environment, then model execution

```sh
python -m pip check
python -m samstudio.selftest --device cuda
```

The self-test checks imports, real CUDA tensor/torchvision operations, exact
mask persistence and Qt window construction. Its headless/offscreen check
does **not** establish interactive display availability or SAM3.1 inference.
Load the authentic weights, open an image, enter a prompt and inspect a real
preview to validate that model. A 6 GB GPU can pass CUDA checks yet run out of
memory loading or executing a large model. Close other GPU applications and
use a smaller model when necessary; ONNX does not guarantee smaller memory use.

## 6. Update without uninstalling

Close the GUI. Download/pull the complete new source into your chosen folder,
enter that folder, then reuse the environment:

```sh
conda activate sam-image-studio-sam3
python GPU/install.py --current --sam3
python -m samstudio
```

For `sam-image-studio-gpu`, activate that name and omit `--sam3`. Installing
only a requirements file does not update application code, hardware-selected
Torch or verified vendor packages. The project installer updates and checks
these together. Existing model caches, native projects and local login remain.
Create a new environment only for an incompatible stack migration or unresolved
conflicts, keeping the old working one until the replacement is validated.

## 7. Problems that still require user action

| Symptom | Action |
| --- | --- |
| PowerShell positional-parameter error | Quote the complete folder path with `Set-Location -LiteralPath`. |
| Native SAM3 selected on Windows | Run the native SAM3.1 recipe inside WSL2/Linux; Windows supports the other GPU paths. |
| No GPU detected | Check the Windows/Linux NVIDIA driver and `nvidia-smi`; the app does not install drivers. |
| HF `Invalid user token` / whoami 401 | Recopy a complete valid read token. GUI paste is masked; CLI input is completely invisible. |
| Login works, model download is denied | Obtain approval and enable access to that gated repository on the fine-grained token. |
| Missing Qt library or `pkg_resources` from an older installation | Update to this source and rerun the installer in the same environment; the repair is automatic. |
| Qt plugin loads but cannot connect to display | Check WSLg/display availability; offscreen is only for diagnostics. |
| sudo unavailable / system package install denied | Ask the machine administrator to run the installer's system-library step. |
| Backend import error after installation | Save the exact error and installer output; `pip check` alone cannot validate lazy backend imports. |
| Kernel/microcode check unavailable at end of apt under WSL | These notices do not mean the requested Qt packages failed; check apt's final exit status. |
| `propagateSizeHints()` during offscreen testing | Harmless if the installation self-test completes with `passed`. |

Avoid reinstalling the whole Conda environment for each missing library.
The [troubleshooting guide](https://iceaiai.github.io/SAM_Image_Studio/troubleshooting.html)
explains diagnostic commands for unresolved failures.

## Uninstall and validation boundaries

Use `conda deactivate`, then `conda env remove -n YOUR_ENVIRONMENT_NAME` to
remove only the selected environment. Preserve source images, native projects,
exports and model caches separately.

Current cloud checks include genuine **CPU** SAM3 ONNX inference and Qt workflow
checks. The cloud machine has no NVIDIA device: these instructions do not claim
new CUDA benchmarks, native Windows execution, or native SAM3.1 weight inference.
