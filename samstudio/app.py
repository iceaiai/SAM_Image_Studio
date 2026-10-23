from __future__ import annotations
import argparse
import logging
from logging.handlers import RotatingFileHandler
import sys
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox
from . import __version__
from .inference import data_directory

STYLE = """
QMainWindow { background: #f3f5f8; }
QToolBar { background: #f8fafc; border: 1px solid #dce3ed; spacing: 7px; padding: 6px; }
QToolButton { border-radius: 5px; padding: 7px; }
QToolButton:hover { background: #e4edfc; }
QToolButton:checked { background: #d8e6ff; border: 1px solid #7399e8; }
QPushButton { padding: 6px 11px; border: 1px solid #cbd5e3; border-radius: 5px; background: #ffffff; color: #20344f; }
QPushButton:hover { background: #eaf1ff; border-color: #87a6e7; }
QPushButton:disabled { color: #94a0af; background: #f5f6f8; }
QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox { border: 1px solid #cbd5e3; border-radius: 4px; padding: 5px; background: white; color:#20344f; }
QComboBox QAbstractItemView { background:white; color:#20344f; selection-background-color:#dce9ff; selection-color:#20344f; }
QTreeWidget { background: white; border: 1px solid #dce3ed; alternate-background-color: #f5f8fc; }
QTreeWidget::item { padding: 4px; }
QTreeWidget::item:selected { background: #e1ebff; color: #193d7e; }
QHeaderView::section { background: #edf2f8; border: 0; padding: 6px; }
QDockWidget::title { background: #e8eef7; padding: 7px; color: #20344f; font-weight: bold; }
QStatusBar { background: #edf2f8; color: #465d77; }
QLabel { color: #304660; }
"""


def main(argv=None):
    parser=argparse.ArgumentParser(description="SAM Image Studio desktop application")
    parser.add_argument("images",nargs="*")
    parser.add_argument("--version",action="version",version=__version__)
    parser.add_argument("--no-restore",action="store_true",help="Do not reopen the previous image session")
    args=parser.parse_args(argv)
    directory=data_directory();directory.mkdir(parents=True,exist_ok=True)
    handler=RotatingFileHandler(directory/"samstudio.log",maxBytes=3_000_000,backupCount=3,encoding="utf-8")
    logging.basicConfig(level=logging.INFO,handlers=[handler],format="%(asctime)s %(levelname)s %(name)s %(message)s")
    app=QApplication.instance() or QApplication([sys.argv[0]])
    app.setOrganizationName("SAMImageStudio");app.setApplicationName("SAM Image Studio");app.setStyle("Fusion");app.setStyleSheet(STYLE)
    from .main_window import MainWindow
    window=MainWindow(restore_session=not args.no_restore and not args.images)
    def error_hook(kind,value,tb):
        logging.getLogger(__name__).error("Unhandled GUI error",exc_info=(kind,value,tb))
        QMessageBox.critical(window,"Unexpected error",f"{value}\n\nWork already autosaved remains available. Details are in samstudio.log.")
    sys.excepthook=error_hook
    window.show()
    if args.images:window.open_paths(args.images)
    return app.exec()

