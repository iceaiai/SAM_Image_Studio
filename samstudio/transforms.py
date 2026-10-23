"""Pixel-coordinate transforms shared by rotation and proportional mask scaling."""
from __future__ import annotations
import copy
import math
from dataclasses import asdict
import cv2
import numpy as np
from .domain import pack_array, unpack_array, pack_mask, unpack_mask, Calibration
from .processing import cast_like, mask_contours, shape_mask


def rotation_matrix(shape, angle, padding="none"):
    if not math.isfinite(float(angle)) or padding not in ("none", "rectangle", "square"):
        raise ValueError("Choose a finite angle and a supported padding shape.")
    h, w = shape
    matrix = cv2.getRotationMatrix2D(((w-1)/2, (h-1)/2), float(angle), 1.)
    out_w, out_h = w, h
    if padding != "none":
        c, s = abs(matrix[0,0]), abs(matrix[0,1])
        out_w, out_h = int(math.ceil(w*c+h*s-1e-9)), int(math.ceil(w*s+h*c-1e-9))
        if padding == "square":
            out_w = out_h = max(out_w, out_h)
        matrix[:,2] += [(out_w-w)/2, (out_h-h)/2]
    if out_w*out_h > 100_000_000:
        raise ValueError("The padded image would exceed 100 million pixels.")
    return matrix, (out_h, out_w)


def warp_pixels(raw, matrix, shape, nearest=False, edge=False):
    # OpenCV does not accept int64/uint64; float64 intermediates avoid integer
    # overflow. Exact right-angle permutations stay in their original dtype.
    if raw.dtype.kind in "cO" or raw.dtype.kind in "iu" and raw.dtype.itemsize>4:
        raise ValueError("Rotation does not support complex or 64-bit integer pixels.")
    source = np.asarray(raw)
    dtype = source.dtype
    if dtype == bool:
        source = source.astype(np.uint8)
    elif dtype not in (np.dtype('uint8'),np.dtype('uint16'),np.dtype('int16'),np.dtype('float32'),np.dtype('float64')):
        source = source.astype(np.float64)
    output = cv2.warpAffine(source, np.asarray(matrix,float), (shape[1],shape[0]),
                            flags=cv2.INTER_NEAREST if nearest else cv2.INTER_LINEAR,
                            borderMode=cv2.BORDER_REPLICATE if edge else cv2.BORDER_CONSTANT,
                            borderValue=0)
    return output.astype(bool) if dtype == bool else cast_like(output,dtype)


def transform_points(points, matrix):
    if not points:
        return []
    pts = np.asarray(points,float)
    return (pts @ matrix[:,:2].T + matrix[:,2]).tolist()


def transform_object(obj, matrix, shape, rotate=False):
    old_mask = obj.mask
    if old_mask is not None:
        obj.mask = warp_pixels(old_mask,matrix,shape,nearest=True)
    if obj.role == "cleaning":
        values = unpack_array(obj.cleaning['values'])
        dense = np.zeros((*old_mask.shape,*values.shape[1:]),values.dtype)
        dense[old_mask] = values
        # Nearest sampling uses the same source pixel as the footprint, keeping
        # per-region restoration exact even for overlapping cleaning objects.
        obj.cleaning['values'] = pack_array(warp_pixels(dense,matrix,shape,nearest=True)[obj.mask])
        obj.cleaning['pending'] = pack_mask(warp_pixels(unpack_mask(obj.cleaning['pending']),matrix,shape,nearest=True) & obj.mask)
    if rotate and obj.kind in ('rectangle','ellipse','circle'):
        obj.contours = mask_contours(old_mask)
        obj.kind, obj.points = 'mask', []
    else:
        obj.points = transform_points(obj.points,matrix)
    if obj.contours is not None:
        for contour in obj.contours:
            contour['points'] = transform_points(contour['points'],matrix)


def rotate_document(document, angle, padding="none"):
    """Return the padding footprint. Caller commits this operation with History."""
    if any(not c.get("pasted") for c in document.detached_crops):
        raise ValueError("Paste or remove retained crop snapshots before rotating the image.")
    if any(o.locked for o in document.objects):
        raise ValueError("Unlock objects before rotating the image and its annotations.")
    if abs(float(angle)) % 360 < 1e-9:
        return np.zeros(document.frame.shape,bool)
    old_shape = document.frame.shape
    matrix, shape = rotation_matrix(old_shape,angle,padding)
    valid = warp_pixels(np.ones(old_shape,bool),matrix,shape,nearest=True)
    base = warp_pixels(document.frame.raw,matrix,shape,edge=True)
    base[~valid] = 0
    # Compute all replacements before mutating the live document.
    objects = copy.deepcopy(document.objects)
    for obj in objects:
        transform_object(obj,matrix,shape,rotate=True)
    if not document.rotation:
        document.source_calibration=copy.deepcopy(document.calibration)
    document.frame.raw = base
    document.objects = [o for o in objects if o.mask is None or o.mask.any()]
    document.draft = {"points":[],"roi":None,"patches":[]}
    if document.calibration.valid:
        cal = copy.deepcopy(document.calibration)
        basis = cal.matrix() @ np.linalg.inv(matrix[:,:2])
        cal.origin = (np.asarray(cal.origin or [0.,0.])-basis@matrix[:,2]).tolist()
        cal.basis = basis.tolist()
        cal.pixel_size_x, cal.pixel_size_y = np.linalg.norm(basis,axis=0).tolist()
        cal.source += "; rotated coordinate basis"
        document.calibration = cal
    document.rotation.append({"angle_degrees":float(angle),"padding":padding,"matrix":matrix.tolist(),
                              "input_shape":list(old_shape),"output_shape":list(shape),
                              "padding_region":pack_mask(~valid)})
    document.rebuild_cleaning()
    return ~valid


def scaled_objects(document, object_ids, factor):
    factor = float(factor)
    if not math.isfinite(factor) or not .01 <= factor <= 10:
        raise ValueError("Scale factor must be between 0.01 and 10.")
    ids = set(object_ids)
    selected = [o for o in document.objects if o.id in ids]
    if not selected or len(selected)!=len(ids) or any(o.locked or o.role!='object' or o.mask is None for o in selected):
        raise ValueError("Choose unlocked area annotations. Cleaning records and point annotations cannot be scaled.")
    result=[]
    for original in selected:
        obj = copy.deepcopy(original)
        yy,xx=np.nonzero(obj.mask)
        cx,cy=float(xx.mean()),float(yy.mean())
        matrix=np.array([[factor,0,cx*(1-factor)],[0,factor,cy*(1-factor)]],float)
        transform_object(obj,matrix,document.frame.shape)
        if not obj.mask.any():
            raise ValueError("This factor removes an entire object at the current pixel resolution.")
        obj.provenance={**obj.provenance,'mask_scale_factor':factor,'mask_scale_center':[cx,cy]}
        result.append(obj)
    return result


def apply_scaled_objects(document, replacements):
    mapping={o.id:o for o in replacements}
    document.objects=[mapping.get(o.id,o) for o in document.objects]
