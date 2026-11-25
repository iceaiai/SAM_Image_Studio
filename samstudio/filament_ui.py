"""Filament group actions, detected endpoints and drawn connections."""
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QInputDialog

from .filaments import FilamentLink, fragment_traces, open_endpoints, resolve_bridge


class FilamentWorkflowMixin:
    def _init_filament_ui(self, edit_menu):
        menu = edit_menu.addMenu("Filament")
        self.mark_filament_action = self._action("Mark group as Filament…", lambda: self.set_filament_group(True))
        self.unmark_filament_action = self._action("Use particle measurements for group…",
                                                  lambda: self.set_filament_group(False))
        self.connect_filament_action = self._action("Connect visible fragments…", self.begin_filament_link)
        self.draw_filament_action = self._action("Draw filament connection…", self.begin_drawn_filament_link)
        self.disconnect_filament_action = self._action("Disconnect selected fragments", self.disconnect_filaments)
        for action in (self.mark_filament_action, self.unmark_filament_action, self.connect_filament_action,
                       self.draw_filament_action, self.disconnect_filament_action):
            menu.addAction(action)
        self.canvas.filament_end_picked.connect(self.pick_filament_end)
        self.canvas.filament_connection_drawn.connect(self.finish_drawn_filament_link)
        self.canvas.tool_changed.connect(self._filament_tool_changed)
        self._filament_start = None

    def _filament_tool_changed(self, tool):
        if tool != "select" and self.canvas.filament_link_active:
            self.cancel_filament_link()

    def _refresh_filament_controls(self, doc, selected):
        editing = doc is not None and self.canvas.edit_mode and not self.busy
        groups = [g for g in doc.groups if g.id != doc.background_group_id] if doc else []
        self.mark_filament_action.setEnabled(editing and any(not g.filament for g in groups))
        self.unmark_filament_action.setEnabled(editing and any(g.filament for g in groups))
        can_connect = editing and self._can_link_filaments(selected)
        self.connect_filament_action.setEnabled(can_connect)
        self.draw_filament_action.setEnabled(can_connect)
        selected_ids = {obj.id for obj in selected if not obj.locked}
        self.disconnect_filament_action.setEnabled(editing and bool(self._selected_filament_links(selected_ids)))

    def set_filament_group(self, enabled):
        doc = self.document
        if self.busy or not self.canvas.edit_mode or doc is None:
            return
        groups = [g for g in doc.groups if g.id != doc.background_group_id and g.filament != enabled]
        if not groups:
            return
        self.cancel_filament_link()
        index = next((i for i, group in enumerate(groups) if group.id == doc.active_group), 0)
        title = "Mark group as Filament" if enabled else "Use particle measurements"
        prompt = ("Choose the group whose area masks describe filaments." if enabled else
                  "Choose a group. Its saved filament connections will be removed.")
        name, ok = QInputDialog.getItem(self, title, prompt, [g.name for g in groups], index, False)
        if ok:
            group = next(g for g in groups if g.name == name)
            self._commit(title, lambda: doc.set_filament_group(group.id, enabled))

    def _can_link_filaments(self, objects):
        if self.document is None or len(objects) != 2:
            return False
        first, second = objects
        return (first.group_id == second.group_id and first.group_id != self.document.background_group_id
                and self.document.get_group(first.group_id).filament
                and all(obj.role == "object" and obj.mask is not None and obj.visible and not obj.locked
                        for obj in objects))

    def _filament_endpoints(self, ids):
        pixel_basis = np.eye(2)
        return {obj.id: open_endpoints(fragment_traces(obj, pixel_basis))
                for obj in self.document.foreground_objects()
                if obj.id in ids and obj.mask is not None and self.document.get_group(obj.group_id).filament}

    def _filament_pair(self):
        selected = self.selected_objects()
        if self.busy or not self.canvas.edit_mode or not self._can_link_filaments(selected):
            return None
        first, second = selected
        if (first.mask & second.mask).any():
            self.notify("Connect visible fragments", "Choose two separate visible masks.")
            return None
        return first, second

    def begin_filament_link(self):
        selected = self._filament_pair()
        if selected is None:
            return
        first, second = selected
        doc = self.document
        ids = {ident for link in doc.filament_links if not link.drawn for ident, _ in link.ends}
        endpoints = self._filament_endpoints(ids | {first.id, second.id})
        if endpoints.get(first.id) is None or endpoints.get(second.id) is None:
            self._start_drawn_filament_link()
            return
        masks = {obj.id: obj.mask for obj in doc.foreground_objects()}
        used = set()
        for link in doc.filament_links:
            for ident, index, point in resolve_bridge(link, endpoints, masks) or ():
                pair = endpoints.get(ident)
                if index is None and pair is not None:
                    index = int(np.argmin(np.linalg.norm(pair - point, axis=1)))
                if index is not None:
                    used.add((ident, index))
        picks = {}
        for obj in (first, second):
            available = [(i, point) for i, point in enumerate(endpoints[obj.id]) if (obj.id, i) not in used]
            if not available:
                self.notify("Connect visible fragments", "Each selected fragment needs a free end.")
                return
            picks[obj.id] = available
        self._prepare_filament_link()
        self.canvas.filament_picks = picks
        self.canvas.update()
        self._refresh_controls()
        self.statusBar().showMessage("Click a marked end on each fragment. Esc cancels.", 15000)

    def _prepare_filament_link(self):
        self.cancel_filament_link()
        self.canvas.set_tool("select")
        self.tool_actions["select"].setChecked(True)

    def begin_drawn_filament_link(self):
        if self._filament_pair() is not None:
            self._start_drawn_filament_link()

    def _start_drawn_filament_link(self):
        self._prepare_filament_link()
        self.canvas.draw_filament_connection = True
        self.canvas.setCursor(Qt.CursorShape.CrossCursor)
        self._refresh_controls()
        self.statusBar().showMessage("Drag from just inside one visible tip to just inside the facing tip. Esc cancels.", 20000)

    def finish_drawn_filament_link(self, start, end):
        if not self.canvas.draw_filament_connection or self.busy:
            return
        selected = self.selected_objects()
        if not self._can_link_filaments(selected):
            self.cancel_filament_link()
            self._refresh_controls()
            return
        if start is not None and end is not None:
            x0, y0 = map(int, start)
            x1, y1 = map(int, end)
            first, second = selected
            if second.mask[y0, x0]:
                first, second = second, first
            if first.mask[y0, x0] and second.mask[y1, x1]:
                link = FilamentLink(first.id, second.id, np.asarray(start) - .5, np.asarray(end) - .5, drawn=True)
                if resolve_bridge(link, {}, {first.id: first.mask, second.id: second.mask}) is not None:
                    self._connect_filament_link(link)
                    return
        self.statusBar().showMessage("Start inside one selected mask and release inside the other, across their gap.", 12000)

    def pick_filament_end(self, ident, index):
        picks = self.canvas.filament_picks
        if self.busy or ident not in picks:
            return
        point = dict(picks[ident])[index]
        if self._filament_start is None or self._filament_start[0] == ident:
            self._filament_start = (ident, point)
            self.canvas.filament_first = point
            self.canvas.update()
            self.statusBar().showMessage("Click the facing end of the other fragment.", 15000)
            return
        other_id, other_point = self._filament_start
        link = FilamentLink(other_id, ident, other_point, point)
        self._connect_filament_link(link)

    def _connect_filament_link(self, link):
        doc = self.document
        self.cancel_filament_link()
        if self._commit("Connect filament fragments", lambda: doc.connect_filament(link)):
            self.statusBar().showMessage("Fragments will be measured as one filament.", 8000)

    def cancel_filament_link(self):
        active = self.canvas.filament_link_active
        if self.canvas.draw_filament_connection and self.canvas.tool == "select":
            self.canvas.setCursor(Qt.CursorShape.ArrowCursor)
        self._filament_start = None
        self.canvas.filament_picks = {}
        self.canvas.filament_first = None
        self.canvas.draw_filament_connection = False
        self.canvas.filament_connection_draft = None
        if active:
            self.canvas.update()
        return active

    def _selected_filament_links(self, ids):
        if self.document is None:
            return []
        return [link for link in self.document.filament_links
                if (len(ids) == 1 and bool({link.first_id, link.second_id} & ids)) or
                   {link.first_id, link.second_id} <= ids]

    def disconnect_filaments(self):
        doc = self.document
        if doc is None or self.busy or not self.canvas.edit_mode:
            return
        links = self._selected_filament_links({obj.id for obj in self.selected_objects() if not obj.locked})
        if not links:
            return
        affected = {ident for link in links for ident, _ in link.ends}
        if any(obj.id in affected and obj.locked for obj in doc.objects):
            self.notify("Disconnect fragments", "Unlock the connected fragments first.")
            return
        self.cancel_filament_link()
        self._commit("Disconnect filament fragments",
                     lambda: setattr(doc, "filament_links", [link for link in doc.filament_links if link not in links]))

    def _refresh_filament_bridges(self):
        doc = self.document
        bridges = []
        if doc is not None and self.canvas.edit_mode and doc.filament_links:
            ids = {ident for link in doc.filament_links if not link.drawn for ident, _ in link.ends}
            endpoints = self._filament_endpoints(ids)
            masks = {obj.id: obj.mask for obj in doc.foreground_objects()}
            visible = {obj.id for obj in doc.objects if obj.visible}
            for link in doc.filament_links:
                if {link.first_id, link.second_id} <= visible:
                    bridge = resolve_bridge(link, endpoints, masks)
                    if bridge is not None:
                        points = tuple(point + .5 if link.drawn else point for _, _, point in bridge)
                        bridges.append(points)
        self.canvas.filament_bridges = bridges
