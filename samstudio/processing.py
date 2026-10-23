from __future__ import annotations

import math
from dataclasses import asdict
import cv2
import numpy as np
from scipy import ndimage as ndi

from .domain import Annotation, Calibration, Document, LENGTH_UNITS


def display_rgb(raw: np.ndarray, brightness=0.0, contrast=1.0) -> np.ndarray:
    """A display/inference copy. Never changes acquired pixel values."""
    a = np.abs(raw) if np.iscomplexobj(raw) else np.asarray(raw)
    if a.ndim == 3:
        a = a[..., :3]
    if a.dtype == np.uint8:
        out = a.astype(np.float32) / 255
    else:
        finite = np.isfinite(a)
        if not finite.any():
            out = np.zeros(a.shape, np.float32)
        else:
            values = a[finite]
            # Sample huge inputs for a responsive display without altering source data.
            values = values[::max(1, values.size // 500_000)]
            lo, hi = np.percentile(values, [.5, 99.5])
            if hi <= lo:
                lo, hi = float(values.min()), float(values.max())
            out = np.nan_to_num((a.astype(np.float64) - lo) / (hi - lo if hi > lo else 1), nan=0, posinf=1, neginf=0)
    out = np.clip((out - .5) * contrast + .5 + brightness, 0, 1)
    out = np.rint(out * 255).astype(np.uint8)
    if out.ndim == 2:
        out = np.repeat(out[..., None], 3, axis=2)
    return np.ascontiguousarray(out)


def shape_mask(kind: str, points, shape) -> np.ndarray:
    h, w = shape
    mask = np.zeros((h, w), bool)
    pts = np.asarray(points, dtype=np.float64)
    if not np.isfinite(pts).all():
        raise ValueError("Shape coordinates must be finite.")
    if kind == "point":
        return mask
    if kind == "polygon":
        if len(pts) < 3:
            raise ValueError("A polygon requires at least three vertices.")
        canvas = np.zeros((h, w), np.uint8)
        cv2.fillPoly(canvas, [np.rint(pts).astype(np.int32)], 1)
        return canvas.astype(bool)
    if len(pts) != 2:
        raise ValueError("Draw two corners for this shape.")
    x0, y0 = np.minimum(pts[0], pts[1])
    x1, y1 = np.maximum(pts[0], pts[1])
    if x1 - x0 < 1 or y1 - y0 < 1:
        raise ValueError("The selected shape is smaller than one pixel.")
    if kind == "rectangle":
        mask[max(0, int(math.floor(y0))):min(h, int(math.ceil(y1))),
             max(0, int(math.floor(x0))):min(w, int(math.ceil(x1)))] = True
    elif kind in ("circle", "ellipse"):
        rx, ry = (x1 - x0) / 2, (y1 - y0) / 2
        if kind == "circle":
            rx = ry = min(rx, ry)
        yy, xx = np.ogrid[:h, :w]
        mask = ((xx + .5 - (x0 + x1) / 2) / rx) ** 2 + ((yy + .5 - (y0 + y1) / 2) / ry) ** 2 <= 1
    else:
        raise ValueError(f"Unsupported shape: {kind}")
    return mask


def brush_mask(point, radius: float, shape):
    x, y = point
    yy, xx = np.ogrid[:shape[0], :shape[1]]
    return (xx + .5 - x) ** 2 + (yy + .5 - y) ** 2 <= max(1, radius) ** 2


def bounding_box(mask):
    yy, xx = np.nonzero(mask)
    if not xx.size:
        return (0, 0, 0, 0)
    return int(xx.min()), int(yy.min()), int(xx.max() - xx.min() + 1), int(yy.max() - yy.min() + 1)


def mask_contours(mask: np.ndarray, epsilon: float = 0.0):
    contours, hierarchy = cv2.findContours(mask.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    result = []
    if hierarchy is None:
        return result
    for i, contour in enumerate(contours):
        if epsilon > 0:
            contour = cv2.approxPolyDP(contour, epsilon, True)
        points = contour.reshape(-1, 2).astype(float).tolist()
        if len(points) >= 3:
            result.append({"points": points, "hole": bool(hierarchy[0, i, 3] >= 0)})
    return result


def curve_segments(points):
    """Periodic Catmull-Rom spline as cubic Bezier segments, in image pixels."""
    p = np.asarray(points, dtype=float)
    if len(p) < 3 or p.ndim != 2 or p.shape[1] != 2 or not np.isfinite(p).all():
        raise ValueError("A curve needs at least three finite control points.")
    return [(p[i], p[i] + (p[(i+1) % len(p)] - p[(i-1) % len(p)]) / 6,
             p[(i+1) % len(p)] - (p[(i+2) % len(p)] - p[i]) / 6,
             p[(i+1) % len(p)]) for i in range(len(p))]


def sample_curve(points, spacing=.5):
    sampled = []
    for a, b, c, d in curve_segments(points):
        length = np.linalg.norm(b-a) + np.linalg.norm(c-b) + np.linalg.norm(d-c)
        t = np.linspace(0, 1, max(2, int(math.ceil(length/spacing))), endpoint=False)[:, None]
        sampled.append((1-t)**3*a + 3*(1-t)**2*t*b + 3*(1-t)*t**2*c + t**3*d)
    return np.concatenate(sampled)


def raster_contours(contours, shape):
    out = np.zeros(shape, np.uint8)
    outlines = []
    for contour in contours:
        points = np.asarray(contour["points"], np.float64)
        if points.ndim != 2 or points.shape[1:] != (2,) or len(points) < 3 or not np.isfinite(points).all():
            raise ValueError("A contour needs at least three finite vertices.")
        if contour.get("curve"):
            points = sample_curve(points)
        outlines.append(np.rint(points).astype(np.int32).reshape(-1, 1, 2))
    if outlines:
        # Even-odd contour filling preserves the exact boundary of raster holes.
        # Filling hole contours with zero separately erodes another pixel ring.
        cv2.drawContours(out, outlines, -1, 1, cv2.FILLED)
    return out.astype(bool)


def smooth_contours(mask, sigma):
    """Smooth along arc length and retain actual cubic curves for editing/display."""
    result = []
    for contour in mask_contours(mask):
        p = np.asarray(contour["points"], dtype=float)
        closed = np.vstack([p, p[0]])
        distance = np.r_[0, np.cumsum(np.linalg.norm(np.diff(closed, axis=0), axis=1))]
        if distance[-1] <= 0:
            continue
        count = max(12, int(math.ceil(distance[-1])))
        along = np.linspace(0, distance[-1], count, endpoint=False)
        uniform = np.column_stack([np.interp(along, distance, closed[:, i]) for i in range(2)])
        filtered = ndi.gaussian_filter1d(uniform, max(.6, sigma)*count/distance[-1], axis=0, mode="wrap")
        step = max(1, int(round(max(2., sigma*1.5)*count/distance[-1])))
        controls = filtered[::step]
        if len(controls) < 3:
            controls = filtered[np.linspace(0, count-1, 3).astype(int)]
        result.append({"points": controls.tolist(), "hole": contour["hole"], "curve": True})
    return result


def refinement_geometry(mask, sigma, protected=None):
    contours = smooth_contours(mask, sigma)
    result = raster_contours(contours, mask.shape)
    if protected is not None:
        clipped = result & ~protected
        if not np.array_equal(clipped, result):
            # Keep the other object's exact boundary as a hard clipping edge.
            # The editable curves still describe the smooth proposed boundary.
            result = clipped
    if not result.any() or ndi.label(result)[1] != ndi.label(mask)[1]:
        raise ValueError("Smoothing would remove, split, or merge a component. Reduce the radius.")
    return result, contours


def filter_proposals(masks, protected: np.ndarray, roi=None, min_area=8, duplicate_iou=.90):
    accepted = []
    eligible = ~protected
    if roi is not None:
        eligible &= np.asarray(roi, bool)
    # Prefer smaller instances to prevent a broad mask swallowing several particles.
    for candidate in sorted(masks, key=lambda m: int(np.count_nonzero(m))):
        mask = np.asarray(candidate, bool)
        if mask.shape != eligible.shape:
            raise ValueError("The model returned a mask with incorrect image dimensions.")
        mask = mask & eligible
        if int(mask.sum()) < min_area:
            continue
        duplicate = False
        for old in accepted:
            overlap = int(np.count_nonzero(mask & old))
            if overlap and overlap / int(np.count_nonzero(mask | old)) >= duplicate_iou:
                duplicate = True
                break
        if not duplicate:
            accepted.append(mask)
    return accepted


def fill_holes(mask, max_area=None, protected=None):
    filled = ndi.binary_fill_holes(mask)
    holes = filled & ~mask
    if max_area is not None:
        labels, count = ndi.label(holes)
        sizes = np.bincount(labels.ravel())
        eligible = np.flatnonzero((sizes <= max_area) & (np.arange(len(sizes)) > 0))
        holes = np.isin(labels, eligible)
    if protected is not None:
        holes &= ~protected
    return np.asarray(mask, bool) | holes


def smooth_mask(mask, sigma: float, protected=None, preserve_holes=True):
    if not math.isfinite(sigma) or not 0 < sigma <= 50:
        raise ValueError("Smoothing radius must be greater than 0 and at most 50 pixels.")
    base = np.asarray(mask, bool)
    result = ndi.gaussian_filter(base.astype(np.float32), sigma, mode="constant") >= .5
    if preserve_holes:
        holes = ndi.binary_fill_holes(base) & ~base
        result &= ~holes
    if protected is not None:
        result &= ~protected
    if not result.any():
        raise ValueError("This smoothing strength would remove the object. Reduce the radius.")
    # Reject unintended component merging/splitting instead of silently changing topology.
    _, original_count = ndi.label(base)
    _, result_count = ndi.label(result)
    if original_count != result_count:
        raise ValueError("Smoothing would split, merge, or remove a component. Reduce the radius.")
    return result


def refine_objects(document: Document, object_ids, method: str, parameter=None):
    selected = [o for o in document.objects if o.id in object_ids]
    if not selected:
        raise ValueError("Select one or more objects.")
    if any(o.locked for o in selected):
        raise ValueError("Unlock the selected objects before modifying them.")
    if any(o.role == "cleaning" for o in selected):
        raise ValueError("Cleaning regions retain their pixel footprint. Delete a cleaning object to restore its pixels.")
    if any(o.mask is None for o in selected):
        raise ValueError("Fill Holes and Smooth Edges require area masks, not point annotations.")
    output = {}
    # Each object's old pixels remain protected from every other object's expansion.
    for obj in selected:
        protected = document.protected_mask([obj.id])
        if method == "holes":
            output[obj.id] = fill_holes(obj.mask, parameter, protected)
        elif method == "smooth":
            output[obj.id] = smooth_mask(obj.mask, float(parameter), protected)
        else:
            raise ValueError("Unknown mask-refinement method.")
    # Also resolve overlapping expansions into previously empty pixels deterministically.
    claimed = np.zeros(document.frame.shape, bool)
    for obj in selected:
        new = output[obj.id] & ~claimed
        if not new.any():
            raise ValueError("The operation would remove an object through overlap.")
        output[obj.id] = new
        claimed |= new
    return output


def neighbor_fill(raw, target):
    target = np.asarray(target, bool)
    if not target.any():
        raise ValueError("There is no removal region to fill.")
    if target.all():
        raise ValueError("Keep some background pixels for interpolation.")
    indices = ndi.distance_transform_edt(target, return_distances=False, return_indices=True)
    nearest = raw[tuple(indices)]
    # Local diffusion softens nearest-neighbor seams and works for uint16 / float data.
    working = nearest.astype(np.float64)
    for _ in range(12):
        blurred = ndi.gaussian_filter(working, sigma=1 if raw.ndim == 2 else (1, 1, 0))
        working[target] = blurred[target]
        working[~target] = raw[~target]
    return cast_like(working, raw.dtype)


def cast_like(array, dtype):
    dtype = np.dtype(dtype)
    if np.issubdtype(dtype, np.integer):
        lim = np.iinfo(dtype)
        array = np.clip(np.rint(array), lim.min, lim.max)
    return np.asarray(array, dtype=dtype)


def smooth_image(raw, method="gaussian", sigma=1.0, size=3, target=None):
    """Filter spatial pixels only. Keep dtype, alpha, nonfinite pixels and the source."""
    raw = np.asarray(raw)
    if np.iscomplexobj(raw):
        raise ValueError("Image smoothing requires real-valued pixels.")
    if method not in ("gaussian", "median"):
        raise ValueError("Choose Gaussian or median image smoothing.")
    if not math.isfinite(sigma) or not .1 <= sigma <= 20:
        raise ValueError("Gaussian sigma must be between 0.1 and 20 image pixels.")
    if type(size) is not int or not 3 <= size <= 31 or size % 2 == 0:
        raise ValueError("Median size must be an odd number between 3 and 31 pixels.")
    target = np.ones(raw.shape[:2], bool) if target is None else np.asarray(target, bool)
    if target.shape != raw.shape[:2] or not target.any():
        raise ValueError("Choose a nonempty image region to smooth.")
    output = raw.copy()
    channels = [None] if raw.ndim == 2 else range(min(3, raw.shape[-1]))
    for channel in channels:
        source = raw if channel is None else raw[..., channel]
        dest = output if channel is None else output[..., channel]
        values = source.astype(np.float64)
        finite = np.isfinite(values)
        if not finite.any():
            continue
        if method == "gaussian":
            if finite.all():
                filtered = ndi.gaussian_filter(values, sigma, mode="reflect")
            else:
                numerator = ndi.gaussian_filter(np.where(finite, values, 0), sigma, mode="reflect")
                weights = ndi.gaussian_filter(finite.astype(float), sigma, mode="reflect")
                filtered = np.divide(numerator, weights, out=values.copy(), where=weights > 0)
        else:
            if not finite.all():
                nearest = ndi.distance_transform_edt(~finite, return_distances=False, return_indices=True)
                values = values[tuple(nearest)]
            filtered = ndi.median_filter(values, size=size, mode="reflect")
        selected = target & finite
        dest[selected] = cast_like(filtered[selected], raw.dtype)
    return output


def patch_fill(raw, target, patches, soften=True):
    if not target.any():
        raise ValueError("There is no removal region to fill.")
    if not patches:
        raise ValueError("Select at least one background patch first.")
    source_patches = []
    h, w = target.shape
    for selection in patches:
        if isinstance(selection, np.ndarray):
            region = np.asarray(selection, bool)
            if region.shape != target.shape or not region.any():
                raise ValueError("A background region is empty or has the wrong dimensions.")
            if (region & target).any():
                raise ValueError("A background region overlaps the removal region.")
            x0,y0,bw,bh = bounding_box(region)
            selected = region[y0:y0+bh,x0:x0+bw]
            pixels = raw[y0:y0+bh,x0:x0+bw].copy()
            if not selected.all():
                # Fill the crop only from selected pixels, never from outside
                # a polygon or ellipse in the chosen group.
                nearest = ndi.distance_transform_edt(~selected, return_distances=False, return_indices=True)
                pixels[~selected] = pixels[tuple(nearest[:,~selected])]
            source_patches.append(pixels)
            continue
        x0, y0, x1, y1 = selection
        x0, x1 = sorted([max(0, min(w, int(x0))), max(0, min(w, int(x1)))])
        y0, y1 = sorted([max(0, min(h, int(y0))), max(0, min(h, int(y1)))])
        if x1 <= x0 or y1 <= y0:
            raise ValueError("A selected background patch is empty.")
        if target[y0:y1, x0:x1].any():
            raise ValueError("A background patch overlaps the removal region.")
        source_patches.append(raw[y0:y1, x0:x1])
    x, y, bw, bh = bounding_box(target)
    montage = np.empty((bh, bw) + raw.shape[2:], raw.dtype)
    cy = 0
    sequence = 0
    while cy < bh:
        row_height = min(p.shape[0] for p in source_patches)
        cx = 0
        while cx < bw:
            patch = source_patches[sequence % len(source_patches)]
            hh, ww = min(row_height, bh - cy), min(patch.shape[1], bw - cx)
            montage[cy:cy+hh, cx:cx+ww] = patch[:hh, :ww]
            cx += ww
            sequence += 1
        cy += min(row_height, bh - cy)
    if soften:
        montage = cast_like(ndi.gaussian_filter(montage.astype(np.float64), 1 if raw.ndim == 2 else (1, 1, 0)), raw.dtype)
    out = raw.copy()
    local = target[y:y+bh, x:x+bw]
    view = out[y:y+bh, x:x+bw]
    view[local] = montage[local]
    return out


def measurements(document: Document, object_ids=None, group_names=None, metric="area", unit=None):
    results, excluded = [], 0
    cal = document.calibration
    for obj in document.foreground_objects():
        group = document.get_group(obj.group_id).name
        if object_ids is not None and obj.id not in object_ids:
            continue
        if group_names and group not in group_names:
            continue
        if obj.mask is None:
            excluded += 1
            continue
        area = obj.pixel_area
        physical = cal.area(area, unit)
        pixel_value = float(area) if metric == "area" else math.sqrt(4 * area / math.pi)
        physical_value = physical if metric == "area" or physical is None else math.sqrt(4 * physical / math.pi)
        chosen_unit = unit or cal.length_unit
        results.append({"object_id": obj.id, "name": obj.name, "group": group,
                        "image": document.frame.source_path, "dataset": document.frame.dataset,
                        "frame": document.frame.frame_index, "pixel_area": area,
                        "physical_area": physical, "area_unit": chosen_unit + "²" if physical is not None else None,
                        "metric": metric, "pixel_value": pixel_value,
                        "physical_value": physical_value,
                        "physical_unit": chosen_unit + ("²" if metric == "area" else "") if physical is not None else None,
                        "calibrated": cal.valid})
    return results, excluded

