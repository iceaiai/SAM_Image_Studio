# Troubleshooting installation and operation

Use current installers from a complete version 1.4.4 source tree. They now handle
the repeated dependency fixes encountered during v1.4.2 WSL installation. Rerunning
in an existing dedicated environment is a supported repair; deleting that
environment is usually unnecessary.

## 1. Confirm the folder and environment

A PowerShell error saying "A positional parameter cannot be found" usually means
an unquoted path with spaces. First download/extract or clone the complete
project. Then enter its root. The following paths are fictional examples;
replace them with your chosen folder:

```powershell
Set-Location -LiteralPath 'C:\Projects\Example Folder\SAM_Image_Studio'
Test-Path .\GPU\install.py
Test-Path .\pyproject.toml
```

Both should return `True`. Linux/WSL needs its own path, for example
`cd '/mnt/c/Projects/Example Folder/SAM_Image_Studio'`. Use Linux Conda inside WSL for native
SAM3.1. Windows Anaconda alone is not Linux Conda. Activate the dedicated
`sam-image-studio-sam3` or `sam-image-studio-gpu` environment before `--current`.
Application installation into Conda base is rejected.

## 2. Dependency problems handled by installation

| Earlier symptom | Current automatic handling |
| --- | --- |
| Default/background Python is not 3.12 | Current CPU helpers choose 64-bit 3.12 or prepare a verified local runtime. Run the helper from the complete extracted folder. |
| `libxkbcommon.so.0`, `libfontconfig.so.1` or `libxcb-shape.so.0` missing | Ubuntu helper detects Qt system libraries and installs the missing packages. |
| Wayland/xcb Qt plugin fails because of a missing library | Installer supplies XCB dependencies; WSLg launch selects X11 when a display is present. |
| `No module named pkg_resources` from native SAM3.1 | Installer and native requirements select setuptools 80.9.0. |
| CPU and GPU ONNX distributions conflict | Runtime helper removes the opposite known distribution and installs the selected one. |
| Torch CUDA wheel does not match driver capability | GPU planner chooses a supported official Torch index or explains why the driver is too old. |

For an older affected native environment, update to the complete current source,
then run from its root:

```sh
conda activate sam-image-studio-sam3
python GPU/install.py --current --sam3
```

For ordinary GPU setup omit `--sam3`; CPU repair uses its CPU installer. Normal
users do not need per-library apt/pip recipes. A non-root Ubuntu user must allow
`sudo` for missing system libraries; on managed machines that may require an
administrator. An installer failure must be resolved before claiming readiness.

## 3. Display failures remaining after installation

An **offscreen self-test passing** means Qt can construct widgets; it does not
establish that an interactive desktop is reachable. Start normally with
`python -m samstudio`. Explicit `QT_QPA_PLATFORM` choices are respected; do not
leave it set to `offscreen` when expecting a visible window.

If a display failure remains on Linux/WSL, collect:

```bash
echo "DISPLAY=$DISPLAY"
echo "WAYLAND_DISPLAY=$WAYLAND_DISPLAY"
ldd "$(python -c 'import pathlib, PySide6; print(pathlib.Path(PySide6.__file__).parent / "Qt/plugins/platforms/libqxcb.so")')"
QT_DEBUG_PLUGINS=1 QT_QPA_PLATFORM=xcb python -m samstudio > /tmp/samstudio-qt.log 2>&1
tail -n 80 /tmp/samstudio-qt.log
```

`not found` identifies a missing library. `cannot connect to display` points to
display/WSLg availability rather than another pip dependency. Reinstallation
without reading the actual load error can repeat the same failure.

WSL apt's kernel/microcode inspection notices are separate from package install
success. `propagateSizeHints()` during offscreen testing is harmless if the
self-test finishes successfully.

## 4. Hugging Face login and gated model access

Select SAM3/SAM3.1 in Model manager to expose its optional masked token field.
Paste a complete approved read token there; it is used for the download and not
saved. Leave it blank to reuse local HF login. Token approval and model-access
approval are separate; a fine-grained token also needs the relevant repository
read permission. Request access on the model page using the token owner's account.

For CLI login, `hf auth login` deliberately shows **no characters or asterisks**.
Paste once with Ctrl+Shift+V or right-click, press Enter, and answer **n** to
adding Git credentials. Ctrl+U clears input before resubmission. Check the
account with `hf auth whoami`. Windows and WSL use separate caches unless you
explicitly configure sharing.

| Error | Interpretation |
| --- | --- |
| `whoami-v2` 401 / `Invalid user token` | The token itself was rejected; recopy/create a valid one. |
| Login valid, checkpoint download 401/403 | Check gated-model approval, account and repository permission. |
| SAM3.1 selected but filename is `sam3.pt` | Check the actual selected family; authentic SAM3.1 uses `sam3.1_multiplex.pt`. |

Do not put tokens into shell arguments, projects, screenshots or Git. The GUI
field does not bypass a gate. For public text weights without HF login, choose
[SAM3 ONNX](segmentation/sam3-onnx.md), which has different capabilities.

## 5. GPU and model errors

Use `python GPU/install.py --inspect` to check detection. `nvidia-smi` must see
a supported NVIDIA device. The installer does not install drivers; AMD/Intel
GPUs use the CPU route. Native SAM3.1 requires Linux/WSL2 and matching weights.

`python -m samstudio.selftest --device cuda` verifies real CUDA operations and
installation contracts. Then load the model and run a real preview. A CUDA pass
does not prove sufficient VRAM for SAM3.1. A 6 GB laptop GPU can still run out of
memory on large models. Capture the actual error instead of assuming CPU fallback.

## 6. Unexpected masks, cleaning or reconstruction

- Check Mode, Scope, text and pending examples. **Point** hides ROI/single-object
  choices; choose an area tool. See [scope diagrams](segmentation/scopes.md).
- Automatic grid ignores text. Single object should use empty text for its
  native instance path. ONNX text requires cleared native point/example prompts.
- Accepted annotations are protected. Use explicit refinement to change one.
- **Fill holes** edits masks; Cleaning fills **image pixels**. Remove a target
  before filling, and use unaffected manual background patches.
- A 100%-sampled L2 reconstruction returns its input. Choose denoise with relaxed
  fidelity for ordinary noisy complete images. See [parameter examples](features/compressed-sensing.md).

For apparently inverted/poor masks, first turn **View / infer from processed
image** off and inspect the original. The choice now starts off for newly opened
images and is separate per image during the session. Toggling preserves edits;
**Forget processed image…** explicitly clears processing and retained crops, with
confirmation and Undo. It preserves annotations and current orientation.

For SAM3 ONNX, inspect the persistent preview count and its tooltip. A model
returning zero differs from proposals removed by score/ROI/protection. On the
bundled STEM example, `particles` returned zero while `white dots` returned 16.
See the [real-example results](segmentation/sam3-onnx.md#when-computation-finishes-with-no-masks).

## 7. Saving, plugins and external fixtures

Choose a writable project folder and keep native `.sam.json` backups. COCO,
YOLO and flat image exports are not a complete editable-project replacement.
If saving fails, image removal is blocked to protect recovery.

Local plugins need compatible dependencies in the active environment. Run
`python -m pip check` and inspect the processor's shape/dtype/target contract.
CAREamics training creates model files before image Apply; Cancel or Undo does
not delete those files.

The original release omitted `external_assets.json`; the fetch helper now looks
under `docs/validation/`. Obtain the authoritative manifest before full external
validation. Do not invent digests, disable TLS/checksums, or call skipped model
tests a full model validation. See [development](development.md).
