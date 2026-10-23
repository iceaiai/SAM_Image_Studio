"""Install SAM3 ONNX into the active dedicated environment, never Conda base."""
from __future__ import annotations

import argparse
import importlib.metadata as metadata
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    conda = os.environ.get("CONDA_PREFIX")
    if (sys.prefix == sys.base_prefix and not conda) or (conda and Path(conda).name.lower() in ("base", "anaconda3", "miniconda3", "miniforge3")):
        parser.error("Activate a dedicated virtual/Conda environment; installation into system Python or Conda base is disabled.")
    if args.device == "cuda" and not conda:
        parser.error("CUDA installation requires a dedicated non-base Conda environment.")
    other = "onnxruntime" if args.device == "cuda" else "onnxruntime-gpu"
    commands = []
    try:
        metadata.version(other)
    except metadata.PackageNotFoundError:
        pass
    else:
        # The two distributions own the same Python module; installing both
        # breaks provider selection. Replace only this known counterpart.
        commands.append([sys.executable, "-m", "pip", "uninstall", "--yes", other])
    requirements = ROOT / ("GPU/requirements-onnx.txt" if args.device == "cuda" else "packaging/requirements/onnx-cpu.txt")
    commands.append([sys.executable, "-m", "pip", "install", "-r", str(requirements)])
    commands.append([sys.executable, "-m", "pip", "check"])
    for command in commands:
        print("Running: " + " ".join(command), flush=True)
        if not args.dry_run:
            subprocess.run(command, cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
