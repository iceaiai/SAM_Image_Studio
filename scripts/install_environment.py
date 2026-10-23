"""Install into an app-owned venv by default. Never changes system Python packages."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import venv

ROOT=Path(__file__).resolve().parents[1]
SAM2_WHEEL_SHA256="a1b5d867f7724c0ed823bf3c65854749cd44a4fd02f1782a709e5306fe54ae8c"


def run(command):
    print("\n> "+" ".join(map(str,command)),flush=True)
    subprocess.run([str(x) for x in command],cwd=ROOT,check=True)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend",choices=["cpu","cuda"],default="cpu")
    parser.add_argument("--current",action="store_true",help="Use the currently activated virtual/Conda environment")
    parser.add_argument("--dry-run",action="store_true")
    args=parser.parse_args(argv)
    if sys.version_info[:2] != (3,12) or struct.calcsize("P")!=8:
        parser.error("Use 64-bit Python 3.12 for this tested release.")
    if args.backend=="cuda":
        parser.error("Use scripts/install_conda_gpu.py inside a dedicated Conda environment. GPU venv installation is disabled.")
    if args.current and sys.prefix==sys.base_prefix and not os.environ.get("CONDA_PREFIX"):
        parser.error("--current requires an activated virtual environment or Conda environment.")
    wheel=ROOT/"vendor/sam_2-1.0-py3-none-any.whl"
    if hashlib.sha256(wheel.read_bytes()).hexdigest()!=SAM2_WHEEL_SHA256:
        raise ValueError("The bundled SAM2 package failed verification. Extract a clean copy of the release.")
    env=ROOT/(".venv" if args.backend=="cpu" else ".venv-gpu")
    py=Path(sys.executable) if args.current else env/("Scripts/python.exe" if os.name=="nt" else "bin/python")
    commands=[
        [py,"-m","pip","install","--upgrade","pip>=24.3","setuptools>=75","wheel"],
        [py,"-m","pip","install","torch==2.7.1","torchvision==0.22.1","--index-url",
         "https://download.pytorch.org/whl/"+("cpu" if args.backend=="cpu" else "cu126")],
        [py,"-m","pip","install","--find-links",ROOT/"vendor","-r",ROOT/"requirements.lock.txt"],
        [py,"-m","pip","install","--no-deps",wheel],
        [py,"-m","pip","install","--no-deps",ROOT],
        [py,"-m","pip","check"],
        [py,"-m","samstudio.selftest","--device",args.backend],
    ]
    if args.dry_run:
        print(json.dumps({"environment":str(py),"backend":args.backend,"commands":[list(map(str,c)) for c in commands]},indent=2))
        return 0
    if not args.current:
        marker=env/".samstudio-owned"
        if env.exists() and not marker.exists():
            raise ValueError(f"{env} already exists and is not marked as an app-owned environment. Rename it first.")
        if not env.exists():
            env.mkdir(parents=True)
            marker.write_text("SAM Image Studio local environment\n")
        venv.EnvBuilder(with_pip=True,clear=False).create(env)
        marker.write_text("SAM Image Studio local environment\n")
    for command in commands:run(command)
    print("\nInstallation verified. Run Start_GUI.bat on Windows or ./start_gui.sh on Linux/macOS.")
    if args.current:print("For this activated environment use: python -m samstudio")
    elif args.backend=="cuda":print("For GPU use: Start_GUI_GPU.bat or .venv-gpu/bin/python -m samstudio")
    return 0


if __name__=="__main__":
    try:raise SystemExit(main())
    except subprocess.CalledProcessError as error:
        print(f"\nInstallation stopped at a failed command (exit {error.returncode}). Resolve the error above and rerun. Existing projects are preserved.",file=sys.stderr)
        raise SystemExit(error.returncode or 1)
