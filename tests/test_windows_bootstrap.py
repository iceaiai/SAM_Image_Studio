"""Regression coverage for the argument rules used by Windows PowerShell."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import stat
import subprocess
import sys
import zipfile

import pytest


BOOTSTRAP = Path(__file__).resolve().parents[1] / "packaging" / "bootstrap_python.ps1"


@pytest.fixture
def project(tmp_path):
    shell = shutil.which("powershell.exe" if os.name == "nt" else "pwsh")
    if not shell:
        pytest.skip("PowerShell is required to exercise the bootstrap script.")

    root = tmp_path / "Project with spaces"
    packaging = root / "packaging"
    packaging.mkdir(parents=True)
    shutil.copy2(BOOTSTRAP, packaging / BOOTSTRAP.name)
    wrapper = root / "bootstrap test.ps1"
    wrapper.write_text(
        "param([string]$Action)\n"
        "$PSNativeCommandArgumentPassing = 'Legacy'\n"
        "& (Join-Path $PSScriptRoot 'packaging/bootstrap_python.ps1') -Action $Action\n"
        "exit $LASTEXITCODE\n",
        encoding="ascii",
    )

    def run(*, project_only=False, action="PreparePython"):
        env = os.environ.copy()
        if project_only:
            env["PATH"] = str(root / "no-system-python")
        options = ["-NoProfile", "-NonInteractive"]
        if os.name == "nt":
            options += ["-ExecutionPolicy", "Bypass"]
        return subprocess.run([shell, *options, "-File", str(wrapper), "-Action", action], cwd=root, env=env,
                              capture_output=True, text=True, timeout=45)

    return root, run


def test_legacy_argument_mode_reuses_healthy_local_python(project):
    root, run = project
    local = root / ".python312"
    if os.name == "nt":
        result = subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(local), sys.base_prefix],
                                capture_output=True, text=True, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
    else:
        local.mkdir()
        wrapper = local / "python.exe"
        wrapper.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} "$@"\n')
        wrapper.chmod(0o755)

    result = run(project_only=os.name != "nt")
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"Python 3.12 ready: {local / 'python.exe'}" in result.stdout
    assert not (root / ".install-cache").exists()


def cache_runtime(root, cache_dir, works=True):
    cache = root / cache_dir / "runtime"
    cache.mkdir(parents=True)
    archive = cache / "fixture.nupkg"
    executable = zipfile.ZipInfo("tools/python.exe")
    executable.create_system = 3
    executable.external_attr = (stat.S_IFREG | 0o755) << 16
    script = (
        f'#!/bin/sh\nexec {shlex.quote(sys.executable)} "$@"\n'
        if works else "#!/bin/sh\nprintf 'test launch error\\n' >&2\nexit 37\n"
    )
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(executable, script)
    manifest = {"windows-x86_64": {"filename": archive.name, "archive_root": "tools",
                                   "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}}
    (root / "packaging" / "python-runtimes.json").write_text(json.dumps(manifest), encoding="ascii")
    return archive


@pytest.mark.skipif(os.name != "posix", reason="The staged runtime fixture is a POSIX executable.")
@pytest.mark.parametrize("works", [True, False])
def test_bootstrap_checks_verified_runtime_before_moving_it_into_place(project, works):
    root, run = project
    archive = cache_runtime(root, ".install-cache", works)

    result = run(project_only=True)
    local = root / ".python312"
    assert not list(root.glob(".python-stage-*"))
    if works:
        assert result.returncode == 0, result.stdout + result.stderr
        assert f"Python 3.12 ready: {local / 'python.exe'}" in result.stdout
        assert (local / ".samstudio-owned").is_file()
        again = run(project_only=True)
        assert again.returncode == 0, again.stdout + again.stderr
        assert again.stdout == result.stdout
    else:
        assert result.returncode != 0
        assert "code 37" in result.stderr and "test launch error" in result.stderr
        assert not local.exists()
        assert archive.is_file()


@pytest.mark.skipif(os.name != "posix", reason="The staged runtime fixture is a POSIX executable.")
@pytest.mark.parametrize(("action", "script"), [("PrepareOffline", "prepare_offline"),
                                                  ("InstallCPU", "install_offline"),
                                                  ("InstallOffline", "install_offline")])
def test_offline_actions_use_the_verified_python_cache(project, action, script):
    root, run = project
    cache_runtime(root, "offline-cache")
    resources = root / "samstudio" / "resources"
    resources.mkdir(parents=True)
    (resources / "offline_profile.json").write_text("{}", encoding="ascii")
    scripts = root / "scripts"
    scripts.mkdir()
    (scripts / f"{script}.py").write_text(f"print('{script} invoked')", encoding="ascii")

    result = run(project_only=True, action=action)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"{script} invoked" in result.stdout
    assert (root / ".python312" / ".samstudio-owned").is_file()
    assert not (root / ".install-cache").exists()
