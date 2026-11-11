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
