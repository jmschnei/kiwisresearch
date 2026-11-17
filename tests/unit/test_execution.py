"""Tests for sandbox execution."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kiwis.execution.sandbox import ExecutionResult, ExecutionStatus


def test_execution_result_success():
    result = ExecutionResult(
        status=ExecutionStatus.SUCCESS,
        stdout="Training complete.",
        exit_code=0,
        execution_time_seconds=1.5,
    )
    assert result.status == ExecutionStatus.SUCCESS
    assert result.exit_code == 0


def test_execution_result_failed():
    result = ExecutionResult(
        status=ExecutionStatus.FAILED,
        stderr="RuntimeError: tensor size mismatch",
        exit_code=1,
    )
    assert result.status == ExecutionStatus.FAILED
    assert result.exit_code == 1


def test_execution_result_timeout():
    result = ExecutionResult(
        status=ExecutionStatus.TIMEOUT,
        execution_time_seconds=600.0,
    )
    assert result.status == ExecutionStatus.TIMEOUT


def test_isolated_sandbox_initialization():
    from kiwis.execution.isolated_sandbox import IsolatedSandbox
    sandbox = IsolatedSandbox()
    # Can't fully test without running, but verify instantiation
    assert sandbox._timeout == 600


def test_docker_sandbox_class_exists():
    from kiwis.execution.docker_sandbox import DockerSandbox
    sandbox = DockerSandbox()
    assert sandbox._image_name == "kiwis-sandbox:latest"


def test_make_sandbox_uses_docker_when_available_and_falls_back_otherwise(tmp_path, monkeypatch, caplog):
    import kiwis.execution.docker_sandbox as ds
    from kiwis.api.jobs import _make_sandbox
    from kiwis.config.settings import Settings
    from kiwis.execution.isolated_sandbox import IsolatedSandbox

    settings = Settings(sandbox={"mode": "docker", "memory_mb": 1024, "network_isolated": False, "timeout_seconds": 30})
    monkeypatch.setattr(ds, "docker_available", lambda *a, **k: True)
    sbx = _make_sandbox(settings, tmp_path)
    assert isinstance(sbx, ds.DockerSandbox) and sbx._memory_mb == 1024 and sbx._network is True and sbx._timeout == 30

    monkeypatch.setattr(ds, "docker_available", lambda *a, **k: False)
    with caplog.at_level("WARNING"):
        assert isinstance(_make_sandbox(settings, tmp_path), IsolatedSandbox)
    assert "does NOT isolate" in caplog.text

    assert isinstance(_make_sandbox(Settings(sandbox={"mode": "isolated"}), tmp_path), IsolatedSandbox)
