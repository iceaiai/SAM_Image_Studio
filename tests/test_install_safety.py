import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def load_uninstaller():
    spec=importlib.util.spec_from_file_location("uninstaller",ROOT/"scripts/uninstall_environment.py")
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def test_uninstall_preserves_projects_and_unknown_environments(tmp_path):
    owned=tmp_path/".venv";owned.mkdir();(owned/".samstudio-owned").write_text("owned")
    (owned/"package.txt").write_text("remove")
    unknown=tmp_path/".venv-gpu";unknown.mkdir();(unknown/"important.txt").write_text("keep")
    project=tmp_path/"SAM_Annotations";project.mkdir();(project/"one.sam.json").write_text("{}")
    removed=load_uninstaller().uninstall(tmp_path)
    assert removed==[str(owned)] and not owned.exists()
    assert (unknown/"important.txt").exists() and (project/"one.sam.json").exists()


def test_installer_defaults_to_cpu_and_local_environment():
    output=subprocess.check_output([sys.executable,str(ROOT/"scripts/install_environment.py"),"--dry-run"],text=True)
    value=json.loads(output);assert value["backend"]=="cpu"
    assert ".venv" in value["environment"] and any("https://download.pytorch.org/whl/cpu" in c for c in value["commands"])


def test_installation_selftest_preserves_user_session_settings(tmp_path):
    import os
    profile=tmp_path/"user-profile";profile.mkdir()
    settings=profile/"settings.ini";before=b"[General]\nlast_files=important_image.tif\n"
    settings.write_bytes(before)
    env=dict(os.environ);env["SAM_STUDIO_DATA_DIR"]=str(profile);env["QT_QPA_PLATFORM"]="offscreen"
    result=subprocess.run([sys.executable,"-m","samstudio.selftest"],cwd=ROOT,env=env,capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
    assert settings.read_bytes()==before
