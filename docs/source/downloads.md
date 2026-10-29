# CPU version downloads and manuals

Click **Download ZIP**, extract the whole archive, then follow the installer
for that version. No Git account or clone command is required for ZIP downloads.

## CPU application versions

| Version | Download | Platforms and contents | After extracting |
| --- | --- | --- | --- |
| **1.4.4 — recommended** | **[Download ZIP](https://github.com/iceaiai/SAM_Image_Studio/archive/refs/tags/v1.4.4.zip)** · [Source tag](https://github.com/iceaiai/SAM_Image_Studio/tree/v1.4.4) | Windows/Linux CPU source, automatic Python 3.12 selection/bootstrap; optional GPU setup included | Extract `SAM_Image_Studio-1.4.4/`; Windows: `packaging/Install_CPU.bat`, then `packaging/Start_GUI.bat`; Linux: `bash packaging/install_cpu.sh`, then `bash packaging/start_gui.sh`. |
| **1.4.4 — offline CPU** | **[Download ZIP](https://github.com/iceaiai/SAM_Image_Studio/archive/refs/tags/v1.4.4-offline.zip)** · [Offline guide](installation-offline.md) | CPU only: SAM1 ViT-B, SAM2.1 Small and Base+; source-sized initial ZIP | Extract `SAM_Image_Studio-1.4.4-offline/`; first run `offline/Prepare_Offline.bat` or `bash offline/prepare_offline.sh` while online. Copy the whole prepared folder, then use the normal CPU installer offline. |
| **1.4.3 — previous** | **[Download ZIP](https://github.com/iceaiai/SAM_Image_Studio/archive/refs/tags/v1.4.3.zip)** · [Source tag](https://github.com/iceaiai/SAM_Image_Studio/tree/v1.4.3) | Complete Windows/Linux CPU source bundle, including shared optional GPU setup | Open `SAM_Image_Studio-1.4.3/`, containing `pyproject.toml`; Windows: `packaging/Install_CPU.bat`, then `packaging/Start_GUI.bat`; Linux: `bash packaging/install_cpu.sh`, then `bash packaging/start_gui.sh`. |
| **1.4.2 — original** | **[Download ZIP](https://raw.githubusercontent.com/iceaiai/SAM_Image_Studio/main/uploads/SAM_Image_Studio_v1.4.2_CPU.zip)** · [SHA-256](https://raw.githubusercontent.com/iceaiai/SAM_Image_Studio/main/uploads/SHA256SUMS) | Original, unchanged CPU source archive | Open its inner `SAM_Image_Studio` folder; Windows: `Install_CPU.bat`, then `Start_GUI.bat`; Linux: `bash install_cpu.sh`, then `bash start_gui.sh`. Its earlier installers do not include the v1.4.3 repairs. |

These are the CPU application archives currently available in this repository.
The table does not advertise unprovided older versions or standalone executables.
Every source package needs installation after extraction. The v1.4.4 CPU helpers
automatically use or prepare **64-bit Python 3.12** on Windows/Linux x86-64.
Older versions need Python 3.12 beforehand. Normal-edition model weights download
on demand. The offline edition must pre-download its complete cache first; its
initial ZIP does not contain those large dependencies/checkpoints.

The normal v1.4.4 archive contains the full shared application, including `GPU/`, and
can be used with either the CPU installer or its optional GPU installer. Follow the
[common download/clone step](installation.md#first-for-every-route-download-extract-or-clone)
before choosing any CPU/GPU installation route. If you use Git instead, run the
clone commands once; do not both clone and download unless you want two copies.

## Which CPU package should I choose?

Use **1.4.4 normal** for new connected installations, or **1.4.4 offline CPU**
for a fully prepared disconnected installation. Both add Otsu + watershed,
signal-scaled noise, processing-input controls and automatic Python preparation.
The normal edition also includes public SAM3 ONNX text segmentation.
CPU also supports SAM1 and SAM2/2.1. Native SAM3/SAM3.1 require the separate
[GPU installation route](installation-gpu.md); they are not CPU model options.

The **1.4.2** ZIP remains available for reproducing the original release. Its
folder layout and installation instructions differ. Use its own included
manuals rather than running v1.4.3 helper paths inside that archive.

## Original PDF manuals and notebook

These files are retained byte-for-byte as originally supplied. The PDF manuals
describe the original release; use the current website for newer install paths
and features.

| File | Download |
| --- | --- |
| User manual (PDF) | [Download PDF](https://raw.githubusercontent.com/iceaiai/SAM_Image_Studio/main/uploads/SAM_Image_Studio_User_Manual.pdf) |
| Developer manual (PDF) | [Download PDF](https://raw.githubusercontent.com/iceaiai/SAM_Image_Studio/main/uploads/SAM_Image_Studio_For_Developer.pdf) |
| Denoising parameters (PDF) | [Download PDF](https://raw.githubusercontent.com/iceaiai/SAM_Image_Studio/main/uploads/SAM_Image_Studio_Denoising_Parameters.pdf) |
| Compressed-sensing notebook | [Download notebook](https://raw.githubusercontent.com/iceaiai/SAM_Image_Studio/main/uploads/3PM_Compressed_Sensing.ipynb) |
| Original artifact checksums | [Download SHA256SUMS](https://raw.githubusercontent.com/iceaiai/SAM_Image_Studio/main/uploads/SHA256SUMS) |

Earlier packaged PDFs inside the ZIP and in `samstudio/resources/` are also
preserved. See [provenance](provenance.md) for the source/version distinctions.
