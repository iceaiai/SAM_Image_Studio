"""Live scale-bar preview and canvas painting in image coordinates."""
from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainterPath, QPen
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFontComboBox, QFormLayout, QLabel, QLineEdit, QSpinBox

from .scale_bar import SCALE_BAR_POSITIONS, ScaleBar
from .target_size import PHYSICAL_UNITS
from .widgets import combo


def scale_bar_layout(bar, calibration, shape):
    """Return font, label and line endpoints. Reject a layout that cannot fit."""
    height, width = shape
    length = bar.length_in_pixels(calibration)
    font = QFont(bar.font_family)
    font.setPixelSize(bar.font_size)
    metrics = QFontMetricsF(font)
    label = f"{bar.length:g} {bar.unit}"
    ink = metrics.tightBoundingRect(label)
    half_width = max(length / 2 + bar.line_width / 2, ink.width() / 2 + 1)
    margin = max(4., min(width, height) * .04)
    gap = max(2., bar.line_width / 2)
    stack_height = ink.height() + gap + bar.line_width + 2
    if 2 * (half_width + margin) > width or stack_height + 2 * margin > height:
        raise ValueError("The scale bar and label must fit inside the image.")
    center = width - margin - half_width if bar.position.endswith("right") else margin + half_width
    top = height - margin - stack_height if bar.position.startswith("bottom") else margin
    baseline = QPointF(center - ink.center().x(), top + 1 - ink.y())
    line_y = top + 1 + ink.height() + gap + bar.line_width / 2
    return font, label, baseline, QPointF(center - length / 2, line_y), QPointF(center + length / 2, line_y)


def draw_scale_bar(painter, bar, calibration, shape):
    try:
        font, label, baseline, start, end = scale_bar_layout(bar, calibration, shape)
    except ValueError:
        return
    painter.save()
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor("black"), bar.line_width + 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
    painter.drawLine(start - QPointF(1, 0), end + QPointF(1, 0))
    painter.setPen(QPen(QColor("white"), bar.line_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
    painter.drawLine(start, end)
    text = QPainterPath()
    text.addText(baseline, font, label)
    painter.strokePath(text, QPen(QColor("black"), 2, Qt.PenStyle.SolidLine,
                                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.fillPath(text, QColor("white"))
    painter.restore()


class ScaleBarDialog(QDialog):
    preview_changed = Signal(object)

    def __init__(self, document, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Scale bar")
        self.calibration = document.calibration
        self.shape = document.frame.shape
        pixel_length = max(1, self.shape[1] // 5)
        default = ScaleBar(pixel_length, "px", line_width=max(1, min(200, min(self.shape) // 108)),
                           font_size=max(1, min(500, min(self.shape) // 25)))
        if self.calibration.valid:
            length_per_pixel = default.length / ScaleBar(1, self.calibration.length_unit).length_in_pixels(self.calibration)
            default = ScaleBar(float(f"{length_per_pixel:.2g}"), self.calibration.length_unit,
                               default.line_width, font_size=default.font_size)
        bar = document.scale_bar or default
        unit_choices = list(dict.fromkeys(("px", *PHYSICAL_UNITS, bar.unit)))
        layout = QFormLayout(self)
        self.length = QLineEdit(str(bar.length))
        self.length.setObjectName("scaleBarLength")
        self.unit = combo(unit_choices, "scaleBarUnit")
        self.unit.setCurrentText(bar.unit)
        self.line_width = QSpinBox()
        self.line_width.setRange(1, 200)
        self.line_width.setValue(bar.line_width)
        self.line_width.setSuffix(" px")
        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(QFont(bar.font_family))
        self.font_size = QSpinBox()
        self.font_size.setRange(1, 500)
        self.font_size.setValue(bar.font_size)
        self.font_size.setSuffix(" px")
        self.position = combo([(label, key) for key, label in SCALE_BAR_POSITIONS.items()])
        self.position.setCurrentIndex(self.position.findData(bar.position))
        layout.addRow("Length", self.length)
        layout.addRow("Units", self.unit)
        layout.addRow("Line width", self.line_width)
        layout.addRow("Font", self.font_combo)
        layout.addRow("Font size", self.font_size)
        layout.addRow("Position", self.position)
        self.notice = QLabel()
        self.notice.setWordWrap(True)
        layout.addRow(self.notice)
        self.controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.controls.button(QDialogButtonBox.StandardButton.Ok).setText("Apply")
        self.controls.accepted.connect(self.accept)
        self.controls.rejected.connect(self.reject)
        layout.addRow(self.controls)
        self.length.textChanged.connect(self.update_preview)
        self.unit.currentIndexChanged.connect(self.update_preview)
        self.line_width.valueChanged.connect(self.update_preview)
        self.font_combo.currentFontChanged.connect(self.update_preview)
        self.font_size.valueChanged.connect(self.update_preview)
        self.position.currentIndexChanged.connect(self.update_preview)
        self.update_preview()

    def update_preview(self, *args):
        try:
            length = float(self.length.text())
        except ValueError:
            self._set_preview(None, "Enter a numeric length.")
            return
        try:
            bar = ScaleBar(length, self.unit.currentText(), self.line_width.value(),
                           self.font_combo.currentFont().family(), self.font_size.value(), self.position.currentData())
            scale_bar_layout(bar, self.calibration, self.shape)
        except ValueError as error:
            self._set_preview(None, str(error))
            return
        self._set_preview(bar, f"Preview on image · {bar.length_in_pixels(self.calibration):.4g} pixels across")

    def _set_preview(self, bar, notice):
        self.value = bar
        self.notice.setText(notice)
        self.controls.button(QDialogButtonBox.StandardButton.Ok).setEnabled(bar is not None)
        self.preview_changed.emit(bar)
