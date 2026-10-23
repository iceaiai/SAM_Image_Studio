# Manual annotation and editing

## Open images and create a group

Use **File → Open images…** for one or several images, or **Open folder…**.
Select an image/frame in **Image files**. Create a group with **+ Group** and
select it in the top **Group** control. Groups organize labels and colors;
background groups are chosen explicitly for cleaning.

## Draw an object

Choose **Manual**, then Polygon, Rectangle, Circle, Ellipse, or Point. Area tools
produce filled annotations; points remain point annotations. A polygon finishes
with Enter, double-click, or a click near its first vertex after at least three
vertices. Completed Manual shapes are committed to the active group.

Select on the canvas or in **Objects**. Ctrl+click supports multiple selection.
**Select all objects** and **Invert region** let you work with the complement of
selected area masks. Use **Create object from region** in Manual/Edit to turn
that exact region into a new annotation. Points have no filled area to invert.

## Edit geometry and appearance

Switch to **Edit**, select an object, and use **Edit object vertices** to drag
existing handles. Delete removes an eligible selected vertex or an object,
depending on the editing state. **Vertex deletion radius…** controls the search
radius in image pixels. Locked objects are protected.

Use **Fill holes…** or **Smooth edges…** for a reviewed mask/contour change.
**Smooth edges** edits annotation boundaries; **Smooth image pixels…** modifies
derived image intensities. They solve different tasks.

**Object properties…**, **Change selected objects' group…**, **Object color…**,
and **Object transparency…** control metadata and display. **Assign mask colors…**
supports default group/object colors or a 20-color lookup table. Colors and
transparency are display choices, not changes to binary mask ownership.

## Rotate an image

Use **Edit → Rotate image…** for angle presets or a custom angle. Choose no
padding, rectangle padding, or square padding. Padding can use black,
neighboring pixels, LaMa, or selected background patches. Preview before Apply.
Pixels, masks, and physical coordinates rotate together; no-padding can crop
corners. Paste/remove retained crop snapshots before rotating.

## Scale masks and savepoints

Use **Edit → Scale masks / savepoints…** for selected objects or all area objects
in one selected group. Enter a factor or use the slider. Masks scale uniformly
about their centroids; clipping and overlap can occur.

The dialog preserves an original snapshot and can name a result snapshot.
**Temporary (memory only)** savepoints are listed for the session and are not
stored in project files. **Local folder** snapshots persist to disk. Use
**Restore selected** or **Restore local snapshot…** with matching image/rotation
coordinates. **Apply scale** commits the reviewed result.

Example: compare factors 0.95 and 1.05 to study how boundary placement changes
particle area. Keep the original snapshot and report the applied factor.

Mode changes with pending input offer Yes to add, No to discard, or Cancel to
remain. See [modes](../documentation/modes.md) and the
[complete user manual](../user-manual.md).
