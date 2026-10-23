from __future__ import annotations
import copy,json,threading
from dataclasses import asdict
from PySide6.QtWidgets import QDialog,QFileDialog,QVBoxLayout,QListWidget,QPushButton,QHBoxLayout,QMessageBox
from .inference import data_directory
from .plugin_api import PluginManager,ProcessingContext,run_processor
from .processing_ui import ProcessingDialog
from .image_processing import apply_processing,processing_target
from .dialogs import ImagePreviewDialog

class PluginWorkflowMixin:
    def _init_plugin_ui(self):
        self.plugin_manager=PluginManager(data_directory()/'plugins',self);self.plugin_menu=self.menuBar().addMenu('Plugin');self.plugin_actions=[]
        self.plugin_menu.addAction(self._action('Install local plugin folder…',self.install_plugin_dialog));self.plugin_menu.addAction(self._action('Manage / reload plugins…',self.manage_plugins_dialog));self.plugin_menu.addAction(self._action('For Developer (PDF)',lambda:self.open_pdf_help(True)));self.plugin_menu.addSeparator()
        self._reload_plugins()
    def _enabled_plugins(self):
        value=self.settings.value('enabled_plugins',[]) or []
        return [value] if isinstance(value,str) else list(value)
    def _reload_plugins(self):
        for action in self.plugin_actions:self.plugin_menu.removeAction(action);action.deleteLater()
        self.plugin_actions=[];self.plugin_manager.loaded={};errors=[]
        for ident in self._enabled_plugins():
            try:
                api=self.plugin_manager.load(ident)
                for name,spec in api.processors.items():
                    action=self._action(name+'…',lambda checked=False,n=name,s=spec,i=ident:self._run_plugin_processor(i,n,s));self.plugin_menu.addAction(action);self.plugin_actions.append(action)
                for name,function in api.actions.items():
                    action=self._action(name,lambda checked=False,f=function,a=api:self._plugin_action(f,a));self.plugin_menu.addAction(action);self.plugin_actions.append(action)
            except Exception as e:errors.append(ident+': '+str(e))
        if errors:self.statusBar().showMessage('Some plugins were not loaded: '+'; '.join(errors),15000)
        return errors
    def install_plugin_dialog(self):
        if self.busy:return
        folder=QFileDialog.getExistingDirectory(self,'Install a local plugin folder containing plugin.json')
        if not folder:return
        try:
            ident=self.plugin_manager.install(folder);enabled=self._enabled_plugins()+[ident];self.settings.setValue('enabled_plugins',enabled)
            errors=self._reload_plugins()
            if errors:self.notify('Plugin load','\n'.join(errors))
        except Exception as e:self.notify('Plugin install',str(e))
    def _plugin_action(self,function,api):
        if self.busy:return
        try:function(api)
        except Exception as e:self.notify('Plugin action',str(e))
    def _run_plugin_processor(self,ident,name,spec):
        if self.busy or not self.document:return
        dialog=ProcessingDialog([name],self,{name:spec['parameters']})
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        doc=self.document;key=self.current_key;revision=doc.revision
        try:
            raw=(doc.frame.raw if dialog.original.isChecked() or doc.working is None else doc.working).copy()
            target=processing_target(doc,self._processing_selection() if dialog.selection.isChecked() else None);params=dialog.values()
            objects=[o.to_dict() for o in doc.objects];cal=asdict(doc.calibration)
            def worker(progress,cancel):
                context=ProcessingContext(raw.copy(),target.copy(),copy.deepcopy(params),copy.deepcopy(cal),copy.deepcopy(objects),progress,cancel)
                return run_processor(spec['function'],context)
            def finished(result):
                if key!=self.current_key or doc.revision!=revision:raise ValueError('The image changed; run the plugin again.')
                preview=ImagePreviewDialog(raw,result,'Plugin: '+name,self)
                if preview.exec()==QDialog.DialogCode.Accepted:
                    self._commit('Plugin '+name,lambda:apply_processing(doc,result,target,'Plugin '+name,{'plugin_id':ident,'parameters':params}));self.cleaned_checkbox.setChecked(True)
            self._start_job('Running plugin '+name+'…',worker,finished)
        except Exception as e:self.notify('Plugin processor',str(e))
    def manage_plugins_dialog(self):
        if self.busy:return
        from PySide6.QtCore import Qt
        dialog=QDialog(self);dialog.setWindowTitle('Installed local plugins');dialog.resize(620,350);layout=QVBoxLayout(dialog);items=QListWidget();layout.addWidget(items)
        def reload():
            items.clear();enabled=self._enabled_plugins()
            from PySide6.QtWidgets import QListWidgetItem
            for path in self.plugin_manager.manifests():
                data=json.loads(path.read_text());item=QListWidgetItem(data.get('name',data['id'])+' | '+data['id']);item.setData(Qt.ItemDataRole.UserRole,data['id']);item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable);item.setCheckState(Qt.CheckState.Checked if data['id'] in enabled else Qt.CheckState.Unchecked);items.addItem(item)
        reload();row=QHBoxLayout();layout.addLayout(row)
        def apply():
            self.settings.setValue('enabled_plugins',[items.item(i).data(Qt.ItemDataRole.UserRole) for i in range(items.count()) if items.item(i).checkState()==Qt.CheckState.Checked]);errors=self._reload_plugins()
            if errors:QMessageBox.warning(dialog,'Plugin load','\n'.join(errors))
        def remove():
            item=items.currentItem()
            if item:
                ident=item.data(Qt.ItemDataRole.UserRole);self.plugin_manager.remove(ident);self.settings.setValue('enabled_plugins',[i for i in self._enabled_plugins() if i!=ident]);self._reload_plugins();reload()
        for title,cb in [('Apply / reload',apply),('Remove plugin',remove),('Close',dialog.accept)]:
            button=QPushButton(title);button.clicked.connect(cb);row.addWidget(button)
        dialog.exec()
