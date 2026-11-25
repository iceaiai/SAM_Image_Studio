from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from heapq import nsmallest
import numpy as np
from PySide6.QtCore import QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from .domain import Document, unpack_mask
from .exports import hex_rgb
from .processing import (bounding_box, carve_mask_segment, curve_segments, display_rgb, mask_components,
                         mask_contours, push_mask_segment)
from .scale_bar_ui import draw_scale_bar


DISTANCE_TOOLS = ("measure_line", "measure_curve")
MAX_VERTEX_DELETE_COUNT = 10
MAX_MASK_PUSHER_RADIUS = 1000
MAX_POLYGON_CLOSE_DISTANCE = 100


@dataclass
class _MaskPusherStroke:
    object_id: str
    source_mask: np.ndarray
    mask: np.ndarray
    button: Qt.MouseButton
    radius: int
    last_point: list[float]
    bounds: QRect | None = None
    preview: QImage | None = None
    offsets: dict[tuple[int, int], np.ndarray] = field(default_factory=dict)


@dataclass
class _MaskPartSelection:
    object_id: str
    source_mask: np.ndarray
    pixel: tuple[int, int]
    position: tuple[int, int]
    overlay: QImage


def rgb_image(rgb):
    a = np.ascontiguousarray(rgb, dtype=np.uint8)
    return QImage(a.data, a.shape[1], a.shape[0], a.strides[0], QImage.Format.Format_RGB888).copy()


def rgba_image(rgba):
    a = np.ascontiguousarray(rgba, dtype=np.uint8)
    return QImage(a.data, a.shape[1], a.shape[0], a.strides[0], QImage.Format.Format_RGBA8888).copy()


class ImageCanvas(QWidget):
    selection_changed = Signal(object)
    shape_completed = Signal(str, object)
    prompt_added = Signal(float, float, int)
    geometry_changed = Signal(str, object)
    mask_pushed = Signal(str, object, object)
    mask_part_delete_requested = Signal()
    message = Signal(str)
    zoom_changed = Signal(float)
    tool_changed = Signal(str)
    object_context_requested = Signal(object, object)
    preview_count_changed = Signal(int)
    filament_end_picked = Signal(str, int)
    filament_connection_drawn = Signal(object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 320)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.document: Document | None = None
        self.mode = "Manual"
        self.tool = "select"
        self.read_only = False
        self.prompt_input_only = False
        self.edit_mode = False
        self.selected: set[str] = set()
        self.show_masks = True
        self.show_contours = True
        self.show_prompts = True
        self.show_cleaning = True
        self.use_cleaned = False
        self.brightness = 0.0
        self.contrast = 1.0
        self.scale = 1.0
        self.offset = QPointF()
        self.brush_radius = 12
        self.vertex_delete_radius = 20.0
        self.vertex_delete_count = 1
        self.polygon_close_distance = 14
        self.mask_pusher_radius = 12
        self.handle_radius = 5.1  # screen pixels; half the v1.3 radius
        self.preview_masks = []
        self.scale_bar_preview = None
        self.previewing_scale_bar = False
        self.filament_picks = {}
        self.filament_first = None
        self.filament_bridges = []
        self.draw_filament_connection = False
        self.filament_connection_draft = None
        self._mask_part = None
        self.object_colors = {}
        self._base = self._overlay = self._preview = None
        self._region = None
        self._region_source = None
        self._region_contours = []
        self._contours = {}
        self._contour_cache = {}
        self._base_key = None
        self._drawing = []
        self._distance_image = None
        self._distance_draft = []
        self._distance_points = []
        self._pusher_stroke = None
        self._cursor = None
        self._pan = None
        self._drag_handle = None
        self._edit_geometry = None
        self._delete_origin = None
        self._drag_start = None

    def set_document(self, document, fit=True):
        self.cancel_mask_pusher()
        self.clear_mask_part()
        self.document = document
        self.selected.clear()
        self.edit_mode = False
        self._drawing.clear()
        self._distance_image = None
        self.clear_distance_measurement()
        self._drag_handle = None
        self._edit_geometry = self._delete_origin = None
        self._base_key = None
        self._contour_cache.clear()
        self.preview_masks = []
        self.clear_scale_bar_preview()
        self.filament_picks = {}
        self.filament_first = None
        self.filament_bridges = []
        self.draw_filament_connection = False
        self.filament_connection_draft = None
        self.object_colors = {}
        self.refresh()
        if fit:
            self.fit_image()

    def refresh(self):
        doc = self.document
        if doc is None:
            self._base = self._overlay = self._preview = None
            self._region = self._region_source = None
            self._region_contours = []
            self.update()
            return
        if self._pusher_stroke and not self._valid_pusher_stroke():
            self.cancel_mask_pusher()
        if self._mask_part and self.selected_mask_part() is None:
            self.clear_mask_part()
        if self._distance_image is not doc.frame.raw:
            self._distance_image = doc.frame.raw
            self.clear_distance_measurement()
        source = doc.working if self.use_cleaned and doc.working is not None else doc.frame.raw
        base_key = (id(doc.frame), id(source), doc.revision if source is doc.working else 0,
                    self.brightness, self.contrast)
        if self._base is None or self._base_key != base_key:
            self._base = rgb_image(display_rgb(source, self.brightness, self.contrast))
            self._base_key = base_key
        overlay = np.zeros((*doc.frame.shape, 4), np.uint8)
        self._contours = {}
        for obj in doc.objects:
            if not obj.visible or (obj.role == "cleaning" and not self.show_cleaning):
                continue
            if obj.mask is not None:
                overlay[obj.mask, :3] = hex_rgb(self.object_colors.get(obj.id, obj.color))
                overlay[obj.mask, 3] = round(255 * obj.opacity)
                if obj.id in self.selected or self.show_contours:
                    cached = self._contour_cache.get(obj.id)
                    if obj.contours is not None:
                        contours = obj.contours
                    elif cached and cached[0] is obj.mask:
                        contours = cached[1]
                    else:
                        contours = mask_contours(obj.mask)
                    self._contours[obj.id] = contours
                    self._contour_cache[obj.id] = (obj.mask, contours)
        valid_ids = {o.id for o in doc.objects}
        self._contour_cache = {k: v for k, v in self._contour_cache.items() if k in valid_ids}
        self._overlay = rgba_image(overlay)
        roi = doc.draft.get("roi")
        if roi is not self._region_source:
            self._region_source = roi
            self._region = None
            self._region_contours = []
            if roi and roi.get("kind") == "mask":
                mask = unpack_mask(roi["mask"], doc.frame.shape)
                region = np.zeros((*mask.shape, 4), np.uint8)
                region[mask] = [37, 99, 235, 48]
                self._region = rgba_image(region)
                self._region_contours = mask_contours(mask)
        self.set_preview(self.preview_masks)
        self.update()

    def set_preview(self, masks):
        self.preview_masks = list(masks)
        self.preview_count_changed.emit(len(self.preview_masks))
        if self.document and self.preview_masks:
            mask = self.preview_masks[0].copy()
            for candidate in self.preview_masks[1:]:
                mask |= candidate
            out = np.zeros((*mask.shape, 4), np.uint8)
            out[mask] = [45, 138, 255, 140]
            self._preview = rgba_image(out)
        else:
            self._preview = None
        self.update()

    def preview_scale_bar(self, bar):
        self.previewing_scale_bar = True
        self.scale_bar_preview = bar
        self.update()

    def clear_scale_bar_preview(self):
        self.previewing_scale_bar = False
        self.scale_bar_preview = None
        self.update()

    def set_selected(self, ids):
        ids = set(ids)
        if ids == self.selected:
            self.update()
            return
        self.selected = ids
        self.cancel_mask_pusher()
        self.clear_mask_part()
        self._drag_handle = None
        self._edit_geometry = None
        self._delete_origin = None
        if self.document:
            for obj in self.document.objects:
                if obj.id in self.selected and obj.mask is not None and obj.id not in self._contours:
                    self._contours[obj.id] = obj.contours if obj.contours is not None else mask_contours(obj.mask)
        self.update()

    def set_tool(self, tool):
        self.cancel_mask_pusher()
        self.clear_mask_part()
        if tool != self.tool:
            self._drag_handle = self._edit_geometry = self._delete_origin = self._drag_start = None
        self.tool = tool
        self._drawing = []
        self._distance_draft.clear()
        self._cursor = None
        self.setCursor(Qt.CursorShape.ArrowCursor if tool == "select" else Qt.CursorShape.OpenHandCursor if tool == "pan" else Qt.CursorShape.CrossCursor)
        self.tool_changed.emit(tool)
        self.update()

    @property
    def filament_link_active(self):
        return bool(self.filament_picks) or self.draw_filament_connection

    def clear_mask_part(self):
        if self._mask_part is None:
            return False
        self._mask_part = None
        self.update()
        return True

    def selected_mask_part(self):
        part = self._mask_part
        obj = self._selected_object()
        if (part and obj and obj.id == part.object_id and obj.mask is part.source_mask
                and obj.visible and not obj.locked):
            return part.object_id, *part.pixel
        return None

    def _select_mask_part(self, point):
        self.clear_mask_part()
        if point is None:
            return
        x, y = map(int, point)
        obj = self._selected_object()
        if obj is None or obj.mask is None or not obj.visible or not obj.mask[y, x]:
            obj = self.object_at(point)
        if obj is None or obj.role != "object" or obj.mask is None or obj.locked:
            self.message.emit("Click a visible, unlocked area mask to select a disconnected part.")
            return
        labels, areas = mask_components(obj.mask)
        if len(areas) <= 2:
            self.message.emit("This mask has only one connected part.")
            return
        part = labels == labels[y, x]
        left, top, width, height = bounding_box(part)
        overlay = np.zeros((height, width, 4), np.uint8)
        overlay[part[top:top+height, left:left+width]] = [251, 146, 60, 211]
        self.set_selected({obj.id})
        self.selection_changed.emit(self.selected)
        self._mask_part = _MaskPartSelection(obj.id, obj.mask, (x, y), (left, top), rgba_image(overlay))
        self.message.emit("Selected mask part. Press Delete to remove it or Esc to clear the selection.")
        self.update()

    def fit_image(self):
        if not self.document:
            return
        h, w = self.document.frame.shape
        self.scale = max(.001, min((self.width()-40)/w, (self.height()-40)/h))
        self.offset = QPointF((self.width()-w*self.scale)/2, (self.height()-h*self.scale)/2)
        self.zoom_changed.emit(self.scale)
        self.update()

    def to_image(self, point, clamp=False):
        if not self.document:
            return None
        x, y = (point.x()-self.offset.x())/self.scale, (point.y()-self.offset.y())/self.scale
        h, w = self.document.frame.shape
        if clamp:
            return [max(0., min(float(w), x)), max(0., min(float(h), y))]
        return [x, y] if 0 <= x < w and 0 <= y < h else None

    def to_widget(self, point):
        return QPointF(point[0]*self.scale+self.offset.x(), point[1]*self.scale+self.offset.y())

    def clear_distance_measurement(self):
        self._distance_draft.clear()
        self._distance_points.clear()
        self.update()

    def distance_readout(self):
        points = self._distance_draft or self._distance_points
        if len(points) < 2 or self.document is None:
            return ""
        deltas = np.diff(points, axis=0)
        pixels = np.linalg.norm(deltas, axis=1).sum()
        readout = f"{pixels:.5g} px"
        calibration = self.document.calibration
        if calibration.valid:
            physical = np.linalg.norm(deltas @ calibration.matrix().T, axis=1).sum()
            readout += f" · {physical:.5g} {calibration.length_unit}"
        return readout

    def _extend_distance_trace(self, point):
        if self.tool == "measure_line":
            self._distance_draft[1:] = [point]
        elif point != self._distance_draft[-1]:
            self._distance_draft.append(point)

    def cancel_mask_pusher(self):
        if self._pusher_stroke is None:
            return False
        self._pusher_stroke = None
        self.update()
        return True

    def _pusher_object(self):
        obj = self._selected_object()
        if (self.edit_mode and not self.read_only and not self.prompt_input_only and obj
                and obj.role == "object" and obj.mask is not None and obj.visible and not obj.locked):
            return obj
        return None

    def _valid_pusher_stroke(self):
        obj = self._pusher_object()
        stroke = self._pusher_stroke
        return stroke is not None and obj is not None and obj.id == stroke.object_id and obj.mask is stroke.source_mask

    def _extend_mask_pusher(self, point):
        stroke = self._pusher_stroke
        if not self._valid_pusher_stroke():
            self.cancel_mask_pusher()
            return
        if stroke.button == Qt.MouseButton.LeftButton:
            bounds = push_mask_segment(stroke.mask, stroke.source_mask, stroke.offsets,
                                       stroke.last_point, point, stroke.radius)
        else:
            bounds = carve_mask_segment(stroke.mask, stroke.last_point, point, stroke.radius)
        stroke.last_point = point
        if bounds is None:
            return
        x0, y0, x1, y1 = bounds
        rect = QRect(x0, y0, x1 - x0, y1 - y0)
        stroke.bounds = rect if stroke.bounds is None else stroke.bounds.united(rect)
        rect = stroke.bounds
        region = np.s_[rect.y():rect.y() + rect.height(), rect.x():rect.x() + rect.width()]
        original, edited = stroke.source_mask[region], stroke.mask[region]
        added = edited & ~original
        removed = original & ~edited
        if not (added.any() or removed.any()):
            stroke.preview = None
            return
        overlay = np.zeros((*edited.shape, 4), np.uint8)
        overlay[added] = [32, 201, 151, 196]
        overlay[removed] = [241, 82, 84, 204]
        stroke.preview = rgba_image(overlay)

    def _polygon_will_close(self, point):
        return (self.polygon_close_distance > 0 and point is not None and len(self._drawing) >= 3
                and math.dist(self._drawing[0], point) * self.scale <= self.polygon_close_distance + 1e-9)

    def _selected_object(self):
        if not self.document or len(self.selected) != 1:
            return None
        return next((o for o in self.document.objects if o.id in self.selected), None)

    def _geometry(self, obj):
        if self._edit_geometry is not None:
            return self._edit_geometry
        if obj.kind == "mask":
            contours = obj.contours if obj.contours is not None else self._contours.get(obj.id)
            return {"kind": "contours", "contours": copy.deepcopy(contours if contours is not None else mask_contours(obj.mask))}
        return {"kind": obj.kind, "points": copy.deepcopy(obj.points)}

    @staticmethod
    def _handles(geometry):
        if geometry["kind"] == "contours":
            return [(ci, pi, p) for ci, c in enumerate(geometry["contours"]) for pi, p in enumerate(c["points"])]
        return [(0, pi, p) for pi, p in enumerate(geometry.get("points", []))]

    def _vertices_to_delete(self, geometry, handles):
        if self._delete_origin is None or geometry["kind"] not in ("polygon", "contours"):
            return []
        nearby = []
        for contour_index, point_index, point in handles:
            distance = math.dist(self._delete_origin, point)
            if distance <= self.vertex_delete_radius + 1e-9:
                nearby.append((distance, contour_index, point_index))
        if not nearby:
            return []
        contour_index = min(nearby)[1]
        points = (geometry["contours"][contour_index]["points"] if geometry["kind"] == "contours"
                  else geometry["points"])
        limit = max(0, min(self.vertex_delete_count, MAX_VERTEX_DELETE_COUNT, len(points) - 3))
        closest = nsmallest(limit, ((distance, pi) for distance, ci, pi in nearby if ci == contour_index))
        return [(contour_index, pi) for _, pi in closest]

    def _draw_geometry(self, painter, geometry, fill=None):
        kind = geometry["kind"]
        if kind == "contours":
            for c in geometry["contours"]:
                if c.get("curve"):
                    path = QPainterPath(QPointF(*c["points"][0]))
                    for _, b, ctrl, end in curve_segments(c["points"]):
                        path.cubicTo(QPointF(*b), QPointF(*ctrl), QPointF(*end))
                    path.closeSubpath()
                    painter.drawPath(path)
                else:
                    self._draw_geometry(painter, {"kind": "polygon", "points": c["points"]})
            return
        points = geometry.get("points", [])
        if not points:
            return
        if kind == "point":
            painter.drawEllipse(QPointF(*points[0]), 4/self.scale, 4/self.scale)
        elif kind in ("rectangle", "circle", "ellipse") and len(points) == 2:
            rect = QRectF(QPointF(*points[0]), QPointF(*points[1])).normalized()
            if kind == "circle":
                radius = min(rect.width(), rect.height())/2
                rect = QRectF(rect.center().x()-radius, rect.center().y()-radius, radius*2, radius*2)
            if kind == "rectangle":
                painter.drawRect(rect)
            else:
                painter.drawEllipse(rect)
        else:
            path = QPainterPath(QPointF(*points[0]))
            for p in points[1:]:
                path.lineTo(QPointF(*p))
            if kind == "polygon" and len(points) >= 3:
                path.closeSubpath()
            painter.drawPath(path)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#e9edf3"))
        if not self.document or self._base is None:
            painter.setPen(QColor("#607087"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Open images to start\nPNG · TIFF · JPEG · BMP · EMD · DM3 · DM4")
            return
        painter.save()
        painter.translate(self.offset)
        painter.scale(self.scale, self.scale)
        painter.drawImage(0, 0, self._base)
        if self.show_masks and self._overlay:
            painter.drawImage(0, 0, self._overlay)
        if self._preview:
            painter.drawImage(0, 0, self._preview)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        for obj in self.document.objects:
            if not obj.visible or (obj.role == "cleaning" and not self.show_cleaning):
                continue
            selected = obj.id in self.selected
            if selected or self.show_contours or obj.kind == "point":
                color = self.object_colors.get(obj.id, obj.color)
                painter.setPen(QPen(QColor("#245dd8" if selected else color), (4.4 if selected else 2.2)/self.scale))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                editing = (selected and self.edit_mode and obj.role == "object" and not obj.locked
                           and self.tool not in ("mask_pusher", "mask_part") and not self.filament_link_active)
                if editing:
                    geometry = self._geometry(obj)
                elif obj.kind != "mask":
                    geometry = {"kind": obj.kind, "points": obj.points}
                else:
                    geometry = {"kind": "contours", "contours": self._contours.get(obj.id, [])}
                self._draw_geometry(painter, geometry)
                if editing:
                    handles = self._handles(geometry)
                    deleting = set(self._vertices_to_delete(geometry, handles)) if len(self.selected) == 1 else set()
                    for ci, pi, point in handles:
                        painter.setBrush(QColor("#fbbf24" if (ci, pi) in deleting else "white"))
                        r = self.handle_radius/self.scale
                        painter.drawRect(QRectF(point[0]-r, point[1]-r, 2*r, 2*r))
        stroke = self._pusher_stroke
        if stroke and stroke.preview is not None:
            painter.drawImage(stroke.bounds.topLeft(), stroke.preview)
        if self._mask_part is not None:
            painter.drawImage(*self._mask_part.position, self._mask_part.overlay)
        draft = self.document.draft
        if draft.get("roi"):
            painter.setPen(QPen(QColor("#2563eb"), 1.6/self.scale, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            if draft["roi"].get("kind") == "mask":
                if self._region:
                    painter.drawImage(0, 0, self._region)
                self._draw_geometry(painter, {"kind": "contours", "contours": self._region_contours})
            else:
                self._draw_geometry(painter, draft["roi"])
        if self.show_prompts:
            for example in draft.get("examples", []):
                painter.setPen(QPen(QColor("#16a475" if example.get("label",1) else "#e44848"),2/self.scale,Qt.PenStyle.DashLine));painter.setBrush(Qt.BrushStyle.NoBrush);self._draw_geometry(painter,example)
            for x, y, label in draft.get("points", []):
                painter.setBrush(QColor("#16a475" if label else "#e44848"))
                painter.setPen(QPen(QColor("white"), 1/self.scale))
                painter.drawEllipse(QPointF(x, y), 4.5/self.scale, 4.5/self.scale)
        if (self.edit_mode and self.tool == "select" and not self.filament_link_active
                and self._delete_origin is not None):
            painter.setPen(QPen(QColor("#c27b16"), 1/self.scale, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(*self._delete_origin),self.vertex_delete_radius,self.vertex_delete_radius)
        if self._drawing:
            painter.setPen(QPen(QColor("#2563eb"), 1.8/self.scale))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            points = self._drawing + ([self._cursor] if self._cursor else [])
            if self.tool == "polygon":
                if self._polygon_will_close(self._cursor):
                    points = self._drawing + [self._drawing[0]]
                    painter.setPen(QPen(QColor("#15803d"), 2.2/self.scale))
                    painter.setBrush(QColor("#dcfce7"))
                    painter.drawEllipse(QPointF(*points[0]), 5/self.scale, 5/self.scale)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                self._draw_geometry(painter, {"kind": "polyline", "points": points})
            elif self.tool in ("rectangle", "ellipse", "circle") and self._cursor:
                self._draw_geometry(painter, {"kind": self.tool, "points": [self._drawing[0], self._cursor]})
            elif self.tool == "point" and self.mode == "Clean":
                for p in points:
                    painter.drawEllipse(QPointF(*p), self.brush_radius, self.brush_radius)
        bar = self.scale_bar_preview if self.previewing_scale_bar else self.document.scale_bar
        if bar is not None:
            draw_scale_bar(painter, bar, self.document.calibration, self.document.frame.shape)
        self._draw_filament_guides(painter)
        if self.tool == "mask_pusher" and self._cursor is not None:
            center = QPointF(*self._cursor)
            radius = stroke.radius if stroke else self.mask_pusher_radius
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#172632"), 3.5/self.scale))
            painter.drawEllipse(center, radius, radius)
            painter.setPen(QPen(QColor("white"), 1.5/self.scale))
            painter.drawEllipse(center, radius, radius)
        painter.restore()
        self._draw_distance_measurement(painter)

    def _draw_distance_measurement(self, painter):
        points = self._distance_draft or self._distance_points
        if not points:
            return
        start, end = self.to_widget(points[0]), self.to_widget(points[-1])
        path = QPainterPath(start)
        for point in points[1:]:
            path.lineTo(self.to_widget(point))
        edge = QColor("#173042")
        highlight = QColor("#67e8f9")
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(edge, 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawPath(path)
        painter.setPen(QPen(highlight, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawPath(path)
        painter.setPen(QPen(edge, 1.5))
        painter.setBrush(highlight)
        painter.drawEllipse(start, 3.5, 3.5)
        if end != start:
            painter.drawEllipse(end, 3.5, 3.5)

        label = self.distance_readout()
        if label:
            metrics = painter.fontMetrics()
            width = metrics.horizontalAdvance(label) + 16
            height = metrics.height() + 8
            x = max(8, min(end.x() + 10, self.width() - width - 8))
            y = max(8, min(end.y() + 10, self.height() - height - 8))
            rect = QRectF(x, y, width, height)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(edge)
            painter.drawRoundedRect(rect, 5, 5)
            painter.setPen(QColor("white"))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)

    def _draw_filament_guides(self, painter):
        painter.setPen(QPen(QColor("#f59e0b"), 3 / self.scale, Qt.PenStyle.DashLine))
        for first, second in self.filament_bridges:
            painter.drawLine(QPointF(*first), QPointF(*second))
        if self.filament_connection_draft:
            first, second = self.filament_connection_draft
            painter.drawLine(QPointF(*first), QPointF(*second))
        painter.setPen(QPen(QColor("#292524"), 1.5 / self.scale))
        for options in self.filament_picks.values():
            for _, point in options:
                selected = self.filament_first is point
                painter.setBrush(QColor("#f59e0b" if selected else "#fef3c7"))
                radius = (7 if selected else 6) / self.scale
                painter.drawEllipse(QPointF(*point), radius, radius)

    def wheelEvent(self, event):
        if not self.document:
            return
        position = event.position()
        image_point = self.to_image(position, True)
        self.scale = max(.005, min(100, self.scale * (1.2 if event.angleDelta().y() > 0 else 1/1.2)))
        self.offset = QPointF(position.x()-image_point[0]*self.scale, position.y()-image_point[1]*self.scale)
        self.zoom_changed.emit(self.scale)
        self.update()

    def mousePressEvent(self, event):
        self.setFocus()
        if event.button() == Qt.MouseButton.MiddleButton or self.tool == "pan":
            self.cancel_mask_pusher()
            self.filament_connection_draft = None
            self._pan = (event.position(), QPointF(self.offset))
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        point = self.to_image(event.position())
        if self.read_only:
            return
        if self.draw_filament_connection:
            if point is not None and event.button() == Qt.MouseButton.LeftButton and not self.prompt_input_only:
                self.filament_connection_draft = (point, point)
                self.update()
            return
        if self.tool == "mask_part" and event.button() == Qt.MouseButton.LeftButton:
            if self.edit_mode and not self.prompt_input_only:
                self._select_mask_part(point)
            return
        if self.tool == "mask_pusher":
            button = event.button()
            if button in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
                self.cancel_mask_pusher()
                if point is None:
                    return
                obj = self._pusher_object()
                if obj is not None:
                    self._cursor = point
                    self._pusher_stroke = _MaskPusherStroke(obj.id, obj.mask, obj.mask.copy(), button,
                                                           self.mask_pusher_radius, point)
                    self._extend_mask_pusher(point)
                    self.update()
                else:
                    self.message.emit("Select one visible, unlocked area mask in Edit mode.")
            return
        if self.tool in DISTANCE_TOOLS:
            if point is not None and not self.prompt_input_only and event.button() == Qt.MouseButton.LeftButton:
                self._distance_draft = [point]
                self.update()
            return
        if self.filament_picks and event.button() == Qt.MouseButton.LeftButton:
            choices = [((self.to_widget(end) - event.position()).manhattanLength(), ident, index)
                       for ident, options in self.filament_picks.items() for index, end in options]
            distance, ident, index = min(choices)
            if distance <= 16:
                self.filament_end_picked.emit(ident, index)
            return
        if point is None:
            return
        if self.prompt_input_only:
            if self.mode == "Segment" and self.tool == "point":
                self.prompt_added.emit(point[0], point[1], int(event.button() != Qt.MouseButton.RightButton))
                return
            if self.mode != "Segment" or self.tool == "select":return
        if event.button() == Qt.MouseButton.RightButton and self.mode != "Segment":
            picked = self.object_at(point)
            if picked:
                if picked.id not in self.selected:
                    self.set_selected({picked.id})
                    self.selection_changed.emit(self.selected)
                self.object_context_requested.emit(event.globalPosition().toPoint(), point)
            return
        obj = self._selected_object()
        if self.edit_mode and obj and not obj.locked and obj.role != "cleaning" and self.tool == "select":
            geometry = self._geometry(obj)
            handles = self._handles(geometry)
            if handles:
                best = min(handles, key=lambda h: math.dist(point, h[2]))
                if math.dist(point, best[2]) * self.scale <= self.handle_radius + 2:
                    self._edit_geometry = geometry
                    self._drag_handle = (best[0], best[1])
                    self._delete_origin = list(point)
                    self._drag_start = QPointF(event.position())
                    self.update()
                    return
            if event.button() == Qt.MouseButton.LeftButton:
                # Keep the deletion origin on this object, but allow selecting
                # another object with the same canvas interaction as the list.
                picked = self.object_at(point)
                if picked is None or picked.id == obj.id:
                    self._delete_origin = list(point)
                    self.update()
                    return
        if self.mode == "Segment" and self.tool == "point":
            self.prompt_added.emit(point[0], point[1], int(event.button() != Qt.MouseButton.RightButton))
        elif event.button() == Qt.MouseButton.LeftButton and self.tool == "select":
            candidate = self.object_at(point)
            picked = candidate.id if candidate else None
            selected = set(self.selected) if event.modifiers() & Qt.KeyboardModifier.ControlModifier else set()
            if picked:
                selected.symmetric_difference_update({picked})
            self.set_selected(selected)
            self.selection_changed.emit(selected)
        elif event.button() == Qt.MouseButton.LeftButton:
            if self.mode == "Edit":
                return
            if self.tool == "polygon":
                if self._polygon_will_close(point):
                    self.finish_polygon()
                    return
                self._drawing.append(point)
                self._cursor = point
            elif self.tool == "point" and self.mode == "Manual":
                self.shape_completed.emit("point", [point])
            else:
                self._drawing = [point]
                self._cursor = point
            self.update()

    def object_at(self, point):
        if self.document is None:
            return None
        h,w = self.document.frame.shape
        x,y = min(w-1,max(0,int(point[0]))),min(h-1,max(0,int(point[1])))
        for candidate in reversed(self.document.objects):
            if not candidate.visible or (candidate.role == "cleaning" and not self.show_cleaning):
                continue
            # A whole-image processing record is managed in the object list.
            # It must not intercept every foreground click after smoothing.
            if candidate.provenance.get("method") == "image smoothing":
                continue
            if ((candidate.mask is not None and candidate.mask[y,x]) or
                    (candidate.kind == "point" and candidate.points and math.dist(point,candidate.points[0])*self.scale < 9)):
                return candidate
        return None

    def mouseMoveEvent(self, event):
        if self._pan:
            self.offset = self._pan[1] + event.position() - self._pan[0]
            self.update()
            return
        point = self.to_image(event.position(), True)
        if point is None:
            return
        if self.draw_filament_connection:
            if self.filament_connection_draft and event.buttons() & Qt.MouseButton.LeftButton:
                self.filament_connection_draft = (self.filament_connection_draft[0], point)
                self.update()
            return
        if self.tool == "mask_pusher":
            stroke = self._pusher_stroke
            if stroke and event.buttons() & stroke.button:
                self._cursor = point
                self._extend_mask_pusher(point)
            else:
                self.cancel_mask_pusher()
                self._cursor = self.to_image(event.position())
            self.update()
            return
        if self.tool in DISTANCE_TOOLS:
            if (self._distance_draft and event.buttons() & Qt.MouseButton.LeftButton
                    and not (self.read_only or self.prompt_input_only)):
                self._extend_distance_trace(point)
                self.update()
            return
        if self._drag_handle and self._edit_geometry:
            if self._drag_start is not None and (event.position()-self._drag_start).manhattanLength() < 2:
                return
            ci, pi = self._drag_handle
            if self._edit_geometry["kind"] == "contours":
                self._edit_geometry["contours"][ci]["points"][pi] = point
            else:
                self._edit_geometry["points"][pi] = point
            self.update()
        elif self._drawing:
            self._cursor = point
            if self.tool == "point" and self.mode == "Clean" and math.dist(self._drawing[-1], point) >= max(1., self.brush_radius/3):
                self._drawing.append(point)
            self.update()

    def mouseReleaseEvent(self, event):
        if self._pan:
            self._pan = None
            if self.tool == "pan":self.setCursor(Qt.CursorShape.OpenHandCursor)
            elif self.draw_filament_connection or self.tool in (*DISTANCE_TOOLS, "mask_pusher", "mask_part"):
                self.setCursor(Qt.CursorShape.CrossCursor)
            else:self.setCursor(Qt.CursorShape.ArrowCursor)
            return
        if self.draw_filament_connection:
            if self.filament_connection_draft and event.button() == Qt.MouseButton.LeftButton:
                start = self.filament_connection_draft[0]
                self.filament_connection_draft = None
                self.update()
                self.filament_connection_drawn.emit(start, self.to_image(event.position()))
            return
        if self.tool == "mask_pusher":
            stroke = self._pusher_stroke
            if stroke and event.button() == stroke.button:
                point = self.to_image(event.position(), True)
                if point is not None:
                    self._extend_mask_pusher(point)
                valid = self.cancel_mask_pusher()
                if valid and stroke.preview is not None:
                    if stroke.mask.any():
                        self.mask_pushed.emit(stroke.object_id, stroke.source_mask, stroke.mask)
                    else:
                        self.message.emit("The stroke would erase the entire mask. Try a smaller radius or a shorter stroke.")
            return
        if self.tool in DISTANCE_TOOLS:
            if event.button() == Qt.MouseButton.LeftButton and self._distance_draft:
                point = self.to_image(event.position(), True)
                if point is not None and not (self.read_only or self.prompt_input_only):
                    self._extend_distance_trace(point)
                    if any(a != b for a, b in zip(self._distance_draft, self._distance_draft[1:])):
                        self._distance_points = self._distance_draft
                self._distance_draft = []
                self.update()
            return
        if self._drag_handle:
            obj = self._selected_object()
            edited = self._edit_geometry
            point = self.to_image(event.position(), True)
            moved = self._drag_start is not None and (event.position()-self._drag_start).manhattanLength() >= 2
            if edited and point is not None and moved:
                ci, pi = self._drag_handle
                pts = edited["contours"][ci]["points"] if edited["kind"] == "contours" else edited["points"]
                # Mouse release is authoritative even if the OS coalesced moves.
                if math.dist(point, pts[pi]) * self.scale > .5:
                    pts[pi] = point
                self._delete_origin = list(pts[pi])
            self._edit_geometry = None
            if obj and edited and moved and edited != self._geometry(obj):
                self.geometry_changed.emit(obj.id, copy.deepcopy(edited))
            self._drag_handle = self._edit_geometry = None
            self._drag_start = None
            self.update()
            return
        if event.button() != Qt.MouseButton.LeftButton or not self._drawing or self.tool == "polygon":
            return
        if self.tool == "point" and self.mode != "Clean":
            self._drawing, self._cursor = [], None
            return
        point = self.to_image(event.position(), True)
        if point:
            points = [self._drawing[0], point] if self.tool != "point" else self._drawing + [point]
            self.shape_completed.emit("brush" if self.tool == "point" else self.tool, points)
        self._drawing, self._cursor = [], None
        self.update()

    def finish_polygon(self):
        points = self._drawing
        while len(points) > 1 and math.dist(points[-1], points[-2]) < .5:
            points.pop()
        if len(points) >= 3:
            self.shape_completed.emit("polygon", copy.deepcopy(points))
            self._drawing, self._cursor = [], None
        else:
            self.message.emit("A polygon needs three vertices. Click more points, then double-click or press Enter.")
        self.update()

    def mouseDoubleClickEvent(self, event):
        if self.tool in ("mask_pusher", "mask_part"):
            self.mousePressEvent(event)
        elif self.tool == "polygon" and event.button() == Qt.MouseButton.LeftButton and not self.read_only:
            self.finish_polygon()

    def leaveEvent(self, event):
        if self.tool == "mask_pusher":
            self._cursor = None
            self.update()
        super().leaveEvent(event)

    def delete_vertex(self):
        obj = self._selected_object()
        if not self.edit_mode or not obj or obj.locked or obj.role != "object" or not obj.visible:
            return False
        if self._delete_origin is None:
            return False
        geometry = self._geometry(obj)
        candidates = self._vertices_to_delete(geometry, self._handles(geometry))
        if not candidates:
            self.message.emit("No removable vertices within the radius. Each contour keeps at least three vertices.")
            return True
        ci = candidates[0][0]
        points = geometry["contours"][ci]["points"] if geometry["kind"] == "contours" else geometry["points"]
        for pi in sorted((pi for _, pi in candidates), reverse=True):
            points.pop(pi)
        self._drag_handle = self._edit_geometry = None
        geometry["vertices_deleted"] = len(candidates)
        self.geometry_changed.emit(obj.id, geometry)
        self.update()
        return True

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete and self.tool == "mask_part" and self.edit_mode:
            self.mask_part_delete_requested.emit()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.tool == "polygon" and self._drawing:
            self.finish_polygon()
        elif event.key() == Qt.Key.Key_Escape:
            if self.tool == "mask_pusher":
                self.set_tool("select")
                return
            if self.clear_mask_part():
                return
            if self.tool in DISTANCE_TOOLS:
                self.clear_distance_measurement()
                return
            self._drawing, self._cursor = [], None
            self._drag_handle = self._edit_geometry = None
            self.update()
        else:
            super().keyPressEvent(event)

