# Folders, projects, and model files

| Location or file | What it contains |
| --- | --- |
| Source images | Acquired data; retained separately from cleaning/processing records. |
| `.sam.json` native projects | Full editable annotations, groups, calibration, prompt state, exact masks, and image edit records; retain backups. |
| `SAM_Annotations` / chosen project folder | Native saves; choose a writable folder through File. |
| COCO / YOLO exports | Dataset output for interchange/training; not a complete native project replacement. |
| Model cache | Separately downloaded segmentation/inpainting weights. |
| CAREamics output folders | Trained N2V/N2V2 models/checkpoints, including per-channel models for RGB. |
| Local mask savepoint folder | Explicit persistent geometry snapshots; temporary savepoints stay in memory. |
| Application `settings.ini` and `samstudio.log` | Workspace/settings persistence and rotating diagnostic logs. |
| Installed `plugins/` | Trusted local plugin source; large checkpoints should be stored elsewhere. |

Application data defaults to `%LOCALAPPDATA%/SAMImageStudio` on Windows and
`~/.local/share/sam-image-studio` on Linux. `SAM_STUDIO_DATA_DIR` overrides it.
Changing/removing a Conda environment does not imply that image/project/cache
folders have been removed. Preserve those separately when migrating machines.

## Repository directory map

| Directory | Purpose |
| --- | --- |
| `samstudio/` | Application source; `resources/` contains packaged help PDFs. |
| `scripts/` | CPU/GPU environment installers, diagnostics and validation helpers. |
| `docs/source/` | Sphinx website pages and configuration. |
| `docs/` | Original editable manuals, screenshots, documentation requirements. |
| `docs/_build/html/` | Generated website; not application source. |
| `examples/` | Demo images and local U-Net plugin example. |
| `tests/` | Existing regression tests. |
| `validation/` | Original release reports and test records, not automatically rerun evidence. |
| `vendor/` | Bundled dependency wheels, including the verified SAM2 wheel. |
| `dist/` | Original installable application wheel. |
| `uploads/` | The five original supplied artifacts, retained unchanged. |
| `.venv/` | Default app-owned CPU installation, if used. |
| `.docs-venv/` | Optional isolated documentation build environment. |

## SAM checkpoint names

Select weights matching the model family and variant. In particular,
`sam3.pt` belongs to SAM3 and `sam3.1_multiplex.pt` belongs to SAM3.1.
Renaming a checkpoint does not change its architecture. Keep approved weights
and their provenance outside source-control histories.
