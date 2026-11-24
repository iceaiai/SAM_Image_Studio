"""Shared Qt form controls."""

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (QComboBox, QDialogButtonBox, QStyle, QStyledItemDelegate,
    QStyleOptionComboBox, QStylePainter)

class CheckedComboDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option,index)
        if index.row() == self.parent().currentIndex():
            option.text += "  √"
        option.palette.setColor(QPalette.ColorRole.Text,QColor("#20344f"))
        option.palette.setColor(QPalette.ColorRole.HighlightedText,QColor("#20344f"))
        option.palette.setColor(QPalette.ColorRole.Highlight,QColor("#dce9ff"))


class CheckedComboBox(QComboBox):
    """The check is visual only, so currentText and saved values stay stable."""
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setItemDelegate(CheckedComboDelegate(self))
        self.view().setStyleSheet("QAbstractItemView { color:#20344f; background:white; selection-color:#20344f; selection-background-color:#dce9ff; }")

    def paintEvent(self,event):
        painter=QStylePainter(self)
        option=QStyleOptionComboBox();self.initStyleOption(option)
        if self.currentIndex() >= 0:option.currentText += "  √"
        option.palette.setColor(QPalette.ColorRole.ButtonText,QColor("#20344f"))
        painter.drawComplexControl(QStyle.ComplexControl.CC_ComboBox,option)
        painter.drawControl(QStyle.ControlElement.CE_ComboBoxLabel,option)

    def minimumSizeHint(self):
        size=super().minimumSizeHint();size.setWidth(size.width()+24);return size

    def sizeHint(self):
        size=super().sizeHint();size.setWidth(size.width()+24);return size


def combo(items, name=""):
    out = CheckedComboBox()
    out.setObjectName(name)
    for item in items:
        if isinstance(item, tuple):
            out.addItem(item[0], item[1])
        else:
            out.addItem(item, item)
    return out


def buttons(dialog, layout):
    controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    controls.accepted.connect(dialog.accept)
    controls.rejected.connect(dialog.reject)
    layout.addWidget(controls)
    return controls
