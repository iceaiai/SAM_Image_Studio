"""Named image cohorts for shared mask colors and statistics."""
from dataclasses import asdict, dataclass
import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout)

from .metric_colors_ui import MetricColorControls
from .palette import MetricColorScheme, base_mask_colors, document_mask_colors, metric_palette
from .widgets import buttons, combo


@dataclass(frozen=True)
class PlotGroup:
    name: str
    frames: dict[str, str]
    scheme: MetricColorScheme | None

    def __post_init__(self):
        if not isinstance(self.name, str) or not 1 <= len(self.name.strip()) <= 80:
            raise ValueError("Enter a plot group name of 1–80 characters.")
        if not isinstance(self.frames, dict) or not self.frames:
            raise ValueError("Include at least one image or frame in the plot group.")
        if any(not isinstance(key, str) or not isinstance(label, str) for key, label in self.frames.items()):
            raise ValueError("Invalid plot group frames.")


class PlotGroupDialog(QDialog):
    def __init__(self, documents, selected, existing=None, names=(), parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit plot group" if existing else "Create plot group")
        self.resize(600, 530)
        self.existing = existing
        self.names = {name.casefold() for name in names if existing is None or name != existing.name}
        self.remove_requested = False
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(existing.name if existing else "")
        self.name.setObjectName("plotGroupName")
        self.name.setMaxLength(80)
        form.addRow("Name", self.name)
        layout.addLayout(form)
        layout.addWidget(QLabel("Images and frames included in this plot group"))
        self.frames = QListWidget()
        self.frames.setObjectName("plotGroupFrames")
        layout.addWidget(self.frames, 1)
        previous = existing.frames if existing else {}
        checked = previous if existing else selected
        open_frames = {d.frame.key: f"{Path(d.frame.source_path).name} · {d.frame.frame_label}"
                       for d in documents}
        for key, label in (open_frames | {k: v for k, v in previous.items() if k not in open_frames}).items():
            item = QListWidgetItem(label if key in open_frames else label + " (closed)")
            item.setData(Qt.ItemDataRole.UserRole, (key, label))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if key in checked else Qt.CheckState.Unchecked)
            self.frames.addItem(item)
        self.metric = MetricColorControls(existing.scheme if existing else MetricColorScheme(),
                                          optional=True, parent=self)
        layout.addWidget(self.metric)
        controls = buttons(self, layout)
        if existing:
            remove = controls.addButton("Remove plot group", QDialogButtonBox.ButtonRole.DestructiveRole)
            remove.clicked.connect(self._remove)

    def value(self):
        frames = dict(self.frames.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.frames.count())
                      if self.frames.item(i).checkState() == Qt.CheckState.Checked)
        name = self.name.text().strip()
        if name.casefold() in self.names:
            raise ValueError("Choose a unique plot group name.")
        return PlotGroup(name, frames, self.metric.value())

    def accept(self):
        try:
            self.value()
        except ValueError as error:
            QMessageBox.warning(self, "Plot group", str(error))
            return
        super().accept()

    def _remove(self):
        self.remove_requested = True
        super().accept()


class PlotGroupWorkflowMixin:
    def _init_plot_groups(self):
        self.plot_groups = {}
        try:
            saved = json.loads(self.settings.value("plot_groups", "[]", type=str))
            for entry in saved:
                scheme = MetricColorScheme(**entry["scheme"]) if entry.get("scheme") is not None else None
                group = PlotGroup(entry["name"], entry["frames"], scheme)
                self.plot_groups[group.name] = group
        except (KeyError, TypeError, ValueError, AttributeError):
            # A preferences file predating this feature or an invalid saved cohort
            # must not prevent opening the image workspace.
            pass
        active = self.settings.value("active_plot_group", "", type=str)
        self.active_plot_group = active if active in self.plot_groups else None
        self._plot_palette_cache = (None, None)

        self.create_plot_group_action = self._action("Create plot group from selected images…", self.create_plot_group)
        self.edit_plot_group_action = self._action("Edit active plot group…", self.edit_plot_group)
        self.statistics_menu.addSeparator()
        self.statistics_menu.addAction(self.create_plot_group_action)
        self.statistics_menu.addAction(self.edit_plot_group_action)
        row = QHBoxLayout()
        self.plot_group_combo = combo([], "workspacePlotGroup")
        self.plot_group_combo.setSizeAdjustPolicy(self.plot_group_combo.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.plot_group_combo.setToolTip("Choose which plot group supplies canvas measurement colors.")
        row.addWidget(QLabel("Plot group"))
        row.addWidget(self.plot_group_combo, 1)
        create = QPushButton("Create…")
        create.clicked.connect(self.create_plot_group)
        row.addWidget(create)
        self.edit_plot_group_button = QPushButton("Edit…")
        self.edit_plot_group_button.clicked.connect(self.edit_plot_group)
        row.addWidget(self.edit_plot_group_button)
        self.files_dock.widget().layout().addLayout(row)
        self._refresh_plot_group_choices()
        self.plot_group_combo.currentIndexChanged.connect(
            lambda: self.set_active_plot_group(self.plot_group_combo.currentData())
        )
        self.files_tree.itemSelectionChanged.connect(self._workspace_image_selection_changed)

    def _refresh_plot_group_choices(self):
        self.plot_group_combo.blockSignals(True)
        self.plot_group_combo.clear()
        self.plot_group_combo.addItem("No plot group", None)
        for name in sorted(self.plot_groups, key=str.casefold):
            self.plot_group_combo.addItem(name, name)
        index = self.plot_group_combo.findData(self.active_plot_group)
        self.plot_group_combo.setCurrentIndex(max(0, index))
        self.plot_group_combo.blockSignals(False)

    def _workspace_image_selection_changed(self):
        if self._updating:
            return
        self._refresh_statistics()

    def set_active_plot_group(self, name):
        if name not in self.plot_groups:
            name = None
        if self.active_plot_group == name:
            return
        self.active_plot_group = name
        self.settings.setValue("active_plot_group", name or "")
        self._refresh_plot_group_choices()
        self._refresh()

    def create_plot_group(self):
        if self.busy or not self.documents:
            return None
        dialog = PlotGroupDialog(self.documents.values(), self.selected_images(), names=self.plot_groups, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        group = dialog.value()
        self.plot_groups[group.name] = group
        self._save_plot_groups(group.name)
        return group

    def edit_plot_group(self):
        if self.busy or self.active_plot_group is None:
            return
        active = self.active_plot_group
        dialog = PlotGroupDialog(self.documents.values(), self.selected_images(), self.plot_groups[active],
                                 self.plot_groups, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            group = None if dialog.remove_requested else dialog.value()
            del self.plot_groups[active]
            if group is not None:
                self.plot_groups[group.name] = group
            self._save_plot_groups(group.name if group is not None else None)

    def _save_plot_groups(self, active):
        self.active_plot_group = active
        self._plot_palette_cache = (None, None)
        self.settings.setValue("plot_groups", json.dumps([asdict(group) for group in self.plot_groups.values()]))
        self.settings.setValue("active_plot_group", active or "")
        self.settings.sync()
        self._refresh_plot_group_choices()
        self._refresh()

    def _active_plot_palette(self):
        group = self.plot_groups.get(self.active_plot_group)
        if group is None or group.scheme is None:
            return None
        members = [doc for key, doc in self.documents.items() if key in group.frames]
        key = (group.name, group.scheme, tuple((doc, doc.revision) for doc in members))
        previous, palette = self._plot_palette_cache
        if key != previous:
            palette = metric_palette(members, group.scheme)
            self._plot_palette_cache = (key, palette)
        return palette

    def _mask_colors(self, document):
        group = self.plot_groups.get(self.active_plot_group)
        if group is None or group.scheme is None or document.frame.key not in group.frames:
            return document_mask_colors(document)
        colors = base_mask_colors(document)
        colors.update(self._active_plot_palette().colors.get(document.frame.key, {}))
        return colors

    def _refresh_plot_group_controls(self):
        self.create_plot_group_action.setEnabled(bool(self.documents) and not self.busy)
        group = self.plot_groups.get(self.active_plot_group)
        can_edit = group is not None and not self.busy
        self.edit_plot_group_button.setEnabled(can_edit)
        self.edit_plot_group_action.setEnabled(can_edit)
        description = "Choose which plot group supplies canvas measurement colors."
        if group is not None:
            opened = len(group.frames.keys() & self.documents.keys())
            description = f"{group.name} · {opened}/{len(group.frames)} frames open"
            palette = self._active_plot_palette()
            if palette is not None:
                description += "\n" + palette.description
        self.plot_group_combo.setToolTip(description)
