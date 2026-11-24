"""Preset mask colors and shared measurement palettes."""
from __future__ import annotations

from dataclasses import dataclass
import math

LUT20 = (
    ("Blue", "#1f77b4"), ("Light blue", "#aec7e8"),
    ("Orange", "#ff7f0e"), ("Peach", "#ffbb78"),
    ("Green", "#2ca02c"), ("Light green", "#98df8a"),
    ("Red", "#d62728"), ("Rose", "#ff9896"),
    ("Purple", "#9467bd"), ("Lavender", "#c5b0d5"),
    ("Brown", "#8c564b"), ("Tan", "#c49c94"),
    ("Pink", "#e377c2"), ("Light pink", "#f7b6d2"),
    ("Gray", "#7f7f7f"), ("Silver", "#c7c7c7"),
    ("Olive", "#bcbd22"), ("Light olive", "#dbdb8d"),
    ("Cyan", "#17becf"), ("Light cyan", "#9edae5"),
)


def validate_scheme(value):
    if not isinstance(value, dict):
        raise ValueError("Invalid mask color scheme.")
    result = {"mode": value.get("mode", "default"), "by": value.get("by", "object"),
              "offset": value.get("offset", 0)}
    if (result["mode"] not in ("default", "lut20") or result["by"] not in ("object", "group")
            or type(result["offset"]) is not int or not 0 <= result["offset"] < 20):
        raise ValueError("Invalid mask color scheme.")
    return result


def lookup_color(index, offset=0):
    return LUT20[(int(index) + offset) % len(LUT20)][1]


def assign_colors(document, scheme, object_ids=None, use_for_new=True):
    """Assign exact preset colors, or restore the document's group colors."""
    scheme = validate_scheme(scheme)
    selected = [o for o in document.objects if object_ids is None or o.id in set(object_ids)]
    groups = {o.group_id for o in selected}
    affected = [o for o in document.objects if o.group_id in groups] if scheme["by"] == "group" else selected
    affected_ids = {o.id for o in affected}
    if any(o.locked for o in affected):
        raise ValueError("Unlock affected objects before assigning their colors.")
    if scheme["mode"] == "lut20" and scheme["by"] == "group":
        for index, group in enumerate(document.groups):
            if group.id in groups:
                group.color = lookup_color(index, scheme["offset"])
    for index, obj in enumerate(document.objects):
        if obj.id not in affected_ids:
            continue
        obj.color = (lookup_color(index, scheme["offset"])
                     if scheme["mode"] == "lut20" and scheme["by"] == "object"
                     else document.get_group(obj.group_id).color)
    if use_for_new:
        document.color_scheme = scheme


@dataclass(frozen=True)
class MetricColorScheme:
    metric: str = "area"
    count: int = 20
    unit: str = "px"

    def __post_init__(self):
        from .domain import LENGTH_UNITS
        from .statistics import METRICS

        if self.metric not in METRICS or self.metric == "object_id":
            raise ValueError("Choose a numeric measurement for mask colors.")
        if type(self.count) is not int or not 2 <= self.count <= 256:
            raise ValueError("Choose between 2 and 256 colors.")
        if self.unit not in ("px", *LENGTH_UNITS):
            raise ValueError("Choose a supported unit for mask colors.")


@dataclass
class MetricPalette:
    colors: dict[str, dict[str, str]]
    description: str


def metric_palette(documents, scheme):
    """Use one equal-width color scale across the supplied frames."""
    from matplotlib import colormaps
    from matplotlib.colors import to_hex
    from .statistics import METRICS, measurement_records

    label, dimension = METRICS[scheme.metric]
    physical = scheme.unit != "px"
    suffix = "_physical" if physical else "_px"
    column = scheme.metric + suffix
    samples = []
    for document in documents:
        rows, _ = measurement_records(document, unit=scheme.unit if physical else None)
        for row in rows:
            value = row[column]
            if value is not None and math.isfinite(value):
                ids = row["fragment_ids"] or (row["object_id"],)
                samples.append((document.frame.key, ids, value))

    if not samples:
        return MetricPalette({}, f"{label} · no values in the selected units")
    low = min(sample[2] for sample in samples)
    high = max(sample[2] for sample in samples)
    colors = [to_hex(colormaps["plasma"](index / (scheme.count - 1))) for index in range(scheme.count)]
    by_frame = {}
    for key, ids, value in samples:
        index = min(scheme.count - 1, int((value - low) / (high - low) * scheme.count)) if high > low else scheme.count // 2
        by_frame.setdefault(key, {}).update(dict.fromkeys(ids, colors[index]))

    unit = "°" if dimension == -1 else "" if dimension == 0 else scheme.unit + ("²" if dimension == 2 else "")
    return MetricPalette(by_frame, f"{label} · {low:.4g}–{high:.4g} {unit} · {scheme.count} colors".strip())


def base_mask_colors(document):
    """A linked filament has one color, initialized from its first fragment."""
    from .filaments import filament_chains

    colors = {obj.id: obj.color for obj in document.objects}
    if document.filament_links:
        for members, links in filament_chains(document.foreground_objects(), document.filament_links):
            if links:
                colors.update(dict.fromkeys((obj.id for obj in members), members[0].color))
    return colors


def image_metric_palette(document):
    if document.metric_color_scheme is None:
        return None
    key = (document.revision, document.metric_color_scheme)
    previous, palette = getattr(document, "_metric_palette_cache", (None, None))
    if previous != key:
        palette = metric_palette([document], document.metric_color_scheme)
        document._metric_palette_cache = (key, palette)
    return palette


def document_mask_colors(document):
    colors = base_mask_colors(document)
    palette = image_metric_palette(document)
    if palette is not None:
        colors.update(palette.colors.get(document.frame.key, {}))
    return colors
