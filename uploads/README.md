# Original supplied artifacts

These five files are preserved byte-for-byte as supplied:

- [CPU source release 1.4.2](SAM_Image_Studio_v1.4.2_CPU.zip)
- [User manual PDF](SAM_Image_Studio_User_Manual.pdf)
- [Developer manual PDF](SAM_Image_Studio_For_Developer.pdf)
- [Denoising parameter guide PDF](SAM_Image_Studio_Denoising_Parameters.pdf)
- [Compressed sensing notebook](3PM_Compressed_Sensing.ipynb)

Verify their digests from this directory with `sha256sum -c SHA256SUMS`.
The ZIP is also extracted at the repository root for development. Its packaged
PDFs are different versions from the three separately supplied PDFs retained
here; none have been replaced or regenerated.

The notebook targets Google Colab and requires external workshop images.
See the [notebook guide](../docs/source/notebook.md). Application installation
and Sphinx build instructions are in the [repository README](../README.md).

## Earlier CPU archives

The six supplied CPU ZIPs from 1.0 through 1.4.1 are in [legacy-cpu/](legacy-cpu/).
The file named `SAM_Image_Studio_v1.4.0_CPU.zip` contains an app and release
notes marked 1.5.0. The download listing retains the supplied filename.

Run `sha256sum -c SHA256SUMS` from `legacy-cpu/` to check those six ZIPs.
Open the downloads page for a description of each archive. [Show all versions](https://iceaiai.github.io/SAM_Image_Studio/downloads.html#earlier-cpu-versions)
