from __future__ import annotations

import hashlib
import itertools
import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from .domain import Calibration, ImageFrame, LENGTH_UNITS

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".dm3", ".dm4", ".emd", ".webp", ".gif"}
MAX_PIXELS = 150_000_000
MAX_FRAMES = 10_000


@dataclass
class LoadResult:
    frames: list[ImageFrame] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def normalize_unit(unit):
    text = str(unit or "").strip().replace("μ", "µ")
    aliases = {"micron": "µm", "microns": "µm", "micrometre": "µm", "micrometer": "µm",
               "nanometre": "nm", "nanometer": "nm", "nanometers": "nm", "angstroms": "Å",
               "angstrom": "Å", "Angstrom": "Å", "micrometers": "µm"}
    return aliases.get(text, text)


def calibration_from_axes(axes, x_index, y_index, source):
    by_index = {int(a.get("index_in_array", i)): a for i, a in enumerate(axes)}
    x, y = by_index.get(x_index, {}), by_index.get(y_index, {})
    ux, uy = normalize_unit(x.get("units")), normalize_unit(y.get("units"))
    try:
        sx, sy = abs(float(x["scale"])), abs(float(y["scale"]))
        if ux not in LENGTH_UNITS or uy not in LENGTH_UNITS or x.get("axis") is not None or y.get("axis") is not None:
            return Calibration(source="missing or nonuniform spatial calibration")
        sy *= LENGTH_UNITS[uy] / LENGTH_UNITS[ux]
        return Calibration(sx, sy, ux, source, True)
    except (KeyError, ValueError, TypeError):
        return Calibration(source="missing spatial calibration")


def source_fingerprint(path: Path, cancel=None):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(4 * 1024 * 1024):
            if cancel and cancel.is_set():
                raise InterruptedError("Opening images was cancelled.")
            digest.update(block)
    return digest.hexdigest()


def split_frames(array, path, dataset, fingerprint, axes=None, axis_string=None, calibration=None):
    a = np.asanyarray(array)
    if a.ndim < 2:
        return []
    channel = None
    if axis_string and len(axis_string) == a.ndim:
        if "Y" not in axis_string or "X" not in axis_string:
            return []
        yi, xi = axis_string.index("Y"), axis_string.index("X")
        for name in ("S", "C"):
            if name in axis_string and a.shape[axis_string.index(name)] in (3, 4):
                channel = axis_string.index(name)
                break
    else:
        nav = {int(axis.get("index_in_array", i)) for i, axis in enumerate(axes or []) if axis.get("navigate") is True}
        signal = [i for i in range(a.ndim) if i not in nav]
        if a.ndim >= 3 and a.shape[-1] in (3, 4) and len(signal) >= 3:
            channel = a.ndim - 1
            signal.remove(channel)
        if len(signal) < 2:
            return []
        yi, xi = signal[-2:]
    remaining = [i for i in range(a.ndim) if i not in (yi, xi, channel)]
    order = remaining + [yi, xi] + ([channel] if channel is not None else [])
    a = np.transpose(a, order)
    if a.shape[len(remaining)] * a.shape[len(remaining) + 1] > MAX_PIXELS:
        raise ValueError("The image is too large for this release. Open a smaller region or downsampled copy.")
    indices = list(np.ndindex(a.shape[:len(remaining)])) if remaining else [()]
    if len(indices) > MAX_FRAMES:
        raise ValueError(f"This file contains more than {MAX_FRAMES:,} frames. Split the stack first.")
    cal = calibration or calibration_from_axes(axes or [], xi, yi, "file metadata")
    frames = []
    for i, index in enumerate(indices):
        raw = np.asarray(a[index]) if index else np.asarray(a)
        if raw.ndim == 2 or raw.ndim == 3 and raw.shape[-1] in (3, 4):
            label = f"{dataset} / " + (", ".join(str(n + 1) for n in index) if index else "image")
            frames.append(ImageFrame(str(path), raw, dataset, i, label, cal, fingerprint))
    return frames


def _ome_calibration(ome, series_index):
    if not ome:
        return None
    try:
        root = ET.fromstring(ome)
        pixels = root.findall(".//{*}Pixels")
        node = pixels[min(series_index, len(pixels) - 1)]
        sx, sy = float(node.attrib["PhysicalSizeX"]), float(node.attrib["PhysicalSizeY"])
        ux = normalize_unit(node.attrib.get("PhysicalSizeXUnit", "µm"))
        uy = normalize_unit(node.attrib.get("PhysicalSizeYUnit", "µm"))
        if ux in LENGTH_UNITS and uy in LENGTH_UNITS:
            return Calibration(sx, sy * LENGTH_UNITS[uy] / LENGTH_UNITS[ux], ux, "OME-TIFF", True)
    except (ET.ParseError, KeyError, ValueError, IndexError):
        pass
    return None


def _tiff_page_calibration(page, imagej=None):
    # Scientific metadata is preferred. Arbitrary print-resolution tags are never assumed to be microscope calibration.
    if imagej and normalize_unit(imagej.get("unit")) in LENGTH_UNITS:
        try:
            rx, ry = page.tags["XResolution"].value, page.tags["YResolution"].value
            return Calibration(rx[1] / rx[0], ry[1] / ry[0], normalize_unit(imagej["unit"]), "ImageJ TIFF", True)
        except (KeyError, TypeError, ZeroDivisionError):
            pass
    return None


def load_tiff(path, fingerprint):
    import tifffile
    result = []
    with tifffile.TiffFile(path) as tf:
        for si, series in enumerate(tf.series):
            shape = series.shape
            if math.prod(shape) * np.dtype(series.dtype).itemsize > 1_500_000_000:
                raise ValueError("The TIFF series exceeds the memory limit. Split it into smaller stacks first.")
            cal = _ome_calibration(tf.ome_metadata, si) or _tiff_page_calibration(series.pages[0], tf.imagej_metadata)
            if cal is None and tf.shaped_metadata:
                try:
                    saved=tf.shaped_metadata[si]
                    if saved.get("derived_image") and saved.get("calibration"):
                        cal=Calibration(**saved["calibration"])
                except (IndexError,KeyError,ValueError,TypeError):
                    pass
            if cal is None:
                try:
                    from rsciio.tiff import file_reader
                    meta = file_reader(str(path), lazy=True)[si]
                    axs = meta.get("axes", [])
                    if "Y" in series.axes and "X" in series.axes:
                        cal = calibration_from_axes(axs, series.axes.index("X"), series.axes.index("Y"), "TIFF scientific metadata")
                except (ImportError, KeyError, IndexError, ValueError, TypeError, OSError):
                    cal = None
            frames = split_frames(series.asarray(), path, f"series {si + 1}", fingerprint,
                                  axis_string=series.axes, calibration=cal or Calibration())
            result.extend(frames)
    return result


def load_microscopy(path, fingerprint):
    if path.suffix.lower() in (".dm3", ".dm4"):
        from rsciio.digitalmicrograph import file_reader
    else:
        from rsciio.emd import file_reader
    datasets = file_reader(str(path), lazy=False)
    frames = []
    for i, dataset in enumerate(datasets):
        axes = dataset.get("axes", [])
        raw = dataset["data"]
        if hasattr(raw, "compute"):
            raw = raw.compute()
        title = dataset.get("metadata", {}).get("General", {}).get("title") or f"dataset {i + 1}"
        frames.extend(split_frames(raw, path, str(title) + f" #{i + 1}", fingerprint, axes=axes))
    if not frames:
        raise ValueError("No supported 2D image dataset was found. Spectra and proprietary pruned EMD streams are not image frames.")
    return frames


def load_file(path: str | Path, cancel=None) -> list[ImageFrame]:
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(str(path))
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported image format: {path.suffix}")
    fingerprint = source_fingerprint(path, cancel)
    if path.suffix.lower() in (".tif", ".tiff"):
        return load_tiff(path, fingerprint)
    if path.suffix.lower() in (".dm3", ".dm4", ".emd"):
        return load_microscopy(path, fingerprint)
    frames = []
    with Image.open(path) as image:
        if image.width * image.height > MAX_PIXELS:
            raise ValueError("This image exceeds the pixel limit. Use a smaller image or region.")
        for index in range(getattr(image, "n_frames", 1)):
            image.seek(index)
            transformed = ImageOps.exif_transpose(image)
            if transformed.mode not in ("L", "I", "I;16", "F", "RGB", "RGBA"):
                transformed = transformed.convert("RGB")
            frames.append(ImageFrame(str(path), np.asarray(transformed).copy(), "image", index,
                                     f"Frame {index + 1}", Calibration(), fingerprint))
    return frames


def load_files(paths, progress=None, cancel=None):
    result = LoadResult()
    for i, path in enumerate(paths):
        if cancel and cancel.is_set():
            raise InterruptedError("Opening images was cancelled.")
        if progress:
            progress(f"Opening {Path(path).name} ({i + 1}/{len(paths)})")
        try:
            result.frames.extend(load_file(path, cancel))
        except InterruptedError:
            raise
        except Exception as error:
            result.warnings.append(f"{Path(path).name}: {error}")
    if not result.frames:
        raise ValueError("No image could be opened.\n" + "\n".join(result.warnings))
    return result

