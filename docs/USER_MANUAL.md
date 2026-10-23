# SAM Image Studio 1.4.2


## Start, modes and workspace

SAM Image Studio opens one or many images for annotation, segmentation, calibrated measurements and reversible image processing. Acquired pixels remain available separately from derived pixels. The top-right Objects list and the canvas select the same objects. Source filenames appear in the lower-right Image files list; stacks have child frame entries.

Manual adds shapes. Segment creates disposable model previews. Clean edits derived image pixels through retained cleaning records. Edit changes existing shapes, rotates images, assigns morphology and scales masks. Switching mode with pending shapes/prompts/previews asks Yes to add, No to discard or Cancel to remain. An incomplete polygon cannot be added.

Example: open two TIFFs, select the first in Image files, draw one Manual rectangle, then switch to Edit and select it in Objects. The Objects, Groups and Image files docks keep the v1.4 layout and can be resized.

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

The v1.4 annotation workflow and COCO export representation are retained. A matching native SAM_Annotations project restores objects, prompts, groups, calibration, exact contours, original/derived pixels, cleaning history and rotation. Native schema 5 also stores the new exemplar prompts and retained crops and reads earlier schemas 1-4.

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

SAM3 uses native image concept prompting. SAM3.1 uses the official multiplex predictor on a lossless single PNG frame, with its own sam3.1_multiplex.pt checkpoint. SAM3.1 receives all positive/negative boxes together in normalized top-left XYWH format; point exemplars first produce an instance whose box becomes a concept prompt. SAM3.1 is GPU-only and requires the separate Linux/WSL2 Conda environment and approved facebook/sam3.1 weights. Other shapes and points first identify an exemplar object, whose bounding box becomes a SAM3 concept example. SAM1/2 use the application's candidate-and-retrieval layer: propose masks, pool SAM features, compare image/shape descriptors and filter using positive/negative examples. Repeated small objects also receive template-based candidate seeds. This is a heuristic retrieval layer, not native SAM3 or a trained nanoparticle classifier.

Example: mark one bright particle positive, then mark a contamination feature negative. The preview searches for similar particles throughout the image. Add another positive particle if size or appearance varies. A clearly negative type suppresses similar candidate types; an explicitly negative object is excluded. When positive and negative appearances cannot be distinguished, inspect and correct the preview.

Single object (native SAM) keeps the ordinary point/box refinement behavior for one object. Inside ROI only predicts from an area prompt and clips its result to that region. With Point (dot) selected, Single object and Inside ROI only are hidden and disabled. A previously selected area-only scope switches to Prompt project, whole image. To use Single object or ROI only, choose an area tool. Point coordinates remain image pixels at every zoom.

Accepted, hidden and locked foreground masks are protected from accidental replacement. Use Refine selected object explicitly to replace one unlocked foreground object while keeping its identity and group. An inverted exact region can constrain allowed inference pixels; background groups and cleaning objects are not foreground training targets.


## Automatic grid and text prompts

Automatic grid, unannotated only starts when selected in Segment with a loaded model, when entering Segment with that selection, or when the model finishes loading in that state. Run preview also starts it explicitly. It ignores any text field and samples unannotated pixels with native SAM point prompts.

The status bar shows prompt counts and the number of candidate masks. After filtering, the preview reports the resulting count. Zero masks is a visible result, not a silent success; lower the minimum model score/area or increase grid density when appropriate. Larger grids cost more time, especially on CPU. Cancellation preserves accepted annotations.

Text prompting has its own Run text segmentation button, in addition to the shared Run preview control. Enter in the text field also runs it. SAM2/2.1 resolve phrases through Grounding DINO Tiny detections and segment those boxes with SAM; SAM3 and SAM3.1 have native text paths. SAM1 hides text controls.

Aliases map complete phrases and are case-insensitive. Example: nanoparticle -> big dots, powder -> big dots. Aliases can chain; cycles/duplicate conflicting names are rejected. They replace input phrases and do not train the detector. The effective phrase appears in the tooltip and accepted-mask provenance.

Text does not establish scientific detection accuracy. The verified public text integration image contains vehicles, not nanoparticles. Use the review preview and compare against the acquired image.


## Manual geometry and Edit tools

Use Manual for points and closed shapes. A polygon closes when a click is within 3 original image pixels of its first point after at least three vertices; Enter and double-click also finish it. Point annotations remain points at every zoom.

Use Edit to select an object by canvas or list and drag its existing handles. Dragging does not create extra vertices. The handle radius is 5.1 screen pixels, half the previous release's large radius. The separate deletion radius defaults to 20 image pixels and is adjustable. Repeated Delete removes nearest eligible vertices around the chosen point only in that selected object, retaining at least three per contour.

Fill holes and Smooth edges open previews. Smooth edges retains editable cubic curves rather than merely changing a jagged display. Batch changes are one undoable operation. Mask sizes and statistics update after applying changes.

Rotation offers angle presets and arbitrary angles. No padding keeps original dimensions and may crop corners. Rectangle or square padding enlarges the canvas; choose black, neighbor, LaMa or a manually selected background-group fill. Review the result before Apply. Pixels, masks, cleaning records and the physical coordinate basis rotate together. Paste/remove retained crop snapshots before rotating.

Scale masks / savepoints scales selected unlocked objects or all area objects in their groups, uniformly about each centroid. Enter a factor or use the slider. Clipping at image boundaries and overlaps can occur. Original geometry and result snapshots can be temporary in-memory list entries or local folders with exact JSON and binary masks. Temporary savepoints do not enter project files; local snapshots can be restored only when source/rotation coordinates match.


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
| particle_count | 1 for a particle annotation, 0 for a valid explicitly linked core/cavity. Point annotations are excluded. |
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
| Drawing tools | Manual point, polygon, rectangle, circle and ellipse tools add annotations. | Draw a polygon around an irregular particle; click within 3 image pixels of its first vertex to close. |
| Hand / middle-button drag / mouse wheel | Pan and zoom the displayed image. Zoom does not change pixel coordinates. | Zoom to 40x and add a point; it remains a point rather than a one-pixel ROI. |
| Reset magnification / F | Fit the complete current image to the canvas. | Reset the view after inspecting a small edge region. |
| Groups > + Group / Rename / Color | Organize objects and choose default group colors. | Create Particle, Core and Cavity groups. |
| Object lock / visibility checkboxes | Protect geometry or hide a mask without removing its annotation. | Hide an accepted particle; automatic segmentation still protects its mask. |
| Edit > Object properties / Change group | Rename or regroup selected objects using the v1.4 properties dialog. | Move one object into the Core group. |
| Edit > Brightness / contrast | Change display normalization without modifying acquired pixels. | Increase contrast for drawing an uncertain boundary. |
| Edit > Object color / transparency | Set object appearance separately from numeric labels and mask geometry. | Make one object red at 40% opacity. |
| Assign mask colors | Use default group colors or the fixed 20-color lookup table by object/group. | Use distinct colors for overlapping particles, preserving their IDs. |
| Edit > Vertices / deletion radius | Move existing vertices; Delete removes the nearest vertex within a configurable radius in the selected object only. | Use a 20-image-pixel deletion radius; neighboring objects stay unchanged. |
| Edit > Fill holes / Smooth edges | Preview exact hole filling or smooth editable cubic contours. | Smooth a jagged outline and compare the area before Apply. |
| Edit > Rotate image | Rotate pixels and annotations together; optionally enlarge to a rectangle/square and fill padding. | Rotate 30 degrees, select square padding and neighbor fill, then inspect the preview. |
| Edit > Scale masks / savepoints | Uniformly scale selected masks or a group about each object centroid. | Create original and 1.10x savepoints; restore original if objects grow too far. |
| Edit > Morphology / inner region | Assign morphology and explicit outer/core/cavity links for applicable measurements. | Link a separate core mask to its enclosing particle before measuring shell thickness. |
| Models > Model manager | Choose family, variant, compatible checkpoint and CPU or Conda CUDA device. | Download SAM2.1 Tiny for CPU; a local checkpoint must match the selected architecture. |
| Models > Segmentation options | Set candidate-grid density, minimum model score/area and maximum masks. | Increase grid density when small objects fall between sparse sample points. |
| Models > Text prompt aliases | Map complete phrases to an effective prompt, without retraining. | Map nanoparticle and powder to big dots; the resolved phrase appears in the tooltip. |
| Run preview / Accept masks / Cancel | Generate a disposable preview, commit eligible masks or cancel pending work. | Add two positive examples and one negative example; Accept only after inspection. |
| Cleaning > Remove selected image area | Retain removals as visible, reversible cleaning objects. | Remove a contamination spot, then choose a fill method. |
| Object context > Delete for cleaning | Convert an unlocked area object into a cleaning region while in Clean mode. | Use a drawn mask to remove an unwanted particle from the derived image. |
| Cleaning > Restore selected area / all edits | Restore pixels while retaining other valid cleaning records. | Restore a small removed area without erasing a separate filled region. |
| Cleaning > Fill from neighboring pixels | Estimate fill values from nearby available pixels. | Fill a small isolated background spot. |
| Cleaning > Fill with LaMa | Run asynchronous model-based inpainting inside the requested region. | Preview a larger removed contamination region; pixels outside it stay exact. |
| Cleaning > Background patches | Tile source pixels from a selected manual background group. | Choose a group named Clean support; its name need not be Background. |
| Cleaning > Choose / Add / Clear background group | Select manually drawn polygon/rectangle/ellipse background areas, or clear that selection. | Select several clean background patches; reject sources intersecting processed pixels. |
| Cleaning > Brush radius | Set the radius of the point cleaning brush, independently of SAM point prompts. | Use a small brush to remove a thin mark in Clean mode. |
| Show cleaning regions | Hide/show the display of cleaning objects; deleting a cleaning object restores its pixels. | Hide the removal outline to inspect a filled region. |
| Processing > Denoise | Preview TV, TV Bregman, sparse wavelet, non-local means, bilateral or median restoration. | Compare a TV weight of 0.08 against the original before Apply. |
| Processing > Smooth (Gaussian) | Select an odd kernel size and sigma. | Use kernel 5 and sigma 1 for a small spatial smoothing operation. |
| Processing > Crop selected region / masks | Retain real pixels in the mask bounding rectangle plus 3 pixels of context. | Store an irregular particle and its real surrounding background; no artificial black corners are added. |
| Processing > Retained crops / paste back | Protect/release, export, remove or paste retained crop snapshots. | Denoise the rest of the image, then paste the preserved rectangular patch back. |
| Processing > Add noise | Add reproducible Gaussian, Poisson or salt-and-pepper noise with adjustable strength/seed. | Use a fixed seed to compare two denoisers on the same synthetic noise. |
| Export > COCO dataset | Write exact masks, groups, calibration, attributes and cleaning extensions. | Export all open images with an uncleaned image and a separate processed-image copy. |
| Export > YOLO dataset | Export polygons with explicit handling of holes/disconnected masks. | Choose COCO for exact holes, or explicitly review a lossy YOLO conversion. |
| Save masks / Transparent mask images | Choose binary, overlap-weighted grayscale, color masks, labels, overlay, opacity and alpha options. | Keep binary masks for training and export a transparent colored overlay for presentation. |
| File > Save original / processed images | Save the acquired image, current processed image or both as TIFF. | Keep the acquired TIFF and save a rotated/denoised derivative separately. |
| Statistics > Plot Object Statistics | Choose up to nine metrics, adjust axes/colors and resize the plotted area. | Plot ECD, circularity and area together; rename X/Y axes and change bar colors. |
| Statistics > Edit image calibration | Enter X/Y physical pixel size and length unit. | Use X=0.2 nm and Y=0.3 nm when pixels are anisotropic. |
| Statistics > Export plot / Export statistics | Save a visual plot or all/a subset of numeric metrics independently. | Display three metrics but save all 32 available choices and summary tables. |
| View > Masks / Contours / Prompts / Panels | Adjust visibility and reopen hidden docks. | Hide prompt markers while inspecting a mask, then reopen the Objects panel. |
| View > Toolbar icon size | Adjust drawing-tool icon sizes. Undo/Redo retain their enlarged controls. | Use Large icons on a high-resolution display. |
| Plugin > Install / Manage | Install a local plugin folder; enable, disable, reload or remove it. | Disable a plugin that fails to load, without changing images or annotations. |
| Help > User manual (PDF) / Quick start | Open this complete English manual inside the GUI or view a short reminder. | Use the PDF fit-width and zoom controls to inspect an example. |
| Help > Diagnostics / versions | Inspect runtime versions and the current platform. | Record diagnostics when reporting a model-loading failure. |


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
| Delete | Delete selected object or an eligible selected vertex |
| Esc | Cancel drawing / prompt preview / running task |
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
