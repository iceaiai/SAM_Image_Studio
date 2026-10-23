import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import numpy as np
import pytest
from PIL import Image
from samstudio.domain import Calibration, Document, ImageFrame

@pytest.fixture
def document(tmp_path):
    raw=(np.arange(128*160,dtype=np.uint16).reshape(128,160)*3)
    path=tmp_path/"source.tif"
    import tifffile
    tifffile.imwrite(path,raw)
    doc=Document(ImageFrame(str(path),raw,calibration=Calibration(.2,.3,"nm","test",True)))
    doc.ensure_group("Particle")
    mask=np.zeros(raw.shape,bool);mask[10:55,10:55]=True;mask[20:30,20:30]=False
    doc.add_object("mask",mask=mask)
    return doc

@pytest.fixture
def window(qtbot,tmp_path,monkeypatch):
    monkeypatch.setenv("SAM_STUDIO_DATA_DIR",str(tmp_path/"profile"))
    from samstudio.main_window import MainWindow
    win=MainWindow(restore_session=False);win.errors=[]
    win.notify=lambda title,message:win.errors.append((title,str(message)))
    qtbot.addWidget(win);win.show();qtbot.wait(30)
    yield win
    if win.busy:
        win._job.cancel.set();qtbot.waitUntil(lambda:not win.busy,timeout=30000)
    # Avoid an irrelevant leave-behind modal if a test intentionally simulates failed saving.
    for doc in win.documents.values():doc.saved_revision=doc.revision
    win.close()

