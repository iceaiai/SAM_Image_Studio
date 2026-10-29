"""Installation diagnostics, with an opt-in genuine SAM inference check."""
from __future__ import annotations
import argparse
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import platform
import sys
import tempfile
import time
import traceback


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device",choices=["cpu","cuda"],default="cpu")
    parser.add_argument("--model",choices=["sam1","sam2"],help="Run a real checkpoint. Downloads official weights if --checkpoint is omitted.")
    parser.add_argument("--checkpoint",type=Path)
    parser.add_argument("--image",type=Path)
    parser.add_argument("--report",type=Path)
    args=parser.parse_args(argv)
    report={"platform":platform.platform(),"python":sys.version,"device":args.device,"checks":[],"status":"failed"}
    def passed(name,detail=""):
        report["checks"].append({"check":name,"passed":True,"detail":detail})
        print("PASS "+name+(": "+str(detail) if detail else ""),flush=True)
    try:
        import numpy as np
        import torch
        import torchvision
        import cv2
        from .inference import CATALOG,InferenceEngine
        from .domain import Calibration,Document,ImageFrame,ProjectStore
        from .exports import coco_rle,decode_coco_rle
        import sam2
        from rsciio.digitalmicrograph import file_reader as dm_reader
        from rsciio.emd import file_reader as emd_reader
        passed("Core and microscopy imports")
        if args.device=="cuda" and not os.environ.get("CONDA_PREFIX"):
            raise RuntimeError("The GPU self-test requires a dedicated Conda environment.")
        if args.device=="cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable; install the NVIDIA environment/driver or use CPU.")
        device=torch.device(args.device)
        probe=torch.arange(16,dtype=torch.float32,device=device).reshape(4,4)
        assert torch.isfinite(probe @ probe.T).all().item()
        boxes=torch.tensor([[0,0,10,10]],dtype=torch.float32,device=device)
        assert torchvision.ops.nms(boxes,torch.tensor([.9],device=device),.5).numel()==1
        if args.device=="cuda":torch.cuda.synchronize()
        passed("PyTorch and torchvision native operations",str(torch.__version__)+" on "+str(device))
        if not os.environ.get("DISPLAY") and sys.platform.startswith("linux"):
            os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
        from PySide6.QtWidgets import QApplication
        app=QApplication.instance() or QApplication([])
        from .main_window import MainWindow
        with tempfile.TemporaryDirectory(prefix="samstudio-selftest-") as directory:
            rgb=np.full((256,384,3),45,np.uint8)
            cv2.circle(rgb,(192,128),55,(210,210,210),-1)
            frame=ImageFrame(str(Path(directory)/"synthetic.png"),rgb,calibration=Calibration(.2,.3,"nm","selftest",True))
            doc=Document(frame);doc.ensure_group("Selftest")
            mask=np.zeros(frame.shape,bool);mask[60:180,130:250]=True
            doc.add_object("mask",mask=mask)
            store=ProjectStore(Path(directory));store.save(doc)
            restored=Document(frame);assert store.load(restored)[0]
            assert np.array_equal(restored.objects[0].mask,mask)
            assert np.array_equal(decode_coco_rle(coco_rle(mask)),mask)
            passed("Autosave recovery and exact COCO RLE")
            previous_profile=os.environ.get("SAM_STUDIO_DATA_DIR")
            os.environ["SAM_STUDIO_DATA_DIR"]=str(Path(directory)/"isolated-gui-profile")
            try:
                window=MainWindow(restore_session=False)
                window.show();app.processEvents();window.close();app.processEvents()
            finally:
                if previous_profile is None:os.environ.pop("SAM_STUDIO_DATA_DIR",None)
                else:os.environ["SAM_STUDIO_DATA_DIR"]=previous_profile
            passed("Qt desktop window construction")
            if args.model:
                from .edition import offline_profile
                wanted=("SAM1","ViT-B") if args.model=="sam1" else ("SAM2.1","Small" if offline_profile() else "Tiny")
                spec=next(s for s in CATALOG if (s.family,s.variant)==wanted)
                engine=InferenceEngine();started=time.perf_counter()
                engine.load(spec,args.device,args.checkpoint,progress=lambda m:print(m,flush=True))
                if args.image:
                    from PIL import Image
                    image=Image.open(args.image).convert("RGB");image.thumbnail((1024,1024));rgb=np.asarray(image).copy()
                h,w=rgb.shape[:2]
                result,score=engine.predict(rgb,[[w/2,h/2,1]])
                assert result.shape==(h,w) and result.any() and np.isfinite(score)
                passed("Genuine SAM checkpoint inference",{"model":spec.label,"area":int(result.sum()),"score":score,"seconds":round(time.perf_counter()-started,3)})
        report["versions"]={}
        for name in ["sam-image-studio","PySide6","torch","torchvision","numpy","SAM-2","rosettasciio","tifffile"]:
            try:report["versions"][name]=metadata.version(name)
            except metadata.PackageNotFoundError:report["versions"][name]="source checkout"
        report["status"]="passed"
    except Exception as error:
        report["error"]=str(error);traceback.print_exc()
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("Installation self-test "+report["status"]+".",flush=True)
    return 0 if report["status"]=="passed" else 1


if __name__=="__main__":
    raise SystemExit(main())
