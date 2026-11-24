"""Shared metric color controls for a single image or a plot group."""
from PySide6.QtWidgets import QFormLayout, QGroupBox, QLabel, QSpinBox

from .palette import MetricColorScheme
from .statistics import METRICS
from .target_size import PHYSICAL_UNITS
from .widgets import combo


class MetricColorControls(QGroupBox):
    def __init__(self, scheme=None, *, optional=False, parent=None):
        super().__init__("Color by measurement", parent)
        self.setCheckable(optional)
        if optional:
            self.setChecked(scheme is not None)
        scheme = scheme or MetricColorScheme()
        form = QFormLayout(self)
        self.metric = combo([(label, key) for key, (label, _) in METRICS.items() if key != "object_id"],
                            "maskMeasurementMetric")
        self.metric.setCurrentIndex(self.metric.findData(scheme.metric))
        self.unit = combo([("Pixels", "px"), *((u, u) for u in PHYSICAL_UNITS)], "maskMeasurementUnit")
        self.unit.setCurrentIndex(self.unit.findData(scheme.unit))
        self.count = QSpinBox()
        self.count.setObjectName("maskMeasurementColorCount")
        self.count.setRange(2, 256)
        self.count.setValue(scheme.count)
        form.addRow("Measurement", self.metric)
        form.addRow("Units", self.unit)
        form.addRow("Colors", self.count)
        note = QLabel("Values share one color scale across the included images. Objects without "
                      "a value in the chosen units keep their base colors.")
        note.setWordWrap(True)
        form.addRow(note)

    def value(self):
        if self.isCheckable() and not self.isChecked():
            return None
        return MetricColorScheme(self.metric.currentData(), self.count.value(), self.unit.currentData())
