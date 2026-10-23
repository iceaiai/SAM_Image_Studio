"""Run every test and reject accidentally skipped model/reader integration checks."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets",type=Path,default=ROOT/"validation_assets")
    parser.add_argument("--output",type=Path,default=ROOT/"validation/local_full_results.xml")
    args=parser.parse_args();assets=args.assets.resolve()
    required=[assets/"truck.jpg",assets/"models/sam_vit_b_01ec64.pth",assets/"models/sam2.1_hiera_tiny.pt",
              assets/"models/big-lama.pt",assets/"fixtures/test_STEM_image.dm3",assets/"fixtures/test-2.dm4",
              assets/"fixtures/multi_signal.dm3",assets/"fixtures/example_image.emd",assets/"fixtures/fei_example_tem_stack.emd"]
    missing=[str(p) for p in required if not p.is_file()]
    if missing:
        parser.error("Missing genuine test assets. Run scripts/fetch_validation_assets.py --models first:\n"+"\n".join(missing))
    from huggingface_hub import try_to_load_from_cache
    from samstudio.text_prompts import GROUNDING_MODEL, GROUNDING_REVISION
    if not isinstance(try_to_load_from_cache(GROUNDING_MODEL,"model.safetensors",revision=GROUNDING_REVISION),str):
        parser.error("Missing genuine text-model assets. Run scripts/fetch_validation_assets.py --models --text first.")
    env=dict(os.environ);env.update({"QT_QPA_PLATFORM":"offscreen","SAM_STUDIO_TEST_WEIGHTS":str(assets/"models"),
        "SAM_STUDIO_TEST_IMAGE":str(assets/"truck.jpg"),"SAM_STUDIO_TEST_FIXTURES":str(assets/"fixtures"),
        "SAM_STUDIO_TEST_REPORT":str(args.output.with_suffix(".models.json").resolve())})
    code=subprocess.call([sys.executable,"-m","pytest","-q","--junitxml="+str(args.output.resolve())],cwd=ROOT,env=env)
    if code:return code
    skipped=sum(int(s.attrib.get("skipped",0)) for s in ET.parse(args.output).getroot().iter("testsuite"))
    if skipped:
        print(f"Validation rejected: {skipped} tests were skipped.",file=sys.stderr)
        return 1
    print("Complete validation passed with no skipped tests.")
    return 0


if __name__=="__main__":raise SystemExit(main())
