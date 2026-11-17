"""Docker-based isolated execution environment.

Talks to Docker through the ``docker`` CLI (no Python SDK needed) and never bind-mounts host paths: files are
copied in and out with ``docker create`` / ``docker cp`` / ``docker start -a``. That works the same with Docker
Desktop, Colima, remote daemons and when the API itself runs in a container.

Each run gets a throw-away container with no network (unless allowed), a memory limit, one CPU, a PID limit, all
Linux capabilities dropped and ``no-new-privileges``. It is removed afterwards, also on timeout or error.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import time
import uuid
from typing import Optional

from .sandbox import CodeSandbox, ExecutionResult, ExecutionStatus

MAX_OUTPUT_BYTES = 10_000_000
ARTIFACT_SUFFIXES = (".png", ".jpg", ".svg", ".csv", ".json", ".pkl", ".pdf")


def docker_available(timeout: float = 5.0) -> bool:
    """True if a Docker daemon answers (``docker info``)."""
    import subprocess
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=timeout).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


class DockerSandbox(CodeSandbox):
    """Run experiment code (and LaTeX) in ephemeral Docker containers."""

    DOCKERFILE = """FROM python:3.11-slim
RUN pip install --no-cache-dir numpy pandas matplotlib seaborn scipy scikit-learn plotly
WORKDIR /workspace
"""

    def __init__(
        self,
        base_dir: Optional[str] = None,
        timeout: int = 600,
        memory_mb: int = 4096,
        network: bool = False,
        image_name: str = "kiwis-sandbox:latest",
        dockerfile: Optional[str] = None,
        latex_image: str = "texlive/texlive:latest-small",
    ):
        self._base_dir = base_dir or tempfile.mkdtemp(prefix="kiwis_docker_")
        self._timeout = timeout
        self._memory_mb = memory_mb
        self._network = network
        self._image_name = image_name
        self._dockerfile = dockerfile or self.DOCKERFILE
        self._latex_image = latex_image
        self._image_ready = False
        self._build_lock: Optional[asyncio.Lock] = None

    # ------------------------------------------------------------------ docker plumbing
    @staticmethod
    async def _docker(*args: str, input: Optional[bytes] = None, timeout: Optional[float] = None) -> tuple[int, bytes, bytes]:
        """Run ``docker <args>``; kills the CLI on timeout (raises ``asyncio.TimeoutError``)."""
        proc = await asyncio.create_subprocess_exec(
            "docker", *args,
            stdin=asyncio.subprocess.PIPE if input is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, limit=MAX_OUTPUT_BYTES,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(input), timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise
        return proc.returncode or 0, out, err

    async def initialize(self) -> None:
        os.makedirs(os.path.join(self._base_dir, "work"), exist_ok=True)
        await self._ensure_image()

    async def _ensure_image(self) -> None:
        """Build the sandbox image once (kept for later runs)."""
        if self._image_ready:
            return
        if self._build_lock is None:
            self._build_lock = asyncio.Lock()
        async with self._build_lock:
            if self._image_ready:
                return
            rc, _, _ = await self._docker("image", "inspect", self._image_name, timeout=30)
            if rc != 0:
                rc, _, err = await self._docker("build", "-t", self._image_name, "-",
                                                input=self._dockerfile.encode(), timeout=1800)
                if rc != 0:
                    raise RuntimeError(f"Could not build sandbox image: {err.decode(errors='replace')[-500:]}")
            self._image_ready = True

    async def _run_container(self, image: str, command: list[str], workdir: str, timeout: int,
                             network: bool) -> ExecutionResult:
        """Copy ``workdir`` into a fresh container, run ``command`` there and copy the files back."""
        start = time.monotonic()
        name = f"kiwis-sbx-{uuid.uuid4().hex[:12]}"
        mem = f"{self._memory_mb}m"
        elapsed = lambda: time.monotonic() - start  # noqa: E731
        try:
            rc, _, err = await self._docker(
                "create", "--name", name, "--network", "bridge" if network else "none",
                "--memory", mem, "--memory-swap", mem, "--cpus", "1", "--pids-limit", "512",
                "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--tmpfs", "/tmp",
                "-w", "/workspace", image, *command, timeout=60)
            if rc != 0:
                return ExecutionResult(ExecutionStatus.ERROR, stderr=err.decode(errors="replace"),
                                       exit_code=rc, execution_time_seconds=elapsed(),
                                       error_traceback=err.decode(errors="replace"))
            rc, _, err = await self._docker("cp", f"{workdir}/.", f"{name}:/workspace", timeout=120)
            if rc != 0:
                return ExecutionResult(ExecutionStatus.ERROR, stderr=f"docker cp failed: {err.decode(errors='replace')}",
                                       execution_time_seconds=elapsed())
            try:
                _, out, err = await self._docker("start", "-a", name, timeout=timeout)
            except asyncio.TimeoutError:
                await self._docker("kill", name, timeout=30)
                return ExecutionResult(ExecutionStatus.TIMEOUT, stderr=f"Execution timed out after {timeout}s",
                                       execution_time_seconds=elapsed())

            _, info, _ = await self._docker("inspect", "-f", "{{.State.ExitCode}} {{.State.OOMKilled}}", name, timeout=30)
            code_text, _, oom_text = info.decode().strip().partition(" ")
            exit_code = int(code_text) if code_text.lstrip("-").isdigit() else 1
            await self._docker("cp", f"{name}:/workspace/.", workdir, timeout=120)  # results back to the host

            stderr = err.decode(errors="replace")
            if oom_text == "true":
                stderr += f"\nKilled: the container exceeded its {self._memory_mb} MB memory limit."
            artifacts = [os.path.join(workdir, f) for f in sorted(os.listdir(workdir)) if f.endswith(ARTIFACT_SUFFIXES)]
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS if exit_code == 0 else ExecutionStatus.FAILED,
                stdout=out.decode(errors="replace"), stderr=stderr, exit_code=exit_code,
                execution_time_seconds=elapsed(), artifacts=artifacts,
                error_traceback=stderr if exit_code != 0 else None,
            )
        except Exception as e:  # docker missing, daemon down, ...
            return ExecutionResult(ExecutionStatus.ERROR, stderr=str(e), execution_time_seconds=elapsed(),
                                   error_traceback=str(e))
        finally:
            try:
                await self._docker("rm", "-f", name, timeout=30)
            except Exception:
                pass

    # ------------------------------------------------------------------ CodeSandbox API
    async def execute_python(
        self,
        code: str,
        filename: Optional[str] = "script.py",
        timeout: Optional[int] = None,
        extra_args: list[str] | None = None,
    ) -> ExecutionResult:
        filename = os.path.basename(filename or "script.py")
        workdir = os.path.join(self._base_dir, "work")
        os.makedirs(workdir, exist_ok=True)
        with open(os.path.join(workdir, filename), "w") as f:
            f.write(code)
        try:
            await self._ensure_image()
        except Exception as e:
            return ExecutionResult(ExecutionStatus.ERROR, stderr=str(e), error_traceback=str(e))
        return await self._run_container(self._image_name, ["python", "-u", filename, *(extra_args or [])],
                                         workdir, timeout or self._timeout, self._network)

    async def compile_latex(
        self,
        tex_content: str,
        filename: Optional[str] = "document.tex",
        timeout: Optional[int] = None,
    ) -> ExecutionResult:
        filename = os.path.basename(filename or "document.tex")
        workdir = os.path.join(self._base_dir, "latex")
        os.makedirs(workdir, exist_ok=True)
        with open(os.path.join(workdir, filename), "w") as f:
            f.write(tex_content)
        result = await self._run_container(
            self._latex_image, ["latexmk", "-pdf", "-interaction=nonstopmode", filename],
            workdir, timeout or self._timeout, network=False)
        pdf = os.path.join(workdir, filename.rsplit(".", 1)[0] + ".pdf")
        if result.status == ExecutionStatus.SUCCESS and not os.path.exists(pdf):
            result.status = ExecutionStatus.FAILED
        result.artifacts = [pdf] if os.path.exists(pdf) else []
        return result

    async def copy_to_sandbox(self, src_path: str, dest_path: str) -> bool:
        """Stage a host file; it is copied into the container on the next run."""
        try:
            workdir = os.path.join(self._base_dir, "work")
            os.makedirs(workdir, exist_ok=True)
            shutil.copy2(src_path, os.path.join(workdir, os.path.basename(dest_path)))
            return True
        except OSError:
            return False

    async def copy_from_sandbox(self, src_path: str, dest_path: str) -> bool:
        """Fetch a file produced by an earlier run (results are copied back to the host after each run)."""
        try:
            shutil.copy2(os.path.join(self._base_dir, "work", os.path.basename(src_path)), dest_path)
            return True
        except OSError:
            return False

    async def cleanup(self) -> None:
        shutil.rmtree(self._base_dir, ignore_errors=True)
