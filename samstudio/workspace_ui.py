"""Image-list removal and opt-in reopening of the previous v1.4 workspace."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMenu, QMessageBox, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QTreeWidget


class WorkspaceWorkflowMixin:
    def _init_workspace_ui(self):
        self.groups_tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        for tree,panel,name in [(self.objects_tree,self.objects_dock.widget(),'objects'),(self.groups_tree,self.groups_dock.widget(),'groups')]:
            row=QHBoxLayout()
            for label,callback in [('Select all',tree.selectAll),('Deselect all',tree.clearSelection)]:
                button=QPushButton(label);button.setObjectName(name+label.replace(' ',''));button.clicked.connect(callback);row.addWidget(button)
            panel.layout().insertLayout(0,row)
        self.files_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.files_tree.customContextMenuRequested.connect(self._image_context_menu)
        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.files_tree)
        row=QHBoxLayout()
        for label,callback in [('Select all',self.files_tree.selectAll),('Deselect all',self.files_tree.clearSelection)]:
            button=QPushButton(label);button.setObjectName('images'+label.replace(' ',''));button.clicked.connect(callback);row.addWidget(button)
        layout.addLayout(row)
        self.remove_images_button = QPushButton('Remove selected images')
        self.remove_images_button.setObjectName('removeWorkspaceImages')
        self.remove_images_button.setToolTip('Save annotations and remove images from this session. Source files remain available.')
        self.remove_images_button.clicked.connect(self.remove_workspace_images)
        layout.addWidget(self.remove_images_button)
        self.files_dock.setWidget(panel)

    def _image_context_menu(self, position):
        menu = QMenu(self)
        menu.addAction('Select all images',self.files_tree.selectAll)
        menu.addAction('Deselect all images',self.files_tree.clearSelection)
        menu.addAction('Remove selected images (keep annotations)', self.remove_workspace_images)
        menu.exec(self.files_tree.viewport().mapToGlobal(position))

    def remove_workspace_images(self, keys=None):
        if self.busy:
            return
        keys = keys if isinstance(keys, set) else self.selected_images() or ({self.current_key} if self.current_key else set())
        keys = keys.intersection(self.documents)
        if not keys:
            return
        try:
            for key in keys:
                self._persist(self.documents[key])
        except Exception as error:
            self.notify('Image removal blocked', str(error))
            return
        current_removed = self.current_key in keys
        if current_removed:
            self.preview_timer.stop()
            self._pending_preview = False
            self._prompt_version += 1
            self._preview_context = self._refine_target = None
            self.canvas.set_preview([])
            self.current_key = None
            self.canvas.set_document(None)
        for key in keys:
            self.documents.pop(key)
            self.histories.pop(key, None)
            self.stores.pop(key, None)
            self.mask_savepoints.pop(key, None)
        self._rebuild_file_tree()
        if current_removed and self.documents:
            self.select_document(next(iter(self.documents)))
        else:
            self._refresh()
        self.settings.setValue('last_files', list(dict.fromkeys(d.frame.source_path for d in self.documents.values())))
        self.settings.sync()

    def _offer_session_restore(self, paths):
        answer = QMessageBox.question(
            self, 'Reopen previous images?',
            'Reopen the images from the previous session? Saved annotations remain available if you choose No.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self.open_paths(paths)
        else:
            self.settings.setValue('last_files', [])
            self.settings.sync()
