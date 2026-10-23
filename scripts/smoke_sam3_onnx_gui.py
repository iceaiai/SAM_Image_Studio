"""Genuine ONNX Qt smoke: public synthetic image, text, alias, ROI, accept/reopen.

Requires the installed app and separately downloaded public export. Uses a fresh
profile/project so existing accepted objects cannot affect a repeated check.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir',type=Path,required=True)
    parser.add_argument('--device',choices=['cpu','cuda'],default='cpu')
    parser.add_argument('--report',type=Path)
    parser.add_argument('--screenshot',type=Path)
    args=parser.parse_args()
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    with tempfile.TemporaryDirectory(prefix='samstudio-onnx-smoke-') as scratch:
        os.environ['SAM_STUDIO_DATA_DIR']=str(Path(scratch)/'profile')
        from PySide6.QtWidgets import QApplication,QDialog
        from samstudio.app import STYLE
        import samstudio.main_window as gui
        from samstudio.dialogs import ModelDialog
        from samstudio.domain import Document
        app=QApplication([]);app.setStyle('Fusion');app.setStyleSheet(STYLE)
        class SelectedDialog(ModelDialog):
            def __init__(self,*parents):
                super().__init__(*parents)
                self.family.setCurrentText('SAM3 ONNX');self.path.setText(str(args.model_dir.resolve()))
                self.device.setCurrentIndex(1 if args.device=='cuda' else 0)
            def exec(self):return QDialog.DialogCode.Accepted
        gui.ModelDialog=SelectedDialog
        window=gui.MainWindow(restore_session=False)
        window.project_directory=str(Path(scratch)/'projects');window.resize(1500,980);window.show()
        errors=[];window.notify=lambda title,message:errors.append((title,str(message)))
        def wait():
            deadline=time.monotonic()+300
            while window.busy:
                app.processEvents();time.sleep(.01)
                if time.monotonic()>deadline:raise TimeoutError('ONNX GUI task timed out')
            app.processEvents()
        window.open_paths([str(ROOT/'examples/synthetic_particles.ome.tif')]);wait()
        assert window.document is not None and not window.document.objects
        window.model_dialog();wait();assert window.engine.ready and not errors,errors
        window.document.ensure_group('ONNX demo');window._refresh();window.auto_checkbox.setChecked(False)
        window.mode.setCurrentText('Segment');window.text_prompt.setText('white dots')
        started=time.perf_counter();window.text_run_button.click();wait();seconds=time.perf_counter()-started
        count=len(window.canvas.preview_masks);assert count>0,errors
        print(f'Real GUI whole image: {count} masks, {seconds:.3f} seconds',flush=True)
        window.tool_actions['rectangle'].trigger();window.scope.setCurrentIndex(window.scope.findData('roi'))
        window._shape_completed('rectangle',[[0,0],[384,512]])
        window.document.text_aliases={'demo particles':'white dots'}
        window.text_prompt.setText('demo particles');window.text_run_button.click();wait()
        roi=window._selection_mask();assert roi is not None
        assert window.canvas.preview_masks and all(not (mask&~roi).any() for mask in window.canvas.preview_masks),errors
        roi_count=len(window.canvas.preview_masks);window.accept_button.click();app.processEvents()
        assert len(window.document.objects)==roi_count and not errors,errors
        assert all(obj.provenance['effective_text_prompt']=='white dots' and obj.provenance['text_backend']=='SAM3 ONNX' for obj in window.document.objects)
        restored=Document(window.document.frame);assert window.stores[window.current_key].load(restored)[0]
        assert len(restored.objects)==roi_count
        window.canvas.fit_image()
        window.statusBar().showMessage(f'Real SAM3 ONNX {args.device.upper()} on synthetic demo - alias + ROI - accepted and saved')
        app.processEvents()
        if args.screenshot:
            args.screenshot.parent.mkdir(parents=True,exist_ok=True)
            assert window.grab().save(str(args.screenshot))
        report={'backend':'SAM3 ONNX','device':args.device,'image':'bundled synthetic_particles.ome.tif',
                'text':'white dots','whole_image_count':count,'whole_image_seconds_including_gui_worker':seconds,
                'roi_accepted_count':roi_count,'alias_resolved':True,'no_masks_outside_roi':True,
                'native_project_reopened':True,'providers':window.engine.predictor.providers}
        if args.report:
            args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2),flush=True)
        window.close();app.processEvents()
    return 0


if __name__=='__main__':raise SystemExit(main())
