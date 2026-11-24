# Calibration and statistics

## Confirm the physical scale

Microscopy readers retain supported physical metadata. If it is missing, use
**Statistics → Edit image calibration…** for X/Y sizes and a length unit.
Do not interpret a pixel area as a physical area without a valid scale.

For batch lookup, choose **Read pixel sizes from Excel…**, select the worksheet
and unit, and supply these header columns:

| converted_image_name | converted_size |
| --- | --- |
| Sample_07.png | 0.25 |

With unit nm, that row sets 0.25 nm/pixel in both directions for matching
`Sample_07.tiff`, `.dm3`, or another extension. Matching removes directories
and the last extension and ignores case, while retaining internal dots.
Conflicting sizes for one normalized name are rejected. Unmatched images keep
their existing scale.

The lookup is remembered for later opens, including after native restore.
**Forget automatic Excel lookup** removes the association and retains scales
already assigned. Changing calibration does not change masks; rotated images
rebuild the physical coordinate basis from their saved transforms.

## Add a scale bar

Choose **Edit → Add scale bar…**. Use a physical length for a calibrated image
or px for a pixel reference. Set the corner position, line width, font and
font size and check the live preview. **Apply** stores the bar in the native
project. **Edit scale bar…** and **Remove scale bar** are undoable.

## Measure a line or curve

Choose **Measure line** in the left toolbar and drag between two points.
Use **Measure curve** to trace a path and measure its length. The canvas shows
image pixels and, for calibrated images, the physical distance in the image's
current unit. The calculation uses both pixel scales, including after rotation.
Draw again to replace the result, or press **Esc** with the tool selected to clear
the temporary overlay. See the [User Manual](../user-manual.md#distance-measurements).

## Explore object and group measurements

Open **Plot Object Statistics…** and choose up to nine metrics for display.
Adjust plot size, axes, labels, intervals, and colors. Export a plot or choose
all/a subset of numerical metrics independently of the nine-metric display.

| Metric family | Examples |
| --- | --- |
| Size and shape | Area, equivalent diameter, Feret diameter, perimeter, major/minor dimensions, aspect ratio, circularity, solidity |
| Position and orientation | Centroid, major-axis orientation, border status |
| Polygon morphology | Equal-area side estimate, corner quality, edge deviation |
| Core–shell / hollow | Explicitly linked core/cavity size, thickness, center displacement and uniformity |
| Filament | Visible centerline length, estimated gap and total lengths, visible-width mean, minimum, maximum, standard deviation and variance |
| Identification and quality | Object ID, particle count, recorded model score |
| Summaries | Count, mean, median, standard deviation and distributions |

**Morphology / inner region…** assigns morphology and links a valid fully
enclosed core/cavity. A linked inner region is not counted as a second outer
particle. A missing or invalid relationship produces notes/blank values, not
invented thickness. Model confidence is not a calibrated probability;
manual objects may have no score.

Shell/wall thickness is a 2-D boundary-distance estimate, not a 3-D measurement.
The [full manual](../user-manual.md#statistics-and-metric-applicability) defines
each metric, formula, unit, and applicability rule.

## Measure filaments across gaps

Switch to **Edit** and choose **Filament → Mark group as Filament…**. The
centerline follows the visible outline through bends. To treat an occluded
filament as one measured object, select two separate visible masks in that
group, choose **Connect visible fragments…**, and click the two marked ends
facing the gap. Each free end can connect once. The result reports the visible
arc length, a straight-line estimate across linked gaps, and their sum.
Perpendicular cross-sections contribute widths only where a mask is visible.
Use [Filaments and occluded fragments](../user-manual.md#filaments-and-occluded-fragments)
for measurement details and disconnect controls.

## Share metric colors across a plot group

1. In **Image files**, Ctrl+click the files or frames to compare and choose
   **Create…** next to **Plot group**. Name the group and check its membership.
2. Choose the measurement for colors, such as projected area or perimeter.
   Set the unit and color count. The default is 20, and the scale is computed
   across the group's open frames. Choose **Edit…** to reopen these settings.
3. In **Plot Object Statistics…**, select **Plot group: name** under **Images**.
   Choose **Object points (mask colors)** for one point per measured object in
   the displayed mask color. Check up to nine metrics. The color metric can
   differ from the plotted metrics.

Reopen any closed member frames to include them in the group scale and plots.
Physical palettes use calibrated values in the chosen unit. A mask without a
value in those units keeps its base color. To color a single image independently,
use **Edit → Assign mask colors… → By measurement** with **No plot group**
selected. See the [User Manual](../user-manual.md#metric-colors-and-plot-groups).
