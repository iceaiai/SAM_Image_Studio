# Data cleaning: remove, fill and restore

Use cleaning to remove contamination or unwanted regions from **derived pixels**.
The acquired image is retained. Native projects store cleaning records so you
can undo, restore a region, or remove one record later. Cleaning changes image
intensities; deleting an ordinary annotation only removes geometry.

```{image} ../_static/workflows/cleaning-comparison.png
:alt: Synthetic contaminant and cleaning target, followed by actual neighbor-fill and background-patch-fill results
:width: 100%
```

*Computed with the application's real neighbor/patch algorithms on synthetic
data. The same intensity scale is used in every panel. These are illustrative
fills, not recovered observations of an unknown specimen.*

## 1. File and Group: prepare the image

Open the image through **File → Open images…**. Keep a writable native project
folder. Inspect the original image before editing and keep original/processed
exports distinct. If accepted masks already identify the unwanted material,
you can select those area objects instead of redrawing the target.

For patch filling, create a group containing only manually marked **clean
background** regions. Choose several patches with appropriate texture, avoiding
particles, gradients or damaged pixels that should not be copied.

## 2. Mode and drawing tools: define what to remove

Choose **Mode → Clean**. Rectangle is initially selected; Polygon, Circle and
Ellipse also define area targets. **Point / cleaning brush** becomes a brush
in this mode. Set its radius through **Cleaning → Cleaning brush radius…**;
this is unrelated to SAM's point prompt size.

For a complement target, select area objects then choose **Edit → Invert region**.
The resulting exact region includes all pixels outside the selected masks.
Inspect it carefully before removing a large area.

## 3. Cleaning menu: remove the selected area

Choose **Cleaning → Remove selected image area** (Ctrl+D). The operation creates
a reversible removal record. Alternatively right-click an unlocked foreground
area object in Clean mode and choose **Delete for cleaning**; this removes its
pixels and records the operation, rather than merely deleting an annotation.

Inspect the target outline before filling. A temporary removed region is not
an acceptable final scientific measurement or evidence of what was originally
there. Retained/protected crops remain excluded from processing operations.

## 4. Cleaning menu: choose a fill

| Entry | Use it for | What to inspect |
| --- | --- | --- |
| Fill from neighboring pixels | Small isolated defects with nearby usable pixels | Diffusion seams, gradients and copied neighboring structure |
| Fill with background patches | Texture matched to manually selected real support/background | Patch repetition, texture mismatch, artificial specimen features |
| Fill with LaMa… | A separately loaded learned-inpainting model | Invented structure; model compatibility and provenance |

Neighbor filling uses nearest available pixels followed by local diffusion.
It requires some unremoved content. Patch filling copies actual source pixels;
it does not infer the material behind contamination. LaMa needs its own compatible
checkpoint; no LaMa weights are bundled.

**Fill with LaMa…** first opens adjustable application controls. All defaults
are zero, preserving full-image/native-resolution replacement:

| Parameter | Default / range | Purpose and first comparison |
| --- | --- | --- |
| Mask dilation | 0 / 0–64 px | Expand the mask supplied to the network; compare 1–4 for contaminated edges. Final output still changes only the original removal region. |
| Context margin | 0 / 0–2,048 px | 0 uses the full image. Compare 32–256 to process local context around the target. |
| Max side | 0 / 0–8,192 px | 0 keeps native resolution; compare 1,024 to reduce model input memory. A reduced result is interpolated back. |
| Blend width | 0 / 0–128 px | Blend inside the original boundary; compare 1–4 for seams. Original contamination may remain in this band. |

```{image} ../_static/workflows/v144-lama-dialog.png
:alt: Actual LaMa mask dilation, context, resolution and blend parameter dialog
:width: 100%
```

These control mask/context preparation and compositing; LaMa's fixed inference
graph has no invented training/iteration controls. Each **?** explains the option.
Click **Preview** to compute and inspect the fill before committing it.

All three fill methods compute in the background and open **Cleaning fill
preview**. Inspect the generated pixels, then choose **Apply** or **Cancel**.
Only Apply commits the fill. Removing an area is itself a reversible committed
record, so canceling a fill keeps the preceding removal; use Undo or Restore
to recover it. Processing's Denoise dialog uses its own Preview → Apply flow.

## 5. Background group: configure real patch sources

1. In Manual mode, draw clean background areas and put them in one Group.
2. Choose **Cleaning → Choose background group…**. Any group name is allowed;
   the source association is explicit, not inferred from the word "Background".
3. **Add selection to background group…** adds eligible manual area annotations.
4. Return to Clean, remove a target, then choose **Fill with background patches**.
5. Use **Clear background group selection** if those sources are no longer valid.

For ellipse/polygon patches, only pixels inside the true mask are sources; the
app does not borrow arbitrary pixels outside their boundary. Patches intersecting
already modified pixels are rejected. A patch source must not overlap the target.

## 6. Objects and restoration: inspect the editing history

Cleaning records appear in **Objects**. **Show cleaning regions** toggles their
outlines without deleting edits. The **View / infer from processed image**
checkbox chooses derived pixels when present; turning it off compares the
retained acquired source. It starts **off** for newly opened/reopened images;
each image remembers its own session choice. Toggling does not erase processing.
An explicit processing Apply may select the processed view to show its result.
**Forget processed image…** separately clears cleaning/processing records and
retained crops after confirmation, while keeping annotations/current orientation;
Undo recovers the previous state. Display brightness/contrast is separate from pixel edits.

- **Cleaning → Restore selected area / all edits** restores the requested pixels.
- Deleting a cleaning record restores its footprint and replays retained edits.
- **Undo / Redo** traverses committed history.

If a later denoising record exists, removing one cleaning record does not mean
all subsequent processing is discarded. Check the complete history and processed
view before exporting.

## 7. Save reproducible results

Use **File → Save project now** for full editable `.sam.json` recovery. Use
**Save original / processed images…** for TIFF pixel output and keep both
versions when scientific interpretation depends on the acquired data.
A flat TIFF does not preserve the reversible edit history. See
[saving](saving.md) and the [Cleaning menu reference](../documentation/menus.md#cleaning).
