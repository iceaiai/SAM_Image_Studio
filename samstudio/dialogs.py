from __future__ import annotations

import copy
import math
from pathlib import Path
import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPixmap, QPalette
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QSlider, QSpinBox, QVBoxLayout, QWidget, QStyledItemDelegate,
    QStyle, QStyleOptionComboBox, QStylePainter, QGridLayout, QButtonGroup, QToolButton)

from .canvas import rgb_image, rgba_image
from .domain import Calibration, LENGTH_UNITS
from .exports import render_mask_pixels, write_measurement_csv
from .inference import CATALOG
from .processing import display_rgb, measurements, refine_objects, refinement_geometry
from .palette import LUT20


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


class ModelDialog(QDialog):
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Model manager")
        self.resize(610, 360)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.family = combo(list(dict.fromkeys(s.family for s in CATALOG)), "modelFamily")
        self.variant = QComboBox()
        self.variant.setObjectName("modelVariant")
        self.device = combo([("CPU (default)", "cpu"), ("NVIDIA CUDA GPU (Conda)", "cuda"), ("Automatic device (GPU only in Conda)", "auto")], "modelDevice")
        self.path = QLineEdit()
        self.path.setObjectName("modelCheckpoint")
        self.path.setPlaceholderText("Empty = download official weights on demand")
        browse = QPushButton("Browse .pt / .pth…")
        browse.clicked.connect(self.browse)
        form.addRow("Model family", self.family)
        form.addRow("Variant", self.variant)
        form.addRow("Execution device", self.device)
        form.addRow("Local checkpoint", self.path)
        form.addRow("", browse)
        layout.addLayout(form)
        self.info = QLabel()
        self.info.setWordWrap(True)
        layout.addWidget(self.info)
        self.controls = buttons(self, layout)
        self.controls.button(QDialogButtonBox.StandardButton.Ok).setText("Download / load")
        self.family.currentTextChanged.connect(self.change_family)
        self.change_family()
        if engine.spec:
            self.family.setCurrentText(engine.spec.family)
            self.variant.setCurrentText(engine.spec.variant)
            self.device.setCurrentIndex(1 if engine.device.startswith("cuda") else 0)

    def change_family(self):
        self.variant.clear()
        for spec in CATALOG:
            if spec.family == self.family.currentText():
                self.variant.addItem(spec.variant, spec)
        self.info.setText("SAM3 / SAM3.1 are optional native CUDA backends. It needs the separate SAM3 environment and approved Hugging Face checkpoint access. This release does not advertise SAM3 CPU support." if self.family.currentText() in ("SAM3", "SAM3.1") else
                          "CPU works without an NVIDIA GPU. A .pt or .pth checkpoint must match the selected family and variant. Downloaded weights are cached for later use. CPU automatic segmentation starts with an 8 × 8 prompt grid.")

    def browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select compatible checkpoint", "", "PyTorch checkpoint (*.pt *.pth)")
        if path:
            self.path.setText(path)

    def values(self):
        return self.variant.currentData(), self.device.currentData(), self.path.text().strip() or None


class CalibrationDialog(QDialog):
    def __init__(self, calibration, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image calibration")
        layout = QVBoxLayout(self)
        self.enabled = QCheckBox("This image has a valid physical pixel size")
        self.enabled.setChecked(calibration.valid)
        layout.addWidget(self.enabled)
        form = QFormLayout()
        self.x, self.y = QDoubleSpinBox(), QDoubleSpinBox()
        for control in (self.x, self.y):
            control.setDecimals(9)
            control.setRange(.000000001, 1e12)
        self.x.setValue(calibration.pixel_size_x or 1)
        self.y.setValue(calibration.pixel_size_y or 1)
        units=["pm","nm","µm","mm","m","Å"]
        self.unit = combo(units)
        equivalent=next((u for u in units if LENGTH_UNITS.get(u)==LENGTH_UNITS.get(calibration.length_unit)),"nm")
        self.unit.setCurrentText(equivalent)
        form.addRow("X pixel size", self.x)
        form.addRow("Y pixel size", self.y)
        form.addRow("Length unit per pixel", self.unit)
        layout.addLayout(form)
        label = QLabel(f"Current source: {calibration.source}\nChanges apply to this dataset/frame. Both axis scales determine area.")
        label.setWordWrap(True)
        layout.addWidget(label)
        buttons(self, layout)

    def value(self):
        return Calibration(self.x.value(), self.y.value(), self.unit.currentText(), "user override", self.enabled.isChecked())


class BrightnessDialog(QDialog):
    changed = Signal(float, float)

    def __init__(self, brightness=0, contrast=1, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Display brightness and contrast")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.brightness = QSlider(Qt.Orientation.Horizontal)
        self.brightness.setRange(-100, 100)
        self.brightness.setValue(round(brightness*100))
        self.contrast = QSlider(Qt.Orientation.Horizontal)
        self.contrast.setRange(10, 400)
        self.contrast.setValue(round(contrast*100))
        form.addRow("Brightness", self.brightness)
        form.addRow("Contrast", self.contrast)
        layout.addLayout(form)
        layout.addWidget(QLabel("Display only. Source pixels and the default SAM normalization remain unchanged."))
        for control in (self.brightness, self.contrast):
            control.valueChanged.connect(lambda: self.changed.emit(self.brightness.value()/100, self.contrast.value()/100))
        reset = QPushButton("Reset display")
        reset.clicked.connect(lambda: (self.brightness.setValue(0), self.contrast.setValue(100)))
        layout.addWidget(reset)
        buttons(self, layout)


class InferenceOptionsDialog(QDialog):
    def __init__(self, options, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Segmentation options")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.grid = QSpinBox();self.grid.setRange(2, 64);self.grid.setValue(options["grid"])
        self.score = QDoubleSpinBox();self.score.setRange(0, 1);self.score.setSingleStep(.05);self.score.setValue(options["min_score"])
        self.area = QSpinBox();self.area.setRange(1, 100_000_000);self.area.setValue(options["min_area"])
        self.maximum = QSpinBox();self.maximum.setRange(1, 10_000);self.maximum.setValue(options["max_objects"])
        for title, widget in [("Automatic grid points / side",self.grid),("Minimum model score",self.score),("Minimum area (pixel²)",self.area),("Maximum candidate masks",self.maximum)]:
            form.addRow(title,widget)
        layout.addLayout(form)
        layout.addWidget(QLabel("Grid settings control automatic and whole-image exemplar candidate searches.\nSingle object uses native SAM inference. Larger grids take longer on CPU."))
        buttons(self,layout)

    def values(self):
        return {"grid":self.grid.value(),"min_score":self.score.value(),"min_area":self.area.value(),"max_objects":self.maximum.value()}


class RefinementDialog(QDialog):
    def __init__(self, document, ids, method, parent=None):
        super().__init__(parent)
        self.document, self.ids, self.method = document, list(ids), method
        self.results = None
        self.contours = {}
        self.setWindowTitle("Fill holes" if method == "holes" else "Smooth edges")
        self.resize(650, 470)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Selected objects: {len(ids)}. This edits masks and preserves acquired image pixels."))
        form = QFormLayout()
        self.value = QDoubleSpinBox()
        self.value.setDecimals(3)
        self.value.setRange(0 if method == "holes" else .1, 1e12 if method == "holes" else 50)
        self.value.setValue(0 if method == "holes" else 1)
        self.units = combo(["pixel²"] + ([document.calibration.length_unit + "²"] if document.calibration.valid else []))
        form.addRow("Maximum hole area (0 = all)" if method == "holes" else "Smoothing radius (pixels)",self.value)
        if method == "holes":
            form.addRow("Area units",self.units)
        layout.addLayout(form)
        self.preview = QLabel("Choose settings and click Preview.")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(230)
        layout.addWidget(self.preview)
        self.summary = QLabel();self.summary.setWordWrap(True);layout.addWidget(self.summary)
        preview = QPushButton("Preview")
        preview.clicked.connect(self.calculate)
        layout.addWidget(preview)
        self.controls = buttons(self, layout)
        self.controls.button(QDialogButtonBox.StandardButton.Ok).setText("Apply")
        self.controls.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.value.valueChanged.connect(self.invalidate)
        self.units.currentIndexChanged.connect(self.invalidate)

    def invalidate(self):
        self.results = None
        self.contours = {}
        self.controls.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

    def calculate(self):
        try:
            value = self.value.value()
            if self.method == "holes":
                value = value / self.document.calibration.pixel_area if value and self.units.currentText() != "pixel²" else value
                value = value or None
            self.results = refine_objects(self.document, self.ids, self.method, value)
            self.contours = {}
            if self.method == "smooth":
                claimed = np.zeros(self.document.frame.shape, bool)
                for obj in self.document.objects:
                    if obj.id not in self.results:
                        continue
                    protected = self.document.protected_mask([obj.id]) | claimed
                    from scipy.ndimage import binary_fill_holes
                    protected |= binary_fill_holes(obj.mask) & ~obj.mask
                    result, curves = refinement_geometry(self.results[obj.id], value, protected)
                    self.results[obj.id] = result
                    self.contours[obj.id] = curves
                    claimed |= result
            old = [o for o in self.document.objects if o.id in self.results]
            before = np.logical_or.reduce([o.mask for o in old])
            after = np.logical_or.reduce(list(self.results.values()))
            rgb = np.zeros((*before.shape,3),np.uint8)
            rgb[before] = [110,125,140]
            rgb[after] = [20,154,126]
            rgb[before & ~after] = [226,79,79]
            self.preview.setPixmap(QPixmap.fromImage(rgb_image(rgb)).scaled(610,240,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
            old_area = sum(o.pixel_area for o in old)
            new_area = sum(int(m.sum()) for m in self.results.values())
            self.summary.setText(f"Total area: {old_area:,} → {new_area:,} pixel² ({(new_area-old_area)/max(1,old_area)*100:+.2f}%). Green = resulting masks. Red = removed pixels. Apply refreshes measurements and statistics.")
            self.controls.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
        except Exception as error:
            self.results = None
            self.summary.setText(str(error))
            self.controls.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)


class ImageExportDialog(QDialog):
    def __init__(self, documents, allow_none=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Dataset image options" if allow_none else "Save image versions")
        layout = QVBoxLayout(self)
        self.original = QCheckBox("Uncleaned image (current orientation)" if allow_none else "Original acquired image");self.original.setObjectName("exportOriginalImage");self.original.setChecked(True)
        self.cleaned = QCheckBox("Processed image (cleaning / smoothing / rotation)");self.cleaned.setObjectName("exportCleanedImage")
        self.cleaned.setEnabled(all(d.working is not None for d in documents))
        layout.addWidget(self.original);layout.addWidget(self.cleaned)
        info = ("Choose either version or both. When both are selected, dataset annotations reference the processed image in images/ and uncleaned copies in the current orientation go in original_images/. Uncheck both to export annotations only. Dataset PNGs use the display normalization."
                if allow_none else "Choose either version or both. TIFF preserves the source data type, dimensions and calibration. Original acquired pixels stay unchanged.")
        if not self.cleaned.isEnabled():
            info += " Apply cleaning, smoothing or rotation to every selected image to enable the processed version."
        label = QLabel(info);label.setWordWrap(True);layout.addWidget(label)
        self.controls = buttons(self, layout)
        self.controls.button(QDialogButtonBox.StandardButton.Ok).setText("Choose folder")
        def refresh():
            self.controls.button(QDialogButtonBox.StandardButton.Ok).setEnabled(allow_none or self.original.isChecked() or self.cleaned.isChecked())
        self.original.toggled.connect(refresh);self.cleaned.toggled.connect(refresh)

    def values(self):
        return {"save_original_image": self.original.isChecked(), "save_cleaned_image": self.cleaned.isChecked()}


class SmoothImageDialog(QDialog):
    def __init__(self, document, has_selection=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Smooth image pixels")
        layout = QVBoxLayout(self);form = QFormLayout()
        self.method = combo([("Gaussian blur", "gaussian"), ("Median filter", "median")], "smoothImageMethod")
        self.sigma = QDoubleSpinBox();self.sigma.setRange(.1,20);self.sigma.setValue(1);self.sigma.setSuffix(" px")
        self.kernel = combo([(f"{n} × {n}", n) for n in range(3,32,2)], "smoothImageKernel")
        self.source = combo([("Current processed image", "cleaned"), ("Uncleaned image (current orientation)", "original")], "smoothImageSource")
        self.source.model().item(0).setEnabled(document.working is not None)
        self.source.setCurrentIndex(0 if document.working is not None else 1)
        self.scope = combo([("Whole image", "whole"), ("Current region / selected objects", "selection")], "smoothImageScope")
        self.scope.model().item(1).setEnabled(has_selection)
        if has_selection:self.scope.setCurrentIndex(1)
        for title, control in (("Filter",self.method),("Gaussian sigma",self.sigma),("Median window",self.kernel),("Input image",self.source),("Area",self.scope)):
            form.addRow(title,control)
        layout.addLayout(form)
        label = QLabel("Smooth image pixels changes image intensities. Smooth edges changes mask geometry. This operation preserves the source data type and alpha channel. Unfilled removed pixels are excluded. Review the preview before Apply, then use Undo or delete the smoothing region to restore the previous image.")
        label.setWordWrap(True);layout.addWidget(label)
        self.controls = buttons(self, layout);self.controls.button(QDialogButtonBox.StandardButton.Ok).setText("Calculate preview")
        def refresh():
            self.sigma.setEnabled(self.method.currentData()=="gaussian");self.kernel.setEnabled(self.method.currentData()=="median")
        self.method.currentIndexChanged.connect(refresh);refresh()

    def values(self):
        return {"method":self.method.currentData(), "sigma":self.sigma.value(), "size":self.kernel.currentData(),
                "source":self.source.currentData(), "scope":self.scope.currentData()}


class ImagePreviewDialog(QDialog):
    def __init__(self, before, after, title, parent=None):
        super().__init__(parent);self.setWindowTitle(title);self.resize(1000,530)
        layout = QVBoxLayout(self);images = QHBoxLayout()
        for caption, pixels in (("Before", before), ("Preview", after)):
            column = QVBoxLayout();column.addWidget(QLabel(caption))
            image = QLabel();image.setAlignment(Qt.AlignmentFlag.AlignCenter)
            image.setPixmap(QPixmap.fromImage(rgb_image(display_rgb(pixels))).scaled(470,400,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
            column.addWidget(image);images.addLayout(column)
        layout.addLayout(images)
        layout.addWidget(QLabel("Apply records a reversible image edit. Original acquired pixels remain available."))
        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Apply|QDialogButtonBox.StandardButton.Cancel)
        controls.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.accept);controls.rejected.connect(self.reject);layout.addWidget(controls)


class MaskColorsDialog(QDialog):
    def __init__(self, document, has_selected=False, parent=None):
        super().__init__(parent);self.setWindowTitle("Assign mask colors");self.resize(640,490)
        layout = QVBoxLayout(self);form = QFormLayout()
        self.mode = combo([("Default group colors", "default"), ("20 preset lookup table", "lut20")], "maskColorScheme")
        self.by = combo([("Object", "object"), ("Group", "group")], "maskColorAssignment")
        self.target = combo([("All objects", "all"), ("Selected objects", "selected")], "maskColorTarget")
        self.target.model().item(1).setEnabled(has_selected)
        if has_selected:self.target.setCurrentIndex(1)
        self.mode.setCurrentIndex(self.mode.findData(document.color_scheme["mode"]))
        self.by.setCurrentIndex(self.by.findData(document.color_scheme["by"]))
        for title, widget in (("Scheme",self.mode),("Assign by",self.by),("Apply to",self.target)):form.addRow(title,widget)
        layout.addLayout(form)
        layout.addWidget(QLabel("Lookup table start color (colors cycle in the order below)"))
        self.swatches = QButtonGroup(self);self.swatches.setExclusive(True);self.palette_widget = QWidget();grid=QGridLayout(self.palette_widget)
        for index, (name,color) in enumerate(LUT20):
            button = QToolButton();button.setText(f"{index+1:02d} {name}");button.setCheckable(True)
            button.setToolTip(color);button.setMinimumSize(112,38)
            rgb=QColor(color);foreground="#ffffff" if .2126*rgb.red()+.7152*rgb.green()+.0722*rgb.blue()<145 else "#101820"
            button.setStyleSheet(f"QToolButton {{background:{color};color:{foreground};border:1px solid #6c7c8c;padding:3px;}} QToolButton:checked {{border:4px solid #101820;}}")
            self.swatches.addButton(button,index);grid.addWidget(button,index//5,index%5)
        self.swatches.button(document.color_scheme["offset"]).setChecked(True);layout.addWidget(self.palette_widget)
        self.future = QCheckBox("Use this scheme for new objects and groups in this image");self.future.setChecked(True);layout.addWidget(self.future)
        label = QLabel("By group updates the group color and every object in each affected group. Default uses the current group colors. Lookup colors repeat after 20 entries; object IDs and numeric mask labels stay unchanged.")
        label.setWordWrap(True);layout.addWidget(label)
        buttons(self,layout)
        self.mode.currentIndexChanged.connect(lambda:self.palette_widget.setEnabled(self.mode.currentData()=="lut20"))
        self.palette_widget.setEnabled(self.mode.currentData()=="lut20")

    def values(self):
        return {"scheme":{"mode":self.mode.currentData(),"by":self.by.currentData(),"offset":self.swatches.checkedId()},
                "selected_only":self.target.currentData()=="selected", "use_for_new":self.future.isChecked()}


class SaveMasksDialog(QDialog):
    def __init__(self, document, transparent=False, parent=None):
        super().__init__(parent)
        self.document = document
        self.setWindowTitle("Export transparent masks" if transparent else "Save mask images")
        self.resize(720,650)
        layout=QVBoxLayout(self);form=QFormLayout()
        self.format=combo([("24-bit BMP","bmp"),("PNG","png"),("TIFF","tif")],"maskFormat")
        if transparent:self.format.setCurrentIndex(1)
        self.organization=combo([("One combined image","combined"),("One file per object","object"),("One file per group","group")],"maskOrganization")
        self.color=combo([("Color by group","group_color"),("Color by object","object_color"),("Binary grayscale","binary"),("Weighted grayscale at overlaps","overlap_gray"),("Numeric instance IDs","instance"),("Numeric class IDs","class")],"maskColor")
        if document.color_scheme["mode"]=="lut20" and document.color_scheme["by"]=="object":self.color.setCurrentIndex(1)
        self.overlay=QCheckBox("Overlay masks on an image")
        self.overlay_source=combo([("Uncleaned image (current orientation)","original"),("Processed image (cleaning / smoothing / rotation)","cleaned")],"overlaySource")
        self.overlay_source.model().item(1).setEnabled(document.working is not None)
        self.transparent=QCheckBox("Make background transparent (all pixels outside objects)");self.transparent.setChecked(transparent)
        self.transparency=QSlider(Qt.Orientation.Horizontal);self.transparency.setRange(0,100);self.transparency.setValue(75 if transparent else 0)
        self.percent=QLabel()
        row=QHBoxLayout();row.addWidget(self.transparency);row.addWidget(self.percent)
        form.addRow("Format",self.format);form.addRow("Organization",self.organization);form.addRow("Appearance",self.color)
        form.addRow(self.overlay);form.addRow("Overlay image",self.overlay_source);form.addRow(self.transparent);form.addRow("Mask transparency",row)
        self.save_original=QCheckBox("Also save original acquired image as TIFF");self.save_original.setObjectName("maskSaveOriginalImage")
        self.save_cleaned=QCheckBox("Also save processed image as TIFF");self.save_cleaned.setObjectName("maskSaveCleanedImage");self.save_cleaned.setEnabled(document.working is not None)
        form.addRow(self.save_original);form.addRow(self.save_cleaned)
        layout.addLayout(form)
        self.preview=QLabel();self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter);self.preview.setMinimumHeight(200);layout.addWidget(self.preview)
        self.info=QLabel();self.info.setWordWrap(True);layout.addWidget(self.info)
        self.controls=buttons(self,layout);self.controls.button(QDialogButtonBox.StandardButton.Ok).setText("Choose folder and save")
        for widget in (self.format,self.organization,self.color,self.overlay_source):widget.currentIndexChanged.connect(self.refresh)
        for widget in (self.overlay,self.transparent):widget.toggled.connect(self.refresh)
        self.transparency.valueChanged.connect(self.refresh)
        self.refresh()

    def values(self):
        return {"file_format":self.format.currentData(),"organization":self.organization.currentData(),
                "color_mode":self.color.currentData(),"overlay":self.overlay_source.currentData() if self.overlay.isChecked() else False,
                "transparent":self.transparent.isChecked(),"transparency":self.transparency.value(),
                "save_original_image":self.save_original.isChecked(),"save_cleaned_image":self.save_cleaned.isChecked()}

    def refresh(self):
        numeric=self.color.currentData() in ("instance","class")
        if numeric:
            self.overlay.setChecked(False);self.transparent.setChecked(False);self.transparency.setValue(0)
            if self.format.currentData()=="bmp":self.format.setCurrentIndex(2)
        self.overlay.setEnabled(not numeric);self.transparent.setEnabled(not numeric);self.transparency.setEnabled(not numeric)
        self.overlay_source.setEnabled(not numeric and self.overlay.isChecked())
        self.percent.setText(f"{self.transparency.value()}%")
        valid=not(self.transparent.isChecked() and self.format.currentData()=="bmp")
        self.controls.button(QDialogButtonBox.StandardButton.Ok).setEnabled(valid)
        self.info.setText("Numeric IDs preserve integer values. First accepted object has precedence at overlaps." if numeric else
                          "Choose PNG/TIFF for transparency. 0% is opaque; 100% is invisible. Binary masks and labels retain exact geometry." if valid else
                          "24-bit BMP has no alpha channel. Choose PNG or TIFF for a transparent background.")
        objects=[o for o in self.document.foreground_objects() if o.mask is not None]
        if not objects:
            self.preview.clear();self.info.setText("There are no accepted object masks to save. Cleaning regions and the selected background group are excluded.")
            self.controls.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            return
        if objects:
            try:
                rgba=render_mask_pixels(self.document,objects,"object_color" if numeric else self.color.currentData(),
                                        self.values()["overlay"],self.transparency.value(),self.transparent.isChecked())
            except ValueError as error:
                self.info.setText(str(error));self.controls.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False);return
            if self.color.currentData()=="overlap_gray":
                from .exports import overlap_grayscale
                _,weight,maximum=overlap_grayscale(objects,self.document.frame.shape)
                self.info.setText(f"Each object adds {weight} gray levels in this combined preview. Two overlaps = {2*weight if maximum>=2 else 'twice the base weight'}. Each saved file uses its own maximum overlap to avoid clipping. The mapping JSON records its weight. Mask transparency and overlay blending affect displayed intensity.")
            # Checkerboard only belongs to the preview; exported RGBA keeps real transparency.
            yy,xx=np.indices(rgba.shape[:2]);base=np.where(((xx//16+yy//16)%2)[...,None],240,218).astype(np.float32)
            alpha=rgba[...,3:4]/255
            rgb=np.rint(rgba[...,:3]*alpha+base*(1-alpha)).astype(np.uint8)
            self.preview.setPixmap(QPixmap.fromImage(rgb_image(rgb)).scaled(630,230,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))


# Keep the public import stable for plugins and existing projects.
from .statistics_dialog import StatisticsDialog
