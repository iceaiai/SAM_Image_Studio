# Reversible cleaning

Cleaning modifies derived pixels while retaining the acquired image. A removal
or fill is stored as an edit record, visible in **Objects**, so it can be
restored later.

## Remove and fill a region

1. Choose **Clean** and draw an area or use the point cleaning brush.
2. Choose **Remove selected image area**, or right-click an eligible unlocked
   area object and choose **Delete for cleaning**.
3. Select a fill method and inspect its preview.
4. Apply the result or cancel it.

| Fill | What it uses | Example |
| --- | --- | --- |
| Fill from neighboring pixels | Available image content near the target | A small isolated background defect |
| Fill with LaMa… | Separately loaded model-based inpainting | A larger contamination region requiring a reviewed fill |
| Fill with background patches | Real pixels from manually marked background areas | Copy the appearance of clean support material |

## Background patch sources

Create area annotations over clean background, place them in one group, then
use **Choose background group…**. Its name can be anything; it need not be
"Background". **Add selection to background group…** adds eligible manual areas.
Polygon/ellipse sources use only real pixels inside their masks. Sources
intersecting already modified pixels are rejected.

**Clear background group selection** removes the source association.
**Cleaning brush radius…** changes brush size independently of SAM point prompts.

## Restore pixels

**Restore selected area / all edits** restores the requested region. Deleting a
cleaning object restores its footprint while replaying other retained edits.
**Show cleaning regions** toggles their display without removing the records.
**Undo/Redo** also participates in normal image history.

Example: fill a contamination spot from clean support patches, inspect the
derived image, then delete that cleaning record if the fill is unsuitable.
A separate denoising record remains part of the edit history.

Store native projects for complete reversible recovery. A flat exported TIFF
contains pixels but not the editing history. See [saving](saving.md).
