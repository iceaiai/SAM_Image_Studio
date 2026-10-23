# Buttons, tools, and segmentation controls

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
| Options… | Configure grid density, minimum score, minimum area and maximum objects. |
| Calibration display | Inspect current pixel size/unit and its source. |
| View / infer from processed image | Choose derived pixels for display/inference when present; the acquired source is retained. |
| Live prompt preview | Schedule a background preview after eligible prompt edits. |
| Background: not selected… / Background group… | Choose the explicit manual background-patch source group for cleaning. |

## Segmentation prompts toolbar

| Control | Meaning / example |
| --- | --- |
| Text prompt / alias (SAM2+) | Type a phrase such as `black dots`, or a project alias. SAM1 hides this control. |
| Run text segmentation | Run the current text in Segment; Enter in the text field also runs it. Check Scope first. |
| Prompt aliases… | Edit case-insensitive complete-phrase mappings, for example `nanoparticle → black dots`. |
| Positive example / Negative example | Label the next area exemplar in whole-image mode; applies to rectangle, circle, ellipse, polygon. |

Left/right clicks give positive/negative point prompts in Segment. Point
polarity is determined by the click, not by the shape-polarity selector.
For detailed text/shape interaction and output scope, see the
[SAM3.1 guide](../segmentation/sam31.md).

## Drawing tools

| Tool | Use |
| --- | --- |
| Select objects | Click on a mask/geometry; Ctrl+click builds a multiple selection. |
| Hand | Drag to pan the image. |
| Reset magnification / fit image | Fit the current image to the viewport. |
| Undo / Redo | Traverse committed editing history; controls are intentionally enlarged. |
| Delete object / selected vertex | Delete the selected object or eligible edited vertex. |
| Edit object vertices | Edit existing geometry rather than draw a new object. |
| Polygon | Click vertices; close using Enter, double-click or a near-first-vertex click. |
| Rectangle / Circle / Ellipse | Draw an area used according to Mode and Scope. |
| Point / cleaning brush | Point annotation/prompt, or a brush in Clean mode. |

## Panel buttons

| Button | Use |
| --- | --- |
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

## Keyboard and mouse

| Shortcut | Action |
| --- | --- |
| Ctrl+O | Open images |
| Ctrl+S | Save masks, not the native "Save project now" command |
| Ctrl+Z / Ctrl+Y | Undo / Redo |
| Ctrl+A / Ctrl+I | Select all objects / Invert region |
| Ctrl+D | Remove selected image area |
| Ctrl+E | Edit object vertices |
| Delete / Esc | Delete eligible selection / Cancel current drawing or task |
| F | Fit image |
| Mouse wheel / Hand / middle drag | Zoom / pan |
| Ctrl+click | Add/remove an object in a multiple selection |
