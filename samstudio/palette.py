"""Fixed, ordered lookup table. Saved RGB values never depend on a session seed."""
from __future__ import annotations

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
