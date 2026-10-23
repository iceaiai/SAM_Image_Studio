# Native projects, masks, and exports

## Keep the editable project

Committed changes are saved atomically to native `.sam.json` files, with a
previous valid backup. **Save project now** forces a native save;
**Choose project folder…** selects a writable destination. Native projects
retain geometry, groups, calibration, prompts/aliases, masks, and image edit
records for editing and recovery.

**Remove selected images** saves/closes workspace entries without deleting
their sources or saved annotations. At launch, choose whether to reopen the
previous session. Choose No for an empty workspace with projects retained.

## Select an output format

| Control | Output and tradeoff |
| --- | --- |
| Save masks… | Binary, weighted grayscale, group/object colors, integer labels, and overlay options |
| Transparent mask images… | Alpha background plus independent mask-opacity controls |
| COCO segmentation dataset… | Exact RLE masks with groups/attributes, calibration and application cleaning extensions |
| YOLO segmentation dataset… | Polygon output; holes/disconnected masks need explicit handling and may require a reviewed lossy conversion |
| Save original / processed images… | Acquired original TIFF, processed TIFF, or both |

Overlap-weighted grayscale sums equal per-object contributions at shared
pixels; it is a visualization, not a substitute for separate instance masks.
Integer ID maps preserve discrete labels. PNG/TIFF support alpha; BMP24 does not.

**Original** image-only export means the acquired, unrotated frame. **Processed**
includes current rotation/cleaning/denoising. Dataset/overlay uncleaned images
use the current orientation to stay aligned with annotations. Always inspect
the exported coordinate alignment.

Example: retain the `.sam.json`, export exact COCO plus original/processed
copies for analysis, and save a transparent colored overlay for review.
A dataset export or flat TIFF does not replace the native editing history.
