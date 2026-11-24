# Workspace and panels

| Area | Purpose and use |
| --- | --- |
| Central canvas | Display the current image, masks/contours, draft shapes, prompts, previews, and selections. Mouse wheel zooms; Hand or middle drag pans; F fits the image. |
| Objects, upper right | Select one/many annotations; canvas/list selections stay synchronized. Columns show Object, Group, Area, Lock. Visibility/lock controls govern display and editing eligibility. Double-click enters object editing. |
| Groups, right | Show group labels, mask counts and the Filament designation. **+ Group** creates a label, **Rename** changes it, **Color** changes its base color. Double-click selects its objects. |
| Image files, lower right | Choose source images, datasets, or stack frames. Multi-select to create a **Plot group** or remove session entries while retaining saved annotations and sources. |
| Workflow toolbar | Choose Mode, model, active Group, and Scope; run, accept, cancel, or configure inference. |
| Segmentation prompts toolbar | Type/run text, manage aliases, and choose positive/negative shape polarity. |
| Drawing tools, left | Two columns for selection, pan, measurements, history, deletion, mask pushing, and drawing shapes including Point and Ellipse. |
| Region tools | Select all, invert, create an object from a region, and reach appearance/transformation tools. |
| Status bar | Shows progress, filtered-mask counts, errors, save state, and zoom. Model loading and processing run as background jobs. |

Each of **Objects**, **Groups** and **Image files** has **Select all** and
**Deselect all**. Group row selection is separate from the active toolbar Group;
use that dropdown to choose where new objects are stored. The status bar retains
a preview mask count; its tooltip explains applicable proposal/filter diagnostics.

Docks can be resized or hidden. Reopen **Objects**, **Groups**, or **Image files**
through **View**. This release retains the v1.4 Objects/Groups/Image files layout.
Use **View → Toolbars** to toggle each bar above the image. The app restores those
choices when reopened.

```{image} ../_static/studio-demo.png
:alt: Workspace showing two left tool columns, synthetic reference masks, and the Objects, Groups and Image files panels on the right
:class: studio-screen
:width: 100%
```

The screenshot shows panels and calibration for the bundled synthetic image with
reference masks.

At startup, **Reopen previous images?** offers Yes or No. No opens an empty
workspace without deleting saved projects. Removing an image saves it first;
a failed save blocks removal so the user can select a writable destination.
