from __future__ import annotations

import copy
import json
import logging
import math
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import QObject, QRunnable, QSettings, QSize, QThreadPool, QTimer, Qt, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QKeySequence, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import (QApplication, QCheckBox, QColorDialog, QComboBox, QDialog,
    QDialogButtonBox, QDockWidget, QFileDialog, QFormLayout, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox, QPushButton, QProgressBar,
    QSlider, QSplitter, QToolBar, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, QDoubleSpinBox, QHeaderView)

from . import __version__
from .canvas import ImageCanvas
from .dialogs import (BrightnessDialog, CalibrationDialog, InferenceOptionsDialog, ModelDialog,
                      RefinementDialog, SaveMasksDialog, StatisticsDialog, combo,
                      SmoothImageDialog, ImagePreviewDialog, MaskColorsDialog, ImageExportDialog)
from .domain import Annotation, Document, Group, History, ProjectStore, pack_mask, unpack_mask
from .exports import export_coco, export_yolo, safe_name, save_cleaned, save_masks, save_image_versions
from .imageio import SUPPORTED_EXTENSIONS, load_files
from .inference import InferenceEngine, data_directory, initialize_torch_runtime, lama_fill
from .processing import bounding_box, brush_mask, cast_like, display_rgb, filter_proposals, neighbor_fill, patch_fill, raster_contours, shape_mask, smooth_image
from .palette import assign_colors
from .dialogs_v14 import PromptAliasesDialog, RotationDialog, MaskScaleDialog, MorphologyDialog
from .text_prompts import resolve_prompt
from .transforms import rotate_document, apply_scaled_objects
from . import savepoints as mask_savepoints
from .workspace_ui import WorkspaceWorkflowMixin
from .calibration_table import CalibrationTableMixin
from .processing_ui import ProcessingWorkflowMixin
from .segmentation_ui import SegmentationWorkflowMixin
from .plugin_ui import PluginWorkflowMixin

LOG = logging.getLogger(__name__)


class JobSignals(QObject):
    progress = Signal(str)
    done = Signal(object, object)


class Job(QRunnable):
    def __init__(self, function):
        super().__init__()
        self.function = function
        self.signals = JobSignals()
        self.cancel = threading.Event()

    def run(self):
        try:
            result = self.function(self.signals.progress.emit, self.cancel)
            self.signals.done.emit(result, None)
        except BaseException as error:
            LOG.error("Background operation failed\n%s", traceback.format_exc())
            self.signals.done.emit(None, error)


def tool_icon(kind, size=28):
    pixmap = QPixmap(size, size);pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size/28,size/28)
    painter.setPen(QPen(QColor("#384b63"), 1.8));painter.setBrush(Qt.BrushStyle.NoBrush)
    if kind == "rectangle":painter.drawRect(5,7,18,14)
    elif kind == "circle":painter.drawEllipse(5,5,18,18)
    elif kind == "ellipse":painter.drawEllipse(3,8,22,12)
    elif kind == "polygon":painter.drawPolygon(QPolygonF([QPointF(4,19),QPointF(7,6),QPointF(19,4),QPointF(24,15),QPointF(15,23)]))
    elif kind == "point":painter.drawLine(14,4,14,24);painter.drawLine(4,14,24,14)
    elif kind == "select":painter.drawPolygon(QPolygonF([QPointF(6,3),QPointF(22,15),QPointF(14,17),QPointF(12,25)]))
    elif kind == "delete":painter.drawRect(8,9,12,15);painter.drawLine(5,6,23,6);painter.drawLine(11,3,17,3)
    elif kind == "edit":painter.drawLine(5,23,22,6);painter.drawRect(3,20,5,5);painter.drawRect(20,3,5,5)
    elif kind == "pan":
        path=QPainterPath(QPointF(8,16));path.lineTo(8,8);path.cubicTo(8,5,11,5,11,8);path.lineTo(11,5);path.cubicTo(11,2,14,2,14,5);path.lineTo(14,8);path.lineTo(14,5);path.cubicTo(14,3,17,3,17,6);path.lineTo(17,9);path.cubicTo(17,6,20,6,20,9);path.lineTo(20,17);path.cubicTo(20,26,10,27,7,20);path.lineTo(4,15);path.cubicTo(2,11,5,10,8,16);painter.drawPath(path)
    elif kind == "fit":
        for x,y,dx,dy in [(4,4,1,1),(24,4,-1,1),(4,24,1,-1),(24,24,-1,-1)]:
            painter.drawLine(x,y,x+dx*6,y);painter.drawLine(x,y,x,y+dy*6)
        painter.drawRect(9,10,10,8)
    elif kind in ("undo","redo"):
        if kind=="redo":painter.translate(28,0);painter.scale(-1,1)
        path=QPainterPath(QPointF(6,10));path.cubicTo(25,2,28,24,11,23);painter.drawPath(path)
        painter.drawPolyline(QPolygonF([QPointF(6,4),QPointF(5,11),QPointF(12,13)]))
    else:
        painter.setFont(QApplication.font());painter.drawText(pixmap.rect(),Qt.AlignmentFlag.AlignCenter,"↶" if kind=="undo" else "↷")
    painter.end()
    return QIcon(pixmap)


class MainWindow(CalibrationTableMixin, WorkspaceWorkflowMixin, ProcessingWorkflowMixin, SegmentationWorkflowMixin, PluginWorkflowMixin, QMainWindow):
    def __init__(self, restore_session=True):
        super().__init__()
        # Bootstrap PyTorch on the GUI thread. Weights and inference stay in
        # workers, but native thread pools must be initialized before those jobs.
        initialize_torch_runtime()
        self.setWindowTitle(f"SAM Image Studio {__version__}")
        self.resize(1500, 960)
        self.engine = InferenceEngine()
        self.documents: dict[str, Document] = {}
        self.histories: dict[str, History] = {}
        self.stores: dict[str, ProjectStore] = {}
        self.current_key = None
        self._updating = False
        self._job = None
        self._job_callback = None
        self._close_requested = False
        self._refine_target = None
        self._preview_context = None
        self._pending_preview = False
        self._job_prompt_editable = False
        self._prompt_version = 0
        self.stats_dialogs = []
        self.mask_savepoints = {}
        self._mode_guard = False
        self._palette = {}
        self.options = {"grid":8,"min_score":.70,"min_area":8,"max_objects":300}
        self.pool = QThreadPool(self);self.pool.setMaxThreadCount(1)
        data_directory().mkdir(parents=True,exist_ok=True)
        self.settings=QSettings(str(data_directory()/"settings.ini"),QSettings.Format.IniFormat)
        self.project_directory = self.settings.value("project_directory", "") or ""
        self.canvas=ImageCanvas(self);self.canvas.setObjectName("imageCanvas")
        self.canvas.vertex_delete_radius = max(0., min(10000., float(self.settings.value("vertex_delete_radius", 20))))
        self.setCentralWidget(self.canvas)
        self.canvas.selection_changed.connect(self._canvas_selected)
        self.canvas.shape_completed.connect(self._shape_completed)
        self.canvas.prompt_added.connect(self._prompt_added)
        self.canvas.geometry_changed.connect(self._geometry_changed)
        self.canvas.message.connect(lambda text:self.statusBar().showMessage(text,8000))
        self.canvas.zoom_changed.connect(lambda value:self.zoom_label.setText(f"Zoom {value*100:.0f}%"))
        self.canvas.object_context_requested.connect(self._show_object_context_menu)
        self._build_actions();self._build_top();self._build_docks();self._build_status();self._init_workspace_ui();self._init_calibration_tables();self._init_processing_ui();self._init_segmentation_ui();self._init_plugin_ui()
        self.preview_timer=QTimer(self);self.preview_timer.setSingleShot(True);self.preview_timer.setInterval(220)
        self.preview_timer.timeout.connect(self._auto_preview)
        self._refresh()
        if restore_session:
            paths=self.settings.value("last_files",[]) or []
            if isinstance(paths,str):paths=[paths]
            paths=[p for p in paths if Path(p).is_file()]
            if paths:QTimer.singleShot(100,lambda:self._offer_session_restore(paths))

    @property
    def document(self):
        return self.documents.get(self.current_key)

    @property
    def busy(self):
        return self._job is not None

    def notify(self,title,message):
        LOG.warning("%s: %s",title,message)
        QMessageBox.warning(self,title,str(message))

    def _action(self,title,method,shortcut=None,icon=None,checkable=False):
        action=QAction(tool_icon(icon) if icon else QIcon(),title,self)
        if shortcut:action.setShortcut(QKeySequence(shortcut))
        action.setCheckable(checkable)
        action.triggered.connect(method)
        return action

    def _build_actions(self):
        self.open_action=self._action("Open images…",self.open_images,"Ctrl+O")
        self.save_action=self._action("Save masks…",self.save_mask_dialog,"Ctrl+S")
        self.undo_action=self._action("Undo",self.undo,"Ctrl+Z","undo")
        self.redo_action=self._action("Redo",self.redo,"Ctrl+Y","redo")
        self.delete_action=self._action("Delete object / selected vertex",self.delete_selected,"Delete","delete")
        self.edit_action=self._action("Edit object vertices",self.edit_object,"Ctrl+E","edit",True)
        self.select_all_action=self._action("Select all objects",self.select_all_objects,"Ctrl+A")
        self.select_all_action.setToolTip("Select annotation and cleaning objects. Image-smoothing records remain selectable in the Objects panel.")
        self.invert_region_action=self._action("Invert region",self.invert_region,"Ctrl+I")
        self.region_object_action=self._action("Create object from region",self.create_region_object)
        self.smooth_image_action=self._action("Smooth image pixels…",self.smooth_image_dialog)
        self.rotation_action=self._action("Rotate image…",self.rotate_image_dialog)
        self.scale_masks_action=self._action("Scale masks / savepoints…",self.scale_masks_dialog)
        self.morphology_action=self._action("Morphology / inner region…",self.morphology_dialog)
        self.mask_colors_action=self._action("Assign mask colors…",self.assign_mask_colors)
        self.remove_action=self._action("Remove selected image area",self.remove_area,"Ctrl+D")
        self.cancel_action=self._action("Cancel current drawing / preview",self.cancel_operation,"Esc")
        self.addAction(self.cancel_action)
        self.tool_actions={}
        self.tool_group=QActionGroup(self);self.tool_group.setExclusive(True)
        self.fit_action=self._action("Reset magnification / fit image",self.canvas.fit_image,"F","fit")
        for kind,title in [("select","Select objects (Ctrl+click for multiple)"),("pan","Hand tool: drag to move image"),("polygon","Polygon"),("rectangle","Rectangle"),("circle","Circle"),("ellipse","Ellipse"),("point","Point / cleaning brush")]:
            action=self._action(title,lambda checked=False,k=kind:self.canvas.set_tool(k),icon=kind,checkable=True)
            self.tool_group.addAction(action);self.tool_actions[kind]=action
        self.tool_actions["select"].setChecked(True)
        self.toolbar=QToolBar("Drawing tools",self);self.toolbar.setObjectName("drawingToolbar");self.toolbar.setMovable(False);self.toolbar.setIconSize(QSize(22,22));self.addToolBar(Qt.ToolBarArea.LeftToolBarArea,self.toolbar)
        for key in ("select","pan"):self.toolbar.addAction(self.tool_actions[key])
        self.toolbar.addAction(self.fit_action)
        self.toolbar.addSeparator()
        for action in (self.undo_action,self.redo_action,self.delete_action,self.edit_action):self.toolbar.addAction(action)
        for action in (self.undo_action,self.redo_action):
            button=self.toolbar.widgetForAction(action)
            button.setIconSize(QSize(44,44));button.setFixedSize(72,72)
        self.toolbar.addSeparator()
        for key in ("polygon","rectangle","circle","ellipse","point"):self.toolbar.addAction(self.tool_actions[key])
        file=self.menuBar().addMenu("File")
        file.addAction(self.open_action);file.addAction(self._action("Open folder…",self.open_folder));file.addAction(self._action("Open project JSON…",self.open_project));file.addSeparator()
        file.addAction(self.save_action);file.addAction(self._action("Save project now",self.save_project));file.addAction(self._action("Choose project folder…",self.choose_project_folder));file.addAction(self._action("Save original / processed images…",self.export_images));file.addSeparator()
        file.addAction(self._action("Close current image",self.close_current));file.addAction(self._action("Exit",self.close))
        edit=self.menuBar().addMenu("Edit")
        for action in (self.undo_action,self.redo_action,self.edit_action,self.delete_action):edit.addAction(action)
        edit.addSeparator()
        for action in (self.select_all_action,self.invert_region_action,self.region_object_action):edit.addAction(action)
        edit.addSeparator();edit.addAction(self._action("Object properties…",self.object_properties));edit.addAction(self._action("Change selected objects' group…",self.change_group))
        edit.addAction(self._action("Brightness / contrast…",self.adjust_display));edit.addAction(self._action("Object color…",self.change_color));edit.addAction(self._action("Object transparency…",self.change_transparency))
        edit.addAction(self.mask_colors_action);edit.addAction(self.smooth_image_action)
        for action in (self.rotation_action,self.scale_masks_action,self.morphology_action):edit.addAction(action)
        edit.addAction(self._action("Vertex deletion radius…",self.change_vertex_delete_radius))
        edit.addSeparator();edit.addAction(self._action("Fill holes…",lambda:self.refine_masks("holes")));edit.addAction(self._action("Smooth edges…",lambda:self.refine_masks("smooth")))
        cleaning=self.menuBar().addMenu("Cleaning");cleaning.addAction(self.remove_action)
        cleaning.addAction(self._action("Restore selected area / all edits",self.restore_area))
        for title,method in [("Fill from neighboring pixels","neighbors"),("Fill with LaMa…","lama"),("Fill with background patches","patches")]:
            cleaning.addAction(self._action(title,lambda checked=False,m=method:self.fill_removed(m)))
        cleaning.addSeparator();cleaning.addAction(self._action("Choose background group…",self.choose_background_group));cleaning.addAction(self._action("Add selection to background group…",self.add_patch));cleaning.addAction(self._action("Clear background group selection",self.clear_patches));cleaning.addAction(self._action("Cleaning brush radius…",self.change_brush_radius))
        models=self.menuBar().addMenu("Models");models.addAction(self._action("Model manager…",self.model_dialog));models.addAction(self._action("Segmentation options…",self.inference_options));models.addAction(self._action("Text prompt aliases…",self.prompt_aliases_dialog))
        exports=self.menuBar().addMenu("Export");exports.addAction(self._action("COCO segmentation dataset…",lambda:self.export_dataset("coco")));exports.addAction(self._action("YOLO segmentation dataset…",lambda:self.export_dataset("yolo")));exports.addSeparator();exports.addAction(self._action("Transparent mask images…",lambda:self.save_mask_dialog(True)))
        statistics=self.statistics_menu=self.menuBar().addMenu("Statistics");statistics.addAction(self._action("Plot Object Statistics…",self.plot_statistics));statistics.addAction(self._action("Edit image calibration…",self.edit_calibration))
        view=self.menuBar().addMenu("View");view.addAction(self.fit_action)
        for title,attribute,initial in [("Show masks","show_masks",True),("Show contours","show_contours",True),("Show prompt points","show_prompts",True)]:
            action=self._action(title,lambda checked,a=attribute:self.set_canvas_option(a,checked),checkable=True);action.setChecked(initial);view.addAction(action)
        sizes=view.addMenu("Toolbar icon size")
        for name,size in [("Small (default)",22),("Medium",30),("Large",40)]:sizes.addAction(self._action(name,lambda checked=False,n=size:self.toolbar.setIconSize(QSize(n,n))))
        self.view_menu=view
        help_menu=self.menuBar().addMenu("Help");help_menu.addAction(self._action("User manual (PDF)",self.open_pdf_help));help_menu.addAction(self._action("Denoising parameter guide (PDF)",lambda:self.open_pdf_help(denoise=True)));help_menu.addAction(self._action("Quick start",self.quick_start));help_menu.addAction(self._action("Diagnostics / versions",self.diagnostics))

    def _build_top(self):
        bar=QToolBar("Workflow",self);bar.setObjectName("workflowToolbar");bar.setMovable(False);self.addToolBar(Qt.ToolBarArea.TopToolBarArea,bar)
        self.mode=combo(["Manual","Segment","Clean","Edit"],"workMode");self.mode.currentTextChanged.connect(self.mode_changed)
        self.model_button=QPushButton("Load model…");self.model_button.setObjectName("loadModelButton");self.model_button.clicked.connect(self.model_dialog)
        self.model_label=QLabel("CPU default · model not loaded")
        self.model_label.setMaximumWidth(175)
        self.group_combo=combo([],"activeGroup");self.group_combo.setMinimumWidth(130);self.group_combo.currentIndexChanged.connect(self.active_group_changed)
        self.scope=combo([("Prompted object, whole image", "prompt"),
                          ("Inside ROI only", "roi"),
                          ("Automatic grid, unannotated only", "automatic")],"inferenceScope")
        self.scope.setToolTip("Point and shape prompts predict one object. Inside ROI clips area prompts only. Automatic grid is a separate operation.")
        self.scope.setMaximumWidth(275)
        self.scope.currentIndexChanged.connect(self.inference_scope_changed)
        self.run_button=QPushButton("Run preview");self.run_button.setObjectName("runPreviewButton");self.run_button.clicked.connect(self.run_inference)
        self.accept_button=QPushButton("Accept masks");self.accept_button.setObjectName("acceptMasksButton");self.accept_button.clicked.connect(self.accept_preview)
        self.cancel_button=QPushButton("Cancel / clear");self.cancel_button.setObjectName("cancelButton");self.cancel_button.clicked.connect(self.cancel_operation)
        self.options_button=QPushButton("Options…");self.options_button.clicked.connect(self.inference_options)
        for widget in (QLabel("Mode "),self.mode,self.model_button,self.model_label,QLabel(" Group "),self.group_combo,self.scope,self.run_button,self.accept_button,self.cancel_button,self.options_button):bar.addWidget(widget)
        second=QToolBar("Image and prompts",self);second.setObjectName("imageToolbar");second.setMovable(False);self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea);self.addToolBar(Qt.ToolBarArea.TopToolBarArea,second)
        self.calibration_label=QLabel("No image")
        self.cleaned_checkbox=QCheckBox("View / infer from processed image");self.cleaned_checkbox.toggled.connect(lambda checked:self.set_canvas_option("use_cleaned",checked))
        self.auto_checkbox=QCheckBox("Live point preview");self.auto_checkbox.setChecked(True)
        self.text_prompt=QLineEdit();self.text_prompt.setMaximumWidth(250);self.text_prompt.setPlaceholderText("Text prompt / alias (SAM2+)");self.text_prompt.setVisible(False)
        for widget in (self.calibration_label,QLabel("   "),self.cleaned_checkbox,QLabel("   "),self.auto_checkbox,QLabel("   "),self.text_prompt):
            added=second.addWidget(widget)
            if widget is self.text_prompt:self.text_prompt_action=added
        self.aliases_button=QPushButton("Prompt aliases…");self.aliases_button.clicked.connect(self.prompt_aliases_dialog);self.aliases_action=second.addWidget(self.aliases_button)
        self.text_prompt.textChanged.connect(self._text_prompt_changed)
        self.vertex_radius_label=QLabel("Vertex radius (px)")
        self.vertex_radius=QDoubleSpinBox();self.vertex_radius.setObjectName("vertexRadius");self.vertex_radius.setRange(0,10000);self.vertex_radius.setDecimals(1);self.vertex_radius.setValue(self.canvas.vertex_delete_radius)
        self.vertex_radius.valueChanged.connect(self.set_vertex_delete_radius)
        self.vertex_radius_actions=[second.addWidget(self.vertex_radius_label),second.addWidget(self.vertex_radius)]
        for action in self.vertex_radius_actions:action.setVisible(False)
        self.background_button=QPushButton("Background group…");self.background_button.setObjectName("backgroundGroupButton");self.background_button.clicked.connect(self.choose_background_group);second.addWidget(self.background_button)
        region_bar=QToolBar("Regions and image processing",self);region_bar.setObjectName("regionToolbar");region_bar.setMovable(False)
        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea);self.addToolBar(Qt.ToolBarArea.TopToolBarArea,region_bar)
        for action in (self.select_all_action,self.invert_region_action,self.region_object_action,self.smooth_image_action,self.mask_colors_action):region_bar.addAction(action)
        for action in (self.rotation_action,self.scale_masks_action,self.morphology_action):region_bar.addAction(action)
        self.region_label=QLabel("  No region");self.region_label.setObjectName("regionPixelCount");region_bar.addWidget(self.region_label)

    def _dock(self,title,name,widget):
        dock=QDockWidget(title,self);dock.setObjectName(name);dock.setWidget(widget);dock.setMinimumWidth(300)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea,dock);self.view_menu.addAction(dock.toggleViewAction());return dock

    def _build_docks(self):
        self.objects_tree=QTreeWidget();self.objects_tree.setObjectName("objectsTree");self.objects_tree.setHeaderLabels(["Object","Group","Area","Lock"]);self.objects_tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection);self.objects_tree.setRootIsDecorated(False)
        header=self.objects_tree.header();header.setStretchLastSection(False);header.setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        for column in (1,2):header.setSectionResizeMode(column,QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3,QHeaderView.ResizeMode.Fixed);header.resizeSection(3,45)
        self.objects_tree.itemSelectionChanged.connect(self._tree_selected);self.objects_tree.itemChanged.connect(self._object_item_changed);self.objects_tree.itemDoubleClicked.connect(lambda item,col:self.edit_object(True))
        self.objects_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu);self.objects_tree.customContextMenuRequested.connect(self.object_context_menu)
        objects_widget=QWidget();objects_layout=QVBoxLayout(objects_widget);objects_layout.setContentsMargins(0,0,0,0);objects_layout.addWidget(self.objects_tree)
        self.show_cleaning_button=QPushButton("Show cleaning regions  √");self.show_cleaning_button.setObjectName("showCleaningRegions");self.show_cleaning_button.setCheckable(True);self.show_cleaning_button.setChecked(True)
        self.show_cleaning_button.toggled.connect(self.toggle_cleaning_regions);objects_layout.addWidget(self.show_cleaning_button)
        self.objects_dock=self._dock("Objects","objectsDock",objects_widget)
        self.objects_dock.setMinimumWidth(420)
        group_widget=QWidget();layout=QVBoxLayout(group_widget);layout.setContentsMargins(5,5,5,5)
        self.groups_tree=QTreeWidget();self.groups_tree.setObjectName("groupsTree");self.groups_tree.setHeaderLabels(["Group","Count"]);self.groups_tree.setRootIsDecorated(False);self.groups_tree.itemDoubleClicked.connect(lambda item,col:self.select_group_item(item))
        layout.addWidget(self.groups_tree);row=QHBoxLayout()
        for title,callback in [("+ Group",self.new_group),("Rename",self.rename_group),("Color",self.group_color)]:
            button=QPushButton(title);button.clicked.connect(callback);row.addWidget(button)
        layout.addLayout(row);self.groups_dock=self._dock("Groups","groupsDock",group_widget)
        self.files_tree=QTreeWidget();self.files_tree.setObjectName("imageFilesTree");self.files_tree.setHeaderLabels(["Image files / datasets / frames"]);self.files_tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection);self.files_tree.itemClicked.connect(self._file_clicked)
        self.files_dock=self._dock("Image files","imageFilesDock",self.files_tree)
        self.splitDockWidget(self.objects_dock,self.groups_dock,Qt.Orientation.Vertical);self.splitDockWidget(self.groups_dock,self.files_dock,Qt.Orientation.Vertical)
        self.resizeDocks([self.objects_dock,self.groups_dock,self.files_dock],[370,170,240],Qt.Orientation.Vertical)

    def _build_status(self):
        self.save_label=QLabel("Ready");self.zoom_label=QLabel("Zoom —");self.progress=QProgressBar();self.progress.setMaximumWidth(180);self.progress.setRange(0,0);self.progress.hide()
        self.statusBar().addPermanentWidget(self.save_label);self.statusBar().addPermanentWidget(self.zoom_label);self.statusBar().addPermanentWidget(self.progress)

    def _start_job(self,title,function,callback,prompt_editable=False):
        if self.busy:
            self.statusBar().showMessage("Wait for the current operation or click Cancel.",5000);return False
        self._job=Job(function);self._job_callback=callback
        self._job_prompt_editable=prompt_editable
        self._job.signals.progress.connect(self._progress_message);self._job.signals.done.connect(self._job_finished)
        self.canvas.read_only=not prompt_editable;self.canvas.prompt_input_only=prompt_editable
        self.files_tree.setEnabled(False);self.model_button.setEnabled(False);self.run_button.setEnabled(False);self.accept_button.setEnabled(False);self.progress.show()
        self.statusBar().showMessage(title);self.pool.start(self._job);return True

    def _progress_message(self,message):
        self.statusBar().showMessage(message)

    def _job_finished(self,result,error):
        job,callback=self._job,self._job_callback
        cancelled=job.cancel.is_set() if job else False
        self._job=self._job_callback=None;self._job_prompt_editable=False
        self.canvas.read_only=False;self.canvas.prompt_input_only=False
        self.files_tree.setEnabled(True);self.model_button.setEnabled(True);self.progress.hide()
        if error is not None and not isinstance(error,InterruptedError) and not cancelled:self.notify("Operation failed",str(error))
        elif not cancelled and error is None:
            try:callback(result)
            except Exception as problem:LOG.exception("Result handling failed");self.notify("Operation failed",str(problem))
        elif cancelled:self.statusBar().showMessage("Operation cancelled. Accepted annotations were preserved.",8000)
        self._refresh()
        if self._close_requested:self.close()
        elif self._pending_preview:
            self._pending_preview=False;self.preview_timer.start()

    def _store_for(self,frame):
        preferred=Path(self.project_directory) if self.project_directory else Path(frame.source_path).parent/"SAM_Annotations"
        try:preferred.mkdir(parents=True,exist_ok=True)
        except OSError:preferred=data_directory()/"projects"
        return ProjectStore(preferred)

    def _persist(self,doc):
        try:
            path=self.stores[doc.frame.key].save(doc);self.save_label.setText("Autosaved "+datetime.now().strftime("%H:%M:%S"));self.save_label.setToolTip(str(path))
        except Exception:
            self.save_label.setText("Save failed — changes remain in memory");raise

    def _commit(self,label,function,allow_prompt=False):
        if not self.document or (self.busy and not (allow_prompt and self._job_prompt_editable)):return False
        try:
            self.histories[self.current_key].apply(label,function)
            return True
        except Exception as error:
            LOG.exception("Edit or autosave failed");self.notify("Edit / autosave",str(error));return False
        finally:self._refresh()

    def _refresh(self):
        if getattr(self,"_tree_callback",False):
            QTimer.singleShot(0,self._refresh)
            return
        doc=self.document;selected=set(self.canvas.selected);self._updating=True
        self.objects_tree.clear();self.groups_tree.clear();self.group_combo.clear()
        if doc:
            for group in doc.groups:
                self.group_combo.addItem(group.name,group.id)
                item=QTreeWidgetItem([group.name,str(sum(o.group_id==group.id for o in doc.objects))]);item.setData(0,Qt.ItemDataRole.UserRole,group.id);self.groups_tree.addTopLevelItem(item)
            if doc.active_group:self.group_combo.setCurrentIndex(self.group_combo.findData(doc.active_group))
            for obj in doc.objects:
                area="Point" if obj.mask is None else f"{obj.pixel_area:,} px²"
                if obj.mask is not None and doc.calibration.valid:area=f"{doc.calibration.area(obj.pixel_area):.4g} {doc.calibration.length_unit}²"
                item=QTreeWidgetItem([obj.name,doc.get_group(obj.group_id).name,area,""])
                if obj.role=="cleaning":
                    item.setText(0,("[Image] " if obj.provenance.get("method")=="image smoothing" else "[Cleaning] ")+obj.name);item.setToolTip(0,"Method: "+obj.cleaning["method"]+". Delete this object to restore its pixels. Other image edits remain applied.")
                elif obj.group_id==doc.background_group_id:item.setText(0,"[Background] "+obj.name)
                item.setData(0,Qt.ItemDataRole.UserRole,obj.id);item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0,Qt.CheckState.Checked if obj.visible else Qt.CheckState.Unchecked);item.setCheckState(3,Qt.CheckState.Checked if obj.locked else Qt.CheckState.Unchecked)
                item.setForeground(0,QColor(obj.color));item.setToolTip(2,f"Pixel area: {obj.pixel_area}\nPhysical area: {doc.calibration.area(obj.pixel_area) if obj.mask is not None else 'N/A'}")
                self.objects_tree.addTopLevelItem(item);item.setSelected(obj.id in selected)
            cal=doc.calibration
            self.calibration_label.setText(f"Pixel size: X {cal.pixel_size_x:g} × Y {cal.pixel_size_y:g} {cal.length_unit}/pixel" if cal.valid else "Pixel size unavailable — measurements use pixels")
            self.calibration_label.setToolTip(cal.source)
            self.setWindowTitle(f"{Path(doc.frame.source_path).name} — {doc.frame.frame_label} — SAM Image Studio {__version__}")
            self.canvas.selected &= {o.id for o in doc.objects};self.canvas.refresh()
        else:
            self.calibration_label.setText("No image");self.setWindowTitle(f"SAM Image Studio {__version__}")
        self._updating=False
        self._refresh_controls()

    def _refresh_controls(self):
        doc=self.document
        has=bool(doc)
        self.run_button.setEnabled(has and self.engine.ready and not self.busy)
        self.accept_button.setEnabled(has and bool(self.canvas.preview_masks) and not self.busy)
        self.save_action.setEnabled(has and not self.busy);self.remove_action.setEnabled(has and not self.busy)
        for action in (self.select_all_action,self.invert_region_action,self.smooth_image_action,self.mask_colors_action):action.setEnabled(has and not self.busy)
        roi=doc.draft.get("roi") if doc else None
        selected_region=self._selection_mask() if doc and roi else None
        pixels=int(selected_region.sum()) if selected_region is not None else 0
        self.region_label.setText(f"  Region: {pixels:,} pixels" if roi else "  No region")
        self.region_object_action.setEnabled(has and self.mode.currentText() in ("Manual","Edit") and pixels>0 and not self.busy)
        history=self.histories.get(self.current_key)
        self.undo_action.setEnabled(bool(history and history.undo_stack) and not self.busy);self.redo_action.setEnabled(bool(history and history.redo_stack) and not self.busy)
        self.delete_action.setEnabled(has and bool(self.canvas.selected) and not self.busy)
        editable=self.selected_objects()
        self.edit_action.setEnabled(has and len(editable)==1 and editable[0].role=="object" and not editable[0].locked and not self.busy)
        self.edit_action.setChecked(self.mode.currentText()=="Edit")
        for kind in ("polygon","rectangle","circle","ellipse","point"):self.tool_actions[kind].setEnabled(self.mode.currentText()!="Edit" and (not self.busy or self._job_prompt_editable))
        name=doc.get_group(doc.background_group_id).name if doc and doc.background_group_id else "not selected"
        self.background_button.setText("Background: "+name+"…");self.background_button.setEnabled(has and not self.busy)
        text_enabled=bool(self.engine.spec and self.engine.spec.family in ("SAM2","SAM2.1","SAM3","SAM3.1"))
        self.text_prompt_action.setVisible(text_enabled);self.aliases_action.setVisible(text_enabled)
        if hasattr(self,"text_run_action"):
            self.text_run_action.setVisible(text_enabled);self.text_run_button.setEnabled(has and bool(self.text_prompt.text().strip()) and self.engine.ready and not self.busy)
        for action in (self.rotation_action,self.scale_masks_action,self.morphology_action):
            action.setEnabled(has and self.mode.currentText()=="Edit" and not self.busy)
        for dialog in list(self.stats_dialogs):
            dialog.documents=list(self.documents.values())
            dialog.selected_objects=set(self.canvas.selected)
            dialog.selected_images=self.selected_images()
            dialog.current=doc
            dialog.refresh()

    def open_images(self):
        if self.busy:return
        paths,_=QFileDialog.getOpenFileNames(self,"Open images / stacks","","Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.dm3 *.dm4 *.emd *.webp *.gif);;All files (*)")
        if paths:self.open_paths(paths)

    def open_folder(self):
        if self.busy:return
        folder=QFileDialog.getExistingDirectory(self,"Open image folder")
        if folder:self.open_paths([str(p) for p in sorted(Path(folder).iterdir()) if p.suffix.lower() in SUPPORTED_EXTENSIONS])

    def open_paths(self,paths):
        if not paths:return
        self._start_job("Opening images…",lambda progress,cancel:load_files(paths,progress,cancel),self._opened)

    def _opened(self,result):
        first=None
        for frame in result.frames:
            if first is None:first=frame.key
            if frame.key in self.documents:continue
            doc=Document(frame);store=self._store_for(frame)
            try:
                restored,message=store.load(doc)
                if message:self.statusBar().showMessage(message,8000)
            except Exception as error:result.warnings.append(f"{frame.frame_label}: {error}")
            calibrated = False
            if self.pixel_size_table:
                cal = self.pixel_size_table.calibration(frame.source_path)
                if cal:
                    from .calibration_table import apply_calibration
                    apply_calibration(doc, cal); doc.revision += 1; calibrated = True
            self.documents[frame.key]=doc;self.stores[frame.key]=store;self.histories[frame.key]=History(doc,lambda d=doc:self._persist(d))
            if calibrated:self._persist(doc)
            for g in doc.groups:self._palette[g.name]=g.color
        self._rebuild_file_tree()
        if first:self.select_document(first)
        self.settings.setValue("last_files",list(dict.fromkeys(d.frame.source_path for d in self.documents.values())))
        if result.warnings:self.notify("Some files / saved annotations need attention","\n\n".join(result.warnings[:12]))

    def _rebuild_file_tree(self):
        self.files_tree.clear();parents={}
        for key,doc in self.documents.items():
            path=doc.frame.source_path
            if path not in parents:
                parent=QTreeWidgetItem([Path(path).name]);parent.setToolTip(0,path);self.files_tree.addTopLevelItem(parent);parents[path]=parent
            child=QTreeWidgetItem([doc.frame.frame_label]);child.setData(0,Qt.ItemDataRole.UserRole,key);parents[path].addChild(child);parents[path].setExpanded(True)

    def select_document(self,key):
        if self.busy or key not in self.documents:return
        if self.document and self.document.revision!=self.document.saved_revision:
            try:self._persist(self.document)
            except Exception as error:self.notify("Image switch blocked",f"Save the current work first. {error}");return
        self.current_key=key;self._refine_target=None
        self.canvas.set_document(self.document);self.canvas.mode=self.mode.currentText();self.canvas.edit_mode=self.mode.currentText()=="Edit";self._refresh()

    def _file_clicked(self,item,column):
        key=item.data(0,Qt.ItemDataRole.UserRole)
        if key:self.select_document(key)

    def selected_images(self):
        keys=set()
        for item in self.files_tree.selectedItems():
            key=item.data(0,Qt.ItemDataRole.UserRole)
            if key:keys.add(key)
            else:
                for i in range(item.childCount()):keys.add(item.child(i).data(0,Qt.ItemDataRole.UserRole))
        return keys

    def choose_project_folder(self):
        if self.busy:return
        folder=QFileDialog.getExistingDirectory(self,"Choose a writable autosave folder")
        if folder:
            self.project_directory=folder;self.settings.setValue("project_directory",folder)
            for key,doc in self.documents.items():
                self.stores[key]=ProjectStore(Path(folder))
                try:self._persist(doc)
                except Exception as error:self.notify("Autosave folder",str(error))

    def open_project(self):
        if self.busy:return
        path,_=QFileDialog.getOpenFileName(self,"Open saved project JSON","","SAM project (*.sam.json *.json)")
        if not path:return
        try:
            state=json.loads(Path(path).read_text("utf-8"));source=state["image"]["path"]
            if not Path(source).exists():
                source,_=QFileDialog.getOpenFileName(self,"Locate the matching source image")
                if not source:return
            def loaded(result):
                matches=[f for f in result.frames if f.fingerprint==state["image"]["fingerprint"] and f.dataset==state["image"]["dataset"] and f.frame_index==state["image"]["frame_index"]]
                if not matches:raise ValueError("The selected source/dataset/frame does not match this project.")
                frame=matches[0];state["image"]["key"]=frame.key
                self._opened(result);doc=self.documents[frame.key];doc.restore(state);doc.saved_revision=-1;self.stores[frame.key]=ProjectStore(Path(path).parent);self._persist(doc);self.select_document(frame.key)
            self._start_job("Opening project…",lambda progress,cancel:load_files([source],progress,cancel),loaded)
        except Exception as error:self.notify("Open project",str(error))

    def save_project(self):
        if not self.document:return
        try:self._persist(self.document)
        except Exception as error:self.notify("Save failed",str(error))

    def close_current(self):
        self.remove_workspace_images({self.current_key} if self.current_key else set())

    def _ensure_group(self):
        doc=self.document
        if not doc:return False
        if doc.active_group and any(g.id==doc.active_group for g in doc.groups):return True
        if self._palette:
            name,color=next(iter(self._palette.items()))
            return self._commit("Select default group",lambda:doc.ensure_group(name,color))
        return self.new_group()

    def new_group(self):
        if self.busy or not self.document:return False
        name,ok=QInputDialog.getText(self,"Create group","Group name (used as the default for new objects):")
        if not ok or not name.strip():return False
        name=name.strip();color=self._palette.get(name,"#148374")
        success=self._commit("Create group",lambda:self.document.ensure_group(name,color))
        if success:self._palette[name]=color
        return success

    def active_group_changed(self,index):
        if self._updating or not self.document or self.busy:return
        value=self.group_combo.itemData(index)
        if value and value!=self.document.active_group:self._commit("Select active group",lambda:setattr(self.document,"active_group",value))

    def select_group_item(self,item):
        ident=item.data(0,Qt.ItemDataRole.UserRole)
        index=self.group_combo.findData(ident)
        if index>=0:self.group_combo.setCurrentIndex(index)

    def rename_group(self):
        if not self.document or self.busy:return
        item=self.groups_tree.currentItem()
        if not item:return
        group=self.document.get_group(item.data(0,Qt.ItemDataRole.UserRole))
        name,ok=QInputDialog.getText(self,"Rename group","New group name:",text=group.name)
        if ok and name.strip():
            if any(g.name==name.strip() and g.id!=group.id for g in self.document.groups):self.notify("Group exists","Choose another name or reassign the objects to the existing group.");return
            self._commit("Rename group",lambda:setattr(group,"name",name.strip()));self._palette[group.name]=group.color

    def group_color(self):
        if not self.document or self.busy:return
        item=self.groups_tree.currentItem()
        if not item:return
        group=self.document.get_group(item.data(0,Qt.ItemDataRole.UserRole));color=QColorDialog.getColor(QColor(group.color),self,"Group color")
        if color.isValid():
            old=group.color
            def update():
                group.color=color.name()
                for obj in self.document.objects:
                    if obj.group_id==group.id and obj.color==old:obj.color=group.color
            self._commit("Group color",update);self._palette[group.name]=group.color

    def _pending_mode_content(self):
        doc=self.document
        return bool(doc and (self.canvas._drawing or self.canvas.preview_masks or doc.draft.get("roi") or doc.draft.get("points") or doc.draft.get("examples")))

    def _resolve_mode_content(self):
        if not self._pending_mode_content():return True
        answer=QMessageBox.question(self,"Unadded shapes", "Add the pending shapes or preview masks before switching mode?\nYes adds them as objects. No discards them. Cancel keeps the current mode.",
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Yes)
        if answer==QMessageBox.StandardButton.Cancel:return False
        doc=self.document
        if answer==QMessageBox.StandardButton.Yes:
            if not self._ensure_group():return False
            if self.canvas.preview_masks and not self.busy:
                before=doc.revision;self.accept_preview()
                if doc.revision==before:return False
            else:
                drawing=copy.deepcopy(self.canvas._drawing)
                kind=self.canvas.tool
                if drawing:
                    if kind=="polygon" and len(drawing)<3:
                        self.notify("Unfinished polygon","Add at least three vertices before adding this polygon, or choose No to discard it.");return False
                    points=drawing
                    if kind!="polygon" and self.canvas._cursor is not None:points=[drawing[0],list(self.canvas._cursor)]
                    geometry=("brush" if kind=="point" and self.canvas.mode=="Clean" else kind,points)
                else:geometry=None
                def add_pending():
                    if geometry:
                        k,pts=geometry
                        if k=="brush":
                            mask=np.zeros(doc.frame.shape,bool)
                            for pt in pts:mask|=brush_mask(pt,self.canvas.brush_radius,doc.frame.shape)
                        else:mask=None if k=="point" else shape_mask(k,pts,doc.frame.shape)
                        doc.add_object("mask" if k=="brush" else k,pts if k!="brush" else [],mask,{"method":"manual","from_pending":True})
                    elif doc.draft.get("roi"):
                        mask=self._selection_mask()
                        if mask is not None and mask.any():doc.add_object("mask",mask=mask,provenance={"method":"manual","from_pending":True})
                    else:
                        for x,y,label in doc.draft.get("points",[]):
                            if label:doc.add_object("point",[[x,y]],provenance={"method":"manual","from_pending":True})
                    for example in doc.draft.get("examples",[]):
                        if example.get("label",1):
                            pts=example["points"];k=example["kind"];doc.add_object(k,pts,shape_mask(k,pts,doc.frame.shape),{"method":"manual","from_pending":True})
                    doc.draft.update(points=[],roi=None,examples=[])
                if not self._commit("Add pending shapes",add_pending,allow_prompt=True):return False
        else:
            if not self._commit("Discard pending shapes",lambda:doc.draft.update(points=[],roi=None,examples=[]),allow_prompt=True):return False
        self.canvas._drawing=[];self.canvas._cursor=None;self.canvas.set_preview([])
        return True

    def mode_changed(self,value):
        old=self.canvas.mode
        if value!=old and not self._mode_guard:
            if self.busy and not self._job_prompt_editable:
                self.notify("Mode switch","Wait for the current operation to finish before switching mode.")
                self.mode.blockSignals(True);self.mode.setCurrentText(old);self.mode.blockSignals(False);return
            if not self._resolve_mode_content():
                self.mode.blockSignals(True);self.mode.setCurrentText(old);self.mode.blockSignals(False);self.edit_action.setChecked(old=="Edit");return
        self.preview_timer.stop();self._pending_preview=False;self._prompt_version+=1
        self.canvas.set_preview([]);self._preview_context=None
        if self.busy and self._job_prompt_editable:self._job.cancel.set()
        self.canvas.mode=value;self.canvas.edit_mode=value=="Edit";self.edit_action.setChecked(value=="Edit")
        for action in self.vertex_radius_actions:action.setVisible(value=="Edit")
        if value=="Segment":self.tool_actions["point"].setChecked(True);self.canvas.set_tool("point")
        elif value=="Clean":self.tool_actions["rectangle"].setChecked(True);self.canvas.set_tool("rectangle")
        else:self.canvas.set_tool("select");self.tool_actions["select"].setChecked(True)
        if value=="Segment" and self.scope.currentData()=="automatic" and self.engine.ready:self.preview_timer.start()
        self._refresh()

    def inference_scope_changed(self,index):
        self.preview_timer.stop();self._pending_preview=False;self._prompt_version+=1
        self.canvas.set_preview([]);self._preview_context=None
        if self.busy and self._job_prompt_editable:self._job.cancel.set()
        if (not self.busy and self.document and self.scope.currentData()!="automatic"
                and self.auto_checkbox.isChecked() and self.engine.ready
                and (self.document.draft.get("points") or self.document.draft.get("roi"))):
            self.preview_timer.start()
        if self.document and self.mode.currentText()=="Segment" and self.scope.currentData()=="automatic" and self.engine.ready:self.preview_timer.start()
        self._refresh()

    def _shape_completed(self,kind,points):
        if not self.document or self.busy and not self._job_prompt_editable:return
        if self.mode.currentText()=="Edit":return
        doc=self.document
        if self.mode.currentText()=="Manual":
            if not self._ensure_group():return
            def draw():doc.add_object(kind,points,None if kind=="point" else shape_mask(kind,points,doc.frame.shape),{"method":"manual"})
            self._commit("Draw annotation",draw)
        else:
            if self.mode.currentText()=="Segment" and kind=="point":
                for x,y in points:self._prompt_added(x,y,1)
                return
            self._refine_target=None
            self._prompt_version+=1
            self.canvas.set_preview([]);self._preview_context=None
            if self.mode.currentText()=="Segment" and self.scope.currentData()=="prompt":
                example={"kind":kind,"points":points,"label":self.example_polarity.currentData()}
                self._commit("Add exemplar shape",lambda:doc.draft.setdefault("examples",[]).append(example),allow_prompt=True)
            else:self._commit("Draw region",lambda:doc.draft.update({"roi":{"kind":kind,"points":points}}),allow_prompt=True)
            if self.busy:self._pending_preview=True
            if self.mode.currentText()=="Segment" and self.auto_checkbox.isChecked() and self.engine.ready:self.preview_timer.start()

    def _selection_mask(self):
        doc=self.document
        if not doc:return None
        roi=doc.draft.get("roi")
        if roi:
            if roi["kind"]=="mask":return unpack_mask(roi["mask"],doc.frame.shape)
            if roi["kind"]=="brush":
                mask=np.zeros(doc.frame.shape,np.uint8)
                points=np.rint(roi["points"]).astype(np.int32)
                cv2.polylines(mask,[points],False,1,max(1,round(self.canvas.brush_radius*2)))
                for p in (points[0],points[-1]):cv2.circle(mask,tuple(p),round(self.canvas.brush_radius),1,-1)
                return mask.astype(bool)
            return shape_mask(roi["kind"],roi["points"],doc.frame.shape)
        objects=[o.mask for o in doc.objects if o.id in self.canvas.selected and o.mask is not None]
        return np.logical_or.reduce(objects) if objects else None

    def select_all_objects(self):
        if self.document and not self.busy:
            self.canvas.set_selected([o.id for o in self.document.objects if o.provenance.get("method")!="image smoothing"]);self._canvas_selected(self.canvas.selected)

    def invert_region(self):
        if not self.document or self.busy:return
        doc=self.document
        selected=[o for o in self.selected_objects() if o.mask is not None]
        mask=np.logical_or.reduce([o.mask for o in selected]) if selected else self._selection_mask()
        if mask is None:
            self.notify("Invert region","Select one or more area objects, or draw a region first. Point annotations have no filled area.");return
        result=~mask
        self.preview_timer.stop();self._pending_preview=False;self._prompt_version+=1
        self.canvas.set_preview([]);self._preview_context=None;self._refine_target=None
        def invert():
            doc.set_region(result,operation="invert",source_object_ids=[o.id for o in selected])
            doc.draft["points"]=[]
        if self._commit("Invert pixel region",invert):
            self.canvas.set_selected([]);self._canvas_selected([])
            self.statusBar().showMessage(f"Inverted region: {int(result.sum()):,} pixels. Manual/Edit: Create object from region. Clean: Remove selected image area. Segment: add prompts or run a grid inside this region.",15000)

    def create_region_object(self):
        if not self.document or self.busy or self.mode.currentText() not in ("Manual","Edit"):return
        mask=self._selection_mask()
        if mask is None or not mask.any():self.notify("Region required","Choose a nonempty region first.");return
        if not self._ensure_group():return
        doc=self.document;created=[]
        def create():
            created.append(doc.add_object("mask",mask=mask,provenance={"method":"manual","region_operation":(doc.draft.get("roi") or {}).get("operation","selection")}))
            doc.draft["roi"]=None
        if self._commit("Create annotation from region",create):
            self.canvas.set_selected([created[0].id]);self._canvas_selected(self.canvas.selected)

    def _prompt_added(self,x,y,label):
        if not self.document or (self.busy and not self._job_prompt_editable):return
        self._refine_target=None
        self._prompt_version+=1
        self.canvas.set_preview([]);self._preview_context=None
        self._commit("Add SAM prompt",lambda:self.document.draft["points"].append([x,y,label]),allow_prompt=True)
        if self.auto_checkbox.isChecked() and self.engine.ready:
            if self.busy:self._pending_preview=True
            else:self.preview_timer.start()

    def _auto_preview(self):
        if not self.document or self.mode.currentText()!="Segment":return
        if self.busy:self._pending_preview=True
        else:self.run_inference()

    def _canvas_selected(self,ids):
        self._updating=True
        for i in range(self.objects_tree.topLevelItemCount()):
            item=self.objects_tree.topLevelItem(i);item.setSelected(item.data(0,Qt.ItemDataRole.UserRole) in ids)
        self._updating=False;self._refresh_controls()

    def _tree_selected(self):
        if self._updating:return
        self.canvas.set_selected([item.data(0,Qt.ItemDataRole.UserRole) for item in self.objects_tree.selectedItems()]);self._refresh_controls()

    def _object_item_changed(self,item,column):
        if self._updating or self.busy or not self.document:return
        ident=item.data(0,Qt.ItemDataRole.UserRole);obj=next((o for o in self.document.objects if o.id==ident),None)
        if not obj:return
        self._tree_callback=True
        try:
            if column==0:self._commit("Object visibility",lambda:setattr(obj,"visible",item.checkState(0)==Qt.CheckState.Checked))
            elif column==3:self._commit("Object lock",lambda:setattr(obj,"locked",item.checkState(3)==Qt.CheckState.Checked))
        finally:self._tree_callback=False

    def selected_objects(self):
        return [o for o in self.document.objects if o.id in self.canvas.selected] if self.document else []

    def delete_selected(self):
        if self.busy or not self.document:return
        if self.canvas.delete_vertex():return
        if self.canvas.edit_mode:
            self.statusBar().showMessage("Click a polygon/contour vertex before pressing Delete. Exit vertex edit mode to delete whole objects.",8000)
            return
        selected=self.selected_objects()
        if any(o.locked for o in selected):self.notify("Locked object","Unlock the selected objects before deleting them.");return
        if selected:self._commit("Delete objects / restore cleaning pixels",lambda:self.document.delete_objects(self.canvas.selected))

    def edit_object(self,checked=True):
        selected=self.selected_objects()
        if len(selected)!=1 or selected[0].locked or selected[0].role=="cleaning":
            self.edit_action.setChecked(False);self.notify("Edit object","Select one unlocked object.");return
        desired="Edit" if checked else "Manual"
        self.mode.setCurrentText(desired)
        if self.mode.currentText()!=desired:return
        self.canvas.edit_mode=checked;self.edit_action.setChecked(checked);self.canvas.set_tool("select");self.tool_actions["select"].setChecked(True);self.canvas.update()
        if checked:self.statusBar().showMessage("Drag a handle to move it. Del removes one nearest vertex per press within the shown radius. Edit > Vertex deletion radius changes its size.",12000)

    def change_vertex_delete_radius(self):
        value,ok=QInputDialog.getDouble(self,"Vertex deletion radius",
            "Radius in image pixels. Each Del removes the nearest remaining vertex\nwithin this radius, in the selected object only.",self.canvas.vertex_delete_radius,0,10000,2)
        if ok:
            self.vertex_radius.setValue(value)

    def set_vertex_delete_radius(self,value):
        self.canvas.vertex_delete_radius=value;self.settings.setValue("vertex_delete_radius",value);self.settings.sync();self.canvas.update()

    def toggle_cleaning_regions(self,checked):
        self.show_cleaning_button.setText("Show cleaning regions  √" if checked else "Show cleaning regions")
        self.set_canvas_option("show_cleaning",checked)

    def _geometry_changed(self,ident,geometry):
        if not self.document or self.busy:return
        obj=next((o for o in self.document.objects if o.id==ident),None)
        if not obj or obj.locked or obj.role=="cleaning":return
        def change():
            if geometry["kind"]=="contours":
                mask=raster_contours(geometry["contours"],self.document.frame.shape)
                if not mask.any():raise ValueError("The edit would remove the object.")
                obj.mask=mask;obj.kind="mask";obj.points=[];obj.contours=copy.deepcopy(geometry["contours"])
            else:
                mask=None if geometry["kind"]=="point" else shape_mask(geometry["kind"],geometry["points"],self.document.frame.shape)
                if mask is not None and not mask.any():raise ValueError("The edit would remove the object.")
                obj.kind=geometry["kind"];obj.points=geometry["points"];obj.mask=mask;obj.contours=None
            obj.provenance["last_edit"]="vertex edit"
        self._commit("Edit vertices",change)

    def undo(self):
        if self.busy or not self.document:return
        self.canvas.set_preview([]);self._refine_target=None
        try:self.histories[self.current_key].undo()
        except Exception as error:self.notify("Undo / autosave",str(error))
        self.canvas._edit_geometry=self.canvas._active_vertex=self.canvas._delete_origin=None
        self._refresh()

    def redo(self):
        if self.busy or not self.document:return
        self.canvas.set_preview([]);self._refine_target=None
        try:self.histories[self.current_key].redo()
        except Exception as error:self.notify("Redo / autosave",str(error))
        self.canvas._edit_geometry=self.canvas._active_vertex=self.canvas._delete_origin=None
        self._refresh()

    def change_group(self):
        selected=self.selected_objects()
        if not selected or self.busy:return
        if any(o.locked for o in selected):self.notify("Locked object","Unlock the selected objects first.");return
        name,ok=QInputDialog.getItem(self,"Change group","Group name",[g.name for g in self.document.groups],editable=True)
        if ok and name.strip():
            def change():
                group=self.document.ensure_group(name.strip(),self._palette.get(name.strip(),"#148374"))
                for obj in selected:obj.group_id=group.id
            self._commit("Change group",change)

    def change_color(self):
        selected=self.selected_objects()
        if not selected or self.busy:return
        color=QColorDialog.getColor(QColor(selected[0].color),self,"Object color")
        if color.isValid():self._commit("Object color",lambda:[setattr(o,"color",color.name()) for o in selected])

    def assign_mask_colors(self):
        if not self.document or self.busy:return
        dialog=MaskColorsDialog(self.document,bool(self.canvas.selected),self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        values=dialog.values();ids=set(self.canvas.selected) if values["selected_only"] else None
        self._commit("Assign mask colors",lambda:assign_colors(self.document,values["scheme"],ids,values["use_for_new"]))

    def change_transparency(self):
        selected=self.selected_objects()
        if not selected or self.busy:return
        value,ok=QInputDialog.getInt(self,"Object transparency","0% = opaque; 100% = invisible",round((1-selected[0].opacity)*100),0,100)
        if ok:self._commit("Object transparency",lambda:[setattr(o,"opacity",1-value/100) for o in selected])

    def object_properties(self):
        selected=self.selected_objects()
        if len(selected)!=1 or self.busy:return
        obj=selected[0];dialog=QDialog(self);dialog.setWindowTitle("Object properties");layout=QVBoxLayout(dialog);form=QFormLayout();name=QLineEdit(obj.name);locked=QCheckBox("Protect from manual edits");locked.setChecked(obj.locked);form.addRow("Name",name);form.addRow("Lock",locked);layout.addLayout(form)
        area="Point annotation" if obj.mask is None else f"Area: {obj.pixel_area:,} pixel²"
        if obj.mask is not None and self.document.calibration.valid:area+=f"\nPhysical area: {self.document.calibration.area(obj.pixel_area):.8g} {self.document.calibration.length_unit}²"
        layout.addWidget(QLabel(area));controls=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);controls.accepted.connect(dialog.accept);controls.rejected.connect(dialog.reject);layout.addWidget(controls)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            def update():obj.name=name.text().strip() or obj.name;obj.locked=locked.isChecked()
            self._commit("Object properties",update)

    def object_context_menu(self,position):
        if self.busy:return
        item=self.objects_tree.itemAt(position)
        if item and not item.isSelected():
            self.objects_tree.clearSelection();item.setSelected(True)
        self._show_object_context_menu(self.objects_tree.viewport().mapToGlobal(position))

    def _show_object_context_menu(self,position):
        if self.busy:return
        menu=QMenu(self);menu.addAction(self.edit_action);menu.addAction("Properties…",self.object_properties);menu.addAction("Change group…",self.change_group);menu.addSeparator()
        menu.addAction(self.invert_region_action);menu.addAction(self.region_object_action);menu.addAction(self.mask_colors_action);menu.addSeparator()
        if self.mode.currentText()=="Clean":
            action=menu.addAction("Delete for cleaning",self.delete_for_cleaning)
            action.setEnabled(bool(self.selected_objects()) and all(o.role=="object" and o.mask is not None and not o.locked for o in self.selected_objects()))
        menu.addAction("Infer inside selected object / ROI",self.infer_selected_roi)
        menu.addAction("Prompted inference across image",lambda:self.run_inference(force_whole=True))
        menu.addAction("Automatic grid across unannotated image",lambda:self.run_inference(force_automatic=True))
        refine=menu.addAction("Refine selected object explicitly",self.refine_selected_inference)
        refine.setEnabled(len(self.selected_objects())==1 and all(o.role=="object" and o.group_id!=self.document.background_group_id and not o.locked and o.mask is not None for o in self.selected_objects()))
        menu.addSeparator()
        menu.addAction("Fill holes…",lambda:self.refine_masks("holes"));menu.addAction("Smooth edges…",lambda:self.refine_masks("smooth"));menu.addSeparator();menu.addAction(self.delete_action);menu.exec(position)

    def model_dialog(self):
        if self.busy:return
        dialog=ModelDialog(self.engine,self)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            spec,device,path=dialog.values()
            def loaded(result):self.model_label.setText(result["model"]+" · "+result["device"].upper());self.model_label.setToolTip(result["checkpoint"]);self.statusBar().showMessage("Model loaded. Choose Segment and add positive/negative examples, text, or automatic grid.",10000);self.preview_timer.start() if self.mode.currentText()=="Segment" and self.scope.currentData()=="automatic" else None
            self._start_job("Loading model…",lambda progress,cancel:self.engine.load(spec,device,path,progress,cancel),loaded)

    def _text_prompt_changed(self):
        if not self.document:return
        resolved=resolve_prompt(self.text_prompt.text(),self.document.text_aliases)
        self.text_prompt.setToolTip("Effective prompt: "+resolved if resolved else "Text prompts require SAM2+; SAM2 uses Grounding DINO Tiny.")
        self.preview_timer.stop();self._prompt_version+=1;self.canvas.set_preview([]);self._preview_context=None
        if self.busy and self._job_prompt_editable:self._job.cancel.set()
        self._refresh_controls()

    def prompt_aliases_dialog(self):
        if not self.document or self.busy:return
        dialog=PromptAliasesDialog(self.document.text_aliases,self)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            self._commit("Change text aliases",lambda:setattr(self.document,"text_aliases",dialog.values()));self._text_prompt_changed()

    def rotate_image_dialog(self):
        if not self.document or self.busy or self.mode.currentText()!="Edit":return
        if not self._resolve_mode_content():return
        doc=self.document;dialog=RotationDialog(doc,self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        values=dialog.values()
        if abs(values["angle"])%360<1e-9:return
        method=values["fill"]
        if method=="patches" and not doc.background_regions():
            if not self.choose_background_group():return
            if not doc.background_regions():self.notify("Background group","Choose a group containing manual background regions.");return
        if method=="patches" and any((o.mask & doc.modified).any() for o in doc.background_regions()):
            self.notify("Background group","Choose unaffected background regions; a selected region overlaps an image edit.");return
        # A detached document keeps preview/fill failures from changing the live image.
        derived=Document(copy.copy(doc.frame));derived.source_raw=doc.source_raw;derived.source_calibration=copy.deepcopy(doc.source_calibration);derived.restore(doc.state())
        key=self.current_key
        def calculate(progress,cancel):
            target=rotate_document(derived,values["angle"],values["padding"])
            if target.any():
                obj=derived.remove_for_cleaning(target);obj.name="Rotation exposed area";obj.provenance={"method":"rotation padding"}
                if method!="black":
                    raw=derived.working.copy()
                    if method=="neighbors":result=neighbor_fill(raw,target)
                    elif method=="patches":result=patch_fill(raw,target,[o.mask for o in derived.background_regions()])
                    else:result=self._lama_pixels(raw,target,progress,cancel)
                    derived.apply_cleaning_fill(result,target,method,derived.background_group_id if method=="patches" else None)
                else:
                    derived.apply_cleaning_fill(derived.working.copy(),target,"black")
            return derived.state()
        def finished(state):
            if self.current_key!=key:return
            preview=ImagePreviewDialog(doc.working if doc.working is not None else doc.frame.raw,derived.working,"Rotation preview",self)
            if preview.exec()==QDialog.DialogCode.Accepted:
                self._commit("Rotate image and annotations",lambda:doc.restore(state));self.cleaned_checkbox.setChecked(True);self.canvas.fit_image()
        self._start_job("Rotating image and masks…",calculate,finished)

    def _lama_pixels(self,raw,target,progress,cancel):
        rgb=display_rgb(raw);filled=lama_fill(rgb,target,progress=progress,cancel=cancel)
        output=raw.copy();values=filled if raw.ndim==3 else cv2.cvtColor(filled,cv2.COLOR_RGB2GRAY)
        if raw.dtype!=np.uint8:
            finite=raw[np.isfinite(raw)]
            lo,hi=np.percentile(finite[::max(1,finite.size//500_000)],[.5,99.5]) if finite.size else (0,1)
            values=values.astype(float)/255*(hi-lo)+lo
        if raw.ndim==3 and raw.shape[-1]==4:output[target,:3]=cast_like(values[target],raw.dtype)
        else:output[target]=cast_like(values[target],raw.dtype)
        return output

    def scale_masks_dialog(self):
        if not self.document or self.busy or self.mode.currentText()!="Edit":return
        doc=self.document;points=self.mask_savepoints.setdefault(doc.frame.key,[])
        dialog=MaskScaleDialog(doc,self.canvas.selected,points,self)
        if dialog.exec()!=QDialog.DialogCode.Accepted or not dialog.operation:return
        operation=dialog.operation
        if operation["kind"]=="restore":
            self._commit("Restore mask savepoint",lambda:mask_savepoints.restore(doc,operation["snapshot"]));return
        original=mask_savepoints.capture(doc,"original")
        saved=[]
        def apply():
            apply_scaled_objects(doc,operation["replacements"])
            result=mask_savepoints.capture(doc,operation["name"])
            if operation["storage"]=="local":
                saved.append(mask_savepoints.write_local(original,operation["directory"]));saved.append(mask_savepoints.write_local(result,operation["directory"]))
            else:
                if not any(p["name"]=="original" and p["coordinates"]==original["coordinates"] for p in points):points.append(original)
                points.append(result)
        self._commit("Scale object masks",apply)

    def morphology_dialog(self):
        selected=self.selected_objects()
        if not self.document or self.busy or self.mode.currentText()!="Edit":return
        if len(selected)!=1 or selected[0].mask is None or selected[0].role!="object" or selected[0].locked:
            self.notify("Morphology","Select one unlocked outer area object.");return
        obj=selected[0];dialog=MorphologyDialog(self.document,obj,self)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            self._commit("Set object morphology",lambda:obj.provenance.update(morphology=dialog.values()))

    def inference_options(self):
        dialog=InferenceOptionsDialog(self.options,self)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.options=dialog.values()

    def run_inference(self,checked=False,force_whole=None,force_automatic=False):
        if self.busy or not self.document:return
        if not self.engine.ready:self.notify("Model required","Load a SAM model using Model manager first.");return
        doc=self.document;key=self.current_key
        automatic=force_automatic or (force_whole is None and self.scope.currentData()=="automatic")
        whole=self.scope.currentData()!="roi" if force_whole is None else force_whole
        version=self._prompt_version
        try:
            if automatic:self._refine_target=None
            exact_region=bool(doc.draft.get("roi") and doc.draft["roi"].get("kind")=="mask")
            clip=self._selection_mask() if exact_region else None
            if clip is not None and not clip.any():raise ValueError("The selected region is empty. Invert again or choose a nonempty region.")
            roi=self._selection_mask() if doc.draft.get("roi") and not automatic else None
            if exact_region:whole=False
            points=copy.deepcopy(doc.draft.get("points",[])) if not automatic else []
            has_text=bool(self.engine.spec.family in ("SAM2","SAM2.1","SAM3","SAM3.1") and self.text_prompt.text().strip())
            examples=self._whole_image_examples(doc,roi)
            exemplar_mode=self.scope.currentData()=="prompt" and not automatic and clip is None and force_whole is None and not self._refine_target
            if not automatic and not points and roi is None and not has_text and not examples:
                selected=self.selected_objects()
                if len(selected)==1:
                    obj=selected[0]
                    if obj.mask is not None:roi=obj.mask.copy()
                    elif obj.kind=="point" and obj.points:points=[[obj.points[0][0],obj.points[0][1],1]]
                # Preserve the old explicit API path for callers requesting a
                # grid with no prompt, while the GUI has a separate grid choice.
                if not points and roi is None and not has_text:
                    if force_whole is True:automatic=True
                    else:raise ValueError("Add a point or draw a shape prompt. For all objects, choose Automatic grid explicitly.")
            if points and roi is None:whole=True  # A dot never defines a one-pixel ROI.
            if points and not any(p[2] for p in points) and roi is None and not has_text and not any(e.get("label",1) for e in examples):raise ValueError("Add at least one positive (left-click) point.")
            protected=doc.protected_mask([self._refine_target] if self._refine_target and not automatic else [])
            if clip is not None:protected|=~clip
            raw=doc.working if self.cleaned_checkbox.isChecked() and doc.working is not None else doc.frame.raw
            rgb=display_rgb(raw);text=resolve_prompt(self.text_prompt.text(),doc.text_aliases) if not automatic and self.engine.spec.family in ("SAM2","SAM2.1","SAM3","SAM3.1") else ""
            context={"target":self._refine_target,"method":"SAM","model":self.engine.spec.label,
                     "device":self.engine.device,"input":"cleaned" if raw is doc.working else "original",
                     "normalization":"uint8 RGB; non-uint8 0.5–99.5 percentile stretch"}
            if exemplar_mode:context.update(prompt_mode="whole-image exemplars",example_backend=self.engine.spec.family+" native concepts" if self.engine.spec.family in ("SAM3","SAM3.1") else "SAM candidates + feature/intensity retrieval",examples=copy.deepcopy(examples),point_examples=copy.deepcopy(points))
            if text:context.update(text_prompt=self.text_prompt.text().strip(),effective_text_prompt=text,text_backend=self.engine.spec.family if self.engine.spec.family in ("SAM3","SAM3.1") else "Grounding DINO Tiny → SAM2")
            if clip is not None:context["clip_region"]=pack_mask(clip)
            self.canvas.set_preview([]);self._preview_context=None;self._refine_target=None
            def finished(masks):
                if self.current_key!=key:return
                if self._prompt_version!=version:
                    self.statusBar().showMessage("Newer prompts received. Updating the preview…",5000)
                    return
                if clip is not None:masks=filter_proposals(masks,protected,clip,min_area=self.options["min_area"])
                context["confidence_scores"]=list(getattr(self.engine,"last_proposal_scores",[]))
                self._preview_context=context
                self.canvas.set_preview(masks);self.statusBar().showMessage(f"{len(masks)} preview mask(s). Review and click Accept masks." if masks else "No eligible new masks. Accepted objects stay protected. Use explicit Refine to change an existing object.",12000)
            self._start_job("Running automatic grid…" if automatic else "Running prompted segmentation…",
                lambda progress,cancel:self._example_inference(self.engine,rgb,points,examples,protected,progress,cancel,text,self.options) if exemplar_mode else self.engine.infer(rgb,points,roi,protected,whole=whole or automatic,progress=progress,cancel=cancel,text_prompt=text,**self.options),
                finished,prompt_editable=not automatic)
        except Exception as error:self.notify("Segmentation",str(error))

    def infer_selected_roi(self):
        if not self.document:return
        objects=self.selected_objects()
        if len(objects)!=1 or objects[0].mask is None:self.notify("ROI required","Select one area object, or draw an ROI.");return
        x,y,w,h=bounding_box(objects[0].mask)
        self.document.draft["roi"]={"kind":"rectangle","points":[[x,y],[x+w,y+h]]};self.document.draft["points"]=[];self._refine_target=None;self.run_inference(force_whole=False)

    def refine_selected_inference(self):
        selected=self.selected_objects()
        if len(selected)!=1 or selected[0].mask is None or selected[0].locked or selected[0].role!="object" or selected[0].group_id==self.document.background_group_id:self.notify("Refine selected object","Select one unlocked foreground area object. Cleaning regions retain their exact pixel footprint.");return
        from scipy.ndimage import distance_transform_edt
        obj=selected[0];yy,xx=np.unravel_index(np.argmax(distance_transform_edt(obj.mask)),obj.mask.shape)
        x,y,w,h=bounding_box(obj.mask);self._refine_target=obj.id
        self.document.draft.update({"roi":{"kind":"rectangle","points":[[x,y],[x+w,y+h]]},"points":[[float(xx),float(yy),1]]})
        self._mode_guard=True
        try:self.mode.setCurrentText("Segment")
        finally:self._mode_guard=False
        self.run_inference(force_whole=False)

    def accept_preview(self):
        if not self.document or self.busy or not self.canvas.preview_masks:return
        if not self._ensure_group():return
        doc=self.document;context=copy.deepcopy(self._preview_context or {});target=context.pop("target",None)
        clip=context.pop("clip_region",None)
        scores=context.pop("confidence_scores",[])
        masks=filter_proposals(self.canvas.preview_masks,doc.protected_mask([target] if target else []),
                               unpack_mask(clip,doc.frame.shape) if clip else None,min_area=1)
        if not masks:
            self.canvas.set_preview([]);self._refine_target=None;self._refresh();self.notify("Preview is no longer eligible","Accepted objects now occupy this preview. Run segmentation again.");return
        def accept():
            provenance=context or {"method":"SAM","model":self.engine.spec.label,"device":self.engine.device,
                                  "input":"original","normalization":"uint8 RGB"}
            if target:
                obj=next(o for o in doc.objects if o.id==target)
                if obj.locked or obj.role!="object" or obj.group_id==doc.background_group_id:raise ValueError("Choose an unlocked foreground object before refining it.")
                obj.mask=masks[0];obj.kind="mask";obj.points=[];obj.contours=None;obj.provenance={**provenance,"confidence_score":scores[0] if scores else None}
            else:
                for i,mask in enumerate(masks):doc.add_object("mask",mask=mask,provenance={**provenance,"confidence_score":scores[i] if i<len(scores) else None})
            doc.draft["roi"]=None;doc.draft["points"]=[];doc.draft["examples"]=[]
        if self._commit("Accept SAM masks",accept):self.canvas.set_preview([]);self._refine_target=None;self._refresh()

    def cancel_operation(self):
        self.preview_timer.stop();self._pending_preview=False;self._prompt_version+=1
        if self.busy:self._job.cancel.set();self.statusBar().showMessage("Stopping after the current model operation…");return
        self.canvas.set_tool(self.canvas.tool)
        self.canvas.set_preview([]);self._refine_target=None
        if self.document:self._commit("Clear prompts / region",lambda:self.document.draft.update({"points":[],"roi":None,"examples":[]}))

    def refine_masks(self,method):
        if self.busy or not self.document:return
        ids=list(self.canvas.selected)
        if not ids:self.notify("Select objects","Select one or more objects in the Objects panel.");return
        dialog=RefinementDialog(self.document,ids,method,self)
        if dialog.exec()==QDialog.DialogCode.Accepted and dialog.results:
            def update():
                for obj in self.document.objects:
                    if obj.id in dialog.results:
                        obj.mask=dialog.results[obj.id].copy();obj.kind="mask";obj.points=[]
                        obj.contours=copy.deepcopy(dialog.contours.get(obj.id)) if method=="smooth" else None
                        obj.provenance["last_refinement"]="fill holes" if method=="holes" else "smooth edges"
            self._commit("Fill holes" if method=="holes" else "Smooth edges",update)

    def edit_calibration(self):
        if not self.document or self.busy:return
        dialog=CalibrationDialog(self.document.calibration,self)
        if dialog.exec()==QDialog.DialogCode.Accepted:self._commit("Edit calibration",lambda:setattr(self.document,"calibration",dialog.value()))

    def plot_statistics(self):
        if not self.document:return
        dialog=StatisticsDialog(self.documents.values(),self.document,self.canvas.selected,self.selected_images(),self)
        self.stats_dialogs.append(dialog);dialog.finished.connect(lambda result,d=dialog:self.stats_dialogs.remove(d) if d in self.stats_dialogs else None);dialog.show()

    def set_canvas_option(self,attribute,value):
        setattr(self.canvas,attribute,value);self.canvas.refresh()

    def adjust_display(self):
        if not self.document:return
        before=(self.canvas.brightness,self.canvas.contrast);dialog=BrightnessDialog(*before,self)
        def changed(brightness,contrast):self.canvas.brightness=brightness;self.canvas.contrast=contrast;self.canvas.refresh()
        dialog.changed.connect(changed)
        if dialog.exec()!=QDialog.DialogCode.Accepted:changed(*before)

    def smooth_image_dialog(self):
        if not self.document or self.busy:return
        doc=self.document;region=self._selection_mask()
        dialog=SmoothImageDialog(doc,region is not None and bool(region.any()),self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        values=dialog.values();target=region.copy() if values["scope"]=="selection" and region is not None else np.ones(doc.frame.shape,bool)
        target&=~doc.removed
        if not target.any():self.notify("Smooth image","No eligible pixels. Fill or restore removed pixels first.");return
        raw=(doc.working if values["source"]=="cleaned" and doc.working is not None else doc.frame.raw).copy()
        key=self.current_key
        def finished(result):
            if self.current_key!=key:return
            preview=ImagePreviewDialog(raw,result,"Smooth image preview",self)
            if preview.exec()!=QDialog.DialogCode.Accepted:return
            if self._commit("Smooth image pixels",lambda:doc.apply_image_smoothing(result,target,values["method"],values)):
                self.cleaned_checkbox.setChecked(True)
        self._start_job("Smoothing image pixels…",lambda progress,cancel:smooth_image(raw,values["method"],values["sigma"],values["size"],target),finished)

    def remove_area(self):
        if self.busy or not self.document:return
        try:
            mask=self._selection_mask()
            if mask is None or not mask.any():raise ValueError("Draw a cleaning region or select an area object first.")
            def remove():
                doc=self.document
                doc.remove_for_cleaning(mask);doc.draft["roi"]=None
            self._commit("Remove image area",remove);self.cleaned_checkbox.setChecked(True)
        except Exception as error:self.notify("Cleaning",str(error))

    def delete_for_cleaning(self):
        if self.busy or not self.document:return
        if self.mode.currentText()!="Clean":
            self.notify("Cleaning mode","Switch to Clean before using Delete for cleaning.");return
        selected=self.selected_objects()
        if not selected or any(o.mask is None or o.locked or o.role!="object" for o in selected):
            self.notify("Cleaning selection","Choose unlocked area objects.");return
        def remove():
            for obj in selected:self.document.remove_for_cleaning(obj.mask,source=obj)
            self.document.draft["roi"]=None
        if self._commit("Delete objects for cleaning",remove):self.cleaned_checkbox.setChecked(True)

    def restore_area(self):
        if self.busy or not self.document:return
        try:
            mask=self._selection_mask()
            if mask is None:mask=self.document.modified.copy()
            if not mask.any():raise ValueError("There are no modified pixels to restore.")
            def restore():
                doc=self.document
                doc.restore_cleaning_area(mask);doc.draft["roi"]=None
            self._commit("Restore image area",restore)
        except Exception as error:self.notify("Restore",str(error))

    def choose_background_group(self):
        if not self.document or self.busy:return False
        doc=self.document
        names=[g.name for g in doc.groups if any(o.group_id==g.id and o.role=="object" and o.mask is not None
               and o.provenance.get("method")=="manual" for o in doc.objects)]
        if not names:
            self.notify("Background group","In Manual mode, draw unaffected background regions in a group of any name, then choose that group here.");return False
        current=doc.get_group(doc.background_group_id).name if doc.background_group_id else ""
        name,ok=QInputDialog.getItem(self,"Choose background group","Use manually drawn regions from this group as background:",names,max(0,names.index(current) if current in names else 0),False)
        if not ok:return False
        group=next(g for g in doc.groups if g.name==name)
        return self._commit("Choose background group",lambda:setattr(doc,"background_group_id",group.id))

    def add_patch(self):
        if not self.document or self.busy:return
        doc=self.document;roi=doc.draft.get("roi")
        if not roi:self.choose_background_group();return
        if not doc.background_group_id:
            self.notify("Background group","Create manual background regions in their own group, then choose that group before adding more regions.");return
        try:
            mask=self._selection_mask()
            if mask is None or not mask.any() or (mask & doc.modified).any():raise ValueError("Choose an unaffected background region.")
            def add():
                active=doc.active_group;doc.active_group=doc.background_group_id
                doc.add_object("mask",mask=mask,provenance={"method":"manual"})
                doc.active_group=active;doc.draft["roi"]=None
            self._commit("Add background region",add)
        except Exception as error:self.notify("Background region",str(error))

    def clear_patches(self):
        if self.document:self._commit("Clear background group selection",lambda:setattr(self.document,"background_group_id",None))

    def change_brush_radius(self):
        value,ok=QInputDialog.getInt(self,"Cleaning brush","Radius in pixels",self.canvas.brush_radius,1,500)
        if ok:self.canvas.brush_radius=value

    def fill_removed(self,method):
        if not self.document or self.busy:return
        doc=self.document;target=doc.removed.copy()
        if not target.any():self.notify("Fill region","Remove an image area first. Fill Holes in Edit instead operates on object masks.");return
        patches=[]
        if method=="patches":
            if not doc.background_group_id and not self.choose_background_group():return
            regions=doc.background_regions()
            if not regions:self.notify("Background group","The selected group has no manual area regions.");return
            if any((o.mask & doc.modified).any() for o in regions):
                self.notify("Background group","Choose unaffected background regions; a selected region overlaps a cleaning edit.");return
            patches=[o.mask.copy() for o in regions]
        raw=(doc.working if doc.working is not None else doc.frame.raw).copy();key=self.current_key
        background_id=doc.background_group_id
        def calculate(progress,cancel):
            if method=="neighbors":return neighbor_fill(raw,target)
            if method=="patches":return patch_fill(raw,target,patches)
            rgb=display_rgb(raw);result=lama_fill(rgb,target,progress=progress,cancel=cancel)
            output=raw.copy();values=result if raw.ndim==3 else cv2.cvtColor(result,cv2.COLOR_RGB2GRAY)
            if raw.dtype!=np.uint8:
                finite=np.asarray(raw)[np.isfinite(raw)];sample=finite[::max(1,finite.size//500_000)];lo,hi=np.percentile(sample,[.5,99.5]);values=values.astype(float)/255*(hi-lo)+lo
            if raw.ndim==3 and raw.shape[-1]==4:output[target,:3]=cast_like(values[target],raw.dtype)
            else:output[target]=cast_like(values[target],raw.dtype)
            return output
        def finished(result):
            if self.current_key!=key:return
            # Show a disposable preview, then require an explicit Apply before changing saved image pixels.
            dialog=QDialog(self);dialog.setWindowTitle("Cleaning fill preview");layout=QVBoxLayout(dialog)
            from .canvas import rgb_image
            preview=QLabel();preview.setPixmap(QPixmap.fromImage(rgb_image(display_rgb(result))).scaled(780,550,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation));layout.addWidget(preview)
            layout.addWidget(QLabel("Preview of generated/estimated replacement pixels. The original image stays unchanged."));controls=QDialogButtonBox(QDialogButtonBox.StandardButton.Apply|QDialogButtonBox.StandardButton.Cancel);controls.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(dialog.accept);controls.rejected.connect(dialog.reject);layout.addWidget(controls)
            if dialog.exec()==QDialog.DialogCode.Accepted:
                def apply():doc.apply_cleaning_fill(result,target,method,background_id if method=="patches" else None)
                self._commit("Fill image region",apply);self.cleaned_checkbox.setChecked(True)
        self._start_job("Filling removed pixels…",calculate,finished)

    def save_mask_dialog(self,transparent=False):
        if not self.document or self.busy:return
        dialog=SaveMasksDialog(self.document,bool(transparent),self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        folder=QFileDialog.getExistingDirectory(self,"Save mask images")
        if not folder:return
        try:
            paths=save_masks(self.document,Path(folder),**dialog.values());self.statusBar().showMessage(f"Saved {len(paths)} mask / source image file(s).",10000)
        except Exception as error:self.notify("Save masks",str(error))

    def export_dataset(self,format):
        if not self.documents or self.busy:return
        choice,ok=QInputDialog.getItem(self,"Dataset export","Image scope",["Current image","Selected images","All open images"],editable=False)
        if not ok:return
        docs=[self.document] if choice=="Current image" else [d for k,d in self.documents.items() if k in self.selected_images()] if choice=="Selected images" else list(self.documents.values())
        docs=[d for d in docs if d is not None]
        if not docs:self.notify("Dataset export","Select image entries in the Image files panel.");return
        image_dialog=ImageExportDialog(docs,True,self)
        if image_dialog.exec()!=QDialog.DialogCode.Accepted:return
        versions=image_dialog.values();original=versions["save_original_image"];cleaned=versions["save_cleaned_image"]
        image_options={"include_images":original or cleaned,"image_source":"cleaned" if cleaned else "original","include_alternate":original and cleaned}
        lossy=False
        if format=="yolo":
            answer=QMessageBox.question(self,"YOLO polygons","Allow lossy conversion of holes / disconnected masks?\nChoose No to require exact compatibility. COCO preserves exact mask pixels.",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.No)
            if answer==QMessageBox.StandardButton.Cancel:return
            lossy=answer==QMessageBox.StandardButton.Yes
        folder=QFileDialog.getExistingDirectory(self,"Choose dataset output folder")
        if not folder:return
        try:
            result=export_coco(docs,Path(folder),**image_options) if format=="coco" else export_yolo(docs,Path(folder),lossy,**image_options)
            self.statusBar().showMessage(f"{format.upper()} export complete. Point annotations excluded: {result.get('skipped_points',0)}.",12000)
        except Exception as error:self.notify("Dataset export",str(error))

    def export_cleaned(self):
        if not self.document or self.busy:return
        path,_=QFileDialog.getSaveFileName(self,"Save derived cleaned image",Path(self.document.frame.source_path).stem+"_cleaned.tif","TIFF (*.tif *.tiff)")
        if path:
            try:save_cleaned(self.document,path);self.statusBar().showMessage("Saved derived TIFF and cleaning history.",10000)
            except Exception as error:self.notify("Save cleaned image",str(error))

    def export_images(self):
        if not self.document or self.busy:return
        dialog=ImageExportDialog([self.document],False,self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        folder=QFileDialog.getExistingDirectory(self,"Save image versions as TIFF")
        if not folder:return
        try:
            paths=save_image_versions(self.document,Path(folder),**dialog.values())
            self.statusBar().showMessage(f"Saved {len(paths)} image version(s) as TIFF.",10000)
        except Exception as error:self.notify("Save images",str(error))

    def open_pdf_help(self,developer=False,denoise=False):
        try:
            from .help_viewer import open_pdf_help
            return open_pdf_help(self,bool(developer),denoise)
        except Exception as error:self.notify("Help",str(error))

    def quick_start(self):
        text=("1. Open images and load SAM2.1 Tiny on CPU.\n"
              "2. Manual draws annotations. Close a polygon within 3 image pixels of its start, or press Enter.\n"
              "3. Segment uses point/shape prompts. Left/right clicks add positive/negative points. Review and Accept masks. Automatic grid is a separate scope.\n"
              "4. Edit (Ctrl+E) moves existing handles and deletes nearby vertices. Set the radius in the top bar; default 20 image pixels.\n"
              "5. Select some objects (Ctrl+click) or all (Ctrl+A), then Invert region (Ctrl+I). This selects remaining image pixels. Manual/Edit can Create object from region. Clean can remove it. Segment clips prompted or grid results to it.\n"
              "6. Clean removes image regions. Right-click an object > Delete for cleaning. Delete a cleaning object to restore its pixels. For patch fill, choose a group of manually drawn background regions, then fill and review.\n"
              "7. Smooth image pixels offers Gaussian and median filters with preview and Undo. Smooth edges instead changes mask geometry. Original acquired pixels remain available.\n"
              "8. Assign mask colors offers default group colors or a 20-color lookup table, by object or group.\n"
              "9. Save masks retains binary, weighted overlap, colors and transparency. Optionally save original and/or processed TIFF images. Dataset export also offers either version, both, or annotations only.\n"
              "10. Edit > Rotate image offers presets, free angles and optional rectangle/square padding with black, neighbors, LaMa or background fill. Review the preview.\n"
              "11. Edit > Scale masks scales selected objects or a group. Temporary savepoints stay in memory. Local saves include original masks and editable geometry.\n"
              "12. SAM2+ supports text prompts and project aliases. SAM2 uses Grounding DINO Tiny. Clear text to return to point/shape prompts.\n"
              "13. Statistics plots up to nine metrics. Set axes/colors and export all or selected measurements, summaries and histograms. Use Edit > Morphology to link cores/cavities.\n"
              "14. When switching mode, Yes adds pending shapes, No discards them, and Cancel keeps the current mode. Work autosaves.\n\n"
              "Hand or middle-drag = pan. Reset or F = fit. Ctrl+Z/Y = undo/redo.")
        QMessageBox.information(self,"Quick start",text)

    def diagnostics(self):
        import importlib.metadata as metadata
        names=["PySide6","numpy","scipy","torch","torchvision","segment-anything","SAM-2","rosettasciio","tifffile","transformers","huggingface-hub"]
        values=[]
        for name in names:
            try:values.append(name+": "+metadata.version(name))
            except metadata.PackageNotFoundError:values.append(name+": not installed")
        QMessageBox.information(self,"Diagnostics",f"SAM Image Studio {__version__}\n"+"\n".join(values)+f"\n\nData / log folder: {data_directory()}\nNative SAM3 needs the optional CUDA environment.")

    def closeEvent(self,event):
        self.preview_timer.stop()
        if self.busy:
            answer=QMessageBox.question(self,"Operation running","Cancel the current operation and close when it stops?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
            if answer==QMessageBox.StandardButton.Yes:self._close_requested=True;self._job.cancel.set()
            event.ignore();return
        for doc in self.documents.values():
            if doc.revision!=doc.saved_revision:
                try:self._persist(doc)
                except Exception as error:self.notify("Close blocked",f"Some changes could not be saved. Choose a writable project folder.\n{error}");event.ignore();return
        self.settings.setValue("last_files",list(dict.fromkeys(d.frame.source_path for d in self.documents.values())));self.settings.sync();event.accept()

