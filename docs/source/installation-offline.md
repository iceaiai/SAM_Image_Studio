# Offline CPU installation

First [download the offline CPU ZIP](downloads.md), extract the whole archive,
and open its project root. The initial source ZIP is approximately the same
size as the normal source ZIP. Its runtime, packages and three checkpoints must
be **pre-downloaded while online** before it can install on a disconnected PC.

1. On a matching online Windows/Linux x86-64 computer, run
   `offline/Prepare_Offline.bat` or `bash offline/prepare_offline.sh`.
2. Wait for successful completion and `offline-cache/READY`.
3. Copy the entire source folder **including `offline-cache/`** to the offline PC.
4. Run the normal `packaging/Install_CPU.bat` or `bash packaging/install_cpu.sh`.
5. Launch with `packaging/Start_GUI.bat` or `bash packaging/start_gui.sh`.

The installer selects/prepares Python 3.12 and uses only hashed local packages.
Only **SAM1 ViT-B**, **SAM2.1 Small**, **SAM2.1 Base+** and CPU are available.
There is no SAM3, ONNX text, Grounding DINO text detection or online model download.
Otsu + watershed is available without a checkpoint. No app packages go into base.

Read the [complete offline preparation, platform and update guide on GitHub](https://github.com/iceaiai/SAM_Image_Studio/blob/main/offline/README.md).
For Linux, match the distribution/version when transferring cached Qt system
packages. Preparation requires access to the official model/runtime/package
hosts and preserves failed downloads without marking an incomplete cache ready.
The validation report distinguishes the tested 126-wheel offline installation
from checkpoint/system-package preparation blocked by the cloud's host allowlist.
