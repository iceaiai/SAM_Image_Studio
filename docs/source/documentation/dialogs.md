# Dialogs and their controls

## Model manager and inference options

Choose the family and variant before selecting a checkpoint. **CPU** supports
SAM1/2/2.1 and SAM3 ONNX text. **NVIDIA CUDA (Conda)** requires the dedicated GPU environment.
**Automatic device** selects the CUDA device with most total reported VRAM in
Conda when available; this is not a guarantee of enough free VRAM.

SAM3 ONNX uses a folder containing verified graph/sidecar files, rather than a
`.pt` checkpoint. Browse changes to folder selection for that family.

SAM3/3.1 have distinct checkpoints and optional dependency requirements. The
masked optional **Hugging Face token** field appears only for these native
families. Paste an approved read token for the download, or leave it blank to
reuse local login. It is cleared after submission/cancel and is not stored in
settings or projects.
The first public model download and gated-weight authentication are separate
from accepting a segmentation preview.

| Inference option | Use |
| --- | --- |
| Grid points per side | Density of automatic/candidate point sampling; larger grids cost more work. |
| Minimum model score | Filter applicable proposals by backend score; not a probability guarantee. |
| Candidate noise floor (px²) | Reject small candidates when a target range is unset. |
| Target size range | Set either inclusive bound or both, using projected area or equivalent diameter. Physical units default to image calibration. |
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
restoration parameter is documented in the [User Manual](../user-manual.md#denoising-parameters).
The **Denoising parameters** button opens that chapter.

## Otsu + watershed and LaMa

Both parameter dialogs offer **Restore defaults**, per-control **?** help and
**Preview**. Watershed returns provisional annotation masks to the canvas for
**Accept masks**; LaMa opens a pixel comparison with **Apply**. Their complete
controls are in the [watershed guide](../segmentation/watershed.md) and
[cleaning guide](../features/cleaning.md).

## Retained crops

Select a crop in the list. **Paste back** restores its snapshot; **Paste mask
pixels only** limits compositing to the retained mask rather than the full
rectangle. **Protect / release** controls processing exclusion. **Export TIFF**
saves the real retained pixels; **Remove snapshot** removes the stored crop.

## Rotation and mask scaling

The rotation dialog offers angle presets/custom angle, optional padding shape,
and padding fill methods. Review how dimensions and corners change before
Apply. Rotations update calibration as well as geometry.

**Reset rotation** in this dialog or **Edit → Reset rotation…** restores the
exact snapshot taken before the first rotation, rather than applying an inverse
interpolation. Confirmation explains that edits made after that rotation also
revert. The native project retains this savepoint; Undo can recover the rotated
state. Older rotated projects without such a savepoint cannot restore lost pixels.

The scale dialog selects objects/group, factor/spin control/slider,
temporary/local savepoint storage and a name. **Restore selected** and
**Restore local snapshot…** recover compatible snapshots; **Apply scale**
commits. Temporary snapshots disappear with the session.

## Morphology and object properties

Object properties manage annotation metadata. **Morphology / inner region…**
selects a general/polygon/core–shell/hollow interpretation and, where applicable,
a linked core/cavity or expected side count. Relationships must be valid before
derived metrics are meaningful. The full manual defines per-field applicability.

## Scale bar and Filament

**Add scale bar…** previews the length, units, font, font size, line width and
corner position on the canvas. **Apply** saves the style with the native project.
**Edit scale bar…** and **Remove scale bar** update an existing bar.

Use **Edit → Filament** in Edit mode. [Mark a group and connect visible fragments](../user-manual.md#filaments-and-occluded-fragments)
to report the visible centerline length, straight-gap estimate and visible widths.

## Statistics and export dialogs

Statistics accepts a named plot group under **Images**. **Object points (mask
colors)** shows per-object measurements with the same RGB assignments as the
canvas. Choose up to nine metrics for display and choose the numerical columns
to export independently. The [measurement guide](../features/measurements.md)
describes how to create a plot group and share its color scale.

Mask/image/dataset dialogs select output scope, original/processed pixel copies,
format, colors/opacity/alpha where applicable, and explicit handling of lossy
YOLO geometry. Integer label outputs preserve IDs rather than display effects.

## Aliases, plugins, and help

The alias table maps phrases and validates empty/duplicate/cyclic entries.
See [alias examples](../segmentation/application-tools.md#text-prompt-aliases).
Plugin management offers enable checkboxes, **Apply / reload**, **Remove plugin**,
and **Close**. Installed plugin actions vary by plugin and are not core controls.

**Help → User Manual** opens the English manual, including the Denoising
parameters chapter. **Plugin → For Developer (PDF)** opens the developer guide.
