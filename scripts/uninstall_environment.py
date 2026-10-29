"""Remove only this extracted release's explicitly owned environments."""
import argparse
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def uninstall(root=ROOT,dry_run=False):
    removed=[]
    for name in (".venv",".venv-offline",".venv-gpu","build","dist"):
        target=Path(root)/name
        marker=target/".samstudio-owned"
        if not target.exists():continue
        if target.is_symlink() or not marker.is_file():
            print(f"Kept {target}: it is not a verified app-owned folder.")
            continue
        if not dry_run:shutil.rmtree(target)
        removed.append(str(target));print(("Would remove " if dry_run else "Removed ")+str(target))
    print("Original images, SAM_Annotations, exported data, models and settings were preserved.")
    print("To remove cached models/settings separately, delete only your SAMImageStudio data folder after backing up any projects stored there.")
    return removed


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--dry-run",action="store_true")
    uninstall(dry_run=parser.parse_args().dry_run)
