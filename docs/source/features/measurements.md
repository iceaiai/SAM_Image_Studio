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
