from __future__ import annotations

import base64
import copy
import hashlib
import json
import math
import os
import tempfile
import uuid
import zlib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np

SCHEMA_VERSION = 5
MAX_DECODED_BYTES = 2_000_000_000
LENGTH_UNITS = {"m": 1.0, "mm": 1e-3, "um": 1e-6, "µm": 1e-6,
                "μm": 1e-6, "nm": 1e-9, "pm": 1e-12, "Å": 1e-10,
                "angstrom": 1e-10, "angstroms": 1e-10, "micrometer": 1e-6,
                "micrometers": 1e-6, "nanometer": 1e-9, "nanometers": 1e-9}


@dataclass
class Calibration:
    pixel_size_x: float | None = None
    pixel_size_y: float | None = None
    length_unit: str = "nm"
    source: str = "unavailable"
    valid: bool = False
    basis: list[list[float]] | None = None
    origin: list[float] | None = None

    def __post_init__(self):
        self.length_unit = self.length_unit.replace("μ", "µ")
        self.valid = bool(self.valid and self.length_unit in LENGTH_UNITS and
                          self.pixel_size_x is not None and self.pixel_size_y is not None and
                          math.isfinite(self.pixel_size_x) and math.isfinite(self.pixel_size_y) and
                          self.pixel_size_x > 0 and self.pixel_size_y > 0)

    @property
    def pixel_area(self) -> float | None:
        return float(abs(np.linalg.det(self.matrix()))) if self.valid else None

    def matrix(self, unit=None):
        if not self.valid:
            return np.eye(2)
        matrix = np.asarray(self.basis, float) if self.basis is not None else np.diag([self.pixel_size_x, self.pixel_size_y])
        if matrix.shape != (2, 2) or not np.isfinite(matrix).all() or abs(np.linalg.det(matrix)) < 1e-30:
            raise ValueError("Invalid calibration basis.")
        if self.origin is not None and (len(self.origin)!=2 or not np.isfinite(self.origin).all()):
            raise ValueError("Invalid calibration origin.")
        return matrix * (LENGTH_UNITS[self.length_unit] / LENGTH_UNITS[unit] if unit else 1.)

    def area(self, pixels: int, target_unit: str | None = None) -> float | None:
        if not self.valid:
            return None
        value = pixels * self.pixel_area
        if target_unit:
            value *= (LENGTH_UNITS[self.length_unit] / LENGTH_UNITS[target_unit]) ** 2
        return float(value)


def pack_array(array: np.ndarray) -> dict:
    a = np.ascontiguousarray(array)
    return {"dtype": a.dtype.str, "shape": list(a.shape),
            "data": base64.b64encode(zlib.compress(a.tobytes(), 6)).decode("ascii")}


def unpack_array(value: dict, max_bytes: int = MAX_DECODED_BYTES) -> np.ndarray:
    dtype = np.dtype(value["dtype"])
    if dtype.hasobject:
        raise ValueError("Object arrays are not supported in saved projects.")
    shape = tuple(int(n) for n in value["shape"])
    if not shape or any(n < 0 for n in shape):
        raise ValueError("Invalid saved array dimensions.")
    count = math.prod(shape) * dtype.itemsize
    if count > max_bytes:
        raise ValueError("Saved array exceeds the supported memory limit.")
    decompressor = zlib.decompressobj()
    data = decompressor.decompress(base64.b64decode(value["data"], validate=True), count + 1)
    if len(data) != count or not decompressor.eof or decompressor.unconsumed_tail:
        raise ValueError("Saved array is incomplete or has an invalid byte count.")
    return np.frombuffer(data, dtype=dtype).reshape(shape).copy()


def pack_mask(mask: np.ndarray) -> dict:
    a = np.asarray(mask, dtype=bool)
    return {"shape": list(a.shape), "bits": pack_array(np.packbits(a, bitorder="little"))}


def unpack_mask(value: dict, expected_shape: tuple[int, int] | None = None) -> np.ndarray:
    shape = tuple(int(n) for n in value["shape"])
    if len(shape) != 2 or any(n <= 0 for n in shape) or math.prod(shape) > MAX_DECODED_BYTES:
        raise ValueError("Invalid mask dimensions.")
    if expected_shape and shape != tuple(expected_shape):
        raise ValueError("Saved mask dimensions do not match this image.")
    bits = unpack_array(value["bits"])
    if bits.dtype != np.uint8 or bits.size != (math.prod(shape) + 7) // 8:
        raise ValueError("Invalid packed mask length.")
    return np.unpackbits(bits, bitorder="little", count=math.prod(shape)).reshape(shape).astype(bool)


def atomic_write(path: Path, data: bytes, keep_backup: bool = False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if keep_backup and path.exists():
            # Copy only a valid snapshot. A damaged file never replaces a good backup.
            previous = path.read_bytes()
            try:
                json.loads(previous)
            except (ValueError, UnicodeDecodeError):
                pass
            else:
                atomic_write(path.with_suffix(path.suffix + ".bak"), previous)
        os.replace(tmp, path)
    finally:
        try:
            Path(tmp).unlink(missing_ok=True)
        except OSError:
            pass


def group_id(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "samstudio/group/" + name.strip()))


@dataclass
class Group:
    name: str
    color: str = "#148374"
    id: str = ""

    def __post_init__(self):
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("A group name cannot be empty.")
        self.id = self.id or group_id(self.name)


@dataclass
class Annotation:
    name: str
    group_id: str
    kind: str
    points: list[list[float]] = field(default_factory=list)
    mask: np.ndarray | None = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    color: str = "#148374"
    opacity: float = .42
    visible: bool = True
    locked: bool = False
    provenance: dict = field(default_factory=dict)
    # Persistent edit handles. A raster contour must not be regenerated after
    # every move/delete, or its pixel staircase creates new vertices.
    contours: list[dict] | None = None
    role: str = "object"
    cleaning: dict | None = None

    @property
    def pixel_area(self) -> int | None:
        return int(self.mask.sum()) if self.mask is not None else None

    def to_dict(self):
        result = {k: copy.deepcopy(v) for k, v in vars(self).items()
                  if k != "mask" and not k.startswith("_")}
        if self.mask is None:
            result["mask"] = None
        else:
            # Detect in-place changes too. CRC is cheap compared with repeatedly
            # compressing every unchanged full-size mask during each autosave.
            a = np.ascontiguousarray(self.mask, dtype=bool)
            key = (a.shape, zlib.crc32(memoryview(a)))
            if getattr(self, "_mask_pack_key", None) != key:
                self._mask_pack_cache = pack_mask(a)
                self._mask_pack_key = key
            result["mask"] = copy.deepcopy(self._mask_pack_cache)
        return result

    @classmethod
    def from_dict(cls, data, shape):
        data = copy.deepcopy(data)
        data["mask"] = unpack_mask(data["mask"], shape) if data.get("mask") else None
        if data.get("contours") is not None:
            if not isinstance(data["contours"], list):
                raise ValueError("Invalid saved editable contours.")
            for contour in data["contours"]:
                pts = np.asarray(contour.get("points", []), dtype=float)
                if pts.ndim != 2 or pts.shape[1:] != (2,) or len(pts) < 3 or not np.isfinite(pts).all():
                    raise ValueError("A saved contour needs at least three finite vertices.")
        if data.get("role", "object") not in ("object", "cleaning"):
            raise ValueError("Invalid saved object role.")
        if data.get("role") == "cleaning":
            record = data.get("cleaning") or {}
            pending = unpack_mask(record["pending"], shape)
            values = unpack_array(record["values"])
            if data["mask"] is None or values.shape[0] != int(data["mask"].sum()) or (pending & ~data["mask"]).any():
                raise ValueError("Invalid saved cleaning region.")
        return cls(**data)


@dataclass
class ImageFrame:
    source_path: str
    raw: np.ndarray
    dataset: str = "image"
    frame_index: int = 0
    frame_label: str = ""
    calibration: Calibration = field(default_factory=Calibration)
    fingerprint: str = ""
    key: str = ""

    def __post_init__(self):
        self.source_path = str(Path(self.source_path).resolve())
        if self.raw.ndim not in (2, 3) or self.raw.shape[0] < 1 or self.raw.shape[1] < 1:
            raise ValueError("The selected dataset is not a two-dimensional image.")
        if self.raw.ndim == 3 and self.raw.shape[2] not in (3, 4):
            raise ValueError("An image must be grayscale, RGB, or RGBA.")
        if self.raw.dtype.hasobject:
            raise ValueError("Unsupported object-valued image.")
        self.fingerprint = self.fingerprint or hashlib.sha256(np.ascontiguousarray(self.raw).tobytes()).hexdigest()
        ident = f"{self.source_path}\0{self.fingerprint}\0{self.dataset}\0{self.frame_index}\0{self.raw.shape}"
        self.key = self.key or hashlib.sha256(ident.encode()).hexdigest()
        self.frame_label = self.frame_label or f"{self.dataset} [{self.frame_index + 1}]"

    @property
    def shape(self):
        return tuple(self.raw.shape[:2])


class Document:
    def __init__(self, frame: ImageFrame):
        self.frame = copy.copy(frame)
        self.source_raw = frame.raw
        self.source_calibration = copy.deepcopy(frame.calibration)
        self.rotation = []
        self.rotation_reset_state = None
        self.use_processed = False  # Session-only, per image; never restore a previous session's choice.
        self.text_aliases = {}
        self.detached_crops = []
        self.calibration = copy.deepcopy(frame.calibration)
        self.groups: list[Group] = []
        self.objects: list[Annotation] = []
        self.active_group: str | None = None
        self.next_object_number = 1
        self.draft = {"points": [], "roi": None, "patches": []}
        self.working: np.ndarray | None = None
        self.removed = np.zeros(frame.shape, bool)
        self.modified = np.zeros(frame.shape, bool)
        self.cleaning_history: list[dict] = []
        self.background_group_id: str | None = None
        self.color_scheme = {"mode": "default", "by": "object", "offset": 0}
        self.revision = 0
        self.saved_revision = 0

    def get_group(self, ident: str) -> Group:
        return next(g for g in self.groups if g.id == ident)

    def ensure_group(self, name: str, color="#148374") -> Group:
        group = next((g for g in self.groups if g.name == name.strip()), None)
        if group is None:
            if self.color_scheme["mode"] == "lut20" and self.color_scheme["by"] == "group":
                from .palette import lookup_color
                color = lookup_color(len(self.groups), self.color_scheme["offset"])
            group = Group(name, color)
            if any(existing.id == group.id for existing in self.groups):
                group.id = str(uuid.uuid4())
            self.groups.append(group)
        self.active_group = group.id
        return group

    def add_object(self, kind: str, points=None, mask=None, provenance=None):
        if not self.active_group:
            raise ValueError("Choose a group before creating an object.")
        g = self.get_group(self.active_group)
        if mask is not None:
            mask = np.asarray(mask, dtype=bool)
            if mask.shape != self.frame.shape or not mask.any():
                raise ValueError("The object mask is empty or has the wrong dimensions.")
        obj = Annotation(f"Object {self.next_object_number:03d}", g.id, kind,
                         points or [], mask.copy() if mask is not None else None,
                         color=g.color, provenance=provenance or {})
        self.next_object_number += 1
        if self.color_scheme["mode"] == "lut20" and self.color_scheme["by"] == "object":
            from .palette import lookup_color
            obj.color = lookup_color(self.next_object_number - 2, self.color_scheme["offset"])
        self.objects.append(obj)
        return obj

    def set_region(self, mask, **metadata):
        """An exact shared selection, including holes and disconnected components."""
        mask = np.asarray(mask, bool)
        if mask.shape != self.frame.shape:
            raise ValueError("Selection dimensions do not match this image.")
        self.draft["roi"] = {**metadata, "kind": "mask", "mask": pack_mask(mask)}

    def apply_image_smoothing(self, result, target, method, parameters):
        if result.shape != self.frame.raw.shape or result.dtype != self.frame.raw.dtype:
            raise ValueError("Smoothed pixels must match the source dimensions and data type.")
        target = np.asarray(target, bool)
        if target.shape != self.frame.shape or not target.any():
            raise ValueError("Choose a nonempty smoothing region.")
        if (target & self.removed).any():
            raise ValueError("Fill or restore removed pixels before smoothing them.")
        sequence = max((o.cleaning["sequence"] for o in self.objects if o.role == "cleaning"), default=0) + 1
        active = self.active_group
        self.ensure_group("Image processing", "#8272b2")
        obj = self.add_object("mask", mask=target, provenance={"method": "image smoothing"})
        self.active_group = active
        obj.name, obj.role = f"Smooth image {sequence:03d}", "cleaning"
        obj.opacity = 0.0
        obj.cleaning = {"sequence": sequence, "method": method, "restoration": "replay remaining image edits",
                        "values": pack_array(result[target]), "pending": pack_mask(np.zeros(target.shape, bool)),
                        "steps": [{"method": method, "parameters": copy.deepcopy(parameters)}]}
        self.cleaning_history.append({"operation": "smooth_image", "object_id": obj.id,
                                      "method": method, "parameters": copy.deepcopy(parameters),
                                      "pixels": int(target.sum())})
        self.rebuild_cleaning()
        return obj

    def protected_mask(self, except_ids=()):
        result = np.zeros(self.frame.shape, bool)
        for obj in self.foreground_objects():
            if obj.id not in except_ids and obj.mask is not None:
                result |= obj.mask
        return result

    def foreground_objects(self):
        return [o for o in self.objects if o.role == "object" and o.group_id != self.background_group_id]

    def background_regions(self):
        return [o for o in self.objects if o.role == "object" and o.group_id == self.background_group_id
                and o.mask is not None and o.provenance.get("method") == "manual"]

    def remove_for_cleaning(self, mask, source=None):
        """Keep every removal as an object. Saved pixel values make replay deterministic."""
        from datetime import datetime, timezone
        mask = np.asarray(mask, bool)
        if mask.shape != self.frame.shape or not mask.any():
            raise ValueError("Choose a nonempty cleaning region.")
        if np.iscomplexobj(self.frame.raw):
            raise ValueError("Cleaning complex-valued images is unavailable.")
        if source is not None and (source.locked or source.role != "object"):
            raise ValueError("Choose an unlocked area object.")
        sequence = max((o.cleaning["sequence"] for o in self.objects if o.role == "cleaning"), default=0) + 1
        if source is None:
            active = self.active_group
            self.ensure_group("Cleaning regions", "#dc7526")
            source = self.add_object("mask", mask=mask)
            source.name = "Cleaning " + str(sequence).zfill(3)
            self.active_group = active
        else:
            source.provenance = {**source.provenance, "cleaning_source": {"id": source.id, "kind": source.kind}}
        source.role = "cleaning"
        source.visible = True
        source.mask = mask.copy()
        source.cleaning = {"sequence": sequence, "method": "remove", "restoration": "original acquired pixels",
                           "values": pack_array(np.zeros_like(self.frame.raw[mask])), "pending": pack_mask(mask),
                           "steps": [{"method": "remove", "time": datetime.now(timezone.utc).isoformat()}]}
        self.cleaning_history.append({"operation": "remove", "object_id": source.id, "pixels": int(mask.sum()),
                                      "restoration": "original acquired pixels"})
        self.rebuild_cleaning()
        return source

    def rebuild_cleaning(self):
        """Replay remaining objects in order; removing one cannot erase another's edit."""
        output = self.frame.raw.copy()
        removed = np.zeros(self.frame.shape, bool)
        modified = np.zeros(self.frame.shape, bool)
        for obj in sorted((o for o in self.objects if o.role == "cleaning"), key=lambda o: o.cleaning["sequence"]):
            values = unpack_array(obj.cleaning["values"])
            if values.shape != output[obj.mask].shape or values.dtype != output.dtype:
                raise ValueError("Cleaning pixel values do not match the source.")
            output[obj.mask] = values
            removed[obj.mask] = unpack_mask(obj.cleaning["pending"], self.frame.shape)[obj.mask]
            modified |= obj.mask
        self.modified, self.removed = modified, removed
        self.working = output if modified.any() or self.rotation else None

    def apply_cleaning_fill(self, result, target, method, background_group_id=None):
        if result.shape != self.frame.raw.shape or result.dtype != self.frame.raw.dtype:
            raise ValueError("Filled image does not match the source data type and dimensions.")
        for obj in self.objects:
            if obj.role != "cleaning":
                continue
            pending = unpack_mask(obj.cleaning["pending"], self.frame.shape)
            affected = pending & target & obj.mask
            if not affected.any():
                continue
            values = unpack_array(obj.cleaning["values"])
            values[affected[obj.mask]] = result[affected]
            obj.cleaning["values"] = pack_array(values)
            pending[affected] = False
            obj.cleaning["pending"] = pack_mask(pending)
            obj.cleaning["method"] = method
            obj.cleaning["steps"].append({"method": method, "region": pack_mask(affected),
                                           "background_group_id": background_group_id})
        self.cleaning_history.append({"operation": "fill", "method": method, "pixels": int(target.sum()),
                                      "background_group_id": background_group_id})
        self.rebuild_cleaning()

    def delete_objects(self, ids):
        ids = set(ids)
        selected = [o for o in self.objects if o.id in ids]
        if any(o.locked for o in selected):
            raise ValueError("Unlock the selected objects first.")
        cleaned = [o.id for o in selected if o.role == "cleaning"]
        archived = [o.to_dict() for o in selected if o.role == "cleaning"]
        self.objects = [o for o in self.objects if o.id not in ids]
        if cleaned:
            self.rebuild_cleaning()
            self.cleaning_history.append({"operation": "restore_by_deleting_objects", "object_ids": cleaned,
                                          "objects": archived,
                                          "method": "replay remaining regions over original acquired pixels"})

    def restore_cleaning_area(self, mask):
        archived = [o.to_dict() for o in self.objects if o.role == "cleaning" and (o.mask & mask).any()]
        for obj in list(self.objects):
            if obj.role != "cleaning" or not (obj.mask & mask).any():
                continue
            if obj.locked:
                raise ValueError("Unlock cleaning regions before restoring their pixels.")
            old = obj.mask
            keep = old & ~mask
            if not keep.any():
                self.objects.remove(obj)
                continue
            obj.cleaning["values"] = pack_array(unpack_array(obj.cleaning["values"])[keep[old]])
            obj.cleaning["pending"] = pack_mask(unpack_mask(obj.cleaning["pending"], self.frame.shape) & keep)
            obj.mask = keep
            obj.kind, obj.points, obj.contours = "mask", [], None
        self.rebuild_cleaning()
        self.cleaning_history.append({"operation": "restore", "pixels": int(mask.sum()),
                                      "region": pack_mask(mask), "objects_before_restore": archived,
                                      "method": "original acquired pixels"})

    def state(self):
        return {"schema_version": SCHEMA_VERSION,
                "image": {"path": self.frame.source_path, "fingerprint": self.frame.fingerprint,
                          "key": self.frame.key, "shape": list(self.source_raw.shape[:2]),
                          "dataset": self.frame.dataset, "frame_index": self.frame.frame_index},
                "derived_base": pack_array(self.frame.raw) if self.rotation else None,
                "rotation": copy.deepcopy(self.rotation), "text_aliases": copy.deepcopy(self.text_aliases),
                "rotation_reset_state": copy.deepcopy(self.rotation_reset_state),
                "source_calibration": asdict(self.source_calibration),
                "calibration": asdict(self.calibration), "groups": [asdict(g) for g in self.groups],
                "objects": [a.to_dict() for a in self.objects], "active_group": self.active_group,
                "next_object_number": self.next_object_number, "draft": copy.deepcopy(self.draft),
                "working": pack_array(self.working) if self.working is not None else None,
                "removed": pack_mask(self.removed), "modified": pack_mask(self.modified),
                "cleaning_history": copy.deepcopy(self.cleaning_history), "background_group_id": self.background_group_id,
                "color_scheme": copy.deepcopy(self.color_scheme),
                "detached_crops": copy.deepcopy(self.detached_crops), "revision": self.revision}

    def forget_processing(self):
        """Discard derived pixel edits; keep annotations and the current orientation."""
        self.objects=[o for o in self.objects if o.role!='cleaning']
        self.cleaning_history=[];self.detached_crops=[]
        self.removed=np.zeros(self.frame.shape,bool);self.modified=np.zeros(self.frame.shape,bool)
        self.working=None;self.use_processed=False
        if self.rotation_reset_state:
            state=self.rotation_reset_state
            state['objects']=[o for o in state['objects'] if o.get('role','object')!='cleaning']
            state['working']=None;state['cleaning_history']=[];state['detached_crops']=[]
            shape=tuple(state['image']['shape'])
            state['removed']=pack_mask(np.zeros(shape,bool));state['modified']=pack_mask(np.zeros(shape,bool))

    def restore(self, data: dict):
        rotation_reset = copy.deepcopy(data.get('rotation_reset_state'))
        if rotation_reset is not None and (not isinstance(rotation_reset,dict) or rotation_reset.get('rotation') or rotation_reset.get('rotation_reset_state') is not None):
            raise ValueError('Invalid pre-rotation savepoint.')
        if data.get("schema_version") not in (1, 2, 3, 4, SCHEMA_VERSION):
            raise ValueError("Unsupported project version.")
        im = data.get("image", {})
        if im.get("key") != self.frame.key or im.get("fingerprint") != self.frame.fingerprint or tuple(im.get("shape", ())) != self.source_raw.shape[:2]:
            raise ValueError("This project belongs to a different image or frame. It was not applied.")
        base = unpack_array(data["derived_base"]) if data.get("derived_base") else self.source_raw
        if base.dtype != self.source_raw.dtype or base.ndim != self.source_raw.ndim or base.shape[2:] != self.source_raw.shape[2:] or min(base.shape[:2]) < 1:
            raise ValueError("Invalid rotated image data type or dimensions.")
        shape = base.shape[:2]
        rotation = copy.deepcopy(data.get("rotation", []))
        if bool(rotation) != bool(data.get("derived_base")) or not isinstance(rotation, list):
            raise ValueError("Invalid saved image transform.")
        from .text_prompts import validate_aliases
        aliases = validate_aliases(data.get("text_aliases", {}))
        groups = [Group(**g) for g in data["groups"]]
        ids = {g.id for g in groups}
        objects = [Annotation.from_dict(o, shape) for o in data["objects"]]
        for obj in objects:
            if obj.role == "cleaning":
                pixels = unpack_array(obj.cleaning["values"])
                if pixels.shape != base[obj.mask].shape or pixels.dtype != base.dtype:
                    raise ValueError("Saved cleaning pixels do not match the source channels/type.")
                if not isinstance(obj.cleaning.get("sequence"), int) or not isinstance(obj.cleaning.get("steps"), list):
                    raise ValueError("Invalid saved cleaning order/history.")
        if len(ids) != len(groups) or len({o.id for o in objects}) != len(objects) or any(o.group_id not in ids for o in objects):
            raise ValueError("The saved object/group relationships are invalid.")
        working = unpack_array(data["working"]) if data.get("working") else None
        if working is not None and (working.shape != base.shape or working.dtype != base.dtype):
            raise ValueError("Saved cleaned image does not match source dimensions/type.")
        # Validate the entire state before modifying the live document. A corrupt
        # project must not leave half-restored annotations behind.
        calibration = Calibration(**data["calibration"])
        source_calibration = Calibration(**data.get("source_calibration",asdict(self.source_calibration)))
        removed = unpack_mask(data["removed"], shape)
        modified = unpack_mask(data["modified"], shape)
        next_number = max(int(data.get("next_object_number", 1)), len(objects) + 1)
        revision = int(data.get("revision", 0))
        draft = copy.deepcopy(data.get("draft", {"points": [], "roi": None, "patches": []}))
        if not isinstance(draft, dict) or not isinstance(draft.get("points"), list) or not isinstance(draft.get("patches"), list):
            raise ValueError("Invalid saved prompt/region state.")
        for point in draft["points"]:
            if len(point) != 3 or not all(math.isfinite(float(n)) for n in point) or point[2] not in (0, 1):
                raise ValueError("Invalid saved SAM prompt.")
        examples = draft.get("examples", [])
        if not isinstance(examples, list):
            raise ValueError("Invalid saved exemplar list.")
        for example in examples:
            pts = np.asarray(example.get("points", []), float)
            minimum = 3 if example.get("kind") == "polygon" else 2
            if (example.get("kind") not in ("polygon", "rectangle", "ellipse", "circle")
                    or pts.ndim != 2 or pts.shape[1:] != (2,) or len(pts) < minimum
                    or not np.isfinite(pts).all() or example.get("label", 1) not in (0, 1)):
                raise ValueError("Invalid saved exemplar shape.")
        roi = draft.get("roi")
        if roi is not None:
            if not isinstance(roi, dict):
                raise ValueError("Invalid saved region.")
            if roi.get("kind") == "mask":
                unpack_mask(roi["mask"], shape)
            elif roi.get("kind") not in ("polygon", "rectangle", "ellipse", "circle", "brush") or not roi.get("points"):
                raise ValueError("Invalid saved region.")
        from .palette import validate_scheme
        color_scheme = validate_scheme(data.get("color_scheme", {}))
        if calibration.valid:
            calibration.matrix()
        crops = copy.deepcopy(data.get("detached_crops", []))
        if not isinstance(crops,list): raise ValueError("Invalid saved crop list.")
        for crop in crops:
            pixels = unpack_array(crop["pixels"]); region = unpack_mask(crop["mask"])
            x,y,w,h = crop["bbox"]
            crop_shape = crop.get("coordinate_shape", list(shape))
            if len(crop_shape)!=2 or any(not isinstance(n,int) or n<1 for n in crop_shape):raise ValueError("Invalid crop coordinate image dimensions.")
            if x<0 or y<0 or x+w>crop_shape[1] or y+h>crop_shape[0] or pixels.shape[:2]!=(h,w) or region.shape!=(h,w): raise ValueError("Invalid saved crop coordinates.")
            if not crop.get("pasted") and (tuple(crop_shape)!=tuple(shape) or crop.get("rotation_count")!=len(rotation)):raise ValueError("An active retained crop does not match the current image coordinates.")
        self.detached_crops = crops
        self.frame.raw, self.rotation, self.text_aliases = base, rotation, aliases
        self.rotation_reset_state = rotation_reset
        self.groups, self.objects, self.working = groups, objects, working
        self.calibration = calibration
        self.source_calibration = source_calibration
        self.active_group = data.get("active_group") if data.get("active_group") in ids else None
        self.next_object_number, self.revision = next_number, revision
        self.draft, self.removed, self.modified = draft, removed, modified
        self.cleaning_history = copy.deepcopy(data.get("cleaning_history", []))
        self.background_group_id = data.get("background_group_id") if data.get("background_group_id") in ids else None
        self.color_scheme = color_scheme
        # Earlier releases stored only a derived image and aggregate footprints.
        # Retain their exact pixels as visible, independently restorable objects.
        if working is not None and modified.any() and not any(o.role == "cleaning" for o in objects):
            active = self.active_group
            self.ensure_group("Cleaning regions", "#dc7526")
            for footprint, method in ((modified & ~removed, "legacy fill"), (removed, "remove")):
                if footprint.any():
                    obj = self.add_object("mask", mask=footprint, provenance={"method": "legacy import"})
                    obj.name, obj.role = "Recovered cleaning region", "cleaning"
                    obj.cleaning = {"sequence": len(self.objects), "method": method,
                                    "restoration": "original acquired pixels", "steps": [{"method": method}],
                                    "values": pack_array(working[footprint]), "pending": pack_mask(removed & footprint)}
            self.active_group = active


class ProjectStore:
    def __init__(self, directory: Path):
        self.directory = Path(directory)

    def path(self, document: Document):
        return self.directory / (Path(document.frame.source_path).stem[:70] + "_" + document.frame.key[:16] + ".sam.json")

    def save(self, document: Document):
        target = self.path(document)
        atomic_write(target, json.dumps(document.state(), allow_nan=False, separators=(",", ":"), ensure_ascii=False).encode("utf-8"), True)
        document.saved_revision = document.revision
        return target

    def load(self, document: Document):
        target = self.path(document)
        if not target.exists():
            return False, ""
        try:
            document.restore(json.loads(target.read_text("utf-8")))
            message = "Restored autosaved annotations."
        except (ValueError, KeyError, TypeError, StopIteration, OSError) as error:
            backup = target.with_suffix(target.suffix + ".bak")
            if not backup.exists():
                raise ValueError(f"Cannot restore {target.name}: {error}") from error
            document.restore(json.loads(backup.read_text("utf-8")))
            message = "Recovered the previous valid autosave backup."
        document.saved_revision = document.revision
        return True, message


class History:
    def __init__(self, document: Document, save: Callable[[], None] | None = None):
        self.document, self.save = document, save
        self.undo_stack: list[tuple[str, bytes]] = []
        self.redo_stack: list[tuple[str, bytes]] = []
        self.max_bytes = 128 * 1024 * 1024

    def snapshot(self):
        return zlib.compress(json.dumps(self.document.state(), allow_nan=False, separators=(",", ":")).encode(), 1)

    def _trim(self):
        while len(self.undo_stack) > 30 or sum(len(x[1]) for x in self.undo_stack) > self.max_bytes:
            self.undo_stack.pop(0)

    def apply(self, label, mutation):
        previous = self.snapshot()
        try:
            result = mutation()
        except Exception:
            self.document.restore(json.loads(zlib.decompress(previous)))
            raise
        self.undo_stack.append((label, previous))
        self.redo_stack.clear()
        self._trim()
        self.document.revision += 1
        if self.save:
            self.save()
        return result

    def _move(self, source, destination):
        if not source:
            return False
        label, state = source.pop()
        current = self.snapshot()
        revision = self.document.revision + 1
        self.document.restore(json.loads(zlib.decompress(state)))
        self.document.revision = revision
        destination.append((label, current))
        if self.save:
            self.save()
        return True

    def undo(self):
        return self._move(self.undo_stack, self.redo_stack)

    def redo(self):
        return self._move(self.redo_stack, self.undo_stack)

