## Start, modes and workspace

SAM Image Studio opens one or many images for annotation, segmentation, calibrated measurements and reversible image processing. Acquired pixels remain available separately from derived pixels. The top-right Objects list and the canvas select the same objects. Source filenames appear in the lower-right Image files list; stacks have child frame entries.

Manual adds shapes. Segment creates disposable model previews. Clean edits derived image pixels through retained cleaning records. Edit changes existing shapes, rotates images, scales masks, adds scale bars and configures filament measurements. Switching mode with pending shapes/prompts/previews asks Yes to add, No to discard or Cancel to remain. An incomplete polygon cannot be added.

Example: open two TIFFs, select the first in Image files, draw one Manual rectangle, then switch to Edit and select it in Objects. The Objects, Groups and Image files docks keep the v1.4 layout and can be resized.

The left drawing tools occupy two columns, including Point and Ellipse. Use **View → Toolbars** to show or hide Workflow, Image settings, Regions and image processing, and Segmentation prompts individually. The app remembers these choices when reopened.

Startup asks whether to reopen previous images. No leaves the workspace empty and preserves annotation files. Removing an image from the workspace saves its annotations and does not delete its source image or annotation files.


## Installation, Python and Conda GPU setup

Use 64-bit Python 3.12. Extract the complete release into a writable folder. On Windows run Install_CPU.bat, then Start_GUI.bat. The CPU environment is local to the application. Run Install_Python_3_12.bat if Python 3.12 is missing; other Python versions may remain installed.

```python
winget install --exact --id Python.Python.3.12 --architecture x64 --scope user --source winget
```

For a GPU, install Miniforge/Conda, open its prompt, change to the extracted application folder and inspect the detected NVIDIA devices. GPU execution is permitted only inside Conda. The installer reads driver capability and GPU architecture; it does not install or change drivers. AMD/Intel hardware uses the CPU path in this release.

```python
python scripts/install_conda_gpu.py --inspect
python scripts/install_conda_gpu.py --name sam-image-studio-gpu --dry-run
python scripts/install_conda_gpu.py --name sam-image-studio-gpu
conda activate sam-image-studio-gpu
python -m samstudio
```

If Python is not available in the initial prompt, use conda run -n base python for the installer command. Install_GPU_Conda.bat does this on Windows. A custom environment name must also be used when activating or running it. Start_GUI_GPU.bat targets the default environment name.

For an existing dedicated environment: conda create -n sam-image-studio-gpu python=3.12 pip, then conda activate sam-image-studio-gpu, then python scripts/install_conda_gpu.py --current. Installation into the Conda base environment is rejected. The setup selects the supported PyTorch 2.7.1 CUDA 11.8, 12.6 or 12.8 wheel index from driver/architecture information.

SAM3 CPU is not advertised as a verified backend. Optional native SAM3 uses Linux/WSL2 Conda, CUDA 12.6 or later and approved Hugging Face checkpoint access. Use --sam3 with the installer in Linux/WSL2. Native Windows Conda is supported by the setup path for SAM1/2; native SAM3 Windows inference is not verified. Access to gated model weights remains the user's choice.

CPU inference and native Qt events are tested on Linux. This machine has no NVIDIA GPU: simulated GPU reports test setup decisions, not CUDA execution. Run a real local model preview and acceptance check after GPU installation. See GPU_CONDA_GUIDE.md for commands, troubleshooting and environment removal.


## Opening images and native autosaves

Open images accepts PNG, JPEG, BMP, TIFF and supported EMD, DM3 and DM4 datasets. Each source filename appears in Image files; stack frames have separate entries. Supported physical calibration is read from the source; unavailable calibration remains in pixel units. Edit image calibration sets X/Y sizes and units manually.

The v1.4 annotation workflow and COCO export representation are retained. A matching native SAM_Annotations project restores objects, prompts, groups, calibration, exact contours, original/derived pixels, cleaning history and rotation. Native schema 6 stores scale bars, filament connections, and per-image measurement color settings alongside exemplar prompts and retained crops. It reads native schemas 1–5.

Committed operations autosave atomically into a .sam.json project, with a previous valid backup. Save project now forces a save; Choose project folder selects another writable destination. Open project JSON can locate its source/frame after moving a project. Preserve the native project for complete editable recovery. Area-mask exports omit point annotations and report their count.

Example: draw and accept two masks, close the image, then reopen the same TIFF. Its native project restores those masks. Removing selected entries from Image files saves the native projects and only removes them from the workspace. Source images and annotation files remain. At startup, choose Yes to reopen the previous images or No to start empty.


## Excel pixel-size lookup

Choose Statistics > Read pixel sizes from Excel. Select an .xlsx/.xlsm workbook, its worksheet and the physical unit per pixel. The first row must contain converted_image_name and converted_size. Header whitespace and case are ignored. converted_size is a positive finite numeric size per pixel and is applied to both X and Y. Excel formulas need a cached numeric result saved by a spreadsheet application. Legacy binary .xls files must first be saved as .xlsx.

Matching removes the last file extension, any Windows/Unix directory and surrounding whitespace, then ignores case. A row named Particle.001.png matches particle.001.tiff or PARTICLE.001.dm3. Internal dots remain part of the name. Conflicting rows with the same stem and different sizes are rejected; consistent duplicates are accepted. Blank names are skipped. Invalid numeric rows reject the table before documents change.

Example: converted_image_name = Sample_07.png and converted_size = 0.25 with unit nm set both pixel sizes of Sample_07.tiff to 0.25 nm/pixel. All frames of a matching stack receive the same value. Unmatched images retain their existing calibration. The status bar reports matched and unmatched frame counts.

Loaded documents are recalibrated in one undoable operation per frame and autosaved. The lookup also applies after native project restoration when matching images open later. Rotated coordinates rebuild their physical basis using all saved transforms; masks are unchanged. The table path, sheet and unit are remembered and re-read at next launch. Forget automatic Excel lookup removes the association and retains calibration already assigned. If the table is unavailable at startup, the status bar reports that it was not loaded; no image is assigned a guessed size.


## Whole-image exemplars, single objects and ROI

Prompt project, whole image means that examples describe the desired object type across the current image. The examples are searched across the current image. Before accepting, add multiple positive examples and negative examples. Left/right clicks add positive/negative points. Choose Positive example or Negative example for rectangle, circle, ellipse and polygon prompts.

With Live prompt preview enabled, adding an example schedules a background update. Newer input supersedes older preview results; accepted objects remain protected. Preview masks are disposable until Accept masks. Cancel clears pending examples. CPU searches may take time; the status bar reports progress while the interface remains available.

When candidates are ready, click **Review…** next to **Run preview** to inspect them before **Accept masks**. Choose all candidates or a single candidate, turn the overlay on and off, and zoom or pan to check the outline against the image. Close the review window to return to the pending masks.

SAM3 uses native image concept prompting. SAM3.1 uses the official multiplex predictor on a lossless single PNG frame, with its own sam3.1_multiplex.pt checkpoint. SAM3.1 receives all positive/negative boxes together in normalized top-left XYWH format; point exemplars first produce an instance whose box becomes a concept prompt. SAM3.1 is GPU-only and requires the separate Linux/WSL2 Conda environment and approved facebook/sam3.1 weights. Other shapes and points first identify an exemplar object, whose bounding box becomes a SAM3 concept example. SAM1/2 use the application's candidate-and-retrieval layer: propose masks, pool SAM features, compare image/shape descriptors and filter using positive/negative examples. Repeated small objects also receive template-based candidate seeds. This is a heuristic retrieval layer, not native SAM3 or a trained nanoparticle classifier.

Example: mark one bright particle positive, then mark a contamination feature negative. The preview searches for similar particles throughout the image. Add another positive particle if size or appearance varies. A clearly negative type suppresses similar candidate types; an explicitly negative object is excluded. When positive and negative appearances cannot be distinguished, inspect and correct the preview.

Single object (native SAM) keeps the ordinary point/box refinement behavior for one object. Inside ROI only predicts from an area prompt and clips its result to that region. With Point (dot) selected, Single object and Inside ROI only are hidden and disabled. A previously selected area-only scope switches to Prompt project, whole image. To use Single object or ROI only, choose an area tool. Point coordinates remain image pixels at every zoom.

Accepted, hidden and locked foreground masks are protected from accidental replacement. Use Refine selected object explicitly to replace one unlocked foreground object while keeping its identity and group. An inverted exact region can constrain allowed inference pixels; background groups and cleaning objects are not foreground training targets.


## Target size range

Open **Models → Segmentation options…** or **Options…** in the workflow toolbar. In **Target size range**, choose **Projected area** or **Equivalent circular diameter** (ECD), then choose pixel or physical units. Area uses squared units. ECD is the diameter of a circle with the same area as the mask.

Enter a minimum, a maximum, or both. Each blank field leaves that end open. Both fields start blank. Bounds are inclusive and apply after output is clipped to the ROI or around protected annotations. The range works with Inside ROI only, Prompt project, whole image, Automatic grid, and Otsu + watershed. A configured range replaces the candidate noise floor in these scopes. Single object (native SAM) and explicit Refine use their normal behavior.

Physical limits use the image calibration, including different X/Y sizes. For a filter-specific override, select **Enter pixel sizes for this filter**, enter the X and Y sizes and choose their unit. The override applies only to the filter. Enter equal values for square pixels. For example, with 0.5 nm pixels, a lower area of 25 nm² accepts masks with 100 or more pixels. Leave Maximum blank to accept any larger eligible mask.

Run a fresh preview after changing the limits and review the eligible masks before accepting them.

## Automatic grid and text prompts

Automatic grid, unannotated only starts when selected in Segment with a loaded model, when entering Segment with that selection, or when the model finishes loading in that state. Run preview also starts it explicitly. It ignores any text field and samples unannotated pixels with native SAM point prompts.

The status bar shows prompt counts and the number of candidate masks. After filtering, the preview reports the resulting count. For zero masks, review the score, target size and grid density. Larger grids cost more time, especially on CPU. Cancellation preserves accepted annotations.

Text prompting has its own Run text segmentation button, in addition to the shared Run preview control. Enter in the text field also runs it. SAM2/2.1 resolve phrases through Grounding DINO Tiny detections and segment those boxes with SAM; SAM3 and SAM3.1 have native text paths. SAM1 hides text controls.

Aliases map complete phrases and are case-insensitive. Example: nanoparticle -> big dots, powder -> big dots. Aliases can chain; cycles/duplicate conflicting names are rejected. They replace input phrases and do not train the detector. The effective phrase appears in the tooltip and accepted-mask provenance.

Text does not establish scientific detection accuracy. The verified public text integration image contains vehicles, not nanoparticles. Use the review preview and compare against the acquired image.


## Manual geometry and Edit tools

Use Manual for points and closed shapes. After placing at least three polygon vertices, click near the first vertex to close. It turns green when the cursor is close enough. Choose **Edit → Polygon closing distance…** to set the distance in screen pixels. The default is 14 and 0 turns off closing by proximity. Press Enter or double-click to close at any setting. Point annotations remain points at every zoom.

In Edit, select an object on the canvas or in the list and drag its existing handles. To delete vertices, choose **Vertices per delete** in the Image settings toolbar and set **Vertex radius (px)**. The radius defaults to 20 image pixels and the count defaults to one. Click near the target contour to highlight the closest eligible vertices in amber, then press **Delete vertex** or **Del**. Each press removes up to ten highlighted vertices from one contour, leaves at least three, and can be undone in one step. These settings are also in the Edit menu. Use the separate **Delete objects** button to remove entire annotations.

Fill holes and Smooth edges open previews. Smooth edges retains editable cubic curves rather than merely changing a jagged display. Batch changes are one undoable operation. Mask sizes and statistics update after applying changes.

Rotation offers angle presets and arbitrary angles. No padding keeps original dimensions and may crop corners. Rectangle or square padding enlarges the canvas; choose black, neighbor, LaMa or a manually selected background-group fill. Review the result before Apply. Pixels, masks, cleaning records and the physical coordinate basis rotate together. Paste/remove retained crop snapshots before rotating.

Scale masks / savepoints scales selected unlocked objects or all area objects in their groups, uniformly about each centroid. Enter a factor or use the slider. Clipping at image boundaries and overlaps can occur. Original geometry and result snapshots can be temporary in-memory list entries or local folders with exact JSON and binary masks. Temporary savepoints do not enter project files; local snapshots can be restored only when source/rotation coordinates match.

## Refine disconnected parts

A mask can contain several disconnected parts under one row in Objects. In **Edit**, choose **Edit → Select mask part**, click the fragment on the image to highlight it in orange, then press **Delete**. You can also right-click a fragment with **Select objects** and choose **Remove this disconnected part**. Either action removes the connected pixels in that piece and keeps the object's other parts. Use **Esc** to clear the highlighted part or switch to **Select objects** to resume vertex editing.

For one or more selected unlocked masks, open **Edit → Refine disconnected parts…**. **Keep largest connected part** retains one part per mask. **Remove parts smaller than a chosen area** keeps parts at or above the minimum in px² and always retains the largest. Pixels touching at edges or corners belong to the same part. Click **Preview** to see removed pixels in red, then **Apply** to commit. Use **Undo** to restore the prior masks.

## Mask pusher

In **Edit**, select one visible, unlocked area mask and choose **Mask pusher** in the left toolbar. Change **Mask pusher radius (px)** in the Image settings toolbar or use **Edit → Mask pusher radius…**. The ring shows the brush footprint in image pixels.

Left-drag along the boundary to add a round sweep where the ring touches the mask as it was when you pressed the mouse. You can move to another side during the drag or start a new stroke there. Right-drag to carve inward. Green previews added pixels and red previews removed pixels. Release to commit one undoable stroke or press **Esc** while dragging to cancel. Each stroke edits the selected mask within the swept circle and keeps at least part of the object.


## Scale bars

Choose **Edit → Add scale bar…**. Set the length and its unit, line width, font, font size and corner position. The image previews changes as you type. **Apply** saves the bar in the native project. **Edit scale bar…** reopens it and **Remove scale bar** removes it. Undo and Redo cover these changes.

Use px for a pixel reference or a physical unit for a calibrated length. The horizontal bar uses the current image X direction of the calibration, including after rotation. Width and font size are in image pixels and scale with zoom. If the bar cannot fit after a calibration or size change, reopen its settings and choose a length and style that fit. The bar is a canvas overlay. Source TIFFs and mask exports retain their underlying pixels.

## Distance measurements

In the left toolbar, choose **Measure line** and drag from one endpoint to the other. Choose **Measure curve** and drag along the full path to add up its segment lengths. The readout updates as you drag and shows the length in image pixels. For a calibrated image it also shows the length in the image's physical unit, using the X and Y scales and any applied rotation. Set or check those scales in **Statistics → Edit image calibration…**.

Zoom and pan to position the endpoints or follow a curve more closely. The distance stays on the current image until you draw again, switch images or press **Esc** with a measurement tool selected. Measurements are temporary overlays on the canvas.


## Cleaning and reversible image records

In Clean mode select an area, draw a region or use the brush. Remove selected image area stores a visible cleaning object. Alternatively right-click an unlocked area object and choose Delete for cleaning. Choose neighbor interpolation, LaMa or manually selected background patches to fill removed pixels.

Background-patch sources must be manually added area objects in one explicitly selected group. Any group name is allowed. Sources may be polygon, ellipse or rectangle regions; pixels outside irregular masks are not sampled. Sources intersecting already-modified image pixels are rejected.

Preview the fill, then Apply or Cancel. Only the target pixels change. Show cleaning regions controls display. Delete a cleaning object to restore its footprint while replaying remaining edits. Native JSON and COCO cleaning extensions keep footprints, replacement pixels, methods and restoration history separately from foreground annotations.

Example: remove a contamination spot, fill from clean support patches, then delete that cleaning record if the fill is unsuitable. A separate denoising operation remains replayable. Derived-image saving never overwrites the acquired source.


## Processing: restoration, smoothing and noise

Processing opens a fresh parameter dialog with method defaults on every open or method change. Choose the whole image or selected region/object masks, and choose original uncleaned pixels in the current orientation if needed. Removed pending pixels and protected retained crop rectangles are excluded. Preview, then Apply to commit an undoable image record.

| Method | Parameters and example |
| --- | --- |
| TV restoration | Chambolle total variation: weight 0.08, iterations 100, tolerance 0.0002. Increase weight cautiously for stronger smoothing of noisy flat areas. |
| TV Bregman restoration | Split-Bregman TV: weight 5 and 100 iterations. Its weight convention differs from Chambolle; do not compare numbers directly. |
| Wavelet sparse restoration | db2 wavelet BayesShrink with soft thresholding; sigma 0.04 and up to 2 levels. The image must be large enough for decomposition. |
| Non-local means | Strength 0.08, sigma 0.03, patch 5 and search distance 6. Compare repeated texture carefully because real fine structure can be altered. |
| Bilateral denoise | Color sigma 0.05 and spatial sigma 3. Preview edge retention versus small-feature loss. |
| Median denoise | Odd kernel 3. Useful for an isolated impulse-noise comparison. |
| DCT sparsity | Whole-image, orthonormal 2D DCT per channel; hard threshold retains about 8% of coefficients each iteration. Denoise default: 40 iterations, relaxed L2 fidelity 0.2. |
| TV iterative (notebook) | Forward-difference gradient/divergence prior. Denoise default step 0.01; the reconstruction preset uses notebook step 0.08 and epsilon 1e-6. |
| Sparse dictionary learning | SPORCO learns 64 atoms from up to 2048 mean-centered 8-pixel patches, then performs L1 sparse coding and overlap averaging. |
| BM3D | Official bm3d backend, Gaussian sigma 0.04, normal profile, both stages and one native thread. Upstream academic/non-commercial terms apply. |
| Noise2Void / N2V2 | CAREamics self-supervised blind-spot training or prediction with an existing .ckpt/model folder. Models are trained per image channel; no pretrained denoising weights are bundled. |
| Gaussian smooth | Odd kernel 5 and sigma 1. The kernel width and standard deviation are independently selectable. |
| Gaussian noise | Sigma 0.03 of the processing intensity range and an explicit seed. Same seed/settings reproduce the same added noise. |
| Poisson noise | Peak counts 50 and a seed. Lower counts increase relative shot noise; this is an intensity model, not detector calibration. |
| Salt and pepper noise | Amount 0.01 and a seed. Creates synthetic impulse noise for algorithm comparisons. |

Parameters that use intensity fractions operate on normalized real pixels: unsigned integers use their full type range; signed integers use their type range; floating images already in [0,1] retain that range; other floating images use their observed minimum/maximum. Integer results are rounded/clipped back to their original type. RGB channels are processed spatially and independently. Alpha and pixels outside the target remain exact.

Each control has a ? button and a side-panel explanation with its default, allowed range/options and suggested starting values. Restore defaults resets the current method. Help > Denoising parameter guide opens the separate complete parameter PDF.

DCT and iterative TV offer Denoise and Reconstruct tasks. Denoise uses all input pixels with a relaxed fidelity update; it never hard-replaces all pixels with the original. Reconstruct simulates missing pixels from the chosen input. The Notebook reconstruction preset selects random 10% sampling without replacement, seed 7, nearest initialization, 40 L2 iterations and processing max side 256. With a resolution cap, output is interpolated back onto the original grid. Native-resolution processing is the ordinary default. The preset does not force a grayscale or integer source into RGB; applying the same spatial operation to each RGB channel matches the notebook channel handling.

For Noise2Void/N2V2, Train fits and saves a model, then previews prediction. Start with the supplied defaults, suitable patch sizes and representative regions. A one-epoch trial only verifies execution. Models and checkpoints are saved before image Apply, and remain if you cancel the preview or undo the image operation. Empty output directory creates a unique application-data model directory, reported in progress/provenance. Predict accepts a compatible CAREamics checkpoint or the saved folder. Use only trusted checkpoint files. CPU is supported; CUDA requires a dedicated Conda environment. Training runs in a worker with cancellation between batches. Cancel for BM3D/other native solvers takes effect after the current native call returns.

Denoising can change real TEM/SEM features, including lattice contrast and boundaries. Compare against acquired pixels and retain the method/parameters. The software does not claim one default is optimal for every specimen or detector.


## Retained crops and paste-back workflow

Select one or several area objects or a shared pixel region, then choose Crop selected region / masks. The crop is the union-mask bounding box expanded by 3 pixels on each side and clipped at image boundaries. It contains real image pixels, including background outside an irregular mask; corners are not filled with black or generated pixels.

Example: select an irregular particle, retain a named crop, run TV restoration on the rest of the image, then choose Retained crops / paste back and Paste back. The complete crop rectangle is protected by default during Processing operations.

Retained crops lists each name, coordinates and protection/paste state. Protect / release changes whether Processing skips its rectangle. Export TIFF writes the actual crop pixels. Paste back defaults to the full rectangle including real background; Mask pixels only pastes just the original selected footprint. Remove snapshot deletes the retained copy without deleting image pixels.

Crop pixel snapshots and their coordinates persist in native autosave. Pasting is undoable. Paste/remove retained crops before image rotation so coordinates cannot silently become invalid.


## Filaments and occluded fragments

Use **Edit** mode and choose **Edit → Filament → Mark group as Filament…**. Choose a foreground group with the visible masks of fibers, lines or tubes. Each mask is measured along its skeleton centerline, including bends. The centerline extends to the boundary at visible ends. Branched shapes use a principal path between skeleton endpoints; inspect such masks before interpreting their results.

For a filament interrupted by an occlusion, keep each visible section as its own mask in the same group. Ctrl+click two fragment rows in **Objects** and choose **Edit → Filament → Draw filament connection…**. Drag a straight line from just inside one tip to just inside the facing tip on the other mask. The app trims the line to the two boundaries and draws a dashed bridge across the gap. This works with branched masks. **Connect visible fragments…** lets you click detected ends and switches to drawing when it cannot find a usable open centerline.

Repeat with each neighboring pair to make a chain. Choose **Disconnect selected fragments** to remove links. Selecting one fragment removes its incident links. Selecting several removes the links between those fragments.

In **Statistics → Plot Object Statistics…**, choose the Filament metrics. **Visible length** sums the measured centerlines. **Estimated gap length** sums straight distances between linked visible ends. **Estimated total length** adds those two values when the visible traces and gaps are resolved. Each linked chain appears as one measured filament. Its visible masks remain independently editable and each fragment ID is recorded in the statistics CSV.

Widths are measured across the visible mask along local normals to the centerline, using the calibrated basis for physical results. The report includes mean, minimum, maximum, population standard deviation and population variance. The mean and variance weight cross-sections by arc length. Width statistics exclude gap segments, and width variance uses squared length units. Check the measured boundaries at your image resolution. If editing a mask leaves an unresolved link, reconnect the fragments before using the estimated lengths.

## Statistics and metric applicability

Choose current, selected or all open images; filter groups and selected objects. Plot metrics selects at most nine metric choices. Resize the window or drag the divider; use the Matplotlib toolbar for pan, zoom and reset. Auto units separate calibrated physical cohorts from uncalibrated pixel measurements.

Axes and colors edits the selected plot's X/Y names, min/max, tick intervals, label/tick font sizes and bar color. Blank numeric fields use automatic values. Invalid or excessive tick settings are rejected. Export plot saves PNG, PDF or SVG.

Export statistics independently selects all metrics or a subset with no nine-metric export limit. It writes per-object CSV, grouped mean/median/population standard deviation, histogram counts and definitions JSON. Angular arithmetic summaries require care around the 0/180 or 0/360 wrap.

| Metric key | Definition |
| --- | --- |
| area | Number of accepted mask pixels times pixel area. Projected area and area use this single metric. |
| diameter | ECD = sqrt(4 × area / pi). Diameter and size-distribution requests use this definition. |
| feret_max | Largest distance between vertices of the convex hull of occupied pixel cells. |
| feret_min | Smallest width of that convex hull over its edge-normal directions. |
| perimeter | Length of all 0.5-level marching-square boundaries, including holes. Resolution affects small objects. |
| centroid_x | Mean X coordinate of occupied pixel centers; physical coordinates include the rotated basis and origin. |
| centroid_y | Mean Y coordinate of occupied pixel centers; image Y increases downward before rotation. |
| orientation | Major eigenvector angle from +X, modulo 180 degrees. Isotropic shapes have no unique orientation. |
| length | Major axis of the equivalent second-moment ellipse: 4 × sqrt(largest covariance eigenvalue). |
| width | Minor axis of the equivalent second-moment ellipse: 4 × sqrt(smallest covariance eigenvalue). |
| aspect_ratio | Major-axis length divided by minor-axis width. |
| circularity | 4 × pi × area / perimeter². Pixel resolution can produce values above 1 for very small masks. |
| solidity | Accepted pixel-cell area divided by its convex-hull area. |
| side_length | Side of an equal-area regular n-gon: sqrt(4 × area × tan(pi/n) / n). Set expected sides in Morphology. |
| corner_error | RMS deviation from regular-polygon interior angles, in degrees. Requires a matching polygon fit at 2% perimeter tolerance; lower is better. |
| edge_deviation | RMS distance from boundary pixel centers to fitted polygon edges, divided by ECD; lower is better. |
| confidence | Recorded backend mask score. SAM1/2 use predicted mask quality; this is not a calibrated probability. Manual and legacy objects are blank. |
| border_status | 1 if any accepted pixel touches an image edge, otherwise 0. |
| particle_count | 1 per particle or linked filament. A valid inner core or cavity counts as 0. Point annotations are excluded. |
| object_id | Stable annotation UUID. The plot labels objects by name and short ID; CSV retains the full UUID. |
| outer_size | ECD of the hole-filled outer envelope; requires a valid linked core or cavity. |
| core_size | ECD of the explicitly linked core mask. |
| shell_thickness | Mean nearest outer-boundary distance from 0.5-level core-boundary samples; a 2-D estimate, not a radial or 3-D thickness. |
| center_displacement | Distance from outer-envelope centroid to core centroid. |
| normalized_displacement | Core-center displacement divided by outer-envelope ECD. |
| displacement_direction | Direction from outer centroid to core centroid from +X, modulo 360 degrees; undefined for coincident centers. |
| shell_uniformity | Coefficient of variation of sampled shell thickness (population standard deviation / mean); lower is more uniform. |
| cavity_size | ECD of the explicitly linked cavity mask. |
| wall_thickness | Mean nearest outer-boundary distance from cavity-boundary samples. |
| cavity_x | X centroid of the explicitly linked cavity mask. |
| cavity_y | Y centroid of the explicitly linked cavity mask. |
| wall_uniformity | Coefficient of variation of sampled wall thickness; lower is more uniform. |

Core/shell and hollow measurements require an explicitly linked, fully enclosed, connected inner mask. Invalid/missing relationships produce notes/blank values and do not silently suppress particle counts. A valid linked core/cavity is not counted as a second outer particle. Polygon quality requires the expected side count and a corresponding contour fit. Confidence is a model mask-quality estimate; manual/legacy objects without a model score remain blank.


## Metric colors and plot groups

To color masks in one image, choose **Edit → Assign mask colors… → By measurement**. Pick a metric such as projected area, equivalent diameter or perimeter, the measurement unit and the number of colors. The default is 20 and you can choose up to 256. The palette spans the eligible values in that image. Objects without a value in the chosen units keep their base colors.

To share a color scale across several images, Ctrl+click their file or frame rows in **Image files**, then choose **Create…** next to **Plot group**. Name the group, confirm the included frames and choose the color metric, units and color count. Selecting a file row includes all its frames. The active group uses a single scale across its open member frames. Other images keep their own colors. Reopen any closed group members to include them in the scale and plots. **Edit…** beside the group selector changes its membership or palette.

In **Plot Object Statistics…**, choose **Plot group: name** under **Images**. This uses that group for both the plot and the canvas palette. Select **Object points (mask colors)** to plot one point per eligible object in its exact mask color. Change the plotted metrics independently of the color metric, with up to nine checked at once. Use **Histogram** for a distribution, or export all or selected statistics. The CSV includes the mask color and the fragment IDs for filaments.

Select **Histogram (mask colors)** to color columns. When the plotted metric uses the same measurement and scale as the masks, the histogram uses the palette ranges and their exact colors. Compatible physical units convert automatically, such as nm² to µm². With a different metric or multiple independent color scales, each bin stacks counts in the objects' mask colors. **Bins** controls those other ranges.

Example: group three images from one condition, color by projected area in nm², then plot perimeter, ECD and circularity. A given mask keeps its area color in all three plots. **Save masks… → Color by object** uses those same displayed object colors in its preview and output.

## Masks, overlays and dataset export

Save masks offers binary masks, overlap-weighted grayscale, group/object colors and integer labels. Binary remains available. Weighted grayscale adds equal per-object intensity in shared pixels, so two overlapping masks have double weight when the chosen range permits it. Keep separate binary masks when each overlapping owner must remain recoverable.

Transparent background removes pixels outside objects by alpha. Mask transparency is independent and adjustable. Overlays can use the uncleaned image in the current orientation or the processed image after processing exists. PNG/TIFF preserve alpha; BMP24 does not. Integer ID maps disable display effects that would alter label values.

Image-only export independently saves the original acquired TIFF, the current processed TIFF or both. Original means the exact acquired unrotated frame. Processed includes rotation/cleaning/denoising. Dataset and overlay uncleaned images use current orientation so annotations remain aligned.

COCO saves exact RLE masks, attributes, categories, physical calibration and separate cleaning/background extensions. Standard COCO area stays in pixel squared; physical values are separate. YOLO polygons cannot exactly encode holes/disconnected masks; reject or explicitly accept reviewed lossy conversion and inspect its report. Create independent training/validation splits before training.

Example: export an exact COCO dataset with both uncleaned and processed image copies, then save a transparent colored overlay for inspection. Keep native projects for complete editable recovery.


## Menu and control reference

Each row states what a control does and gives an example. Plugin implementation, model code and developer tests are intentionally in the separate For Developer manual.

| Control | Purpose | Example |
| --- | --- | --- |
| File > Open images / Open folder | Open one or many raster or microscopy files. Names in Image files retain their source filenames. | Open sample.png and sample2.tiff; choose either entry in the lower-right list. |
| File > Open project JSON | Restore a native project after verifying its source, frame and fingerprint. | Locate the original TIFF if a project was moved. |
| File > Save project now / Choose project folder | Force a save or choose a writable project destination. | Use another project folder when source images are read-only. |
| File > Close current image | Remove the current frame from the workspace while preserving saved files. | Close one frame of a TIFF stack; other frames remain open. |
| Image files > Remove selected images | Remove selected entries, including all frames beneath selected file entries. Annotation files remain. | Select two source files and remove them without deleting either image or JSON. |
| Edit > Undo / Redo | Reverse and reapply a committed operation. Large toolbar controls are available. | Undo an accidental denoising apply or group mask resize. |
| Select / Ctrl+click / Ctrl+A | Choose objects on the canvas or in the upper-right Objects list. | Ctrl+click three particles before changing their group. |
| Edit > Invert region / Ctrl+I | Select the remaining image pixels after the union of selected area masks. | Select particles, invert, then clean only the background. |
| Edit > Create object from region | Create an exact annotation from a shared pixel selection, retaining holes and disconnected parts. | Turn an inverted background selection into a named area object. |
| Drawing tools | Manual point, polygon, rectangle, circle and ellipse tools add annotations. | Click near a polygon's first vertex to close it after at least three vertices. |
| Measure line / Measure curve | Measure an endpoint distance or a traced path from the left toolbar. | Trace a bend to see its length in pixels and nm on a calibrated image. |
| Hand / middle-button drag / mouse wheel | Pan and zoom the displayed image. Zoom does not change pixel coordinates. | Zoom to 40x and add a point; it remains a point rather than a one-pixel ROI. |
| Reset magnification / F | Fit the complete current image to the canvas. | Reset the view after inspecting a small edge region. |
| Groups > + Group / Rename / Color | Organize objects and choose default group colors. | Create Particle, Core and Cavity groups. |
| Object lock / visibility checkboxes | Protect geometry or hide a mask without removing its annotation. | Hide an accepted particle; automatic segmentation still protects its mask. |
| Edit > Object properties / Change group | Rename or regroup selected objects using the v1.4 properties dialog. | Move one object into the Core group. |
| Edit > Brightness / contrast | Change display normalization without modifying acquired pixels. | Increase contrast for drawing an uncertain boundary. |
| Edit > Object color / transparency | Set object appearance separately from numeric labels and mask geometry. | Make one object red at 40% opacity. |
| Assign mask colors | Choose group colors, preset colors or a measurement palette. | Color all masks by perimeter using 32 colors. |
| Edit > Delete vertex / Vertex deletion radius / Vertices per deletion | Remove up to ten highlighted vertices from one contour. | Choose four vertices per delete and click near the edge to find candidates within 20 image pixels. |
| Edit > Delete objects | Delete the selected annotations. | Select two unwanted annotations and use the object-delete button. |
| Edit > Polygon closing distance | Set the screen distance for closing a polygon by clicking near its first vertex. | Increase the default 14 px or enter 0 to close with Enter or double-click. |
| Edit > Refine disconnected parts | Preview removal of smaller parts within each selected mask. | Keep the largest part of a segmented object while clearing stray lines. |
| Edit > Select mask part / Delete selected mask part | Highlight and delete just one disconnected part. | Click a stray piece and press Delete. |
| Object context > Remove this disconnected part | In Edit, remove the connected component under the cursor. | Right-click a stray fragment to remove it from the mask. |
| Edit > Mask pusher | Adjust a selected mask with a circular stroke. | Set a 12 px radius and right-drag to carve into an edge. |
| Edit > Add / Edit / Remove scale bar | Preview and save a scale bar on the canvas. | Set a 50 nm bar in the lower-right corner. |
| Edit > Filament | Mark a group as Filament and connect visible ends across gaps. | Link two masks of a bent fiber separated by an occlusion. |
| Edit > Fill holes / Smooth edges | Preview exact hole filling or smooth editable cubic contours. | Smooth a jagged outline and compare the area before Apply. |
| Edit > Rotate image | Rotate pixels and annotations together; optionally enlarge to a rectangle/square and fill padding. | Rotate 30 degrees, select square padding and neighbor fill, then inspect the preview. |
| Edit > Scale masks / savepoints | Uniformly scale selected masks or a group about each object centroid. | Create original and 1.10x savepoints; restore original if objects grow too far. |
| Edit > Morphology / inner region | Assign morphology and explicit outer/core/cavity links for applicable measurements. | Link a separate core mask to its enclosing particle before measuring shell thickness. |
| Models > Model manager | Choose family, variant, compatible checkpoint and CPU or Conda CUDA device. | Download SAM2.1 Tiny for CPU; a local checkpoint must match the selected architecture. |
| Models > Segmentation options | Set candidate options and an optional target size range. | Use a maximum ECD of 20 nm in a calibrated image. |
| Models > Text prompt aliases | Map complete phrases to an effective prompt, without retraining. | Map nanoparticle and powder to big dots; the resolved phrase appears in the tooltip. |
| Run preview / Review / Accept masks / Cancel | Generate, inspect, commit or clear pending masks. | Review one candidate up close before accepting the preview. |
| Cleaning > Remove selected image area | Retain removals as visible, reversible cleaning objects. | Remove a contamination spot, then choose a fill method. |
| Object context > Delete for cleaning | Convert an unlocked area object into a cleaning region while in Clean mode. | Use a drawn mask to remove an unwanted particle from the derived image. |
| Cleaning > Restore selected area / all edits | Restore pixels while retaining other valid cleaning records. | Restore a small removed area without erasing a separate filled region. |
| Cleaning > Fill from neighboring pixels | Estimate fill values from nearby available pixels. | Fill a small isolated background spot. |
| Cleaning > Fill with LaMa | Run asynchronous model-based inpainting inside the requested region. | Preview a larger removed contamination region; pixels outside it stay exact. |
| Cleaning > Background patches | Tile source pixels from a selected manual background group. | Choose a group named Clean support; its name need not be Background. |
| Cleaning > Choose / Add / Clear background group | Select manually drawn polygon/rectangle/ellipse background areas, or clear that selection. | Select several clean background patches; reject sources intersecting processed pixels. |
| Cleaning > Brush radius | Set the radius of the point cleaning brush, independently of SAM point prompts. | Use a small brush to remove a thin mark in Clean mode. |
| Show cleaning regions | Hide/show the display of cleaning objects; deleting a cleaning object restores its pixels. | Hide the removal outline to inspect a filled region. |
| Processing > Denoise | Preview restoration and open the Denoising parameters chapter. | Compare a TV weight of 0.08 against the original before Apply. |
| Processing > Smooth (Gaussian) | Select an odd kernel size and sigma. | Use kernel 5 and sigma 1 for a small spatial smoothing operation. |
| Processing > Crop selected region / masks | Retain real pixels in the mask bounding rectangle plus 3 pixels of context. | Store an irregular particle and its real surrounding background; no artificial black corners are added. |
| Processing > Retained crops / paste back | Protect/release, export, remove or paste retained crop snapshots. | Denoise the rest of the image, then paste the preserved rectangular patch back. |
| Processing > Add noise | Add reproducible Gaussian, Poisson or salt-and-pepper noise with adjustable strength/seed. | Use a fixed seed to compare two denoisers on the same synthetic noise. |
| Export > COCO dataset | Write exact masks, groups, calibration, attributes and cleaning extensions. | Export all open images with an uncleaned image and a separate processed-image copy. |
| Export > YOLO dataset | Export polygons with explicit handling of holes/disconnected masks. | Choose COCO for exact holes, or explicitly review a lossy YOLO conversion. |
| Save masks / Transparent mask images | Choose binary, overlap-weighted grayscale, color masks, labels, overlay, opacity and alpha options. | Keep binary masks for training and export a transparent colored overlay for presentation. |
| File > Save original / processed images | Save the acquired image, current processed image or both as TIFF. | Keep the acquired TIFF and save a rotated/denoised derivative separately. |
| Statistics > Plot Object Statistics | Choose an image scope and up to nine metrics. | Plot ECD and perimeter for a named image group, with points colored by mask area. |
| Statistics > Edit image calibration | Enter X/Y physical pixel size and length unit. | Use X=0.2 nm and Y=0.3 nm when pixels are anisotropic. |
| Statistics > Export plot / Export statistics | Save a visual plot or choose which numerical metrics to export. | Display three metrics and save all measurements and summary tables. |
| View > Masks / Contours / Prompts / Panels | Adjust visibility and reopen hidden docks. | Hide prompt markers while inspecting a mask, then reopen the Objects panel. |
| View > Toolbars | Toggle each top toolbar independently. | Hide Segmentation prompts while editing a mask. |
| View > Toolbar icon size | Adjust drawing-tool icon sizes. Undo/Redo retain their enlarged controls. | Use Large icons on a high-resolution display. |
| Plugin > Install / Manage | Install a local plugin folder; enable, disable, reload or remove it. | Disable a plugin that fails to load, without changing images or annotations. |
| Help > User Manual | Open the English manual for the running app version. | Jump to Denoising parameters inside the manual. |


## Shortcuts, recovery and troubleshooting

| Shortcut / control | Action |
| --- | --- |
| Ctrl+O | Open images |
| Ctrl+S | Save masks |
| Ctrl+Z / Ctrl+Y | Undo / Redo |
| Ctrl+A | Select all objects |
| Ctrl+I | Invert pixel region |
| Ctrl+D | Remove selected image area |
| Ctrl+E | Edit existing object |
| Delete | Remove the highlighted mask part with Select mask part active. Otherwise remove eligible vertices in Edit or selected objects in the other modes. |
| Esc | Cancel a mask-pusher stroke, clear a distance measurement, or cancel a filament connection, drawing, preview or running task. |
| F | Reset magnification / fit image |
| Mouse wheel / Hand / middle drag | Zoom / pan |
| Ctrl+click | Add or remove an object from a multiple selection |

If text controls are hidden, load SAM2/2.1 or an available SAM3 backend. Use Run text segmentation after entering text. For a native single-object correction choose Single object rather than whole-image exemplar retrieval. If Auto grid returns zero masks, inspect the displayed count and candidate thresholds.

On save failure choose a writable project destination before closing. On recovery failure, retain the project and its backup and confirm the source/frame/fingerprint. Keep acquired images separate from cleaned output.

Uninstall_CPU scripts remove only app-owned marked environments/build folders. Projects, images, exports and cached models are preserved. Remove an optional GPU environment explicitly with conda env remove -n sam-image-studio-gpu. Close the GUI first.

Validation reports are supplied with the release. Defined regression cases do not prove every possible image or future dependency version is defect-free. Native Windows/macOS, CUDA and real SAM3 weights require local acceptance when not exercised by the release test machine.


## Official references

https://github.com/facebookresearch/segment-anything

https://github.com/facebookresearch/sam2

https://github.com/facebookresearch/sam3

https://huggingface.co/docs/transformers/v4.53.3/en/model_doc/grounding-dino

https://scikit-image.org/docs/stable/api/skimage.restoration.html

https://pytorch.org/get-started/previous-versions/

https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html

https://github.com/cocodataset/cocoapi

SAM3.1 release and multiplex API: https://github.com/facebookresearch/sam3/blob/main/README_SAM3.1.md

CAREamics: https://careamics.github.io/

SPORCO: https://sporco.readthedocs.io/

BM3D package and licensing: https://pypi.org/project/bm3d/

## Denoising parameters

### Workflow and physical interpretation

Choose Processing > Denoise, select a method and review the controls. Each parameter has an in-dialog ? explanation. The side panel and this guide contain all exposed controls, defaults and suggested values. These are starting points for comparisons, not specimen-specific optimal settings. Defaults reload on each open or method change. Preview first; Apply creates a reversible image record. Keep the acquired source for comparison and save the native .sam.json for exact editable recovery.

Use whole image or selected region/object masks. Algorithms see the current full image as context, and final compositing changes only the target. Protected retained crop rectangles and pending removed pixels are excluded from Apply. Selecting a target does not train a neural model only inside that mask: training uses the full selected input image plane. To train only on a patch, export/open that patch first. Choose original pixels to process the uncleaned image in its current orientation.

Unsigned integers normalize to their full dtype range, signed integers to their full type range. Floating inputs already within [0,1] keep [0,1]; other finite floats normalize using observed min/max. All algorithm sigma/threshold/fidelity values refer to these normalized units. For example, sigma 0.04 means approximately 10.2 counts for uint8, or 2621.4 for uint16. If a uint16 detector only uses 0-4095, scale sigma by the full 65535 range or convert deliberately before processing; display brightness is not the processing normalization. Outputs clip to [0,1], then convert to the original type with integer rounding. RGB channels are independent spatial planes. Alpha and outside-target pixels remain exact. No automatic change to acquired image dimensions occurs.

For a first comparison, estimate noise in a plausibly uniform area, preserve a crop of fine details and try wavelet, NLM and TV. Repeated particles can benefit from patch methods. Gaussian-noise assumptions may be poor for shot noise, stripes, scan drift, correlated artifacts or dose-dependent contrast. Check particle area, edges and lattice features against original pixels; low training loss alone does not establish correctness. Synthetic tests in the validation report are algorithm checks, not universal SEM/TEM accuracy claims.

### DCT and TV: reconstruction versus denoising

Reconstruct simulates a sampling experiment from the input: one spatial mask, shared across RGB channels, retains a fraction of observed positions. Random sampling uses np.random.default_rng(seed), without replacement, with max(1, round(fraction*H*W)) positions. Grid sampling approximates the requested fraction and may have a slightly different count. Missing values initialize by nearest observed neighbor using a Euclidean distance transform, or zero. The notebook comparison uses random 10%, seed 7, nearest initialization and 40 iterations.

DCT uses scipy.fft.dctn/idctn with norm='ortho', axes=(-2,-1), over each full channel plane. It retains coefficients whose absolute value is at least the kth largest threshold, where k=max(1,round(sparsity_fraction*H*W)); ties can retain more than k. The threshold is recomputed every iteration. It is global hard thresholding, with no blocks. After inverse DCT, update observed positions and clip to [0,1].

Iterative TV uses forward horizontal/vertical differences with repeated final columns/rows (zero final forward difference). magnitude=sqrt(gx*gx+gy*gy+gradient_epsilon). Divide each gradient by magnitude, take the backward divergence and form clip(estimate+tv_step*divergence,0,1). Then apply data consistency and clip again. There is no separate lambda. tv_step is not the weight of denoise_tv_chambolle. Large explicit steps can oscillate; denoise defaults to 0.01, while the notebook reconstruction preset retains 0.08.

At sampled positions residual=observed-proposal. L2 update is residual, L1 update is delta*sign(residual), Huber update is clip(residual,-delta,delta). These reproduce the supplied notebook update rules; they are not interchangeable generic optimizer loss implementations. In reconstruction the update strength is one. Full-sampling L2 therefore returns the input and is not a denoiser. In Denoise every pixel participates but the update is multiplied by fidelity_step < 1, retaining a prior contribution. With L2 this is proposal=(1-eta)*prior+eta*observed. Denoise initializes from observed pixels and ignores sampling/initialization controls.

The Notebook reconstruction preset also sets a max-side cap of 256, without enlarging small images. The original notebook converted to RGB/float32 and divided uint8 by 255. Here native grayscale/RGB/uint16 inputs preserve their channel/dtype contract; unsigned-byte RGB has the same normalization. A cap uses area downsampling and linear interpolation back onto the original grid. This is a resolution experiment, not a claim of recovering original high-frequency detail. Leave max_side at 0 for native resolution. For full-sampling identity checks use cap 0.

### How to read each parameter entry

Default is the value restored when the dialog opens or the method changes. Range/options are accepted by the GUI and validator; a legal endpoint is not necessarily a sensible specimen setting. Suggested start provides a practical comparison range. Iteration counts are maxima for convergent library solvers and fixed counts for notebook DCT/TV. Spatial sizes are image pixels regardless of display zoom. Intensity quantities use normalized units described above. Disabled fields are retained for switching modes but ignored by that mode. Restore defaults clears custom parameter values without applying an image operation.


### TV restoration

Use as a baseline for relatively uniform particle regions. Higher weight removes more variation but can flatten gradients and introduce staircase-like appearance. scikit-image Chambolle TV is different from the explicit notebook TV loop.

#### weight

Default: 0.08. Allowed range: 0.0001 to 2.0.

Chambolle TV regularization weight on normalized intensities. Larger weights smooth more. This is not the notebook TV iteration step.

Suggested start: Start 0.03-0.12; compare particle boundaries and texture.

#### iterations

Default: 100. Allowed range: 1 to 2000.

Maximum Chambolle iterations; convergence may stop earlier.

Suggested start: 100; increase to 200 if convergence is incomplete.

#### tolerance

Default: 0.0002. Allowed range: 1e-06 to 0.1.

Relative change stopping tolerance passed as eps.

Suggested start: 0.0002; smaller values take longer.


### TV Bregman restoration

This alternate TV solver uses the inverse weight convention. Lower weight increases smoothing. Do not transfer Chambolle weight values numerically.

#### weight

Default: 5.0. Allowed range: 0.01 to 100.0.

Split-Bregman fidelity weight. Its convention is inverse to denoising strength: smaller values smooth more. It is not interchangeable with Chambolle weight.

Suggested start: Start 2-10, default 5.

#### iterations

Default: 100. Allowed range: 1 to 2000.

Maximum Split-Bregman iterations.

Suggested start: 100-200.

#### tolerance

Default: 0.001. Allowed range: 1e-06 to 0.1.

Absolute change tolerance (eps).

Suggested start: 0.001.

#### isotropic

Default: True. Options: true / false.

Use isotropic TV; false uses directional anisotropic TV.

Suggested start: True for general particle outlines.


### Wavelet sparse restoration

Small coefficients are shrunk using PyWavelets/scikit-image. Sigma estimation assumes a high-frequency noise component; fine lattice structure can inflate it. Requested levels are capped by wavelet support/image size; too-small images produce a clear error.

#### sigma

Default: 0.04. Allowed range: 0.0 to 1.0.

Gaussian noise standard deviation in normalized intensity units; ignored when estimate_sigma is enabled.

Suggested start: Estimate sigma first; otherwise try 0.01-0.08.

#### estimate_sigma

Default: False. Options: true / false.

Estimate Gaussian sigma from high-frequency wavelet coefficients.

Suggested start: Enable for a first comparison when noise level is unknown.

#### levels

Default: 2. Allowed range: 1 to 6.

Requested decomposition depth, capped by image size and wavelet support.

Suggested start: 1-3; default 2.

#### wavelet

Default: db2. Options: db2, haar, sym4, coif1.

PyWavelets wavelet family.

Suggested start: db2 or sym4; Haar is a simple edge-oriented baseline.

#### threshold_rule

Default: BayesShrink. Options: BayesShrink, VisuShrink.

Adaptive BayesShrink or universal VisuShrink threshold.

Suggested start: BayesShrink. VisuShrink often smooths more.

#### threshold_mode

Default: soft. Options: soft, hard.

Soft shrinks retained coefficients; hard only removes coefficients below threshold.

Suggested start: Soft for a conservative baseline; inspect ringing with hard.


### Non-local means

Repeated local appearance supplies averaging evidence. Stronger filtering can merge genuinely different weak structures. Search radius increases computation. Fast and reference modes can differ numerically.

#### strength

Default: 0.08. Allowed range: 0.001 to 1.0.

Filter bandwidth h in normalized intensity units. Larger values combine less-similar patches.

Suggested start: About 0.8-1.2 times a credible Gaussian sigma; compare 0.02-0.10.

#### sigma

Default: 0.03. Allowed range: 0.0 to 1.0.

Gaussian noise sigma used for patch-distance correction; zero disables this correction.

Suggested start: Use a measured/estimated value, typically 0.01-0.08.

#### patch_size

Default: 5. Allowed range: 1 to 15.

Odd square patch side in pixels.

Suggested start: 3, 5 or 7; default 5.

#### search_distance

Default: 6. Allowed range: 1 to 25.

Search radius in pixels; comparisons cover a (2r+1) square neighborhood.

Suggested start: 6-11 for repeated local structures.

#### fast_mode

Default: True. Options: true / false.

Use scikit-image fast NLM; false uses the slower reference approach.

Suggested start: True for interactive work.


### Bilateral denoise

A fast spatial/intensity baseline. The per-channel implementation preserves the RGB contract but does not perform vector-color patch matching.

#### sigma_color

Default: 0.05. Allowed range: 0.001 to 1.0.

Intensity similarity scale on normalized pixels.

Suggested start: 0.02-0.10; smaller values preserve stronger edges.

#### sigma_spatial

Default: 3.0. Allowed range: 0.1 to 20.0.

Spatial Gaussian sigma in image pixels.

Suggested start: 1-5; default 3.


### Median denoise

Useful for sparse impulse artifacts; wide windows can remove small real particles. Kernel 1 is an intentional identity setting.

#### kernel_size

Default: 3. Allowed range: 1 to 31.

Odd median window side in pixels. A kernel of 1 leaves the image unchanged.

Suggested start: 3; use 5 only after checking small-particle loss.


### DCT sparsity

Start with native resolution and compare sparsity fractions. Hard global thresholds can ring around sharp boundaries or erase weak structure. The mask in Reconstruct is generated from input pixels; this UI does not import a separate external missing-pixel mask.

#### task

Default: denoise. Options: denoise, reconstruct.

Denoise uses every input pixel with relaxed fidelity. Reconstruct simulates missing pixels using a sampling mask and hard notebook data consistency.

Suggested start: denoise for ordinary complete SEM/TEM images; reconstruct for sampling experiments.

#### iterations

Default: 40. Allowed range: 1 to 1000.

Number of prior/fidelity iterations.

Suggested start: 40 as in the notebook; compare 20-100.

#### data_loss

Default: l2. Options: l2, l1, huber.

L2 uses residual; L1 uses delta*sign(residual); Huber clips residual to +/-delta.

Suggested start: l2 initially; compare huber for occasional large residuals.

#### fidelity_step

Default: 0.2. Allowed range: 0.0 to 0.99.

Denoise-only relaxation strength. The prior proposal is pulled partway toward the noisy input, not restored exactly.

Suggested start: 0.1-0.4. Higher values retain more input noise; never 1 in denoise mode.

#### huber_delta

Default: 0.05. Allowed range: 1e-06 to 1.0.

Normalized residual update scale for L1 and Huber; ignored for L2.

Suggested start: 0.05 as in the notebook; compare 0.01-0.10.

#### sample_fraction

Default: 0.1. Allowed range: 0.001 to 1.0.

Reconstruct-only fraction of observed pixel positions. Random sampling is without replacement. At 1 with L2, reconstruction returns the input.

Suggested start: 0.10 for notebook comparison; this is not a denoising strength.

#### sampling_method

Default: random. Options: random, grid.

Reconstruct-only random positions or a regular grid; a single mask is shared by RGB channels.

Suggested start: random for the notebook preset.

#### random_seed

Default: 7. Allowed range: 0 to 2147483647.

Seed for reconstruct-mode sample positions.

Suggested start: 7 for the notebook preset.

#### initialization

Default: nearest. Options: nearest, zeros.

Reconstruct-only missing-pixel initialization. Denoise always starts from the observed image.

Suggested start: nearest, matching the notebook.

#### max_side

Default: 0. Allowed range: 0 to 4096.

Optional processing resolution cap. 0 uses the native grid. A smaller cap downsamples before processing and interpolates the result back to the original grid.

Suggested start: 0 for native-resolution SEM/TEM; 256 only for a notebook-resolution comparison.

#### sparsity_fraction

Default: 0.08. Allowed range: 0.001 to 1.0.

Retained fraction of full-image 2D DCT coefficients. The hard threshold is recalculated each iteration; threshold ties can retain additional coefficients.

Suggested start: 0.08 as in the notebook; compare 0.04-0.20. Inspect ringing and weak details.


### TV iterative (notebook)

Use Denoise for complete SEM/TEM images. Step 0.01 is a conservative starting point; step 0.08 is retained in the notebook reconstruction preset. Repeated steps do not guarantee monotonic quality improvement.

#### task

Default: denoise. Options: denoise, reconstruct.

Denoise uses every input pixel with relaxed fidelity. Reconstruct simulates missing pixels using a sampling mask and hard notebook data consistency.

Suggested start: denoise for ordinary complete SEM/TEM images; reconstruct for sampling experiments.

#### iterations

Default: 40. Allowed range: 1 to 1000.

Number of prior/fidelity iterations.

Suggested start: 40 as in the notebook; compare 20-100.

#### data_loss

Default: l2. Options: l2, l1, huber.

L2 uses residual; L1 uses delta*sign(residual); Huber clips residual to +/-delta.

Suggested start: l2 initially; compare huber for occasional large residuals.

#### fidelity_step

Default: 0.2. Allowed range: 0.0 to 0.99.

Denoise-only relaxation strength. The prior proposal is pulled partway toward the noisy input, not restored exactly.

Suggested start: 0.1-0.4. Higher values retain more input noise; never 1 in denoise mode.

#### huber_delta

Default: 0.05. Allowed range: 1e-06 to 1.0.

Normalized residual update scale for L1 and Huber; ignored for L2.

Suggested start: 0.05 as in the notebook; compare 0.01-0.10.

#### sample_fraction

Default: 0.1. Allowed range: 0.001 to 1.0.

Reconstruct-only fraction of observed pixel positions. Random sampling is without replacement. At 1 with L2, reconstruction returns the input.

Suggested start: 0.10 for notebook comparison; this is not a denoising strength.

#### sampling_method

Default: random. Options: random, grid.

Reconstruct-only random positions or a regular grid; a single mask is shared by RGB channels.

Suggested start: random for the notebook preset.

#### random_seed

Default: 7. Allowed range: 0 to 2147483647.

Seed for reconstruct-mode sample positions.

Suggested start: 7 for the notebook preset.

#### initialization

Default: nearest. Options: nearest, zeros.

Reconstruct-only missing-pixel initialization. Denoise always starts from the observed image.

Suggested start: nearest, matching the notebook.

#### max_side

Default: 0. Allowed range: 0 to 4096.

Optional processing resolution cap. 0 uses the native grid. A smaller cap downsamples before processing and interpolates the result back to the original grid.

Suggested start: 0 for native-resolution SEM/TEM; 256 only for a notebook-resolution comparison.

#### tv_step

Default: 0.01. Allowed range: 0.0001 to 0.24.

Gradient-divergence iteration step; this is not a TV regularization lambda or Chambolle weight.

Suggested start: 0.01 for denoising (compare 0.005-0.02). The reconstruction preset uses notebook step 0.08; large steps can oscillate.

#### gradient_epsilon

Default: 1e-06. Allowed range: 1e-09 to 0.01.

Positive value added inside sqrt(gx^2+gy^2+epsilon). Forward differences repeat the last row/column.

Suggested start: 0.000001 as in the notebook.


### Sparse dictionary learning

A real SPORCO BPDNDictLearn dictionary is fit to seeded patches, using mean-centered data and zero-mean atoms. Inference solves BPDN with the same lambda, restores patch means, includes border patches and averages overlaps. Dictionary update/ADMM tolerances are fixed at 1e-3. Learned dictionaries currently belong to this operation and are not reused as saved neural checkpoints.

#### patch_size

Default: 8. Allowed range: 3 to 24.

Square image patch side in pixels.

Suggested start: 6-12; default 8.

#### dictionary_atoms

Default: 64. Allowed range: 4 to 512.

Number of dictionary columns. Larger dictionaries represent more patterns and can fit noise.

Suggested start: 64-128 for 8x8 patches.

#### training_patches

Default: 2048. Allowed range: 32 to 20000.

Maximum randomly selected, mean-centered training patches.

Suggested start: 1024-4096, with at least as many patches as atoms.

#### dictionary_iterations

Default: 10. Allowed range: 1 to 100.

Alternating SPORCO dictionary-learning iterations.

Suggested start: 10-30; start with 10.

#### coding_iterations

Default: 30. Allowed range: 1 to 500.

Maximum ADMM iterations per sparse coding/update solve.

Suggested start: 30-100.

#### regularization

Default: 0.05. Allowed range: 0.0001 to 1.0.

L1 coefficient penalty lambda for 0.5*||D*X-S||^2 + lambda*||X||_1.

Suggested start: 0.02-0.10 after intensity normalization.

#### patch_stride

Default: 4. Allowed range: 1 to 24.

Inference patch spacing; it must not exceed patch_size. Edge patches are included.

Suggested start: Half the patch side; use 1 for more overlap at higher cost.

#### inference_batch

Default: 256. Allowed range: 16 to 2048.

Patches sparse-coded together. Controls working memory.

Suggested start: 128-512.

#### random_seed

Default: 7. Allowed range: 0 to 2147483647.

Seed for initial dictionary and training-patch sampling.

Suggested start: 7 for repeatable comparisons.


### BM3D

Official bm3d 4.0.3 / bm4d 4.2.5 native backend. Gaussian sigma is a standard deviation, not a variance. This backend has academic/non-commercial licensing; installing this application does not replace its upstream terms. See https://pypi.org/project/bm3d/ and the installed bm3d/bm4d licenses. Inputs smaller than 32 pixels on either axis receive reflected context to at least 32x32 before native filtering, then crop back to their original size. This avoids unsafe native block-size edge cases. Cancel becomes effective after the native filtering call returns.

#### sigma

Default: 0.04. Allowed range: 0.0001 to 0.5.

Gaussian noise standard deviation in normalized intensity units.

Suggested start: Estimate the noise; initially compare 0.01-0.08.

#### profile

Default: np. Options: np, lc.

Official bm3d normal profile or low-complexity profile.

Suggested start: np for the main comparison; lc for faster previews.

#### stage

Default: all. Options: all, hard.

Both hard-threshold/Wiener stages, or hard-threshold stage only.

Suggested start: all for final output.

#### num_threads

Default: 1. Allowed range: 1 to 32.

Native BM3D worker threads.

Suggested start: 1-4; avoid oversubscribing other processing.


### Noise2Void

CAREamics 0.3.5 blind-spot self-supervision assumes sufficiently independent noise across neighboring pixels. Correlated scan noise can be learned as signal. Train uses per-plane mean/std normalization internally, undone in prediction. The application disables batch normalization and multiprocessing workers, uses the backend Adam optimizer and default scheduler, and does not enable an experiment logger. Keep sufficient representative training data; one noisy image is a convenience, not a substitute for a dataset/held-out validation.

#### run_mode

Default: train. Options: train, predict.

Train a blind-spot model on noisy input, or load a previously saved CAREamics model.

Suggested start: train for a new image; predict only with a compatible trained model.

#### model_path

Default: (empty). Text or filesystem path.

CAREamics checkpoint path for predict mode. For RGB use a training-output directory with channel_0, channel_1 and channel_2 models.

Suggested start: Use the checkpoint/directory reported after training.

#### output_directory

Default: (empty). Text or filesystem path.

Optional directory for trained models. Empty uses the application model cache; RGB channels receive separate subdirectories.

Suggested start: Keep trained models outside source-image folders.

#### device

Default: cpu. Options: cpu, cuda, auto.

Training/inference device. CUDA is permitted only inside Conda; auto selects CUDA there when available.

Suggested start: cpu for a small trial; use a dedicated Conda GPU environment for larger runs.

#### epochs

Default: 30. Allowed range: 1 to 1000.

Maximum training epochs.

Suggested start: 30-100 after a small interface trial; inspect validation behavior.

#### steps_per_epoch

Default: 20. Allowed range: 1 to 2000.

Training batches per epoch.

Suggested start: 20-100; increasing this increases time and exposure to patches.

#### patch_size

Default: 64. Allowed range: 16 to 512.

Training patch side; must fit the image and be divisible by 2^depth.

Suggested start: 64 or 128; use 32 for a small test.

#### batch_size

Default: 8. Allowed range: 1 to 64.

Training patches per batch.

Suggested start: 4-16; reduce on limited GPU memory.

#### learning_rate

Default: 0.0003. Allowed range: 1e-06 to 0.01.

Adam learning rate.

Suggested start: 0.0001-0.001, default 0.0003.

#### masked_pixel_percentage

Default: 0.2. Allowed range: 0.01 to 10.0.

Percentage of training pixel positions masked for blind-spot loss; 0.2 means 0.2%, not 20%.

Suggested start: 0.2-1.5; default follows CAREamics 0.2.

#### roi_size

Default: 11. Allowed range: 3 to 31.

Odd neighborhood side for blind-spot pixel replacement.

Suggested start: 5-11; default 11.

#### depth

Default: 2. Allowed range: 1 to 4.

U-Net downsampling depth.

Suggested start: 2 for a first trial; 3 for larger patches/data.

#### initial_filters

Default: 16. Allowed range: 8 to 64.

Initial U-Net channel count.

Suggested start: 16-32.

#### validation_patches

Default: 8. Allowed range: 1 to 128.

Held-out validation patch count when the input is split automatically.

Suggested start: 8-32. Same-image validation is not an independent microscopy accuracy study.

#### tile_size

Default: 256. Allowed range: 32 to 2048.

Prediction tile side, padded for small images.

Suggested start: 256; larger tiles need more memory.

#### tile_overlap

Default: 32. Allowed range: 0 to 256.

Overlapping prediction context; must be smaller than half the tile side.

Suggested start: 32 for tile 256.

#### random_seed

Default: 7. Allowed range: 0 to 2147483647.

Seed for training/patch selection. Backend/device differences can still affect numerical reproducibility.

Suggested start: 7 for comparisons.


### N2V2

Uses the official CAREamics use_n2v2=True factory, including its median masking strategy and N2V2 architecture path. It is not ordinary N2V with a changed label. The same parameter interpretation/model persistence rules apply. Same-image validation patches are not an independent image-level assessment.

#### run_mode

Default: train. Options: train, predict.

Train a blind-spot model on noisy input, or load a previously saved CAREamics model.

Suggested start: train for a new image; predict only with a compatible trained model.

#### model_path

Default: (empty). Text or filesystem path.

CAREamics checkpoint path for predict mode. For RGB use a training-output directory with channel_0, channel_1 and channel_2 models.

Suggested start: Use the checkpoint/directory reported after training.

#### output_directory

Default: (empty). Text or filesystem path.

Optional directory for trained models. Empty uses the application model cache; RGB channels receive separate subdirectories.

Suggested start: Keep trained models outside source-image folders.

#### device

Default: cpu. Options: cpu, cuda, auto.

Training/inference device. CUDA is permitted only inside Conda; auto selects CUDA there when available.

Suggested start: cpu for a small trial; use a dedicated Conda GPU environment for larger runs.

#### epochs

Default: 30. Allowed range: 1 to 1000.

Maximum training epochs.

Suggested start: 30-100 after a small interface trial; inspect validation behavior.

#### steps_per_epoch

Default: 20. Allowed range: 1 to 2000.

Training batches per epoch.

Suggested start: 20-100; increasing this increases time and exposure to patches.

#### patch_size

Default: 64. Allowed range: 16 to 512.

Training patch side; must fit the image and be divisible by 2^depth.

Suggested start: 64 or 128; use 32 for a small test.

#### batch_size

Default: 8. Allowed range: 1 to 64.

Training patches per batch.

Suggested start: 4-16; reduce on limited GPU memory.

#### learning_rate

Default: 0.0003. Allowed range: 1e-06 to 0.01.

Adam learning rate.

Suggested start: 0.0001-0.001, default 0.0003.

#### masked_pixel_percentage

Default: 0.2. Allowed range: 0.01 to 10.0.

Percentage of training pixel positions masked for blind-spot loss; 0.2 means 0.2%, not 20%.

Suggested start: 0.2-1.5; default follows CAREamics 0.2.

#### roi_size

Default: 11. Allowed range: 3 to 31.

Odd neighborhood side for blind-spot pixel replacement.

Suggested start: 5-11; default 11.

#### depth

Default: 2. Allowed range: 1 to 4.

U-Net downsampling depth.

Suggested start: 2 for a first trial; 3 for larger patches/data.

#### initial_filters

Default: 16. Allowed range: 8 to 64.

Initial U-Net channel count.

Suggested start: 16-32.

#### validation_patches

Default: 8. Allowed range: 1 to 128.

Held-out validation patch count when the input is split automatically.

Suggested start: 8-32. Same-image validation is not an independent microscopy accuracy study.

#### tile_size

Default: 256. Allowed range: 32 to 2048.

Prediction tile side, padded for small images.

Suggested start: 256; larger tiles need more memory.

#### tile_overlap

Default: 32. Allowed range: 0 to 256.

Overlapping prediction context; must be smaller than half the tile side.

Suggested start: 32 for tile 256.

#### random_seed

Default: 7. Allowed range: 0 to 2147483647.

Seed for training/patch selection. Backend/device differences can still affect numerical reproducibility.

Suggested start: 7 for comparisons.


### Blind-spot training, models and resource constraints

Train fits a separate model for each grayscale/RGB plane. A chosen output folder contains channel_0 (and channel_1/channel_2 for RGB), the backend checkpoints, samstudio_model.ckpt and samstudio_model.json with method/parameters. Empty output_directory creates a unique application-data folder. A folder containing a completed model for the channel is not overwritten. Interrupted training can leave partial backend files; use a new folder when retrying. Prediction accepts a .ckpt or a saved root/channel folder; a saved manifest must match the selected method. An external checkpoint must be a compatible trusted CAREamics model, not an arbitrary U-Net .pt file. The separate plugin developer guide covers TorchScript U-Net integration.

Training patch side and prediction tile side must be divisible by 2^depth. The training patch must fit the image. At least one pixel per patch must be masked: patch_size^2 * masked_pixel_percentage/100 >= 1. With 0.2%, use at least a 32x32 patch. tile_overlap must be less than half the tile side; use even values for the backend tiler. Depth increases the receptive field and memory use; scale patch/tile sizes accordingly. In Predict mode train-only controls are disabled and the checkpoint architecture is used. Tiling values must also satisfy the loaded checkpoint architecture; native validation reports incompatible choices.

For a quick interface test, use a 64x64 image, patch 32, depth 1, filters 8, batch 2, validation patches 2, one epoch/one step, tile 32 and overlap 4. This tests train/save/load only; it does not produce validated denoising. For real comparisons start with patch 64-128, depth 2, filters 16-32, 30 epochs and 20 steps, and inspect validation/real details before increasing training. The defaults do not promise convergence. Use more representative data for scientific work and validate on held-out images or known measurements.

CPU training can be slow. device=auto chooses CUDA only when a dedicated Conda environment and CUDA are both available. Explicit cuda outside Conda or without CUDA fails clearly. A GPU choice does not install drivers. Cancellation is checked between training and prediction batches, and image changes occur only after Apply. Saved models remain when cancelling image preview or undoing image edits. The CPU release includes no pretrained N2V/N2V2 weights.

### Smoothing and synthetic noise controls

Processing > Smooth exposes Gaussian kernel_size (default 5, odd 1-101; start 3-7) and sigma (default 1.0, 0.01-30 spatial pixels; start 0.5-1.5). Processing > Add noise offers Gaussian sigma (default 0.03, 0-1; start 0.01-0.05), Poisson peak_counts (default 50, 1-1000000; start 20-200) and Salt-and-pepper amount (default 0.01, 0-1; start 0.001-0.02). Each noise method has seed (default 0, integer 0-2147483647); keep it fixed for comparisons. Poisson peak counts are a synthetic model, not microscope detector calibration. Alpha and outside-target pixels remain exact for these operations too.

### Official references and validation limits

scikit-image restoration API: https://scikit-image.org/docs/stable/api/skimage.restoration.html

SciPy DCT/IDCT API: https://docs.scipy.org/doc/scipy/reference/fft.html

PyWavelets: https://github.com/PyWavelets/pywt

SPORCO dictionary learning: https://sporco.readthedocs.io/en/latest/dictlrn/bpdndl.html

BM3D package, citations and license: https://pypi.org/project/bm3d/

CAREamics documentation and source: https://careamics.github.io/ ; https://github.com/CAREamics/careamics

The test report distinguishes CPU numerical execution, one-step blind-spot interface tests and native API contract checks. Actual NVIDIA CUDA and SAM3.1 checkpoint inference require target-hardware validation. Synthetic phantom improvement for selected settings is not a specimen-independent accuracy guarantee.
