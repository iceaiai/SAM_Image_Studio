"""Run genuine SAM3 ONNX text inference without constructing a Qt window."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--text", default="black dots")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--min-score", type=float, default=.70)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--masks", type=Path)
    args = parser.parse_args()
    import numpy as np
    from PIL import Image
    from samstudio.inference import CATALOG, InferenceEngine
    from samstudio.processing import display_rgb
    from samstudio.text_prompts import resolve_prompt
    rgb = display_rgb(np.asarray(Image.open(args.image)))
    engine = InferenceEngine()
    started = time.perf_counter()
    spec = next(s for s in CATALOG if s.family == "SAM3 ONNX")
    loaded = engine.load(spec, args.device, args.model_dir, progress=lambda message: print(message, flush=True))
    loading = time.perf_counter() - started
    started = time.perf_counter()
    masks = engine.infer(rgb, whole=True, text_prompt=resolve_prompt(args.text, {}), min_score=args.min_score,
                         progress=lambda message: print(message, flush=True))
    elapsed = time.perf_counter() - started
    report = dict(loaded, status="passed", text=args.text, image_shape=list(rgb.shape),
                  load_seconds=loading, request_seconds=elapsed, count=len(masks),
                  min_score=args.min_score, scores=engine.last_proposal_scores,
                  providers=engine.predictor.providers,
                  timing_scope="Load includes integrity verification/session creation. Request includes encoding, decoding and app filtering; no GUI drawing. Cached requests can be faster.")
    if args.masks:
        args.masks.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(args.masks, masks=np.stack(masks) if masks else np.zeros((0, *rgb.shape[:2]), bool),
                            scores=np.asarray(engine.last_proposal_scores))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
