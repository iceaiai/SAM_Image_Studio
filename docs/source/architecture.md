# Application architecture

The application is a PySide6 desktop GUI. `samstudio.app.main()` parses image
arguments and `--no-restore`, initializes logging and Qt, and constructs
`MainWindow`. `python -m samstudio` and `sam-image-studio` use that entry point.

| Modules | Responsibilities |
| --- | --- |
| `domain`, `imageio`, `calibration_table` | Images and physical calibration, annotations/groups, histories, atomic native project storage, Excel lookup |
| `main_window`, `canvas`, `dialogs`, `*_ui` | Desktop controls, canvas interaction, dialogs and background jobs |
| `inference`, `exemplars`, `text_prompts`, `sam31_backend` | Model catalog/checkpoints, native inference, exemplar matching, text-to-box prompts and optional SAM3.1 adapter |
| `processing`, `image_processing`, `denoise_config` | Processing targets, parameter validation, intensity normalization, preview/apply dispatch and shared parameter descriptions |
| `compressed_sensing`, `sparse_denoising`, `neural_denoising` | Iterative DCT/TV, SPORCO/BM3D, CAREamics N2V/N2V2 |
| `transforms`, `savepoints` | Coordinated pixel/geometry/calibration transformations and annotation snapshots |
| `statistics`, `exports`, `palette` | Applicable measurements, dataset/image output, and display colors |
| `plugin_api`, `plugin_ui`, `hardware` | Plugin registration/validation, desktop integration, and NVIDIA/Conda planning |

## State and transactions

An `ImageFrame` carries acquired pixels and calibration; a `Document` holds
objects, groups, geometry, and editing/processing records. `History` supports
Undo/Redo; `ProjectStore` persists native state. Native schema 5 reads earlier
schemas 1–4. Source images, native projects, dataset exports, app caches, and
neural training outputs have different lifetimes.

Segmentation and processing generate previews before commit. GUI actions use
the normal transaction/autosave path. Background processors work on snapshots
and must not access Qt widgets. Keep heavy computation in workers and
cancellation checks between iterations or batches.

`process_pixels()` normalizes intensities, processes independent spatial
channels, preserves alpha and dtype, and composites only target pixels.
`denoise_config.METHODS` defines defaults, bounds/choices, help, and suggested
starting points used by controls and documentation. Validate cross-field
constraints through `image_processing.parameters()`.

## Plugin contract

Plugin API v1 loads a local folder with `plugin.json` and a module exporting
`register(api)`. Image processors receive `ProcessorContext`, including an image
copy, target mask, parameter dictionary, calibration/annotation snapshots,
progress callback, and cancellation event. Output must preserve shape and dtype
and contain finite values. `run_processor()` restores outside-target pixels and
alpha. GUI actions receive `PluginAPI` and can use `api.commit()`.

The [developer manual](developer-manual.md) contains executable plugin examples
and the tiled TorchScript U-Net contract. Direct `api.window` calls are internal
interfaces whose signatures can change; the [generated API](api.md) reflects
this source tree. No trained U-Net weights are bundled.

## Source-derived API

Sphinx AutoAPI parses the Python source without importing the app. Documentation
can therefore build with only its documentation dependencies, without Qt,
PyTorch, Conda, model downloads, or a display. The generated reference describes
available callables and data; it does not certify model quality or turn internal
APIs into stable public contracts.
