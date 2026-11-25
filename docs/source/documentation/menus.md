# Menu-by-menu reference

This reference covers the core menus in the main window. Some actions depend on
selection, mode, loaded model, or task state. Installed plugins add their own
actions and are documented by their authors.

## File

| Menu entry | What it does | Shortcut |
| --- | --- | --- |
| Open images… | Open one or multiple supported images. Each image/stack frame becomes an Image files entry. | Ctrl+O |
| Open folder… | Select a folder of supported images for the workspace. | — |
| Open project JSON… | Open a native annotation project and locate its source/frame when necessary. | — |
| Save masks… | Export masks or overlays with binary/weighted/color/label options; Ctrl+S opens this dialog. | Ctrl+S |
| Save project now | Force a native editable .sam.json save; this differs from exporting a mask. | — |
| Choose project folder… | Choose a writable destination for native autosaves. | — |
| Save original / processed images… | Save acquired original TIFF, processed TIFF, or both. | — |
| Close current image | Save and close the active workspace image. | — |
| Exit | Close the application after its pending-work/save handling. | — |

## Edit

| Menu entry | What it does | Shortcut |
| --- | --- | --- |
| Undo | Revert the latest committed operation in the current image history. | Ctrl+Z |
| Redo | Reapply an undone operation. | Ctrl+Y |
| Edit object vertices | Edit existing selected geometry instead of adding another shape. | Ctrl+E |
| Delete objects | Delete the selected objects. | Del outside Edit |
| Delete vertex | Delete the highlighted batch of up to ten vertices from one contour. | Del in Edit |
| Select all objects | Select annotation/cleaning objects; image-smoothing records remain selectable in Objects. | Ctrl+A |
| Invert region | Make an exact pixel region from the complement of selected area masks or the current region. | Ctrl+I |
| Create object from region | In Manual/Edit, create an exact mask annotation from the current nonempty region. | — |
| Object properties… | Edit metadata for the selected annotation. | — |
| Change selected objects' group… | Move selected eligible objects to a different group. | — |
| Brightness / contrast… | Adjust the display copy without modifying acquired pixel values. | — |
| Object color… | Change selected object display colors. | — |
| Object transparency… | Set mask display opacity independently of binary mask geometry. | — |
| Assign mask colors… | Use group colors, the preset lookup table, or a measured value with a configurable color count. | — |
| Smooth image pixels… | Preview a smoothing operation on derived pixels; this is different from smoothing a contour. | — |
| Rotate image… | Choose angle, optional rectangle/square padding and fill; transform pixels, masks and calibration together. | — |
| Reset rotation… | Restore the exact pre-first-rotation savepoint, including pixels, masks and calibration; later changes are reverted after confirmation. Undo is available. | — |
| Scale masks / savepoints… | Scale selected/group masks uniformly; keep original/result snapshots temporarily or in a local folder. | — |
| Morphology / inner region… | Assign morphology and link an enclosed core/cavity or expected polygon side count for measurements. | — |
| Add scale bar… / Edit scale bar… | Preview the current image's scale bar and set its length, width, font, size and position. | — |
| Remove scale bar | Remove the current image's scale bar. | — |
| Filament → Mark group as Filament… | Enable centerline length and width measurement for a foreground group in Edit mode. | — |
| Filament → Use particle measurements for group… | Remove the Filament designation and the group's links. | — |
| Filament → Connect visible fragments… | Pick detected ends, or draw across the gap if automatic endpoints are unavailable. | — |
| Filament → Draw filament connection… | Draw from within one selected mask tip to within the other to estimate the intervening gap. | — |
| Filament → Disconnect selected fragments | Remove links incident to one selected fragment or between multiple selected fragments. | — |
| Vertex deletion radius… | Set the eligible-vertex deletion search radius in image pixels. | — |
| Vertices per deletion… | Set how many nearby vertices to highlight and remove per Delete press. | — |
| Polygon closing distance… | Set the screen distance for clicking near the first vertex to close a polygon. | — |
| Mask pusher / Mask pusher radius… | Expand or carve the selected mask with a circular stroke. Set the circle radius in image pixels. | — |
| Fill holes… | Preview filling eligible holes in selected area masks. | — |
| Smooth edges… | Preview smoother editable contours for selected masks; does not smooth image intensities. | — |
| Refine disconnected parts… | Preview retaining only the largest part or trimming the smaller parts of selected masks. | — |
| Select mask part / Delete selected mask part | Highlight a single disconnected piece in Edit and remove it. | Del with Select mask part active |

## Cleaning

Follow the [illustrated data-cleaning walkthrough](../features/cleaning.md) in
this menu order: remove → choose fill → preview/apply → restore.


| Menu entry | What it does | Shortcut |
| --- | --- | --- |
| Remove selected image area | Create a reversible pixel-removal record from the current area in Clean mode. | Ctrl+D |
| Restore selected area / all edits | Restore requested pixels while retaining/replaying other applicable edits. | — |
| Fill from neighboring pixels | Fill removed target pixels from available neighboring image content. | — |
| Fill with LaMa… | Preview a separately loaded LaMa model fill for the target. | — |
| Fill with background patches | Fill from real manual patch sources in the explicitly chosen background group. | — |
| Choose background group… | Choose the group supplying clean manual background patches. | — |
| Add selection to background group… | Add eligible selected manual area patches to the background group. | — |
| Clear background group selection | Remove the current background source-group association. | — |
| Cleaning brush radius… | Set the point brush size used in Clean, separately from SAM prompting. | — |

## Models

| Menu entry | What it does | Shortcut |
| --- | --- | --- |
| Model manager… | Choose model family/variant, matching checkpoint and CPU/Conda CUDA device. | — |
| Otsu + watershed… | Adjust threshold/splitting parameters, preview classical masks without SAM, then accept. | — |
| Segmentation options… | Set candidate controls and optional calibrated area or equivalent-diameter bounds. | — |
| Text prompt aliases… | Edit project aliases such as nanoparticle → black dots; aliases do not train a model. | — |

## Export

| Menu entry | What it does | Shortcut |
| --- | --- | --- |
| COCO segmentation dataset… | Export exact RLE masks plus annotation/calibration and application cleaning extensions. | — |
| YOLO segmentation dataset… | Export polygons with explicit hole/disconnected-mask conversion handling. | — |
| Transparent mask images… | Export mask images with transparent backgrounds and independently configurable mask opacity. | — |

## Statistics

| Menu entry | What it does | Shortcut |
| --- | --- | --- |
| Plot Object Statistics… | Choose an image scope, plain or mask-colored histograms, or mask-colored points, and up to nine displayed metrics. | — |
| Create plot group from selected images… | Save a named set of frames with an optional shared measurement color scale. | — |
| Edit active plot group… | Change its name, membership or color settings, or remove the group. | — |
| Edit image calibration… | Set physical X/Y pixel sizes and length unit. | — |
| Read pixel sizes from Excel… | Select a worksheet/unit and match converted_image_name to converted_size after filename normalization. | — |
| Forget automatic Excel lookup | Stop applying the saved lookup on later opens while retaining calibration already assigned. | — |

## View

| Menu entry | What it does | Shortcut |
| --- | --- | --- |
| Reset magnification / fit image | Fit the current image to the viewport. | F |
| Show masks | Toggle mask rendering without deleting annotations. | — |
| Show contours | Toggle annotation outlines. | — |
| Show prompt points | Toggle prompt marker display. | — |
| Toolbars | Show or hide Workflow, Image settings, Regions and image processing, and Segmentation prompts individually. | — |
| Toolbar icon size → Small (default) | Use 22-pixel drawing icons; enlarged Undo/Redo keep their special size. | — |
| Toolbar icon size → Medium | Use 30-pixel drawing icons. | — |
| Toolbar icon size → Large | Use 40-pixel drawing icons. | — |
| Objects | Show/hide the Objects dock. | — |
| Groups | Show/hide the Groups dock. | — |
| Image files | Show/hide the image/dataset/frame dock. | — |

## Help

| Menu entry | What it does | Shortcut |
| --- | --- | --- |
| User Manual | Open the bundled English manual for the running version. | — |

## Processing

The [compressed-sensing guide](../features/compressed-sensing.md) follows the
DCT/TV dialog controls in order and shows computed parameter comparisons.


| Menu entry | What it does | Shortcut |
| --- | --- | --- |
| Denoise… | Choose a restoration method, preview it, or open the Denoising parameters chapter. | — |
| Smooth (Gaussian)… | Choose an odd kernel size and spatial sigma for derived pixel smoothing. | — |
| Crop selected region / masks… | Retain real pixels in the mask bounding box plus 3 pixels of context and protect them. | — |
| Retained crops / paste back… | Paste, protect/release, export or remove retained snapshots. | — |
| Add noise… | Add reproducible Poisson, Gaussian or salt-and-pepper noise with adjustable strength/seed. | — |

## Plugin

| Menu entry | What it does | Shortcut |
| --- | --- | --- |
| Install local plugin folder… | Copy a trusted local plugin folder with plugin.json into the app profile and load it. | — |
| Manage / reload plugins… | Enable/disable/reload/remove installed plugin source; dependencies are not installed automatically. | — |
| For Developer (PDF) | Open the separate plugin/API/U-Net example manual. | — |

For toolbar/panel buttons, see [controls](controls.md). For parameter dialogs,
see [dialogs](dialogs.md) and the [denoising reference](../user-manual.md#denoising-parameters).
