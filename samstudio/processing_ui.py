from __future__ import annotations
import copy
from pathlib import Path
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QFormLayout,QComboBox,QCheckBox,QSpinBox,QDoubleSpinBox,
    QPushButton,QDialogButtonBox,QLabel,QInputDialog,QFileDialog,QLineEdit,QListWidget,QHBoxLayout,QMessageBox,QScrollArea,QWidget,QTextBrowser)
from .image_processing import METHODS,parameters,process_pixels,processing_target,apply_processing,retain_crop,paste_crop
from .dialogs import ImagePreviewDialog
from .domain import unpack_array
from .denoise_config import DENOISE_METHODS,LEARNING_METHODS,parameter_html

class ProcessingDialog(QDialog):
    def __init__(self,methods,parent=None,plugin_specs=None):
        super().__init__(parent);self.setWindowTitle('Image processing');self.resize(1080,750)
        self.specs=plugin_specs or {};self.controls={}
        layout=QVBoxLayout(self);self.method=QComboBox();self.method.addItems(methods);layout.addWidget(self.method)
        row=QHBoxLayout();layout.addLayout(row)
        defaults=QPushButton('Restore defaults');defaults.clicked.connect(self.reset_controls);row.addWidget(defaults)
        self.notebook_button=QPushButton('Notebook reconstruction preset (10%, max side 256)');self.notebook_button.clicked.connect(self.notebook_preset);row.addWidget(self.notebook_button)
        body=QHBoxLayout();layout.addLayout(body,1)
        area=QScrollArea();area.setWidgetResizable(True);panel=QWidget();self.form=QFormLayout(panel);area.setWidget(panel);body.addWidget(area,1)
        self.explanation=QTextBrowser();self.explanation.setMinimumWidth(420);body.addWidget(self.explanation,1)
        self.selection=QCheckBox('Process selected region / object masks only');layout.addWidget(self.selection)
        self.original=QCheckBox('Use original uncleaned pixels (current orientation)');layout.addWidget(self.original)
        note=QLabel('Parameters reset on open or method change. Protected crops and pending removed pixels are excluded from Apply. RGB channels are processed independently; alpha is retained. Training also saves model files before image Apply.');note.setWordWrap(True);layout.addWidget(note)
        self.buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText('Preview');layout.addWidget(self.buttons);self.buttons.accepted.connect(self.accept);self.buttons.rejected.connect(self.reject)
        self.method.currentTextChanged.connect(self.reset_controls);self.reset_controls()
    def reset_controls(self,*args):
        while self.form.rowCount():self.form.removeRow(0)
        self.controls={};method=self.method.currentText();spec=METHODS.get(method,self.specs.get(method,{}))
        for key,definition in spec.items():
            if isinstance(definition,dict):
                default=definition.get('default','');low=definition.get('min',0);high=definition.get('max',1000000);step=definition.get('step',1)
            else:default,low,high,step=definition;definition={}
            if 'choices' in definition:
                control=QComboBox()
                for choice in definition['choices']:control.addItem(str(choice),choice)
                control.setCurrentIndex(control.findData(default));control.currentIndexChanged.connect(self.update_relevance)
            elif isinstance(default,bool):control=QCheckBox();control.setChecked(default);control.toggled.connect(self.update_relevance)
            elif isinstance(default,int):control=QSpinBox();control.setRange(int(low),int(high));control.setSingleStep(int(step));control.setValue(default)
            elif isinstance(default,float):control=QDoubleSpinBox();control.setDecimals(9 if low and low<.000001 else 6);control.setRange(float(low),float(high));control.setSingleStep(float(step));control.setValue(default)
            else:control=QLineEdit(str(default))
            control.setObjectName('processing_'+key);control.setToolTip(definition.get('help',''))
            self.controls[key]=control;container=QWidget();line=QHBoxLayout(container);line.setContentsMargins(0,0,0,0);line.addWidget(control,1)
            if key in ('model_path','output_directory','checkpoint'):
                browse=QPushButton('Folder' if key=='output_directory' else 'Browse');browse.clicked.connect(lambda checked=False,k=key:self.browse_path(k));line.addWidget(browse)
            help_button=QPushButton('?');help_button.setFixedWidth(25);help_button.clicked.connect(lambda checked=False,k=key:self.show_parameter(k));line.addWidget(help_button)
            self.form.addRow(key.replace('_',' ').capitalize(),container)
        self.notebook_button.setVisible(method in ('DCT sparsity','TV iterative (notebook)'))
        self.explanation.setHtml(parameter_html(method) if method in METHODS else '<h2>'+method+'</h2><p>Plugin parameters use the plugin defaults. See For Developer for the processor contract.</p>')
        self.update_relevance()
    def show_parameter(self,key):
        if self.method.currentText() in METHODS:self.explanation.setHtml(parameter_html(self.method.currentText(),key))
    def browse_path(self,key):
        if key=='output_directory':value=QFileDialog.getExistingDirectory(self,'Choose model output directory')
        elif key=='model_path':
            choice,ok=QInputDialog.getItem(self,'Model path','Choose a checkpoint or a saved model folder',['Checkpoint file','Model folder'],editable=False)
            if not ok:return
            value=QFileDialog.getExistingDirectory(self,'Choose saved model directory') if choice=='Model folder' else QFileDialog.getOpenFileName(self,'Choose CAREamics checkpoint','','Checkpoint (*.ckpt)')[0]
        else:value=QFileDialog.getOpenFileName(self,'Choose model checkpoint','','Model files (*.pt *.pth *.ckpt)')[0]
        if value:self.controls[key].setText(value)
    def notebook_preset(self):
        settings={'task':'reconstruct','iterations':40,'data_loss':'l2','huber_delta':.05,'sample_fraction':.10,'sampling_method':'random','random_seed':7,'initialization':'nearest','max_side':256,'sparsity_fraction':.08,'tv_step':.08,'gradient_epsilon':1e-6}
        for key,value in settings.items():
            if key not in self.controls:continue
            control=self.controls[key]
            if isinstance(control,QComboBox):control.setCurrentIndex(control.findData(value))
            elif hasattr(control,'setValue'):control.setValue(value)
        self.update_relevance()
    def update_relevance(self,*args):
        if 'task' in self.controls:
            reconstruct=self.controls['task'].currentData()=='reconstruct'
            for key in ('sample_fraction','sampling_method','random_seed','initialization'):self.controls[key].setEnabled(reconstruct)
            self.controls['fidelity_step'].setEnabled(not reconstruct)
            self.controls['huber_delta'].setEnabled(self.controls['data_loss'].currentData()!='l2')
        if 'estimate_sigma' in self.controls:self.controls['sigma'].setEnabled(not self.controls['estimate_sigma'].isChecked())
        if 'run_mode' in self.controls:
            train=self.controls['run_mode'].currentData()=='train'
            self.controls['model_path'].setEnabled(not train)
            for key in ('output_directory','epochs','steps_per_epoch','patch_size','batch_size','learning_rate','masked_pixel_percentage','roi_size','depth','initial_filters','validation_patches','random_seed'):self.controls[key].setEnabled(train)
    def values(self):
        return {k:w.currentData() if isinstance(w,QComboBox) else w.isChecked() if isinstance(w,QCheckBox) else w.text() if isinstance(w,QLineEdit) else w.value() for k,w in self.controls.items()}

class ProcessingWorkflowMixin:
    def _init_processing_ui(self):
        menu=self.menuBar().addMenu('Processing');self.processing_menu=menu
        menu.addAction(self._action('Denoise…',lambda:self.process_image_dialog(DENOISE_METHODS)))
        menu.addAction(self._action('Smooth (Gaussian)…',lambda:self.process_image_dialog(['Gaussian smooth'])))
        menu.addAction(self._action('Crop selected region / masks…',self.crop_region_dialog));menu.addAction(self._action('Retained crops / paste back…',self.retained_crops_dialog))
        menu.addAction(self._action('Add noise…',lambda:self.process_image_dialog(['Poisson noise','Gaussian noise','Salt and pepper noise'])))
    def process_image_dialog(self,methods=None):
        if self.busy or not self.document:return
        methods=methods or list(METHODS)
        dialog=ProcessingDialog(methods,self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        doc=self.document
        try:
            method=dialog.method.currentText();params=parameters(method,dialog.values());region=self._processing_selection() if dialog.selection.isChecked() else None
            if method in LEARNING_METHODS:
                from .neural_denoising import prepare_model_directory
                params=prepare_model_directory(params)
            target=processing_target(doc,region)
            raw=(doc.frame.raw if dialog.original.isChecked() or doc.working is None else doc.working).copy()
            key=self.current_key;revision=doc.revision
            def finished(result):
                if key!=self.current_key or doc.revision!=revision:raise ValueError('The image changed during processing; run preview again.')
                preview=ImagePreviewDialog(raw,result,'Preview '+method,self)
                if preview.exec()==QDialog.DialogCode.Accepted:
                    self._commit(method,lambda:apply_processing(doc,result,target,method,params));self.cleaned_checkbox.setChecked(True)
            self._start_job('Processing image…',lambda progress,cancel:process_pixels(raw,method,params,target,progress,cancel),finished)
        except Exception as e:self.notify('Image processing',str(e))
    def _processing_selection(self):
        roi=self._selection_mask()
        if roi is not None and roi.any():return roi
        target=np.zeros(self.document.frame.shape,bool)
        for obj in self.selected_objects():
            if obj.mask is not None:target|=obj.mask
        if not target.any():raise ValueError('Select area objects or draw an area region.')
        return target
    def crop_region_dialog(self):
        if not self.document or self.busy:return
        try:
            region=self._processing_selection();name,ok=QInputDialog.getText(self,'Retain cropped pixels','Crop name (bounding box includes 3 pixels of real neighboring image)')
            if not ok:return
            self._commit('Retain crop',lambda:retain_crop(self.document,region,name or None,True,3))
            self.statusBar().showMessage('Crop retained and protected. Process the remaining image, then use Retained crops / paste back.',15000)
        except Exception as e:self.notify('Crop',str(e))
    def retained_crops_dialog(self):
        if not self.document or self.busy:return
        doc=self.document;dialog=QDialog(self);dialog.setWindowTitle('Retained crops');dialog.resize(620,420);layout=QVBoxLayout(dialog);items=QListWidget();layout.addWidget(items)
        def reload():
            items.clear()
            for c in doc.detached_crops:items.addItem(c['name']+' | '+str(c['bbox'])+' | '+('pasted' if c.get('pasted') else 'protected' if c.get('protected') else 'unprotected'))
        reload();only=QCheckBox('Paste mask pixels only (otherwise paste the complete rectangle and real background)');layout.addWidget(only);row=QHBoxLayout();layout.addLayout(row)
        def selected():
            index=items.currentRow()
            if index<0:raise ValueError('Select a crop from the list.')
            return doc.detached_crops[index]
        def action(kind):
            try:
                crop=selected()
                if kind=='paste':self._commit('Paste retained crop',lambda:paste_crop(doc,crop['id'],only.isChecked()));self.cleaned_checkbox.setChecked(True)
                elif kind=='export':
                    path,_=QFileDialog.getSaveFileName(dialog,'Export real crop pixels',crop['name']+'.tif','TIFF (*.tif *.tiff)')
                    if path:
                        import tifffile
                        tifffile.imwrite(path,unpack_array(crop['pixels']))
                elif kind=='protect':self._commit('Change crop protection',lambda:crop.update(protected=not crop.get('protected'),pasted=False))
                else:self._commit('Remove retained crop',lambda:doc.detached_crops.remove(crop))
                reload()
            except Exception as e:QMessageBox.warning(dialog,'Retained crop',str(e))
        for title,kind in [('Paste back','paste'),('Protect / release','protect'),('Export TIFF','export'),('Remove snapshot','remove')]:
            b=QPushButton(title);b.clicked.connect(lambda checked=False,k=kind:action(k));row.addWidget(b)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons);dialog.exec()
