# CPU install, launch and packaging

Run `Install_CPU.bat` then `Start_GUI.bat` on Windows. On Linux run
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
