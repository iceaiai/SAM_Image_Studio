"""Regression coverage for failures observed during WSL installation."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def system_installer():
    spec = importlib.util.spec_from_file_location("linux_dependencies", ROOT / "scripts/install_linux_dependencies.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_linux_installer_targets_missing_libraries_once(monkeypatch):
    module = system_installer()
    monkeypatch.setattr(module.sys, "platform", "linux")
    monkeypatch.setattr(module.os, "geteuid", lambda: 0)
    monkeypatch.setattr(module.shutil, "which", lambda name: "/usr/bin/" + name)
    states = iter([["libxcb-shape0", "libfontconfig1"], []])
    monkeypatch.setattr(module, "missing_packages", lambda: next(states))
    commands = []
    monkeypatch.setattr(module.subprocess, "run", lambda command, **kwargs: commands.append(command))
    assert module.main([]) == 0
    assert commands == [["apt-get", "update"], ["apt-get", "install", "--yes", "libxcb-shape0", "libfontconfig1", "fonts-dejavu-core"]]


def test_linux_installer_does_nothing_when_ready(monkeypatch):
    module = system_installer()
    monkeypatch.setattr(module.sys, "platform", "linux")
    monkeypatch.setattr(module, "missing_packages", lambda: [])
    monkeypatch.setattr(module.subprocess, "run", lambda *a, **kw: pytest.fail("Should not run apt"))
    assert module.main([]) == 0


def test_wsl_platform_selection_respects_explicit_choice(monkeypatch):
    from samstudio.qt_runtime import configure_qt_platform
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu-22.04")
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
    configure_qt_platform()
    assert __import__("os").environ["QT_QPA_PLATFORM"] == "xcb"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    configure_qt_platform()
    assert __import__("os").environ["QT_QPA_PLATFORM"] == "offscreen"


def test_optional_token_widget_is_ephemeral_and_native_only(qtbot):
    from samstudio.dialogs import ModelDialog
    from samstudio.inference import InferenceEngine
    dialog = ModelDialog(InferenceEngine())
    qtbot.addWidget(dialog)
    dialog.family.setCurrentText("SAM3.1")
    assert not dialog.hf_token.isHidden()
    assert dialog.hf_token.echoMode() == dialog.hf_token.EchoMode.Password
    dialog.hf_token.setText("  hf_test_only  ")
    assert dialog.take_hf_token() == "hf_test_only"
    assert dialog.hf_token.text() == ""
    dialog.hf_token.setText("hf_test_only")
    dialog.family.setCurrentText("SAM3 ONNX")
    assert dialog.hf_token.isHidden() and not dialog.hf_token.text()
    dialog.family.setCurrentText("SAM3.1")
    dialog.hf_token.setText("hf_test_only")
    dialog.reject()
    assert not dialog.hf_token.text()


def test_native_download_uses_token_and_redacts_download_errors(monkeypatch):
    import samstudio.inference as inference
    import huggingface_hub
    monkeypatch.setenv("CONDA_PREFIX", "/opt/conda/envs/sam3-test")
    monkeypatch.setattr(inference, "initialize_torch_runtime", lambda: SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: True)))
    requests = []
    def reject(repo, filename, **options):
        requests.append((repo, filename, options))
        raise ValueError("Rejected hf_test_only")
    monkeypatch.setattr(huggingface_hub, "hf_hub_download", reject)
    engine = inference.InferenceEngine()
    spec = next(s for s in inference.CATALOG if s.family == "SAM3.1")
    with pytest.raises(RuntimeError) as error:
        engine.load(spec, "cuda", hf_token="hf_test_only")
    assert requests == [("facebook/sam3.1", "sam3.1_multiplex.pt", {"token": "hf_test_only"})]
    assert "hf_test_only" not in str(error.value) and "[redacted]" in str(error.value)
    assert not engine.ready


def test_gpu_plan_installs_qt_and_pkg_resources_into_dedicated_env(monkeypatch):
    from samstudio.hardware import conda_gpu_plan
    report = {"gpus": [{"compute_capability": "8.6"}], "cuda_runtime_max": "13.1"}
    monkeypatch.setenv("CONDA_PREFIX", "/opt/conda/envs/sam3-test")
    commands = conda_gpu_plan(ROOT, report, current=True, sam3=True)
    assert commands[0][-1].endswith("scripts/install_linux_dependencies.py")
    assert any("setuptools==80.9.0" in command for command in commands)
    assert any(str(ROOT / "GPU/requirements-sam3.txt") in command for command in commands)
    monkeypatch.setenv("CONDA_PREFIX", "/opt/anaconda3")
    with pytest.raises(ValueError, match="non-base"):
        conda_gpu_plan(ROOT, report, current=True, sam3=True)
