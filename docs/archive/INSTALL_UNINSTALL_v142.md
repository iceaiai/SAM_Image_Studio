# SAM Image Studio 1.4.2 - installation and removal

## Default CPU installation

1. Extract the complete release into a writable folder.
2. Use 64-bit Python 3.12. Other Python versions may remain installed.
3. On Windows run Install_CPU.bat, then Start_GUI.bat.
4. On Linux run `bash install_cpu.sh`, then `bash start_gui.sh`.
5. Open an image and load SAM2.1 Tiny or SAM1 ViT-B using Model manager.

The installer creates an application-owned local `.venv`, installs pinned
application dependencies and CPU PyTorch, checks dependencies and runs the
installation self-test. It does not change system Python packages. Models are
downloaded separately on demand and are not included in the archive.

## If Python 3.12 is missing on Windows

Press the Windows key, type PowerShell and open Windows PowerShell. Run:

```powershell
winget install --exact --id Python.Python.3.12 --architecture x64 --scope user --source winget
```

Close/reopen PowerShell and check `py -3.12 --version`. Run Install_CPU.bat again.
Install_Python_3_12.bat provides the same helper. An administrator shell is not
required by the per-user Python command. Official Python downloads are at
https://www.python.org/downloads/.

## Existing Python 3.12 virtual environment or CPU Conda environment

Activate the dedicated environment, change to the release folder and run:

```text
python scripts/install_environment.py --backend cpu --current
python -m samstudio
```

The installer rejects the system Python when --current is requested without an
activated virtual/Conda environment. For a new CPU Conda environment:

```text
conda create -n sam-image-studio-cpu python=3.12 pip
conda activate sam-image-studio-cpu
python scripts/install_environment.py --backend cpu --current
python -m samstudio
```

## GPU installation: Conda only

Read GPU_CONDA_GUIDE.md. From a Conda prompt, use Install_GPU_Conda.bat on
Windows or the commands below. The setup detects NVIDIA hardware and selects a
supported CUDA wheel index; it never installs a system driver.

```text
python scripts/install_conda_gpu.py --inspect
python scripts/install_conda_gpu.py --name sam-image-studio-gpu --dry-run
python scripts/install_conda_gpu.py --name sam-image-studio-gpu
conda activate sam-image-studio-gpu
python -m samstudio
```

Use `conda run -n base python` in place of `python` for the first three commands
if needed. A dedicated non-base environment is required. Start_GUI_GPU.bat uses
the default GPU environment name. Native SAM3 is optional for Linux/WSL2 Conda,
requires authorized model access and uses --sam3. Native SAM3 CPU is not enabled.
No CUDA hardware or actual SAM3 weights were available on the test machine.

## Workspace, autosaves and help

The Image files list retains source filenames and separate stack frames. The
v1.4 Objects/Groups/Image files layout, native annotation format and COCO export
workflow are retained. Committed operations save native .sam.json projects;
Choose project folder sets another writable destination. Removing image entries
keeps the source images and saved projects. Startup asks before reopening images.

Help > User manual (PDF) opens the English function guide and examples.
Plugin > For Developer (PDF) opens the separate API and executable U-Net guide.
Both PDFs are included in the wheel and the source release. See
RELEASE_NOTES.md and TEST_REPORT.md for the revised scope and actual checks.

## Optional Windows portable build

On native 64-bit Windows, first complete the CPU installation and self-test,
then run Build_Windows_Portable.bat. The supplied PyInstaller recipe produces
`dist/SAM_Image_Studio/SAM_Image_Studio.exe` if the local build succeeds. Copy
its entire folder, including `_internal`, to a target machine. Check actual
models, image readers, save/reopen, editing, processing, exports, PDF help and
statistics on a clean target account. No prebuilt Windows EXE is supplied or
claimed as verified by the Linux validation.

## Removal

Close the GUI. Use Uninstall.bat or `bash uninstall.sh` to remove only this
release's app-owned marked environments/build output. The uninstaller preserves
images, SAM_Annotations projects, exports, caches and unmarked environments.
Remove a Conda environment explicitly:

```text
conda deactivate
conda env remove -n sam-image-studio-gpu
```

Use its actual name. Do not delete source images or annotation files when
removing an image from the workspace. Choose project folder changes the save
destination if the source location is not writable. Application data/model
caches normally live at `%LOCALAPPDATA%/SAMImageStudio` on Windows and
`~/.local/share/sam-image-studio` on Linux. SAM_STUDIO_DATA_DIR overrides this.

## Troubleshooting

- Use a writable extracted folder and 64-bit Python 3.12.
- A .pt/.pth checkpoint must match the selected model family and variant.
- Text controls require SAM2/2.1 or a configured SAM3 backend; use Run text
  segmentation after entering a phrase or alias.
- Inside ROI only is disabled for Point. Whole-image exemplars and Single object
  are separate modes. Automatic grid starts after model/Segment prerequisites.
- Save failures stay visible; choose a writable project folder before closing.
- Plugin dependencies belong in the active environment. Remove/disable a failing
  plugin; no plugin packages are installed automatically.
- For GPU problems, record the --inspect report and run the native self-test in
  the actual Conda environment. Synthetic detection tests do not verify CUDA.


Restoration dependencies now include openpyxl 3.1.5, SPORCO 0.2.2.post1, bm3d 4.0.3 and CAREamics 0.3.5. Follow the lock file through the installation script; CAREamics requires a compatible tifffile/tqdm pair. BM3D/bm4d have upstream academic/non-commercial terms; retain and review their installed licenses. Neural training creates persistent application-data model folders; removing an image or undoing processing does not remove those models.
