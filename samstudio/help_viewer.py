"""Bundled English help for the desktop application."""
from importlib.resources import files
from pathlib import Path
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QPushButton,QLabel,QDoubleSpinBox,QTextBrowser
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView

from . import __version__

DENOISING_SECTION = "denoising-parameters"


class UserManualDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle(f"User Manual — SAM Image Studio {__version__}")
        self.resize(1000, 780)
        layout = QVBoxLayout(self)
        navigation = QHBoxLayout()
        contents = QPushButton("Start of manual")
        contents.clicked.connect(lambda: self.show_section())
        denoising = QPushButton("Denoising parameters")
        denoising.clicked.connect(lambda: self.show_section(DENOISING_SECTION))
        navigation.addWidget(contents)
        navigation.addWidget(denoising)
        navigation.addStretch()
        layout.addLayout(navigation)
        self.browser = QTextBrowser()
        layout.addWidget(self.browser)
        body = files("samstudio").joinpath("resources", "user_manual.md").read_text(encoding="utf-8")
        self.browser.setMarkdown(f"# SAM Image Studio {__version__} User Manual\n\n{body}")
        block = self.browser.document().begin()
        while block.isValid():
            if block.blockFormat().headingLevel() == 2 and block.text() == "Denoising parameters":
                break
            block = block.next()
        if block.isValid():
            heading = QTextCursor(block)
            heading.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor)
            anchor = QTextCharFormat()
            anchor.setAnchor(True)
            anchor.setAnchorNames([DENOISING_SECTION])
            heading.mergeCharFormat(anchor)

    def show_section(self, section=None):
        if section:
            self.browser.scrollToAnchor(section)
        else:
            self.browser.verticalScrollBar().setValue(0)


def open_user_manual(window, section=None):
    dialog = UserManualDialog(window)
    dialog.show()
    QTimer.singleShot(0, dialog, lambda: dialog.show_section(section))
    return dialog


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
