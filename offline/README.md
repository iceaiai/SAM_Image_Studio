# Offline CPU edition: prepare online, install offline

First [download the offline CPU ZIP](https://github.com/iceaiai/SAM_Image_Studio/archive/refs/tags/v1.4.4-offline.zip)
and extract the **whole** archive. Enter `SAM_Image_Studio-1.4.4-offline/`, the
folder containing `pyproject.toml`, `packaging/` and `offline/`. Keep everything
together. The normal source ZIP does not activate this restricted edition.

The initial ZIP is approximately the size of the normal source ZIP. It contains
preparation/install tools, not pre-bundled dependencies or model weights.
Preparation downloads several gigabytes into this folder. Transfer the entire
prepared folder to the disconnected computer; copying just the original ZIP
will not work. No Hugging Face token is needed for these public checkpoints.

## Included models and features

Only **CPU**, **SAM1 ViT-B**, **SAM2.1 Small**, and **SAM2.1 Base+** are offered.
SAM2.1 is the current SAM2 family implementation. Point/box segmentation,
whole-image exemplars, automatic grids, ROI limits and Otsu + watershed work
without model downloads after preparation. SAM3/3.1, SAM3 ONNX, text detection
and new LaMa/model downloads are disabled. SAM1/2 do not natively understand text.
The offline restriction is enforced by the model catalog and network guards.

## 1. Prepare on a connected matching computer

Use the **same operating system and CPU architecture** as the target: Windows
x86-64 or Linux x86-64. For Linux system packages, use the same distribution and
version too. Do not prepare on Windows for a Linux/WSL target or vice versa.
Preparation installs build tools only in a disposable project-owned environment;
it does not put packages into Conda base or your system Python.

**Windows:** open the extracted project folder, then double-click
`offline/Prepare_Offline.bat`. It selects/prepares Python 3.12 automatically.

**Linux:** open a terminal in the extracted project root, then run:

```bash
bash offline/prepare_offline.sh
```

The helper downloads a verified Python 3.12 runtime, the complete CPU wheel set,
the bundled SAM2 implementation and app wheel, all three checkpoints, and, on
Debian/Ubuntu, Qt system packages and their dependency closure. The machine needs
network access to PyPI, the PyTorch CPU index, the official Python runtime hosts,
Meta's public checkpoint host and the Linux distribution's configured apt mirrors.
It retains upstream runtime/package licenses.

Wait for **Offline preparation complete** and `offline-cache/READY`. The manifest
records hashes, platform and Linux distribution. READY is written only after all
stages finish; failed preparation preserves downloads but leaves no READY marker.
Rerun preparation after fixing a network failure. Never manually create READY or
skip hash checks. SAM1 and runtime have upstream-pinned digests; the SAM2 checkpoints'
first successful official HTTPS downloads are recorded in the local manifest.

Advanced Linux desktops that already have every Qt system library may use
`python3 scripts/prepare_offline.py --skip-system-packages`. This cannot prepare
missing OS libraries for a clean target; the normal route caches them automatically.
Other distributions require their Qt libraries to be provisioned separately.

## 2. Transfer, then install without a connection

Copy the **entire project folder including `offline-cache/`**. Existing virtual
environments are not needed and are not portable between computers. On the target:

- **Windows:** double-click `packaging/Install_CPU.bat`, then `packaging/Start_GUI.bat`.
- **Linux:** run `bash packaging/install_cpu.sh`, then `bash packaging/start_gui.sh`.

`offline/Install_Offline.bat` is an equivalent Windows shortcut. The normal CPU
installer detects this edition and automatically uses the offline route.
It verifies the cache, selects or extracts Python 3.12, creates `.venv-offline/`,
installs only hashed local wheels with `--no-index`, runs `pip check` and the CPU
self-test. Missing Linux Qt libraries are installed only from the cached `.deb`
files, on the matching distro; an administrator password may be needed. No online
fallback occurs if a required file is absent or corrupt.

## 3. Load a model and segment

Open an image, create/select a Group, then use **Load model…** and choose one of
the three prepared variants. Leave the checkpoint field blank to use its verified
local cache. Draw a point/box or select an automatic grid, preview, then accept.
For intensity-separated particles, **Models → Otsu + watershed…** needs no SAM
weights. Example images are under `examples/user_samples/`.

## Updates and checks

For a new version, download/extract its complete offline source, rerun preparation
while online, then transfer the prepared folder and use its installer. Keep user
images, projects and exports separately. There is no need to uninstall system
Python or change Conda base. Keep a previous working prepared folder until the
new version passes its self-test. Caches are tied to the app version/platform;
do not mix arbitrary wheels or replace a model file under an existing manifest.

From the target project root, `python3 scripts/install_offline.py --verify-only`
(or the selected Windows Python) checks the cache before installation.

## Validation limits for 1.4.4

A fresh Linux Python 3.12 environment installed all 126 resolved CPU wheels with
network access deliberately unavailable, passed `pip check` and the full CPU
installation self-test. Linux managed-Python extraction and Windows wheel
metadata resolution were checked. The cloud test environment blocked Meta's
checkpoint host and its Debian snapshot mirror, so full three-checkpoint/system-
package preparation and native Windows installation have **not** been verified
end to end. Those failures leave the preparation incomplete rather than creating
a misleading ready-to-install cache. See the repository validation report.
