# CPU version downloads and manuals

Choose a ZIP, extract the whole archive, then follow the installer
for that version. No Git account or clone command is required for ZIP downloads.

## CPU application versions

| Version | Downloads | Main changes |
| --- | --- | --- |
| [**1.4.5.1**](https://github.com/iceaiai/SAM_Image_Studio/tree/v1.4.5.1) **— recommended** | [Standard ZIP](https://github.com/iceaiai/SAM_Image_Studio/archive/refs/tags/v1.4.5.1.zip) · [Offline CPU ZIP](https://github.com/iceaiai/SAM_Image_Studio/archive/refs/tags/v1.4.5.1-offline.zip) | Adds keyboard deletion of mask pieces, segmentation review, measurement-colored histograms, and hand-drawn filament links. Fixes Mask pusher strokes when changing sides. |
| [1.4.5](https://github.com/iceaiai/SAM_Image_Studio/tree/v1.4.5) | [Standard ZIP](https://github.com/iceaiai/SAM_Image_Studio/archive/refs/tags/v1.4.5.zip) · [Offline CPU ZIP](https://github.com/iceaiai/SAM_Image_Studio/archive/refs/tags/v1.4.5-offline.zip) | Adds two-column tools, mask-fragment cleanup, a circular mask pusher, batch vertex deletion, and adjustable polygon closure. |
| [1.4.4.2](https://github.com/iceaiai/SAM_Image_Studio/tree/v1.4.4.2) | [Standard ZIP](https://github.com/iceaiai/SAM_Image_Studio/archive/refs/tags/v1.4.4.2.zip) · [Offline CPU ZIP](https://github.com/iceaiai/SAM_Image_Studio/archive/refs/tags/v1.4.4.2-offline.zip) | Adds calibrated line and curve rulers and fixes crashes in segmentation options, mask-color, and plot-group dialogs. |
| [1.4.4.1](https://github.com/iceaiai/SAM_Image_Studio/tree/v1.4.4.1) | [Standard ZIP](https://github.com/iceaiai/SAM_Image_Studio/archive/refs/tags/v1.4.4.1.zip) · [Offline CPU ZIP](https://github.com/iceaiai/SAM_Image_Studio/archive/refs/tags/v1.4.4.1-offline.zip) | Adds segmentation size filters, editable scale bars, filament measurements, and shared colors for plot groups. |
| [1.4.4](https://github.com/iceaiai/SAM_Image_Studio/tree/v1.4.4) | [Standard ZIP](https://github.com/iceaiai/SAM_Image_Studio/archive/refs/tags/v1.4.4.zip) · [Offline CPU ZIP](https://github.com/iceaiai/SAM_Image_Studio/archive/refs/tags/v1.4.4-offline.zip) | Adds Otsu + watershed, signal-scaled noise, automatic Python 3.12 setup, and the offline CPU edition. |
| [1.4.3](https://github.com/iceaiai/SAM_Image_Studio/tree/v1.4.3) | [Standard ZIP](https://github.com/iceaiai/SAM_Image_Studio/archive/refs/tags/v1.4.3.zip) | Adds public SAM3 ONNX text segmentation, updates CPU/GPU installers, and publishes illustrated guides. |
| 1.4.2 — First stable version | [CPU ZIP](https://raw.githubusercontent.com/iceaiai/SAM_Image_Studio/main/uploads/SAM_Image_Studio_v1.4.2_CPU.zip) · [SHA-256](https://raw.githubusercontent.com/iceaiai/SAM_Image_Studio/main/uploads/SHA256SUMS) | Includes calibrated segmentation, Excel pixel-size lookup, image restoration, and bundled manuals. |

:::{dropdown} Show all versions
:name: earlier-cpu-versions

| Earlier version | Downloads | Main changes |
| --- | --- | --- |
| 1.4.1 | [CPU ZIP](https://raw.githubusercontent.com/iceaiai/SAM_Image_Studio/main/uploads/legacy-cpu/SAM_Image_Studio_v1.4.1_CPU.zip) | Adds whole-image positive and negative examples, dedicated text and grid actions, restoration controls, retained crops, and local plugins. |
| 1.4.0 — ZIP filename | [CPU ZIP](https://raw.githubusercontent.com/iceaiai/SAM_Image_Studio/main/uploads/legacy-cpu/SAM_Image_Studio_v1.4.0_CPU.zip) | The app and release notes inside report **1.5.0**. This build adds autosaving COCO review, whole-image exemplar search, processing, retained crops, and plugins. |
| 1.3 | [CPU ZIP](https://raw.githubusercontent.com/iceaiai/SAM_Image_Studio/main/uploads/legacy-cpu/SAM_Image_Studio_v1.3_CPU.zip) | Adds exact region inversion, original and processed TIFF export, Gaussian and median smoothing, and a 20-color preset palette. |
| 1.2 | [CPU ZIP](https://raw.githubusercontent.com/iceaiai/SAM_Image_Studio/main/uploads/legacy-cpu/SAM_Image_Studio_v1.2_CPU.zip) | Adds panning, improved vertex editing, transparent overlays, overlap-weighted masks, and reversible cleaning history. |
| 1.1 | [CPU ZIP](https://raw.githubusercontent.com/iceaiai/SAM_Image_Studio/main/uploads/legacy-cpu/SAM_Image_Studio_v1.1_CPU.zip) | Fixes prompted inference and histogram crashes, adds editable smooth contours, and improves vertex deletion. |
| 1.0 | [CPU ZIP](https://raw.githubusercontent.com/iceaiai/SAM_Image_Studio/main/uploads/legacy-cpu/SAM_Image_Studio_v1.0_CPU.zip) | Provides the initial microscopy annotation, SAM segmentation, calibrated measurements, reversible cleaning, and native autosaves. |

These are the supplied CPU ZIPs. Follow the README and installer included in the chosen ZIP. [SHA-256 checksums](https://raw.githubusercontent.com/iceaiai/SAM_Image_Studio/main/uploads/legacy-cpu/SHA256SUMS)

:::

Every source package needs installation after extraction. The current CPU helpers
automatically use or prepare **64-bit Python 3.12** on Windows/Linux x86-64.
Versions 1.4.2 and 1.4.3 require Python 3.12 beforehand. Model weights in the
standard edition download on demand. Prepare the offline cache online before
transferring the extracted offline edition. See the [offline installation guide](installation-offline.md).

The standard archive contains the full shared application, including `GPU/`, and
can be used with either the CPU installer or its optional GPU installer. Follow the
[common download/clone step](installation.md#first-for-every-route-download-extract-or-clone)
before choosing any CPU/GPU installation route. If you use Git instead, run the
clone commands once; do not both clone and download unless you want two copies.

## Which CPU package should I choose?

Use **1.4.5.1** for connected installations or prepare **1.4.5.1 offline CPU**
for a disconnected installation. The standard edition also includes public
SAM3 ONNX text segmentation.
CPU also supports SAM1 and SAM2/2.1. Native SAM3/SAM3.1 require the separate
[GPU installation route](installation-gpu.md); they are not CPU model options.

For **1.4.2**, open the inner `SAM_Image_Studio` folder. On Windows, run
`Install_CPU.bat`, then `Start_GUI.bat`. On Linux, run `bash install_cpu.sh`,
then `bash start_gui.sh`. See the manuals bundled with that ZIP.

## Original PDF manuals and notebook

These files are retained byte-for-byte as supplied. The PDF manuals describe
1.4.2, the first stable version. The current website covers newer install paths
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
