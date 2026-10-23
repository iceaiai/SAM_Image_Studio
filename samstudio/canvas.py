from __future__ import annotations

import copy
import math
import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from .domain import Document, unpack_mask
from .exports import hex_rgb
from .processing import curve_segments, display_rgb, mask_contours


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
    message = Signal(str)
    zoom_changed = Signal(float)
    tool_changed = Signal(str)
    object_context_requested = Signal(object)

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
        self.handle_radius = 5.1  # screen pixels; half the v1.3 radius
        self.preview_masks = []
        self._base = self._overlay = self._preview = None
        self._region = None
        self._region_source = None
        self._region_contours = []
        self._contours = {}
        self._contour_cache = {}
        self._base_key = None
        self._drawing = []
        self._cursor = None
        self._pan = None
        self._drag_handle = None
        self._active_vertex = None
        self._edit_geometry = None
        self._delete_origin = None
        self._drag_start = None

    def set_document(self, document, fit=True):
        self.document = document
        self.selected.clear()
        self.edit_mode = False
        self._drawing.clear()
        self._drag_handle = None
        self._active_vertex = self._edit_geometry = self._delete_origin = None
        self._base_key = None
        self._contour_cache.clear()
        self.preview_masks = []
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
                overlay[obj.mask, :3] = hex_rgb(obj.color)
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
        if self.document and masks:
            mask = np.logical_or.reduce(masks)
            out = np.zeros((*mask.shape, 4), np.uint8)
            out[mask] = [45, 138, 255, 140]
            self._preview = rgba_image(out)
        else:
            self._preview = None
        self.update()

    def set_selected(self, ids):
        ids = set(ids)
        if ids == self.selected:
            self.update()
            return
        self.selected = ids
        self._drag_handle = None
        self._active_vertex = None
        self._edit_geometry = None
        self._delete_origin = None
        if self.document:
            for obj in self.document.objects:
                if obj.id in self.selected and obj.mask is not None and obj.id not in self._contours:
                    self._contours[obj.id] = obj.contours if obj.contours is not None else mask_contours(obj.mask)
        self.update()

    def set_tool(self, tool):
        self.tool = tool
        self.tool_changed.emit(tool)
        self._drawing = []
        self._cursor = None
        self.setCursor(Qt.CursorShape.ArrowCursor if tool == "select" else Qt.CursorShape.OpenHandCursor if tool == "pan" else Qt.CursorShape.CrossCursor)
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
                painter.setPen(QPen(QColor("#245dd8" if selected else obj.color), (4.4 if selected else 2.2)/self.scale))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                if selected and self.edit_mode and obj.role != "cleaning" and not obj.locked:
                    geometry = self._geometry(obj)
                elif obj.kind != "mask":
                    geometry = {"kind": obj.kind, "points": obj.points}
                else:
                    geometry = {"kind": "contours", "contours": self._contours.get(obj.id, [])}
                self._draw_geometry(painter, geometry)
                if selected and self.edit_mode and obj.role != "cleaning" and not obj.locked:
                    painter.setBrush(QColor("white"))
                    for _, _, point in self._handles(geometry):
                        r = self.handle_radius/self.scale
                        painter.drawRect(QRectF(point[0]-r, point[1]-r, 2*r, 2*r))
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
        if self.edit_mode and self._delete_origin is not None:
            painter.setPen(QPen(QColor("#c27b16"), 1/self.scale, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(*self._delete_origin),self.vertex_delete_radius,self.vertex_delete_radius)
        if self._drawing:
            painter.setPen(QPen(QColor("#2563eb"), 1.8/self.scale))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            points = self._drawing + ([self._cursor] if self._cursor else [])
            if self.tool == "polygon":
                self._draw_geometry(painter, {"kind": "polyline", "points": points})
            elif self.tool in ("rectangle", "ellipse", "circle") and self._cursor:
                self._draw_geometry(painter, {"kind": self.tool, "points": [self._drawing[0], self._cursor]})
            elif self.tool == "point" and self.mode == "Clean":
                for p in points:
                    painter.drawEllipse(QPointF(*p), self.brush_radius, self.brush_radius)
        painter.restore()

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
            self._pan = (event.position(), QPointF(self.offset))
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        point = self.to_image(event.position())
        if point is None or self.read_only:
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
                self.object_context_requested.emit(event.globalPosition().toPoint())
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
                    self._active_vertex = (best[0], best[1])
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
                    self._active_vertex = None
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
                if len(self._drawing) >= 3 and math.dist(point,self._drawing[0]) <= 3.0 + 1e-9:
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
        if self.tool == "polygon" and not self.read_only:
            self.finish_polygon()

    def delete_vertex(self):
        obj = self._selected_object()
        if not self.edit_mode or not obj or obj.locked:
            return False
        geometry = self._geometry(obj)
        handles = self._handles(geometry)
        origin = self._delete_origin
        if origin is None and self._active_vertex is not None:
            chosen = next((h for h in handles if h[:2] == self._active_vertex), None)
            origin = chosen[2] if chosen else None
        if origin is None:
            return False
        # Each press deletes one vertex, in increasing distance from the click,
        # and never searches outside this one selected object's geometry.
        candidates = [h for h in handles if math.dist(origin, h[2]) <= self.vertex_delete_radius + 1e-9]
        if not candidates:
            self.message.emit("No more vertices within the deletion radius. Click another location or increase the radius.")
            return True
        best = min(candidates, key=lambda h: math.dist(origin, h[2]))
        ci, pi = best[:2]
        if geometry["kind"] == "contours" and not 0 <= ci < len(geometry["contours"]):
            self._active_vertex = None
            return True
        points = geometry["contours"][ci]["points"] if geometry["kind"] == "contours" else geometry.get("points", [])
        if not 0 <= pi < len(points):
            self._active_vertex = None
            return True
        if geometry["kind"] not in ("polygon", "contours") or len(points) <= 3:
            self.message.emit("Only polygon/contour vertices can be removed; retain at least three.")
            return True
        points.pop(pi)
        self._delete_origin = list(origin)
        self._drag_handle = self._edit_geometry = self._active_vertex = None
        self.geometry_changed.emit(obj.id, geometry)
        self.update()
        return True

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.tool == "polygon" and self._drawing:
            self.finish_polygon()
        elif event.key() == Qt.Key.Key_Escape:
            self._drawing, self._cursor = [], None
            self._drag_handle = self._edit_geometry = None
            self.update()
        else:
            super().keyPressEvent(event)

