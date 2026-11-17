"""DockerSandbox against a real Docker daemon (skipped when none is running).

Uses a tiny python:3.12-slim based image instead of the full scientific stack so the tests stay fast.
"""

import asyncio
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kiwis.execution.docker_sandbox import DockerSandbox, docker_available
from kiwis.execution.sandbox import ExecutionStatus

pytestmark = pytest.mark.skipif(not docker_available(), reason="no Docker daemon available")

TEST_IMAGE = "kiwis-sandbox-test:latest"
TEST_DOCKERFILE = "FROM python:3.12-slim\nWORKDIR /workspace\n"


def sandbox(tmp_path, **kw):
    return DockerSandbox(base_dir=str(tmp_path / "sbx"), image_name=TEST_IMAGE, dockerfile=TEST_DOCKERFILE, **kw)


def run(coro):
    return asyncio.run(coro)


def containers_left():
    import subprocess
    out = subprocess.run(["docker", "ps", "-a", "--filter", "name=kiwis-sbx-", "-q"], capture_output=True, text=True)
    return out.stdout.split()


def test_success_returns_stdout_and_artifacts(tmp_path):
    code = "import json\nprint('hello')\njson.dump({'acc': 0.9}, open('metrics.json', 'w'))\n"
    r = run(sandbox(tmp_path).execute_python(code, filename="experiment.py"))
    assert r.status == ExecutionStatus.SUCCESS and r.exit_code == 0 and "hello" in r.stdout
    assert [os.path.basename(a) for a in r.artifacts] == ["metrics.json"]
    assert '"acc"' in Path(r.artifacts[0]).read_text()  # the file was copied back to the host
    assert containers_left() == []


def test_python_error_is_failed_with_traceback_and_exit_code(tmp_path):
    r = run(sandbox(tmp_path).execute_python("print('before')\nraise ValueError('bad data')\n"))
    assert r.status == ExecutionStatus.FAILED and r.exit_code == 1
    assert "ValueError: bad data" in r.stderr and "ValueError" in r.error_traceback and "before" in r.stdout


def test_no_network_by_default(tmp_path):
    probe = ("import socket\ntry:\n    socket.create_connection(('1.1.1.1', 53), timeout=3)\n    print('online')\n"
             "except OSError:\n    print('offline')\n")
    assert "offline" in run(sandbox(tmp_path).execute_python(probe)).stdout


def test_timeout_kills_the_container(tmp_path):
    r = run(sandbox(tmp_path, timeout=3).execute_python("import time\ntime.sleep(60)\n"))
    assert r.status == ExecutionStatus.TIMEOUT and r.execution_time_seconds < 30
    assert containers_left() == []


def test_memory_limit_is_enforced(tmp_path):
    r = run(sandbox(tmp_path, memory_mb=64).execute_python("x = bytearray(512 * 1024 * 1024)\nprint(len(x))\n"))
    assert r.status == ExecutionStatus.FAILED and "memory limit" in r.stderr


def test_host_is_not_visible_and_files_are_staged(tmp_path):
    secret = tmp_path / "host_secret.txt"
    secret.write_text("top secret")
    sbx = sandbox(tmp_path)
    data = tmp_path / "data.csv"
    data.write_text("a,b\n1,2\n")
    assert run(sbx.copy_to_sandbox(str(data), "data.csv"))
    code = f"import os\nprint(open('data.csv').read().strip())\nprint(os.path.exists({str(secret)!r}))\n"
    r = run(sbx.execute_python(code))
    assert "a,b" in r.stdout and "False" in r.stdout  # staged data visible, host filesystem is not
    out = tmp_path / "copied.csv"
    assert run(sbx.copy_from_sandbox("data.csv", str(out))) and out.read_text().startswith("a,b")


def test_extra_args_and_missing_daemon_is_an_error_result(tmp_path, monkeypatch):
    r = run(sandbox(tmp_path).execute_python("import sys\nprint(sys.argv[1:])\n", extra_args=["--lr", "0.1"]))
    assert "['--lr', '0.1']" in r.stdout

    monkeypatch.setenv("PATH", "/nonexistent")  # no docker binary: a result, not an exception
    r = run(sandbox(tmp_path).execute_python("print(1)"))
    assert r.status == ExecutionStatus.ERROR
