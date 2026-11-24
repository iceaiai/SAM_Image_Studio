# Buttons, tools, and segmentation controls

Start at the top toolbar, then the prompt toolbar, left tools and right panels.
The [illustrated scope guide](../segmentation/scopes.md) explains the most
important Segment choices before you run a preview.

## Workflow and image controls

| Control | Meaning / example |
| --- | --- |
| Mode | Manual, Segment, Clean, or Edit; see the mode reference. |
| Load model… | Open Model manager; select family, variant, matching checkpoint and device. |
| Model status | Shows the loaded model/device; tooltip provides checkpoint information. |
| Group | Select the group receiving new annotations. |
| Scope | Whole-image examples, Single object, Inside ROI only, or Automatic grid. |
| Run preview | Generate a provisional segmentation according to the active scope/prompts. |
| Accept masks | Commit eligible current preview masks to annotations. |
| Cancel / clear | Cancel current work/drawing and discard pending preview/prompts. |
| Options… | Configure candidate controls and optional area or diameter bounds. |
| Calibration display | Inspect current pixel size/unit and its source. |
| View / infer from processed image | Choose derived pixels for display/inference when present; the acquired source is retained. |
| Forget processed image… | Confirm clearing derived pixels, processing records and retained crops. Keeps annotations/orientation; undoable. |
| Live prompt preview | Schedule a background preview after eligible prompt edits. |
| Background: not selected… / Background group… | Choose the explicit manual background-patch source group for cleaning. |

## Segmentation prompts toolbar

| Control | Meaning / example |
| --- | --- |
| Model-specific text prompt / alias | The label/placeholder follows the loaded SAM2/2.1, SAM3, SAM3.1 or ONNX family. Type `black dots` or an alias. SAM1 hides it. |
| Run text segmentation | Run the current text in Segment; Enter in the text field also runs it. Check Scope first. |
| Prompt aliases… | Edit case-insensitive complete-phrase mappings, for example `nanoparticle → black dots`. |
| Positive example / Negative example | Label the next area exemplar in whole-image mode; applies to rectangle, circle, ellipse, polygon. |

Left/right clicks give positive/negative point prompts in Segment. Point
polarity is determined by the click, not by the shape-polarity selector.
SAM3 ONNX shows text and aliases but disables native shape polarity; choose
Inside ROI only with an area tool for application output clipping.
For detailed text/shape interaction and output scope, see the
[SAM3.1 guide](../segmentation/sam31.md).

## Drawing tools

The left tools occupy two columns. Each top toolbar has a visibility toggle under
**View → Toolbars**.

| Tool | Use |
| --- | --- |
| Select objects | Click on a mask/geometry; Ctrl+click builds a multiple selection. |
| Hand | Drag to pan the image. |
| Reset magnification / fit image | Fit the current image to the viewport. |
| Measure line / Measure curve | Drag between endpoints or trace a path to measure its length in image pixels and the calibrated unit when available. |
| Undo / Redo | Traverse committed editing history; controls are intentionally enlarged. |
| Delete objects | Delete the selected annotations. Del uses this action outside Edit mode. |
| Delete vertex | In Edit mode, click near a contour to highlight up to ten eligible vertices. Delete removes the highlighted batch in one step. |
| Edit object vertices | Edit existing geometry rather than draw a new object. |
| Polygon | Click vertices. Close with Enter, double-click, or a click within the configured screen distance of the first vertex. |
| Rectangle / Circle / Ellipse | Draw an area used according to Mode and Scope. |
| Point / cleaning brush | Point annotation/prompt, or a brush in Clean mode. |
| Mask pusher | In Edit with one unlocked area mask selected, left-drag to expand or right-drag to carve. The radius is in image pixels. |

## Panel buttons

| Button | Use |
| --- | --- |
| Select all / Deselect all | Available independently in Objects, Groups and Image files. Selecting group rows does not change the active drawing Group in the toolbar. |
| Show cleaning regions | Toggle cleaning record outlines without deleting the records. |
| + Group / Rename / Color | Create/rename groups and choose their colors. |
| Remove selected images | Save and remove selected image/frame entries from this session. Source files and saved projects remain. |

## Object context menu

Right-click an object to edit properties/group, invert a region, create an
object from the region, assign colors, clean, infer, explicitly refine, fill
holes, smooth edges, or delete. **Infer inside selected object / ROI** and
**Automatic grid across unannotated image** select different inference paths.
**Refine selected object explicitly** is required for replacing one unlocked
accepted mask; ordinary previews protect accepted objects.

**Refine disconnected parts…** previews cleanup inside the selected masks. In
Edit, right-click a specific fragment on the canvas and choose **Remove this
disconnected part** to delete that piece.

## Keyboard and mouse

| Shortcut | Action |
| --- | --- |
| Ctrl+O | Open images |
| Ctrl+S | Save masks, not the native "Save project now" command |
| Ctrl+Z / Ctrl+Y | Undo / Redo |
| Ctrl+A / Ctrl+I | Select all objects / Invert region |
| Ctrl+D | Remove selected image area |
| Ctrl+E | Edit object vertices |
| Delete | Delete eligible selection |
| Esc | Cancel a mask-pusher stroke, clear a distance measurement, or cancel the current drawing or task |
| F | Fit image |
| Mouse wheel / Hand / middle drag | Zoom / pan |
| Ctrl+click | Add/remove an object in a multiple selection |
