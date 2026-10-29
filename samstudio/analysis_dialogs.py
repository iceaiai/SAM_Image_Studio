"""Parameter dialogs with defaults, per-control explanations and a Preview action."""
from __future__ import annotations
import html
from PySide6.QtWidgets import QDialog,QVBoxLayout,QFormLayout,QHBoxLayout,QLabel,QComboBox,QDoubleSpinBox,QSpinBox,QCheckBox,QPushButton,QDialogButtonBox,QTextBrowser,QScrollArea,QWidget

class ParameterPreviewDialog(QDialog):
    def __init__(self,title,schema,values=None,note='',parent=None):
        super().__init__(parent);self.setWindowTitle(title);self.resize(850,690)
        self.schema=schema;self.controls={};layout=QVBoxLayout(self);body=QHBoxLayout();layout.addLayout(body,1)
        scroll=QScrollArea();scroll.setWidgetResizable(True);panel=QWidget();form=QFormLayout(panel);scroll.setWidget(panel);body.addWidget(scroll,1)
        self.help=QTextBrowser();body.addWidget(self.help,1)
        for key,s in schema.items():
            value=(values or {}).get(key,s['default']);default=s['default']
            if 'choices' in s:
                control=QComboBox()
                for choice in s['choices']:control.addItem(choice,choice)
                control.setCurrentIndex(control.findData(value))
            elif isinstance(default,bool):control=QCheckBox();control.setChecked(value)
            elif isinstance(default,int):control=QSpinBox();control.setRange(s['min'],s['max']);control.setValue(value)
            else:control=QDoubleSpinBox();control.setDecimals(4);control.setRange(s['min'],s['max']);control.setSingleStep(s.get('step',.1));control.setValue(value)
            control.setObjectName('parameter_'+key);control.setToolTip(s['help']);self.controls[key]=control
            row=QHBoxLayout();row.addWidget(control,1);help_button=QPushButton('?');help_button.setFixedWidth(25);help_button.clicked.connect(lambda checked=False,k=key:self.show_help(k));row.addWidget(help_button)
            form.addRow(key.replace('_',' ').capitalize(),row)
        label=QLabel(note);label.setWordWrap(True);layout.addWidget(label)
        reset=QPushButton('Restore defaults');reset.clicked.connect(self.reset_defaults);layout.addWidget(reset)
        controls=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        controls.button(QDialogButtonBox.StandardButton.Ok).setText('Preview');controls.accepted.connect(self.accept);controls.rejected.connect(self.reject);layout.addWidget(controls)
        self.show_help(next(iter(schema)))
    def show_help(self,key):
        s=self.schema[key]
        self.help.setHtml('<h2>'+html.escape(key.replace('_',' '))+'</h2><p>'+html.escape(s['help'])+'</p><p><b>Default:</b> '+html.escape(str(s['default']))+'</p><p><b>Suggested start:</b> '+html.escape(s.get('recommended',''))+'</p>')
    def reset_defaults(self):
        for key,s in self.schema.items():
            c=self.controls[key];v=s['default']
            if isinstance(c,QComboBox):c.setCurrentIndex(c.findData(v))
            elif isinstance(c,QCheckBox):c.setChecked(v)
            else:c.setValue(v)
    def values(self):
        return {key:c.currentData() if isinstance(c,QComboBox) else c.isChecked() if isinstance(c,QCheckBox) else c.value() for key,c in self.controls.items()}


from .denoise_config import P
LAMA_PARAMETERS={
    'mask_dilation':P(0,0,64,1,help='Expand the mask supplied to LaMa, in pixels. Final compositing still changes only the original removal region.',recommended='0 initially; compare 1-4 for edge contamination.'),
    'context_margin':P(0,0,2048,16,help='Context pixels around the removal bounding box. Zero uses the full image.',recommended='0 for full context; 32-256 to process a local region.'),
    'max_side':P(0,0,8192,128,help='Optional maximum model-input side. Zero preserves native input resolution; smaller values resize the context and interpolate back.',recommended='0 initially; compare 1024 for large images or limited RAM.'),
    'blend_width':P(0,0,128,1,help='Blend replacement pixels with original pixels within this inner boundary width. Zero uses the full model replacement.',recommended='0 initially; compare 1-4 for a softer seam. Original contamination can remain in the blend band.'),
}
