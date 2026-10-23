"""Download public integration fixtures and genuine checkpoints, with recorded digests."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from samstudio.inference import CATALOG,download_file,LAMA_URL,LAMA_SHA256


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory",type=Path,default=ROOT/"validation_assets")
    parser.add_argument("--models",action="store_true",help="Also download approximately 703 MiB of genuine model weights")
    parser.add_argument("--text",action="store_true",help="Also cache the pinned public Grounding DINO Tiny model")
    args=parser.parse_args()
    for asset in json.loads((ROOT/"validation/external_assets.json").read_text()):
        path=args.directory/("truck.jpg" if asset["name"]=="truck.jpg" else "fixtures/"+asset["name"])
        download_file(asset["url"],path,asset["sha256"],progress=print)
    if args.models:
        for family,variant in [("SAM1","ViT-B"),("SAM2.1","Tiny")]:
            spec=next(s for s in CATALOG if (s.family,s.variant)==(family,variant))
            download_file(spec.url,args.directory/"models"/spec.filename,spec.sha256,progress=print)
        download_file(LAMA_URL,args.directory/"models/big-lama.pt",LAMA_SHA256,progress=print)
    if args.text:
        from huggingface_hub import snapshot_download
        from samstudio.text_prompts import GROUNDING_MODEL,GROUNDING_REVISION
        path=snapshot_download(GROUNDING_MODEL,revision=GROUNDING_REVISION,allow_patterns=['*.json','*.txt','*.safetensors'])
        print("Text assets ready:",path)
    print("Assets ready:",args.directory.resolve())


if __name__=="__main__":main()
