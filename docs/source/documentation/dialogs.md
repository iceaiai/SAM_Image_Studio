# Dialogs and their controls

## Model manager and inference options

Choose the family and variant before selecting a checkpoint. **CPU** supports
SAM1/2/2.1. **NVIDIA CUDA (Conda)** requires the dedicated GPU environment.
**Automatic device** selects the CUDA device with most total reported VRAM in
Conda when available; this is not a guarantee of enough free VRAM.

SAM3/3.1 have distinct checkpoints and optional dependency requirements.
The first public model download and gated-weight authentication are separate
from accepting a segmentation preview.

| Inference option | Use |
| --- | --- |
| Grid points per side | Density of automatic/candidate point sampling; larger grids cost more work. |
| Minimum model score | Filter applicable proposals by backend score; not a probability guarantee. |
| Minimum mask area | Reject tiny masks in pixels. |
| Maximum objects | Limit proposals; native model capacity can impose additional limits. |

These options are path-dependent. In particular, grid density does not change
a native SAM3.1 concept request. The full inference API and whole-image exemplar
route do not apply every score threshold identically; use the intended GUI
scope when reproducing an experiment.

## Processing and preview

Select Method, choose whole-image/selected-target and original/derived input,
then inspect the method parameters. **Restore defaults**, per-parameter **?**,
and the explanation panel expose the same parameter schema. The
**Notebook reconstruction preset** is only available for DCT/iterative TV.
**Preview** computes a candidate; the image-preview dialog's **Apply** commits
it and **Cancel** discards it.

For Noise2Void/N2V2, Train/Predict changes which controls are active. Specify
the device, training/patch settings, checkpoint or output directory as needed.
Saved model files remain even when image Apply is canceled. Every exposed
restoration parameter is documented in the [parameter reference](../denoising.md).

## Retained crops

Select a crop in the list. **Paste back** restores its snapshot; **Paste mask
pixels only** limits compositing to the retained mask rather than the full
rectangle. **Protect / release** controls processing exclusion. **Export TIFF**
saves the real retained pixels; **Remove snapshot** removes the stored crop.

## Rotation and mask scaling

The rotation dialog offers angle presets/custom angle, optional padding shape,
and padding fill methods. Review how dimensions and corners change before
Apply. Rotations update calibration as well as geometry.

The scale dialog selects objects/group, factor/spin control/slider,
temporary/local savepoint storage and a name. **Restore selected** and
**Restore local snapshot…** recover compatible snapshots; **Apply scale**
commits. Temporary snapshots disappear with the session.

## Morphology and object properties

Object properties manage annotation metadata. **Morphology / inner region…**
selects a general/polygon/core–shell/hollow interpretation and, where applicable,
a linked core/cavity or expected side count. Relationships must be valid before
derived metrics are meaningful. The full manual defines per-field applicability.

## Statistics and export dialogs

Statistics selects up to nine displayed metrics, plot appearance/axis settings,
and separately the set of numerical columns to export. Resizing changes the
plot area. Export plot and export statistics are independent actions.

Mask/image/dataset dialogs select output scope, original/processed pixel copies,
format, colors/opacity/alpha where applicable, and explicit handling of lossy
YOLO geometry. Integer label outputs preserve IDs rather than display effects.

## Aliases, plugins, and PDF help

The alias table maps phrases and validates empty/duplicate/cyclic entries.
See [alias examples](../segmentation/application-tools.md#text-prompt-aliases).
Plugin management offers enable checkboxes, **Apply / reload**, **Remove plugin**,
and **Close**. Installed plugin actions vary by plugin and are not core controls.

PDF help provides **Fit width** and a zoom percentage for the complete user,
developer, or denoising guide. **Diagnostics / versions** supplies runtime
information for bug reports; it is not a full scientific validation run.
