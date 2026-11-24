"""Optional size bounds in the segmentation options dialog."""
from PySide6.QtWidgets import QCheckBox, QFormLayout, QGroupBox, QLabel, QLineEdit

from .target_size import PHYSICAL_UNITS, TargetSizeRange
from .widgets import combo


class TargetSizeControls(QGroupBox):
    def __init__(self, settings, calibration, parent=None):
        super().__init__("Target size range", parent)
        self.calibration = calibration
        layout = QFormLayout(self)
        self.metric_combo = combo([("Projected area", "area"), ("Equivalent circular diameter", "diameter")],
                                  "targetSizeMetric")
        self.metric_combo.setCurrentIndex(self.metric_combo.findData(settings.metric))
        self.unit = combo([], "targetSizeUnit")
        self.minimum = self._number(settings.minimum, "No lower limit")
        self.maximum = self._number(settings.maximum, "No upper limit")
        self.override = QCheckBox("Enter pixel sizes for this filter")
        self.override.setChecked(settings.pixel_size_x is not None)
        self.pixel_x = self._number(settings.pixel_size_x, "X size per pixel")
        self.pixel_y = self._number(settings.pixel_size_y, "Y size per pixel")
        self.pixel_unit = combo(PHYSICAL_UNITS)
        self.pixel_unit.setCurrentText(settings.pixel_unit)
        layout.addRow("Measure", self.metric_combo)
        layout.addRow("Units", self.unit)
        layout.addRow("Minimum", self.minimum)
        layout.addRow("Maximum", self.maximum)
        layout.addRow(self.override)
        layout.addRow("Pixel size X", self.pixel_x)
        layout.addRow("Pixel size Y", self.pixel_y)
        layout.addRow("Pixel size unit", self.pixel_unit)
        note = QLabel("Applies to Inside ROI, Whole Image, automatic grid and watershed previews. "
                      "Both limits are inclusive. Physical units use image calibration by default.")
        note.setWordWrap(True)
        layout.addRow(note)
        self._set_units(settings.unit)
        self.metric_combo.currentIndexChanged.connect(self._set_units)
        self.unit.currentIndexChanged.connect(self._update_fields)
        self.override.toggled.connect(self._update_fields)
        self._update_fields()

    @staticmethod
    def _number(value, placeholder):
        field = QLineEdit("" if value is None else str(value))
        field.setPlaceholderText(placeholder)
        return field

    def _set_units(self, unit=None):
        previous = unit if isinstance(unit, str) else self.unit.currentData()
        suffix = "²" if self.metric_combo.currentData() == "area" else ""
        self.unit.blockSignals(True)
        self.unit.clear()
        for name in ("px", *PHYSICAL_UNITS):
            self.unit.addItem(name + suffix, name)
        self.unit.setCurrentIndex(max(0, self.unit.findData(previous)))
        self.unit.blockSignals(False)
        self._update_fields()

    def _update_fields(self):
        physical = self.unit.currentData() != "px"
        self.override.setEnabled(physical)
        for field in (self.pixel_x, self.pixel_y, self.pixel_unit):
            field.setEnabled(physical and self.override.isChecked())

    def value(self):
        def number(field):
            return float(field.text()) if field.text().strip() else None

        try:
            minimum, maximum = number(self.minimum), number(self.maximum)
            manual = self.override.isEnabled() and self.override.isChecked() and (minimum is not None or maximum is not None)
            x, y = (number(self.pixel_x), number(self.pixel_y)) if manual else (None, None)
        except ValueError as error:
            raise ValueError("Enter numbers for the size limits and pixel sizes, or leave optional limits blank.") from error
        if manual and (x is None or y is None):
            raise ValueError("Enter both X and Y pixel sizes.")
        settings = TargetSizeRange(self.metric_combo.currentData(), self.unit.currentData(),
                                   minimum, maximum, x, y, self.pixel_unit.currentData())
        settings.pixel_bounds(self.calibration)
        return settings
