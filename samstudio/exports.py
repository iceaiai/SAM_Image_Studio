from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .domain import Document, atomic_write, pack_array
from .processing import bounding_box, display_rgb, mask_contours


def coco_rle(mask):
    """Portable, uncompressed COCO RLE in column-major order."""
    flat = np.asarray(mask, np.uint8).ravel(order="F")
    if not flat.size:
        raise ValueError("A COCO mask cannot have zero dimensions.")
    changes = np.flatnonzero(np.diff(flat)) + 1
    counts = np.diff(np.r_[0, changes, flat.size]).astype(int).tolist()
    if flat[0]:
        counts.insert(0, 0)
    return {"size": list(mask.shape), "counts": counts}


def decode_coco_rle(value):
    counts = value["counts"]
    if not isinstance(counts, list) or any(not isinstance(n, int) or n < 0 for n in counts):
        raise ValueError("Expected uncompressed COCO RLE.")
    h, w = value["size"]
    if sum(counts) != h * w:
        raise ValueError("COCO RLE length does not match its dimensions.")
    return np.repeat(np.arange(len(counts)) % 2, counts).reshape((h, w), order="F").astype(bool)


def hex_rgb(color):
    value = color.lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", value):
        raise ValueError("Invalid RGB color.")
    return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))


def safe_name(name):
    name = re.sub(r"[^\w.\-]+", "_", name, flags=re.UNICODE).strip("._")
    return name[:90] or "image"


def image_name(document):
    frame = document.frame
    return f"{safe_name(Path(frame.source_path).stem)}_{safe_name(frame.dataset)}_{frame.frame_index+1:04d}_{frame.key[:8]}.png"


def _validate_image_options(documents, include_images, image_source, include_alternate):
    if image_source not in ("original", "cleaned"):
        raise ValueError("Choose original or processed dataset images.")
    if include_alternate and not include_images:
        raise ValueError("Choose a primary dataset image before including an alternate version.")
    if include_images and (image_source == "cleaned" or include_alternate):
        if any(doc.working is None for doc in documents):
            raise ValueError("Apply cleaning or smoothing to every selected image before exporting its processed version.")


def _write_dataset_images(doc, directory, include_images, image_source, include_alternate):
    filename = image_name(doc)
    versions = {}
    if include_images:
        folder = directory / "images";folder.mkdir(exist_ok=True)
        source = doc.frame.raw if image_source == "original" else doc.working
        Image.fromarray(display_rgb(source)).save(folder / filename)
        versions[image_source] = "images/" + filename
        if include_alternate:
            alternate = "original" if image_source == "cleaned" else "cleaned"
            folder = directory / (alternate + "_images");folder.mkdir(exist_ok=True)
            source = doc.frame.raw if alternate == "original" else doc.working
            Image.fromarray(display_rgb(source)).save(folder / filename)
            versions[alternate] = folder.name + "/" + filename
    return versions


def export_coco(documents: list[Document], directory: Path, include_images=True,
                image_source="original", include_alternate=False):
    _validate_image_options(documents, include_images, image_source, include_alternate)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    groups = sorted({g.name for d in documents for g in d.groups})
    categories = {name: i + 1 for i, name in enumerate(groups)}
    result = {"info": {"description": "SAM Image Studio annotations", "version": "1.0",
                       "microscopy_extension": "samstudio.microscopy.v1",
                       "standard_area_units": "pixel^2"},
              "images": [], "annotations": [], "cleaning_annotations": [], "background_annotations": [],
              "categories": [{"id": i, "name": name, "supercategory": "object"} for name, i in categories.items()]}
    skipped = 0
    for image_id, doc in enumerate(documents, 1):
        frame = doc.frame
        filename = image_name(doc)
        versions = _write_dataset_images(doc, directory, include_images, image_source, include_alternate)
        result["images"].append({"id": image_id, "file_name": "images/" + filename,
                                 "width": frame.shape[1], "height": frame.shape[0],
                                 "source_file": Path(frame.source_path).name,
                                 "source_dataset": frame.dataset, "source_frame_index": frame.frame_index,
                                 "microscopy_calibration": asdict(doc.calibration),
                                 "samstudio_rotation": doc.rotation, "source_shape": list(doc.source_raw.shape[:2]), "text_prompt_aliases": doc.text_aliases,
                                 "exported_image_source": image_source if include_images else None,
                                 "image_versions": versions, "color_scheme": doc.color_scheme})
        result["images"][-1]["samstudio_cleaning"] = {
            "schema": "samstudio.cleaning.v1", "background_group_id": doc.background_group_id,
            "groups": [asdict(g) for g in doc.groups],
            "restoration": "replay remaining cleaning objects over original acquired pixels",
            "history": doc.cleaning_history,
            "source_pixels": pack_array(frame.raw) if doc.cleaning_history or any(o.role == "cleaning" for o in doc.objects) else None,
            "source_fingerprint": frame.fingerprint}
        for obj in doc.objects:
            if obj.mask is None:
                skipped += 1
                continue
            area = obj.pixel_area
            physical = doc.calibration.area(area)
            collection = "cleaning_annotations" if obj.role == "cleaning" else "background_annotations" if obj.group_id == doc.background_group_id else "annotations"
            result[collection].append({"id": sum(len(result[k]) for k in ("annotations", "cleaning_annotations", "background_annotations")) + 1,
                                          "image_id": image_id, "category_id": categories[doc.get_group(obj.group_id).name],
                                          "segmentation": coco_rle(obj.mask), "area": area,
                                          "bbox": list(bounding_box(obj.mask)), "iscrowd": 0,
                                          "samstudio_id": obj.id, "name": obj.name, "group_id": obj.group_id,
                                          "physical_measurements": {"area": physical,
                                              "area_unit": doc.calibration.length_unit + "^2" if physical is not None else None},
                                          "editable_shape": {"kind": obj.kind, "points": obj.points, "contours": obj.contours},
                                          "provenance": obj.provenance, "role": obj.role,
                                          "color": obj.color, "opacity": obj.opacity,
                                          "visible": obj.visible, "cleaning": obj.cleaning,
                                          "exclude_from_training": collection != "annotations"})
    target = directory / "annotations.coco.json"
    atomic_write(target, json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False).encode("utf-8"))
    return {"path": str(target), "objects": len(result["annotations"]), "cleaning_objects": len(result["cleaning_annotations"]), "skipped_points": skipped}


def export_yolo(documents, directory: Path, allow_lossy=False, include_images=True,
                image_source="original", include_alternate=False):
    _validate_image_options(documents, include_images, image_source, include_alternate)
    # Validate every object before creating output files.
    invalid = []
    for doc in documents:
        for obj in doc.foreground_objects():
            if obj.mask is not None:
                contours = mask_contours(obj.mask)
                if any(c["hole"] for c in contours) or len([c for c in contours if not c["hole"]]) != 1:
                    invalid.append(obj.name)
    if invalid and not allow_lossy:
        raise ValueError("YOLO polygons cannot preserve holes/disconnected components exactly. Use COCO, or explicitly allow lossy conversion. Affected objects: " + ", ".join(invalid[:10]))
    directory = Path(directory)
    (directory / "labels").mkdir(parents=True, exist_ok=True)
    names = sorted({g.name for d in documents for g in d.groups})
    class_ids = {n: i for i, n in enumerate(names)}
    skipped, rows = 0, 0
    versions = []
    for doc in documents:
        filename = image_name(doc)
        versions.append({"source_key": doc.frame.key, "versions": _write_dataset_images(doc, directory, include_images, image_source, include_alternate)})
        output = []
        h, w = doc.frame.shape
        for obj in doc.foreground_objects():
            if obj.mask is None:
                skipped += 1
                continue
            for contour in mask_contours(obj.mask):
                if contour["hole"]:
                    continue
                points = np.asarray(contour["points"])
                normalized = np.clip(points / [w, h], 0, 1).ravel()
                output.append(str(class_ids[doc.get_group(obj.group_id).name]) + " " + " ".join(f"{n:.8f}" for n in normalized))
                rows += 1
        atomic_write(directory / "labels" / (Path(filename).stem + ".txt"), ("\n".join(output) + ("\n" if output else "")).encode())
    import yaml
    atomic_write(directory / "dataset.yaml", yaml.safe_dump({"path": ".", "train": "images", "val": None,
                  "names": dict(enumerate(names))}, allow_unicode=True, sort_keys=False).encode())
    report = {"objects_as_polygon_rows": rows, "skipped_points": skipped, "lossy_objects": invalid,
              "exported_image_source": image_source if include_images else None, "image_versions": versions,
              "note": "Create independent train/validation splits before training. val is intentionally unset."}
    atomic_write(directory / "conversion_report.json", json.dumps(report, indent=2).encode())
    return report


def label_map(document, by_group=False, objects=None):
    objects = document.foreground_objects() if objects is None else objects
    output = np.zeros(document.frame.shape, np.uint32)
    category_ids = {g.id: i + 1 for i, g in enumerate(document.groups)}
    instance_ids = {o.id: i + 1 for i, o in enumerate(document.objects)}
    for obj in objects:
        if obj.mask is not None:
            value = category_ids[obj.group_id] if by_group else instance_ids[obj.id]
            output[obj.mask & (output == 0)] = value  # first accepted object has precedence
    return output


def color_mask(document, objects, by_group=False, opacity=1.0, background=None):
    h, w = document.frame.shape
    output = np.zeros((h, w, 4), np.uint8)
    if background is not None:
        output[..., :3] = background
        output[..., 3] = 255
    for obj in objects:
        if obj.mask is None:
            continue
        mask = obj.mask
        color = np.asarray(hex_rgb(document.get_group(obj.group_id).color if by_group else obj.color), np.float32)
        if background is None:
            output[mask, :3] = color.astype(np.uint8)
            output[mask, 3] = round(255 * opacity)
        else:
            output[mask, :3] = np.rint(output[mask, :3] * (1 - opacity) + color * opacity).astype(np.uint8)
    return output


def overlap_grayscale(objects, shape):
    counts = np.zeros(shape, np.uint32)
    for obj in objects:
        if obj.mask is not None:
            counts += obj.mask
    maximum = int(counts.max(initial=0))
    if maximum > 255:
        raise ValueError("An 8-bit weighted grayscale mask supports at most 255 overlapping objects.")
    weight = 255 // max(1, maximum)
    return (counts * weight).astype(np.uint8), weight, maximum


def overlay_source(document, overlay):
    if overlay in (False, None, "none"):
        return None
    if overlay in (True, "original"):
        return display_rgb(document.frame.raw)
    if overlay == "cleaned":
        if document.working is None:
            raise ValueError("Apply cleaning before choosing the cleaned image as the overlay source.")
        return display_rgb(document.working)
    raise ValueError("Choose no overlay, the original image, or the cleaned image.")


def render_mask_pixels(document, objects, color_mode="group_color", overlay=False, transparency=0, transparent=False):
    """Shared preview/export rendering, with transparency defined as 1-opacity."""
    if color_mode not in ("binary","overlap_gray","group_color","object_color"):
        raise ValueError("Choose binary, overlap grayscale, group color, or object color.")
    if not 0 <= transparency <= 100:
        raise ValueError("Transparency must be between 0 and 100%.")
    objects = [o for o in objects if o.mask is not None and o.role == "object" and o.group_id != document.background_group_id]
    mask = np.zeros(document.frame.shape, bool)
    for obj in objects:
        mask |= obj.mask
    base = overlay_source(document, overlay)
    opacity=1-transparency/100
    if color_mode in ("binary", "overlap_gray"):
        gray = np.full(mask.shape,255,np.uint8) if color_mode == "binary" else overlap_grayscale(objects,mask.shape)[0]
        pixels=np.zeros((*mask.shape,4),np.uint8)
        pixels[mask,:3]=gray[mask,None];pixels[mask,3]=round(255*opacity)
        if base is not None:
            pixels[...,:3]=base;pixels[...,3]=255
            pixels[mask,:3]=np.rint(base[mask]*(1-opacity)+gray[mask,None]*opacity).astype(np.uint8)
        elif not transparent:
            pixels[mask,:3]=np.rint(gray[mask,None]*opacity).astype(np.uint8);pixels[...,3]=255
    else:
        pixels=color_mask(document,objects,color_mode=="group_color",opacity,
                          base)
        if not transparent and base is None:
            alpha=pixels[...,3:4].astype(np.float32)/255
            pixels[...,:3]=np.rint(pixels[...,:3]*alpha).astype(np.uint8)
            pixels[...,3]=255
    if transparent:
        pixels[~mask] = 0
    return pixels


def save_masks(document: Document, directory: Path, file_format="bmp", organization="combined",
               color_mode="group_color", overlay=False, transparency=0, transparent=False,
               save_original_image=False, save_cleaned_image=False):
    file_format = file_format.lower().lstrip(".")
    if file_format not in ("bmp", "png", "tif", "tiff"):
        raise ValueError("Choose BMP, PNG, or TIFF.")
    if not 0 <= transparency <= 100:
        raise ValueError("Transparency must be between 0 and 100%.")
    numeric = color_mode in ("instance", "class")
    if numeric and (overlay not in (False, None, "none") or transparent or transparency != 0):
        raise ValueError("Numeric label maps cannot have overlays or transparency.")
    if numeric and file_format == "bmp":
        raise ValueError("Numeric labels require PNG or TIFF. BMP is a rendered RGB format.")
    if transparent and file_format == "bmp":
        raise ValueError("24-bit BMP cannot store alpha. Choose PNG or TIFF.")
    if save_cleaned_image and document.working is None:
        raise ValueError("Apply cleaning or smoothing before saving a processed image.")
    objects = [o for o in document.foreground_objects() if o.mask is not None]
    if not objects:
        raise ValueError("There are no accepted masks to save.")
    if organization == "combined":
        batches = [("all", objects)]
    elif organization == "object":
        batches = [(safe_name(o.name) + "_" + o.id[:8], [o]) for o in objects]
    elif organization == "group":
        batches = [(safe_name(g.name) + "_" + g.id[:8], [o for o in objects if o.group_id == g.id]) for g in document.groups]
        batches = [(n, batch) for n, batch in batches if batch]
    else:
        raise ValueError("Unknown output organization.")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    weights = []
    for label, batch in batches:
        path = directory / f"{Path(image_name(document)).stem}_{label}.{file_format}"
        if numeric:
            pixels = label_map(document, color_mode == "class", batch)
            if pixels.max() <= 65535:
                pixels = pixels.astype(np.uint16)
            elif file_format == "png":
                raise ValueError("More than 65,535 IDs require 32-bit TIFF.")
            if file_format in ("tif", "tiff"):
                import tifffile
                tifffile.imwrite(path, pixels, photometric="minisblack")
            else:
                Image.fromarray(pixels).save(path)
        else:
            pixels = render_mask_pixels(document,batch,color_mode,overlay,transparency,transparent)
            image = Image.fromarray(pixels, "RGBA")
            if color_mode == "overlap_gray":
                _,weight,maximum=overlap_grayscale(batch,document.frame.shape)
                weights.append({"file":path.name,"weight_per_object":weight,"maximum_overlap":maximum})
            if not transparent or file_format == "bmp":
                image = image.convert("RGB")
                if color_mode == "overlap_gray" and overlay in (False,None,"none"):
                    image = image.convert("L")
            image.save(path)
        paths.append(str(path))
    instance_ids = {o.id: i + 1 for i, o in enumerate(document.objects)}
    class_ids = {g.id: i + 1 for i, g in enumerate(document.groups)}
    image_paths = save_image_versions(document, directory, save_original_image, save_cleaned_image)
    mapping = [{"instance_id": instance_ids[o.id], "class_id": class_ids[o.group_id], "object_id": o.id, "name": o.name,
                "object_color": o.color, "group_color": document.get_group(o.group_id).color,
                "group": document.get_group(o.group_id).name, "pixel_area": o.pixel_area,
                "physical_area": document.calibration.area(o.pixel_area),
                "area_unit": document.calibration.length_unit + "^2" if document.calibration.valid else None}
               for o in objects]
    atomic_write(directory / (Path(image_name(document)).stem + "_mask_mapping.json"),
                 json.dumps({"overlap_policy": "first accepted object wins in a numeric label map",
                             "weighted_grayscale": weights, "overlay_source": overlay,
                             "transparent_background": transparent, "mask_transparency_percent": transparency,
                             "color_scheme": document.color_scheme, "image_versions": image_paths,
                             "objects": mapping, "calibration": asdict(document.calibration)}, indent=2, ensure_ascii=False).encode())
    return paths + image_paths


def save_cleaned(document, path):
    return save_image(document, path, "cleaned")


def save_image(document, path, source="original"):
    if source not in ("original", "cleaned"):
        raise ValueError("Choose the original or processed image.")
    if source == "cleaned" and document.working is None:
        raise ValueError("This image has no cleaning or smoothing edits.")
    pixels = document.source_raw if source == "original" else document.working
    path = Path(path)
    if path.resolve() == Path(document.frame.source_path).resolve() or (path.exists() and Path(document.frame.source_path).exists() and path.samefile(document.frame.source_path)):
        raise ValueError("Choose a different output filename. The original acquired image cannot be overwritten.")
    if path.suffix.lower() not in (".tif", ".tiff"):
        raise ValueError("Use TIFF to preserve the source data type and calibration.")
    import tifffile
    cal = document.source_calibration if source == "original" and document.rotation else document.calibration
    metadata = {"axes": "YX" if pixels.ndim == 2 else "YXS", "image_source": source,
                "derived_image": source == "cleaned", "cleaning_history": document.cleaning_history if source == "cleaned" else [],
                "calibration": asdict(cal), "rotation": document.rotation if source == "cleaned" else []}
    kwargs = {}
    if cal.valid and (cal.basis is None or abs(float(np.dot(cal.matrix()[:,0],cal.matrix()[:,1])))<1e-10):
        kwargs["resolution"] = (1 / cal.pixel_size_x, 1 / cal.pixel_size_y)
        metadata["unit"] = cal.length_unit
    tifffile.imwrite(path, pixels, metadata=metadata, **kwargs)
    if source == "cleaned":
        atomic_write(path.with_suffix(path.suffix + ".cleaning.json"), json.dumps({"original": document.frame.source_path,
            "calibration": asdict(cal), "history": document.cleaning_history,
            "modified_region":coco_rle(document.modified),"unfilled_removed_region":coco_rle(document.removed)}, indent=2).encode())
    return path


def save_image_versions(document, directory, save_original_image=True, save_cleaned_image=False):
    if save_cleaned_image and document.working is None:
        raise ValueError("Apply cleaning or smoothing before saving a processed image.")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    stem = Path(image_name(document)).stem
    paths = []
    for enabled, source in ((save_original_image,"original"),(save_cleaned_image,"cleaned")):
        if enabled:
            paths.append(str(save_image(document, directory / (stem + "_" + source + ".tif"), source)))
    return paths


def write_measurement_csv(rows, path):
    if not rows:
        raise ValueError("There are no eligible objects to export.")
    import io
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    atomic_write(Path(path), ("\ufeff" + stream.getvalue()).encode("utf-8"))

