# Native Windows CPU build recipe. Run Build_Windows_Portable.bat on Windows.
# A successful build still requires the acceptance checks in INSTALL_UNINSTALL.md.
# Spec format and collection helpers: https://pyinstaller.org/en/stable/spec-files.html
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata, collect_dynamic_libs

root = Path(SPECPATH).resolve().parent
datas = [(str(root / "third_party"), "third_party"), (str(root / "LICENSE"), ".")]
hidden = ["matplotlib.backends.backend_qtagg", "PySide6.QtSvg", "PySide6.QtPdf", "PySide6.QtPdfWidgets"]
datas += collect_data_files("samstudio", includes=["resources/*.pdf"])

# SAM2 uses Hydra YAML configuration and dynamically named model classes.
for package in ("sam2", "segment_anything"):
    datas += collect_data_files(package, include_py_files=True)
    hidden += collect_submodules(package)

# Readers and Transformers select these modules lazily at runtime.
for package in (
    "rsciio.digitalmicrograph", "rsciio.emd",
    "transformers.models.grounding_dino", "transformers.models.bert",
):
    hidden += collect_submodules(package)
for package in ("rsciio", "transformers"):
    datas += collect_data_files(package, include_py_files=True)
for package in ("careamics", "sporco", "bm3d", "bm4d", "openpyxl"):
    datas += collect_data_files(package, include_py_files=True)
    hidden += collect_submodules(package)
# bm4d loads its platform-specific native .so-named libraries through ctypes,
# including libbm4d_win.so on Windows. They must remain package data.
datas += collect_data_files("bm4d", includes=["*.mat"])
native_bm4d = [item for item in collect_dynamic_libs("bm4d", search_patterns=["*.so"])
              if Path(item[0]).name == "libbm4d_win.so"]
for distribution in (
    "transformers", "huggingface-hub", "tokenizers", "safetensors",
    "rosettasciio", "torch", "torchvision", "sam_2", "segment-anything",
    "careamics", "lightning", "pytorch-lightning", "torchmetrics",
    "bioimageio.core", "bioimageio.spec", "sporco", "bm3d", "bm4d", "openpyxl",
):
    datas += copy_metadata(distribution, recursive=True)

a = Analysis(
    [str(root / "launch.py")],
    pathex=[str(root)],
    binaries=native_bm4d,
    datas=datas,
    hiddenimports=sorted(set(hidden)),
    hookspath=[],
    hooksconfig={"matplotlib": {"backends": ["QtAgg"]}},
    runtime_hooks=[],
    excludes=["PyQt5", "PyQt6", "PySide2", "tensorflow", "sam3"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name="SAM_Image_Studio", debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=False,
)
coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False, upx=False, name="SAM_Image_Studio",
)
