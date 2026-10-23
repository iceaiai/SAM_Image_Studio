# First annotation and export

## Open an image and prepare calibration

Start the application after [installation](installation.md). Open
`examples/synthetic_particles.ome.tif`, or a supported microscopy image.
The **Objects**, **Groups**, and **Image files** docks hold annotations, labels,
and image/stack frame entries. Startup asks before reopening a previous session.

Check physical pixel size before interpreting measurements. When a reader
does not provide calibration, enter it explicitly or import the supported Excel
lookup. A missing calibration remains explicit; pixels are not silently
converted into nanometers. The workbook uses `converted_image_name` and
`converted_size` columns, where the size is a positive numeric nm/pixel value.
See the user manual for lookup matching, rotations, and applicability.

## Create a model preview

1. Open **Model manager** and load **SAM2.1 Tiny** or **SAM1 ViT-B** on CPU.
   Compatible weights download separately or can be selected locally.
2. Create a group, switch to **Segment**, and select
   **Prompt project, whole image**.
3. Add a positive point or area example, then negative examples for unwanted
   instances. Inspect the live preview and adjust prompts.
4. Choose **Accept masks** to commit reviewed results.

**Single object (native SAM)** and **Inside ROI only** require an area tool;
they are hidden/disabled for **Point**. Whole-image exemplar matching for SAM1/2
is the application's candidate/retrieval layer, not a trained microscopy
classifier. Previewed masks remain disposable until accepted.

For SAM2/2.1 text prompts, enter a phrase and use **Run text segmentation**.
Grounding DINO supplies boxes which SAM segments. SAM1 does not expose this
text path. Native SAM3/3.1 require the separate GPU setup.

## Edit, process, and inspect measurements

Use **Manual** to add geometry and **Edit** to change existing objects. Check
the selected group, object locks, and scope before applying changes.
**Processing** previews denoising/smoothing/noise operations; **Apply** commits
an undoable image record. Compare with acquired pixels before trusting small
features. The [parameter guide](denoising.md) explains units and tradeoffs.

**Clean** records removals/fills separately. Deleting a cleaning record restores
its footprint while replaying the remaining image changes. Derived images do
not overwrite acquired source pixels.

Open **Statistics** for object and group measurements. Metrics depend on
geometry and calibration; an unavailable metric is not a valid zero.

## Save and export

Committed operations save native `.sam.json` projects. Use **Choose project
folder** when the source folder is not writable, and retain native projects for
complete editable recovery. Removing an entry from **Image files** saves/closes
it without deleting its source or saved annotations.

Use **Export** for COCO, YOLO, masks, overlays, and derived images. COCO uses
exact RLE masks and application cleaning extensions where applicable. Generic
dataset formats do not replace the full native project. Reopen a saved native
project and inspect accepted masks before distributing an export.

```{image} ../screenshots/v142_workspace.png
:alt: SAM Image Studio workspace with the image canvas and annotation docks
:width: 100%
```

The complete [user manual](user-manual.md) covers modes, tools, shortcuts,
calibration, retained crops, statistics, export options, and recovery.
