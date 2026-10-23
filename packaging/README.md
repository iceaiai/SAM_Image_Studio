# CPU install, launch and packaging

First [download the current CPU source ZIP](https://github.com/iceaiai/SAM_Image_Studio/archive/refs/tags/v1.4.3.zip),
extract the complete archive and open `SAM_Image_Studio-1.4.3/`, containing
`pyproject.toml`.
Alternatively, clone the full repository and enter its root using the
[shared download/clone steps](../README.md#first-download-or-clone-the-complete-project-cpu-and-gpu).
For older CPU packages, see the [version download list](https://iceaiai.github.io/SAM_Image_Studio/downloads.html).

After obtaining the source, run `Install_CPU.bat` then `Start_GUI.bat` from this
`packaging/` folder on Windows. On Linux run
`bash packaging/install_cpu.sh` and `bash packaging/start_gui.sh` from the
repository root. The helpers find the root themselves, including paths with spaces.

`requirements/` stores shared CPU, ONNX and development dependencies. Use the
project installer for installation or updates; requirements alone do not install
all verified vendor packages or update source. `Uninstall.bat` / `uninstall.sh`
remove only app-owned environments and preserve user projects.

`windows.spec` and `Build_Windows_Portable.bat` are the native Windows build recipe;
a native Windows acceptance check is required before distributing its output.
The portable build uses `launch.py` here and the application package at the root.

All GPU setup is collected separately in [GPU/](../GPU/README.md).
