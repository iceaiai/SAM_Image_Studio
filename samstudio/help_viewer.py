"""Bundled English PDF help displayed inside the desktop application."""
from pathlib import Path
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QPushButton,QLabel,QDoubleSpinBox
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView

class PdfHelpDialog(QDialog):
    def __init__(self,path,title,parent=None):
        super().__init__(parent);self.setWindowTitle(title);self.resize(1080,820)
        self.document=QPdfDocument(self)
        error=self.document.load(str(path))
        if error!=QPdfDocument.Error.None_:raise ValueError('Cannot load help PDF: '+str(error))
        layout=QVBoxLayout(self);row=QHBoxLayout();layout.addLayout(row)
        row.addWidget(QLabel(f'{self.document.pageCount()} pages'));row.addStretch()
        self.view=QPdfView(self);self.view.setDocument(self.document);self.view.setPageMode(QPdfView.PageMode.MultiPage);self.view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        fit=QPushButton('Fit width');fit.clicked.connect(lambda:self.view.setZoomMode(QPdfView.ZoomMode.FitToWidth));row.addWidget(fit)
        zoom=QDoubleSpinBox();zoom.setRange(25,300);zoom.setSuffix('%');zoom.setValue(100)
        def changed(value):self.view.setZoomMode(QPdfView.ZoomMode.Custom);self.view.setZoomFactor(value/100)
        zoom.valueChanged.connect(changed);row.addWidget(zoom);layout.addWidget(self.view)

def open_pdf_help(window,developer=False,denoise=False):
    name='SAM_Image_Studio_Denoising_Parameters.pdf' if denoise else 'SAM_Image_Studio_For_Developer.pdf' if developer else 'SAM_Image_Studio_User_Manual.pdf'
    path=Path(__file__).parent/'resources'/name
    if not path.exists():path=Path(__file__).resolve().parents[1]/'docs'/name
    if not path.exists():raise ValueError('Help PDF is missing. Extract the complete release package or reinstall its wheel.')
    dialog=PdfHelpDialog(path,'Denoising Parameters' if denoise else 'For Developer' if developer else 'User Manual',window)
    if not hasattr(window,'help_windows'):window.help_windows=[]
    window.help_windows.append(dialog);dialog.finished.connect(lambda result:window.help_windows.remove(dialog) if dialog in window.help_windows else None);dialog.show()
    return dialog
