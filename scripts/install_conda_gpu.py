"""Compatibility entry point; GPU setup is maintained in GPU/install.py."""
import runpy
from pathlib import Path
if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parents[1] / "GPU/install.py"), run_name="__main__")
