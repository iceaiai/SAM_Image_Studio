# Image workflows

Choose the task you want to perform. Each guide describes the input, controls,
expected result, and limitations. Install the application first, then try the
[first annotation walkthrough](../quickstart.md) with the bundled demo image.

::::{grid} 1 2 2 2
:gutter: 3

:::{grid-item-card} Annotate and edit
:link: annotation
:link-type: doc

Draw geometry, organize groups, select objects, refine masks, rotate an image,
and scale masks with savepoints.
:::

:::{grid-item-card} Segment with SAM
:link: ../segmentation/index
:link-type: doc

Choose a model and use text, points, shapes, whole-image examples, or an ROI.
Follow the dedicated SAM3.1 guide.
:::

:::{grid-item-card} Restore and process pixels
:link: processing
:link-type: doc

Compare denoisers, smooth an image, add controlled noise, and preserve crops.
:::

:::{grid-item-card} Clean and restore regions
:link: cleaning
:link-type: doc

Remove contamination, fill from neighbors/LaMa/background patches, and restore
pixels by removing an edit record.
:::

:::{grid-item-card} Calibrate and measure
:link: measurements
:link-type: doc

Import Excel pixel sizes, inspect object metrics, and export plots and tables.
:::

:::{grid-item-card} Save and export
:link: saving
:link-type: doc

Keep editable native projects and export exact COCO masks, YOLO polygons,
overlays, and original/processed images.
:::
::::

```{toctree}
:maxdepth: 2

../quickstart
annotation
../segmentation/index
processing
cleaning
measurements
saving
extensions
```
