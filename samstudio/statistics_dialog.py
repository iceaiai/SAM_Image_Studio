from __future__ import annotations
import math
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox,QColorDialog,QDialog,QFileDialog,QFormLayout,QHBoxLayout,
 QLabel,QLineEdit,QListWidget,QListWidgetItem,QMessageBox,QPushButton,QSpinBox,QVBoxLayout,
 QWidget,QSplitter,QTabWidget,QDialogButtonBox)
from .dialogs import combo,buttons
from .domain import LENGTH_UNITS
from .processing import measurements
from .statistics import METRICS,METRIC_DEFINITIONS,measurement_records,summary_records,export_statistics


class StatisticsDialog(QDialog):
    def __init__(self,documents,current,selected_objects=None,selected_images=None,parent=None):
        super().__init__(parent)
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg,NavigationToolbar2QT
        self.documents=list(documents);self.current=current;self.selected_objects=set(selected_objects or []);self.selected_images=set(selected_images or [])
        self.rows=[];self.records=[];self.axis_settings={};self.plot_keys=[];self._updating=False;self._bar_color='#245dd8'
        self.setWindowTitle('Plot Object Statistics');self.resize(1320,850)
        layout=QVBoxLayout(self);row=QHBoxLayout()
        self.scope=combo(['Current image','All open images','Selected images']);self.group=combo(['All groups']+sorted({g.name for d in self.documents for g in d.groups}))
        self.metric_combo=combo([(label,key) for key,(label,dim) in METRICS.items()])
        self.unit=combo(['Auto','Pixels','nm','µm','mm']);self.bins=QSpinBox();self.bins.setRange(2,500);self.bins.setValue(20)
        self.only_selected=QCheckBox('Selected objects only')
        for title,widget in [('Images',self.scope),('Group',self.group),('Single metric',self.metric_combo),('Units',self.unit),('Bins',self.bins)]:
            col=QVBoxLayout();col.addWidget(QLabel(title));col.addWidget(widget);row.addLayout(col)
        layout.addLayout(row);layout.addWidget(self.only_selected)
        split=QSplitter(Qt.Orientation.Horizontal);layout.addWidget(split,1);panel=QWidget();left=QVBoxLayout(panel);split.addWidget(panel)
        tabs=QTabWidget();left.addWidget(tabs);metrics_page=QWidget();metrics_layout=QVBoxLayout(metrics_page)
        metrics_layout.addWidget(QLabel('Choose up to 9 metrics.\nResize the window or drag the divider.'))
        self.metrics_list=QListWidget();self.metrics_list.setObjectName('plotMetrics')
        for key,(label,dim) in METRICS.items():
            item=QListWidgetItem(label);item.setToolTip(METRIC_DEFINITIONS[key]);item.setData(Qt.ItemDataRole.UserRole,key);item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable);item.setCheckState(Qt.CheckState.Checked if key=='area' else Qt.CheckState.Unchecked);self.metrics_list.addItem(item)
        metrics_layout.addWidget(self.metrics_list);tabs.addTab(metrics_page,'Plot metrics')
        axes_page=QWidget();form=QFormLayout(axes_page);self.axis_combo=combo([]);form.addRow('Plot',self.axis_combo)
        self.x_label=QLineEdit();self.y_label=QLineEdit();self.x_min=QLineEdit();self.x_max=QLineEdit();self.y_min=QLineEdit();self.y_max=QLineEdit();self.x_step=QLineEdit();self.y_step=QLineEdit()
        for widget in (self.x_min,self.x_max,self.y_min,self.y_max,self.x_step,self.y_step):widget.setPlaceholderText('Auto')
        self.label_size=QSpinBox();self.label_size.setRange(6,36);self.label_size.setValue(11)
        self.tick_size=QSpinBox();self.tick_size.setRange(6,30);self.tick_size.setValue(9)
        for name,widget in [('X-axis name',self.x_label),('Y-axis name',self.y_label),('X minimum',self.x_min),('X maximum',self.x_max),('X tick interval',self.x_step),('Y minimum',self.y_min),('Y maximum',self.y_max),('Y tick interval',self.y_step),('Axis font size',self.label_size),('Tick font size',self.tick_size)]:form.addRow(name,widget)
        self.color_button=QPushButton('Choose bar color…');self.color_button.clicked.connect(self.choose_color);form.addRow(self.color_button)
        apply=QPushButton('Apply axis settings');apply.clicked.connect(self.apply_axes);form.addRow(apply);tabs.addTab(axes_page,'Axes and colors')
        right=QWidget();plot_layout=QVBoxLayout(right);split.addWidget(right);split.setSizes([290,1000])
        self.figure=Figure(figsize=(9,6),layout='constrained');self.canvas=FigureCanvasQTAgg(self.figure);self.canvas.setObjectName('statisticsCanvas')
        plot_layout.addWidget(NavigationToolbar2QT(self.canvas,self));plot_layout.addWidget(self.canvas,1)
        self.summary=QLabel();self.summary.setWordWrap(True);layout.addWidget(self.summary)
        actions=QHBoxLayout();plot_button=QPushButton('Export plot…');csv=QPushButton('Export statistics…');close=QPushButton('Close')
        plot_button.clicked.connect(self.save_plot);csv.clicked.connect(self.save_csv);close.clicked.connect(self.accept)
        for button in (plot_button,csv,close):actions.addWidget(button)
        layout.addLayout(actions)
        for widget in (self.scope,self.group,self.unit):widget.currentIndexChanged.connect(self.refresh)
        self.metric_combo.currentIndexChanged.connect(self.single_metric_changed);self.metrics_list.itemChanged.connect(self.metrics_changed)
        self.bins.valueChanged.connect(self.refresh);self.only_selected.toggled.connect(self.refresh);self.axis_combo.currentIndexChanged.connect(self.load_axis_settings)
        self.refresh()

    def selected_metrics(self):
        return [self.metrics_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.metrics_list.count()) if self.metrics_list.item(i).checkState()==Qt.CheckState.Checked]

    def single_metric_changed(self):
        key=self.metric_combo.currentData();self._updating=True
        for i in range(self.metrics_list.count()):
            item=self.metrics_list.item(i);item.setCheckState(Qt.CheckState.Checked if item.data(Qt.ItemDataRole.UserRole)==key else Qt.CheckState.Unchecked)
        self._updating=False;self.refresh()

    def metrics_changed(self,item):
        if self._updating:return
        if len(self.selected_metrics())>9:
            self._updating=True;item.setCheckState(Qt.CheckState.Unchecked);self._updating=False
            self.summary.setText('Choose at most 9 metrics.');return
        self.refresh()

    def filtered_documents(self):
        docs=([self.current] if self.current is not None else []) if self.scope.currentIndex()==0 else self.documents
        return [d for d in docs if d.frame.key in self.selected_images] if self.scope.currentIndex()==2 else docs

    def refresh(self):
        if self._updating:return
        names=['All groups']+sorted({g.name for d in self.documents for g in d.groups})
        if [self.group.itemText(i) for i in range(self.group.count())]!=names:
            old=self.group.currentText();self.group.blockSignals(True);self.group.clear();self.group.addItems(names);self.group.setCurrentIndex(max(0,self.group.findText(old)));self.group.blockSignals(False)
        docs=self.filtered_documents();unit=self.unit.currentText()
        physical_unit=next((d.calibration.length_unit for d in docs if d.calibration.valid),'nm') if unit=='Auto' else unit
        physical_unit=physical_unit if physical_unit in LENGTH_UNITS else None
        self.rows=[];self.records=[];excluded=0
        for doc in docs:
            ids=self.selected_objects if self.only_selected.isChecked() else None;groups=[self.group.currentText()] if self.group.currentIndex()>0 else None
            records,skip=measurement_records(doc,ids,groups,physical_unit);self.records.extend(records);excluded+=skip
            rows,_=measurements(doc,ids,groups,self.metric_combo.currentData(),physical_unit);self.rows.extend(rows)
        self.figure.clear();panels=[]
        for key in self.selected_metrics():
            dim=METRICS[key][1]
            cohorts=[]
            geometry_ratio_or_angle=key in ('orientation','aspect_ratio','circularity','solidity','corner_error','edge_deviation','normalized_displacement','displacement_direction','shell_uniformity','wall_uniformity')
            if dim==-2 or dim==0 and not geometry_ratio_or_angle:cohorts=[('px','',self.records)]
            elif dim in (0,-1):
                label='deg, ' if dim==-1 else ''
                if unit=='Pixels':cohorts=[('px',label+'pixels',self.records)]
                else:
                    calibrated=[r for r in self.records if r['calibrated']]
                    uncalibrated=[r for r in self.records if not r['calibrated']]
                    if calibrated:cohorts.append(('physical',label+'physical',calibrated))
                    if uncalibrated and unit=='Auto':cohorts.append(('px',label+'pixels',uncalibrated))
            elif unit=='Pixels':cohorts=[('px','pixel²' if dim==2 else 'pixels',self.records)]
            else:
                calibrated=[r for r in self.records if r['calibrated']]
                uncalibrated=[r for r in self.records if not r['calibrated']]
                if calibrated:cohorts.append(('physical',(physical_unit or 'nm')+('²' if dim==2 else ''),calibrated))
                if uncalibrated and unit=='Auto':cohorts.append(('px','pixel²' if dim==2 else 'pixels',uncalibrated))
            for suffix,label,records in cohorts:panels.append((key,suffix,label,records))
        count=max(1,len(panels));cols=min(3,count);rows=math.ceil(count/cols);self.plot_keys=[]
        if not panels:
            ax=self.figure.add_subplot(111);ax.text(.5,.5,'No eligible objects or metrics',ha='center',va='center',transform=ax.transAxes);ax.set_axis_off()
        for i,(key,suffix,label,records) in enumerate(panels):
            ax=self.figure.add_subplot(rows,cols,i+1);plot_key=key+'|'+label;self.plot_keys.append(plot_key)
            options=self.axis_settings.get(plot_key,{});color=options.get('color','#245dd8')
            values=[r.get(key+'_'+suffix) for r in records] if key!='object_id' else []
            values=[v for v in values if v is not None and np.isfinite(v)]
            if key=='object_id':
                ax.bar(range(len(records)),[1]*len(records),color=color);ax.set_xticks(range(len(records)),[r['name']+'\n'+r['object_id'][:8] for r in records],rotation=60)
            elif key=='particle_count':
                groups=sorted({r['group'] for r in records});counts=[sum(r['particle_count_px'] for r in records if r['group']==g) for g in groups];ax.bar(groups,counts,color=color)
            elif values:ax.hist(values,bins=self.bins.value(),color=color,edgecolor='white')
            else:ax.text(.5,.5,'Not applicable / unavailable',ha='center',va='center',transform=ax.transAxes)
            default_x=METRICS[key][0]+(f' ({label})' if label else '')
            ax.set_xlabel(options.get('xlabel') or default_x,fontsize=options.get('label_size',11));ax.set_ylabel(options.get('ylabel') or ('Particle count' if key=='particle_count' else 'Object count'),fontsize=options.get('label_size',11))
            ax.set_title(METRICS[key][0]+f' · n={len(records) if key=="object_id" else len(values)}',fontsize=11);ax.tick_params(labelsize=options.get('tick_size',9));ax.grid(axis='y',alpha=.2)
            for axis in ('x','y'):
                lo,hi=options.get(axis+'min'),options.get(axis+'max')
                if lo is not None or hi is not None:getattr(ax,'set_'+axis+'lim')(lo,hi)
                if options.get(axis+'step'):
                    from matplotlib.ticker import MultipleLocator
                    getattr(ax,axis+'axis').set_major_locator(MultipleLocator(options[axis+'step']))
        old=self.axis_combo.currentData();self.axis_combo.blockSignals(True);self.axis_combo.clear()
        for key in self.plot_keys:self.axis_combo.addItem(key,key)
        self.axis_combo.setCurrentIndex(max(0,self.axis_combo.findData(old)));self.axis_combo.blockSignals(False);self.load_axis_settings()
        self.canvas.draw_idle()
        self.summary.setText(f'{len(self.records)} measured objects; {sum(r["particle_count_px"] for r in self.records):g} particles; {excluded} point/open annotations excluded. Physical and pixel cohorts are separate. Blank values indicate unavailable metrics. Save all or selected metrics independently of these plots.')

    def load_axis_settings(self):
        options=self.axis_settings.get(self.axis_combo.currentData(),{});self.x_label.setText(options.get('xlabel',''));self.y_label.setText(options.get('ylabel',''))
        for attr in ('xmin','xmax','ymin','ymax','xstep','ystep'):
            widget=getattr(self,attr[0]+'_'+attr[1:]);widget.setText('' if options.get(attr) is None else str(options[attr]))
        self.label_size.setValue(options.get('label_size',11));self.tick_size.setValue(options.get('tick_size',9));self._bar_color=options.get('color','#245dd8')
        self.color_button.setStyleSheet('background:'+self._bar_color+';color:white;')

    def choose_color(self):
        color=QColorDialog.getColor(QColor(self._bar_color),self,'Histogram bar color')
        if color.isValid():self._bar_color=color.name();self.color_button.setStyleSheet('background:'+color.name()+';color:white;')

    def apply_axes(self):
        key=self.axis_combo.currentData()
        if key is None:return
        try:
            options={'xlabel':self.x_label.text(),'ylabel':self.y_label.text(),'color':self._bar_color,'label_size':self.label_size.value(),'tick_size':self.tick_size.value()}
            for attr in ('xmin','xmax','ymin','ymax','xstep','ystep'):
                text=getattr(self,attr[0]+'_'+attr[1:]).text().strip();value=float(text) if text else None
                if value is not None and (not math.isfinite(value) or attr.endswith('step') and value<=0):raise ValueError('Limits must be finite; tick intervals must be positive.')
                options[attr]=value
            for axis in ('x','y'):
                if options[axis+'min'] is not None and options[axis+'max'] is not None and options[axis+'min']>=options[axis+'max']:raise ValueError('Axis minimum must be smaller than maximum.')
                step=options[axis+'step']
                if step and options[axis+'min'] is not None and options[axis+'max'] is not None and (options[axis+'max']-options[axis+'min'])/step>1000:raise ValueError('Choose a larger tick interval (at most 1000 ticks).')
            if key in self.plot_keys:
                current=self.figure.axes[self.plot_keys.index(key)]
                for axis in ('x','y'):
                    low,high=getattr(current,'get_'+axis+'lim')()
                    low=options[axis+'min'] if options[axis+'min'] is not None else low
                    high=options[axis+'max'] if options[axis+'max'] is not None else high
                    if options[axis+'step'] and (high-low)/options[axis+'step']>1000:raise ValueError('Choose a larger tick interval (at most 1000 ticks).')
            self.axis_settings[key]=options;self.refresh()
        except ValueError as error:QMessageBox.warning(self,'Axis settings',str(error))

    def save_plot(self):
        path,_=QFileDialog.getSaveFileName(self,'Export statistics plot','object_statistics.png','PNG (*.png);;PDF (*.pdf);;SVG (*.svg)')
        if path:
            try:self.figure.savefig(path,dpi=200)
            except Exception as error:QMessageBox.warning(self,'Plot export',str(error))

    def save_csv(self):
        dialog=QDialog(self);dialog.setWindowTitle('Choose statistics to save');layout=QVBoxLayout(dialog)
        all_metrics=QCheckBox('Save all metrics');all_metrics.setChecked(True);layout.addWidget(all_metrics)
        items=QListWidget();layout.addWidget(items)
        for key,(label,dim) in METRICS.items():
            item=QListWidgetItem(label);item.setToolTip(METRIC_DEFINITIONS[key]);item.setData(Qt.ItemDataRole.UserRole,key);item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable);item.setCheckState(Qt.CheckState.Checked if key in self.selected_metrics() else Qt.CheckState.Unchecked);items.addItem(item)
        items.setEnabled(False);all_metrics.toggled.connect(lambda value:items.setEnabled(not value));buttons(dialog,layout)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        selected=list(METRICS) if all_metrics.isChecked() else [items.item(i).data(Qt.ItemDataRole.UserRole) for i in range(items.count()) if items.item(i).checkState()==Qt.CheckState.Checked]
        if not selected:QMessageBox.warning(self,'Export statistics','Choose at least one metric.');return
        path,_=QFileDialog.getSaveFileName(self,'Export measurements and summaries','object_measurements.csv','CSV (*.csv)')
        if path:
            try:export_statistics(self.records,path,selected,self.bins.value())
            except Exception as error:QMessageBox.warning(self,'Measurement export',str(error))
