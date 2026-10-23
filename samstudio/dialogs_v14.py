"""Editing controls introduced in 1.4; all product text is English."""
from __future__ import annotations
import copy
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QLineEdit,
 QDoubleSpinBox,QSpinBox,QSlider,QPushButton,QCheckBox,QDialogButtonBox,QListWidget,
 QTableWidget,QTableWidgetItem,QHeaderView,QFileDialog,QMessageBox)
from .dialogs import combo,buttons
from .canvas import rgb_image
from .processing import display_rgb


class PromptAliasesDialog(QDialog):
    def __init__(self,aliases,parent=None):
        super().__init__(parent);self.setWindowTitle('Text prompt aliases');self.resize(680,400)
        layout=QVBoxLayout(self)
        label=QLabel('Map a complete phrase to an effective prompt. Example: nanoparticle → big dots.\nAliases are case insensitive and are saved in this project. Separate concepts with periods.');label.setWordWrap(True);layout.addWidget(label)
        self.table=QTableWidget(0,2);self.table.setHorizontalHeaderLabels(['Alias','Effective prompt']);self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for alias,target in aliases.items():self.add_row(alias,target)
        layout.addWidget(self.table);row=QHBoxLayout();add=QPushButton('Add alias');remove=QPushButton('Remove selected');row.addWidget(add);row.addWidget(remove);layout.addLayout(row)
        add.clicked.connect(lambda:self.add_row());remove.clicked.connect(self.remove_rows)
        buttons(self,layout)
    def add_row(self,alias='',target=''):
        row=self.table.rowCount();self.table.insertRow(row)
        self.table.setItem(row,0,QTableWidgetItem(alias));self.table.setItem(row,1,QTableWidgetItem(target))
    def remove_rows(self):
        for row in sorted({i.row() for i in self.table.selectedIndexes()},reverse=True):self.table.removeRow(row)
    def values(self):
        from .text_prompts import validate_aliases
        rows=[]
        for r in range(self.table.rowCount()):
            a=self.table.item(r,0);b=self.table.item(r,1)
            a=a.text().strip() if a else '';b=b.text().strip() if b else ''
            if a or b:rows.append((a,b))
        if len({a.casefold() for a,b in rows})!=len(rows):raise ValueError('Aliases must be unique (case insensitive).')
        return validate_aliases(dict(rows))
    def accept(self):
        try:self.values()
        except ValueError as error:QMessageBox.warning(self,'Prompt aliases',str(error));return
        super().accept()


class RotationDialog(QDialog):
    def __init__(self,document,parent=None):
        super().__init__(parent);self.document=document;self.setWindowTitle('Rotate image and annotations');self.resize(800,690)
        layout=QVBoxLayout(self);form=QFormLayout()
        self.preset=combo([(f'{a}°',a) for a in (0,30,45,60,90,120,135,150,180,210,225,240,270,300,315,330)]+[('Custom',None)])
        self.angle=QDoubleSpinBox();self.angle.setObjectName('rotationAngle');self.angle.setRange(-360,360);self.angle.setDecimals(2);self.angle.setSuffix('°')
        self.padding=combo([('No padding (crop to current dimensions)','none'),('Pad to enclosing rectangle','rectangle'),('Pad to enclosing square','square')])
        self.fill=combo([('Black','black'),('Neighboring pixels','neighbors'),('LaMa','lama'),('Selected manual background group','patches')])
        for label,widget in [('Preset',self.preset),('Angle, counterclockwise',self.angle),('Canvas',self.padding),('Exposed area fill',self.fill)]:form.addRow(label,widget)
        layout.addLayout(form)
        self.preset.currentIndexChanged.connect(lambda:self.angle.setValue(self.preset.currentData()) if self.preset.currentData() is not None else None)
        self.angle.valueChanged.connect(self.sync_preset)
        label=QLabel('All masks and cleaning regions rotate with the image. No padding keeps the current rectangle and crops its corners. Generated fills are retained as restorable cleaning objects. Undo restores the exact previous pixels and shapes.');label.setWordWrap(True);layout.addWidget(label)
        self.preview=QLabel();self.preview.setMinimumSize(400,300);self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter);layout.addWidget(self.preview,1)
        self.status=QLabel();layout.addWidget(self.status)
        self.angle.valueChanged.connect(self.refresh);self.padding.currentIndexChanged.connect(self.refresh)
        controls=buttons(self,layout);controls.button(QDialogButtonBox.StandardButton.Ok).setText('Rotate')
        self.refresh()
    def sync_preset(self,angle):
        index=self.preset.findData(float(angle))
        self.preset.blockSignals(True);self.preset.setCurrentIndex(index if index>=0 else self.preset.count()-1);self.preset.blockSignals(False)

    def refresh(self):
        from .transforms import rotation_matrix,warp_pixels
        try:
            matrix,shape=rotation_matrix(self.document.frame.shape,self.angle.value(),self.padding.currentData())
            rgb=warp_pixels(display_rgb(self.document.working if self.document.working is not None else self.document.frame.raw),matrix,shape)
            self.preview.setPixmap(QPixmap.fromImage(rgb_image(rgb)).scaled(720,380,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
            self.status.setText(f'Output: {shape[1]} × {shape[0]} pixels. Preview shows black exposed areas; the chosen fill is applied after rotation.')
        except Exception as error:self.status.setText(str(error))
    def values(self):return {'angle':self.angle.value(),'padding':self.padding.currentData(),'fill':self.fill.currentData()}


class MorphologyDialog(QDialog):
    def __init__(self,document,obj,parent=None):
        super().__init__(parent);self.setWindowTitle('Morphology and linked inner region');layout=QVBoxLayout(self);form=QFormLayout()
        self.kind=combo([('General particle','general'),('Rod / elongated particle','rod'),('Regular polygon','polygon'),('Core–shell particle','core-shell'),('Hollow particle','hollow')])
        self.inner=combo([('Not linked',None)]+[(o.name+' — '+document.get_group(o.group_id).name,o.id) for o in document.foreground_objects() if o.id!=obj.id and o.mask is not None])
        self.sides=QSpinBox();self.sides.setRange(3,20);self.sides.setValue(4)
        config=obj.provenance.get('morphology',{});self.kind.setCurrentIndex(max(0,self.kind.findData(config.get('type','general'))));self.inner.setCurrentIndex(max(0,self.inner.findData(config.get('inner_id'))));self.sides.setValue(config.get('sides',4))
        for label,widget in [('Morphology',self.kind),('Core / cavity object',self.inner),('Expected regular-polygon sides',self.sides)]:form.addRow(label,widget)
        layout.addLayout(form);label=QLabel('The selected object defines the outer particle. Link a distinct, fully enclosed inner region. Referenced core/cavity objects are excluded from particle count, but remain in object measurements. Thickness is the nearest outer-boundary distance from sampled inner-boundary points; CV = standard deviation / mean.');label.setWordWrap(True);layout.addWidget(label);buttons(self,layout)
    def values(self):return {'type':self.kind.currentData(),'inner_id':self.inner.currentData() if self.kind.currentData() in ('core-shell','hollow') else None,'sides':self.sides.value()}


class MaskScaleDialog(QDialog):
    def __init__(self,document,selected_ids,savepoints,parent=None):
        super().__init__(parent);self.document=document;self.selected_ids=set(selected_ids);self.savepoints=savepoints;self.operation=None
        self.setWindowTitle('Scale masks and manage savepoints');self.resize(820,700)
        layout=QVBoxLayout(self);form=QFormLayout()
        self.scope=combo([('Selected object(s)','selected'),('All area objects in the selected group','group')])
        self.factor=QDoubleSpinBox();self.factor.setRange(.01,10);self.factor.setDecimals(3);self.factor.setValue(1.);self.factor.setSingleStep(.05)
        self.slider=QSlider(Qt.Orientation.Horizontal);self.slider.setRange(1,1000);self.slider.setValue(100)
        self.factor.valueChanged.connect(self.sync_slider);self.slider.valueChanged.connect(lambda v:self.factor.setValue(v/100))
        self.storage=combo([('Temporary (memory only)','temporary'),('Local folder','local')])
        self.name_edit=QLineEdit();self.name_edit.setPlaceholderText('Default: × factor; original is preserved before scaling')
        for label,widget in [('Scale',self.scope),('Factor (relative to opening shapes)',self.factor),('Adjust factor',self.slider),('Savepoints',self.storage),('Result savepoint name',self.name_edit)]:form.addRow(label,widget)
        layout.addLayout(form)
        self.preview=QLabel();self.preview.setMinimumHeight(230);self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter);layout.addWidget(self.preview,1)
        self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status)
        self.list=QListWidget();self.list.setMaximumHeight(100)
        for snap in savepoints:self.list.addItem(snap['name'])
        layout.addWidget(QLabel('Temporary savepoints (not written to projects or folders):'));layout.addWidget(self.list)
        row=QHBoxLayout();restore=QPushButton('Restore selected');load=QPushButton('Restore local snapshot…');row.addWidget(restore);row.addWidget(load);layout.addLayout(row)
        restore.clicked.connect(self.restore_selected);load.clicked.connect(self.restore_local)
        controls=buttons(self,layout);controls.button(QDialogButtonBox.StandardButton.Ok).setText('Apply scale')
        self.factor.valueChanged.connect(self.refresh);self.scope.currentIndexChanged.connect(self.refresh);self.refresh()
    def sync_slider(self,value):
        self.slider.blockSignals(True);self.slider.setValue(round(value*100));self.slider.blockSignals(False)

    def object_ids(self):
        selected=[o for o in self.document.objects if o.id in self.selected_ids]
        if self.scope.currentData()=='group':
            groups={o.group_id for o in selected}
            if len(groups)!=1:raise ValueError('Select an object in exactly one group.')
            return {o.id for o in self.document.objects if o.group_id in groups and o.role=='object' and o.mask is not None}
        return self.selected_ids
    def refresh(self):
        from .transforms import scaled_objects
        try:
            self.replacements=scaled_objects(self.document,self.object_ids(),self.factor.value())
            rgb=display_rgb(self.document.working if self.document.working is not None else self.document.frame.raw).copy()
            union=np.logical_or.reduce([o.mask for o in self.replacements]);rgb[union]=(rgb[union].astype(float)*.45+np.array([50,200,180])*.55).astype(np.uint8)
            self.preview.setPixmap(QPixmap.fromImage(rgb_image(rgb)).scaled(730,290,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
            self.status.setText(f'{len(self.replacements)} object(s); {sum(o.pixel_area for o in self.replacements):,} mask pixels. Each object scales about its own centroid. Image boundaries clip masks; overlaps are allowed.')
        except Exception as error:self.replacements=None;self.status.setText(str(error))
    def restore_selected(self):
        row=self.list.currentRow()
        if row>=0:self.operation={'kind':'restore','snapshot':copy.deepcopy(self.savepoints[row])};super().accept()
    def restore_local(self):
        from .savepoints import read_local
        path,_=QFileDialog.getOpenFileName(self,'Restore mask savepoint','','Snapshot (snapshot.json)')
        if path:
            try:self.operation={'kind':'restore','snapshot':read_local(path)};super().accept()
            except Exception as error:QMessageBox.warning(self,'Mask savepoint',str(error))
    def accept(self):
        if not self.replacements:QMessageBox.warning(self,'Scale masks',self.status.text());return
        directory=None
        if self.storage.currentData()=='local':
            directory=QFileDialog.getExistingDirectory(self,'Save original and scaled masks')
            if not directory:return
        self.operation={'kind':'scale','replacements':self.replacements,'factor':self.factor.value(),
                        'name':self.name_edit.text().strip() or f'×{self.factor.value():g}',
                        'storage':self.storage.currentData(),'directory':directory}
        super().accept()
