from __future__ import annotations
import copy
from PySide6.QtWidgets import QPushButton,QLabel,QToolBar
from PySide6.QtCore import Qt
from .dialogs import combo
from .exemplars import infer_examples

class SegmentationWorkflowMixin:
    def _init_segmentation_ui(self):
        self.watershed_options={}
        self.watershed_action=self._action('Otsu + watershed…',self.watershed_dialog)
        for action in self.menuBar().actions():
            if action.text()=='Models':action.menu().addAction(self.watershed_action);break
        self.example_polarity=combo([('Positive example',1),('Negative example',0)],'examplePolarity')
        previous=self.findChild(QToolBar,'imageToolbar')
        previous.removeAction(self.text_prompt_action);previous.removeAction(self.aliases_action)
        toolbar=QToolBar('Segmentation prompts',self);toolbar.setObjectName('promptToolbar');toolbar.setMovable(False)
        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea);self.addToolBar(Qt.ToolBarArea.TopToolBarArea,toolbar)
        self.text_prompt_label = QLabel(' Text prompt ')
        self.text_prompt_label_action = toolbar.addWidget(self.text_prompt_label)
        self.text_prompt.setMaximumWidth(420);self.text_prompt.setMinimumWidth(220);self.text_prompt_action=toolbar.addWidget(self.text_prompt)
        self.text_run_button=QPushButton('Run text segmentation');self.text_run_button.setObjectName('runTextSegmentation');self.text_run_button.clicked.connect(self.run_text_segmentation);self.text_run_action=toolbar.addWidget(self.text_run_button)
        self.aliases_action=toolbar.addWidget(self.aliases_button)
        toolbar.addWidget(QLabel(' Shape prompt '));toolbar.addWidget(self.example_polarity)
        self.text_prompt.returnPressed.connect(self.run_text_segmentation)
        self.canvas.tool_changed.connect(self._scope_tool_changed)
        self.scope.setItemText(self.scope.findData('prompt'),'Prompt project, whole image')
        self.scope.addItem('Single object (native SAM)','single');self.scope.currentIndexChanged.connect(self._scope_tool_changed)
        self.scope.setToolTip('Whole image: find objects similar to multiple positive/negative exemplars. SAM1/2 use an application retrieval layer; SAM3 uses native concept prompts. ROI only clips an area prompt. Automatic grid starts when selected.')
        self.auto_checkbox.setText('Live prompt preview');self._scope_tool_changed()
    def run_text_segmentation(self):
        if not self.text_prompt.text().strip():self.notify('Text prompt','Enter a text prompt or alias.');return
        if self.mode.currentText()!='Segment':self.mode.setCurrentText('Segment')
        if self.mode.currentText()=='Segment':self.run_inference()
    def _scope_tool_changed(self,*args):
        if not hasattr(self,'scope'):return
        point=self.canvas.tool=='point'
        onnx=bool(self.engine.spec and self.engine.spec.family=='SAM3 ONNX')
        self.example_polarity.setEnabled(not onnx)
        for value in ('roi','single','automatic'):
            index=self.scope.findData(value)
            if index>=0:
                item=self.scope.model().item(index)
                disabled=(point and value in ('roi','single')) or (onnx and value in ('single','automatic'))
                if item:item.setEnabled(not disabled)
                if hasattr(self.scope.view(),'setRowHidden'):self.scope.view().setRowHidden(index,disabled)
        if (point and self.scope.currentData() in ('roi','single')) or (onnx and self.scope.currentData() in ('single','automatic')):
            self.scope.setCurrentIndex(self.scope.findData('prompt'))
    def _whole_image_examples(self,doc,roi=None):
        examples=copy.deepcopy(doc.draft.get('examples',[]))
        if roi is not None and doc.draft.get('roi') and doc.draft['roi'].get('kind')!='mask':examples.append({**doc.draft['roi'],'label':1})
        if not examples and not doc.draft.get('points') and roi is None and self.engine.spec.family!='SAM3 ONNX':
            from .domain import pack_mask
            examples.extend({'kind':'mask','mask':pack_mask(obj.mask),'label':1,'object_id':obj.id}
                            for obj in self.selected_objects() if obj.role=='object' and obj.mask is not None)
        return examples
    def _example_inference(self,engine,rgb,points,examples,protected,progress,cancel,text,options):
        return infer_examples(engine,rgb,points,examples,protected,progress=progress,cancel=cancel,text_prompt=text,**options)

    def watershed_dialog(self):
        from PySide6.QtWidgets import QDialog
        from .analysis_dialogs import ParameterPreviewDialog
        from .classical_segmentation import WATERSHED_PARAMETERS,watershed_masks
        from .processing import filter_proposals
        if not self.document or self.busy:return
        dialog=ParameterPreviewDialog('Otsu + watershed',WATERSHED_PARAMETERS,self.watershed_options,
            'No SAM model is required. A current region limits output. Preview creates provisional masks on the canvas; review them and use Accept masks.',self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        self.watershed_options=dialog.values();self.preview_timer.stop();self._prompt_version+=1
        doc=self.document;key=self.current_key;version=self._prompt_version
        raw=(doc.working if doc.use_processed and doc.working is not None else doc.frame.raw).copy()
        roi=self._selection_mask() if doc.draft.get('roi') else None
        protected=doc.protected_mask();self.canvas.set_preview([]);self._preview_context=None
        def calculate(progress,cancel):
            masks,info=watershed_masks(raw,self.watershed_options,roi,progress,cancel)
            return filter_proposals(masks,protected,roi,int(self.watershed_options['minimum_area'])),info
        def finished(result):
            if self.current_key!=key or self._prompt_version!=version:return
            masks,info=result
            self._preview_context={'method':'Otsu + watershed','parameters':copy.deepcopy(self.watershed_options),'input':'processed' if doc.use_processed else 'original','diagnostics':info}
            self.canvas.set_preview(masks)
            self.preview_count_label.setText(f'Preview: {len(masks)}')
            self.preview_count_label.setToolTip(str(info))
            self.statusBar().showMessage(f'{len(masks)} watershed mask(s). Review and Accept masks; change polarity/seeds if needed.',20000)
        self._start_job('Otsu + watershed…',calculate,finished)
