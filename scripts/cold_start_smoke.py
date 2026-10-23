"""Real GUI/model smoke test in a fresh process, without preimporting PyTorch."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family",choices=["SAM1","SAM2.1"],default="SAM2.1")
    parser.add_argument("--checkpoint",type=Path,required=True)
    parser.add_argument("--report",type=Path)
    args=parser.parse_args()
    # No torch import here: this test must exercise the app's cold bootstrap.
    os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
    with tempfile.TemporaryDirectory(prefix="sam-cold-smoke-") as scratch:
        os.environ["SAM_STUDIO_DATA_DIR"]=str(Path(scratch)/"profile")
        from PySide6.QtCore import QTimer
        from PySide6.QtGui import QPaintDevice
        from PySide6.QtWidgets import QApplication
        from samstudio.main_window import MainWindow
        from samstudio.dialogs import StatisticsDialog
        from samstudio.domain import Document
        from samstudio.inference import CATALOG
        app=QApplication([]);window=MainWindow(restore_session=False)
        window.project_directory=str(Path(scratch)/"projects")
        errors=[];window.notify=lambda t,m:errors.append((t,str(m)))
        window.show();ticks=[];heartbeat=QTimer();heartbeat.timeout.connect(lambda:ticks.append(1));heartbeat.start(15)
        def wait(predicate):
            deadline=time.monotonic()+120
            while not predicate():
                app.processEvents();time.sleep(.005)
                if time.monotonic()>deadline:raise TimeoutError("Cold GUI smoke timed out")
            app.processEvents()
        window.open_paths([str(ROOT/"examples/synthetic_particles.ome.tif")]);wait(lambda:not window.busy)
        doc=window.document;assert doc is not None
        window._commit("Group",lambda:doc.ensure_group("Particles"))
        window.mode.setCurrentText("Segment");window.tool_actions["rectangle"].trigger();window.scope.setCurrentIndex(window.scope.findData("single"));window._prompt_added(120,115,1)
        spec=next(s for s in CATALOG if s.family==args.family and s.variant==("ViT-B" if args.family=="SAM1" else "Tiny"))
        window._start_job("Cold model loading",lambda p,c:window.engine.load(spec,"cpu",args.checkpoint,p,c),lambda r:None)
        wait(lambda:not window.busy);assert window.engine.ready,errors
        window._prompt_added(122,116,1)
        wait(lambda:bool(window.canvas.preview_masks) and not window.busy)
        assert len(window.canvas.preview_masks)==1
        window._prompt_added(350,400,0)
        wait(lambda:bool(window.canvas.preview_masks) and not window.busy)
        window.accept_preview();assert len(doc.objects)==1 and doc.objects[0].pixel_area>1
        restored=Document(doc.frame);window.stores[doc.frame.key].load(restored)
        assert restored.objects[0].pixel_area==doc.objects[0].pixel_area
        statistics=StatisticsDialog([doc],doc,parent=window);statistics.show();app.processEvents()
        statistics.resize(1100,750);app.processEvents();statistics.canvas.draw()
        assert callable(statistics.metric) and statistics.metric(QPaintDevice.PaintDeviceMetric.PdmWidth)>0
        assert not statistics.grab().isNull();statistics.close();app.processEvents()
        assert not errors and len(ticks)>5
        result={"family":args.family,"device":"cpu","fresh_process":True,"qt_heartbeat_ticks":len(ticks),
                "preexisting_prompts_then_new_clicks":True,"accepted_objects":len(doc.objects),
                "autosave_recovery":True,"histogram_paint_resize":True,"errors":errors}
        heartbeat.stop();window.close();app.processEvents();window.pool.waitForDone(10000)
        if args.report:
            args.report.parent.mkdir(parents=True,exist_ok=True)
            args.report.write_text(json.dumps(result,indent=2))
        print(json.dumps(result))
    return 0


if __name__=="__main__":raise SystemExit(main())
