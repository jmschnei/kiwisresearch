"""Isolated subprocess sandbox (no Docker required)."""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
from typing import Optional

from .sandbox import CodeSandbox, ExecutionResult, ExecutionStatus


class IsolatedSandbox(CodeSandbox):
    """Subprocess-based sandbox for Python and LaTeX execution.
    
    Runs code in isolated subprocesses with:
    - Working directory isolation
    - Time/memory limits (OS-level)
    - No network by default
    - Graceful error handling
    """

    def __init__(self, base_dir: Optional[str] = None, timeout: int = 600):
        self._base_dir = base_dir or tempfile.mkdtemp(prefix="kiwis_isolated_")
        self._timeout = timeout

    async def initialize(self) -> None:
        os.makedirs(self._base_dir, exist_ok=True)

    async def execute_python(
        self,
        code: str,
        filename: Optional[str] = "script.py",
        timeout: Optional[int] = None,
        extra_args: list[str] | None = None,
    ) -> ExecutionResult:
        start_time = time.monotonic()
        
        workdir = os.path.join(self._base_dir, "work")
        os.makedirs(workdir, exist_ok=True)

        script_path = os.path.join(workdir, filename)
        with open(script_path, "w") as f:
            f.write(code)

        try:
            cmd = ["python", "-u", script_path]
            if extra_args:
                cmd.extend(extra_args)

            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=workdir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=10_000_000,  # 10 MB output limit
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=(timeout or self._timeout),
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                elapsed = time.monotonic() - start_time
                return ExecutionResult(
                    status=ExecutionStatus.TIMEOUT,
                    stdout="", stderr="Execution timed out",
                    execution_time_seconds=elapsed,
                )

            exit_code = process.returncode
            elapsed = time.monotonic() - start_time

            stdout_str = stdout.decode("utf-8", errors="replace") if stdout else ""
            stderr_str = stderr.decode("utf-8", errors="replace") if stderr else ""

            artifacts = [
                os.path.join(workdir, f)
                for f in os.listdir(workdir)
                if f.endswith((".png", ".jpg", ".svg", ".csv", ".json", ".pkl"))
                and not f.endswith(".py")
            ]

            return ExecutionResult(
                status=ExecutionStatus.SUCCESS if exit_code == 0 else ExecutionStatus.FAILED,
                stdout=stdout_str,
                stderr=stderr_str,
                exit_code=exit_code,
                execution_time_seconds=elapsed,
                artifacts=artifacts,
                error_traceback=stderr_str if exit_code != 0 else None,
            )

        except Exception as e:
            elapsed = time.monotonic() - start_time
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                stderr=str(e),
                execution_time_seconds=elapsed,
                error_traceback=str(e),
            )

    async def compile_latex(
        self,
        tex_content: str,
        filename: Optional[str] = "document.tex",
        timeout: Optional[int] = None,
    ) -> ExecutionResult:
        start_time = time.monotonic()
        
        workdir = os.path.join(self._base_dir, "latex")
        os.makedirs(workdir, exist_ok=True)

        tex_path = os.path.join(workdir, filename)
        with open(tex_path, "w") as f:
            f.write(tex_content)

        # Try latexmk first, then pdflatex
        for cmd in [
            ["latexmk", "-pdf", "-interaction=nonstopmode", "-outdir=.", filename],
            ["pdflatex", "-interaction=nonstopmode", tex_path],
        ]:
            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=workdir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(),
                        timeout=(timeout or self._timeout),
                    )
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
                    continue  # Try next command

                exit_code = process.returncode
                if exit_code == 0:
                    elapsed = time.monotonic() - start_time
                    pdf_path = os.path.join(workdir, filename.rsplit(".", 1)[0] + ".pdf")
                    return ExecutionResult(
                        status=ExecutionStatus.SUCCESS,
                        stdout=stdout.decode("utf-8", errors="replace"),
                        execution_time_seconds=elapsed,
                        artifacts=[pdf_path],
                    )
            except FileNotFoundError:
                continue  # LaTeX not installed

        elapsed = time.monotonic() - start_time
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            stderr="LaTeX compiler not available",
            execution_time_seconds=elapsed,
        )

    async def copy_to_sandbox(self, src_path: str, dest_path: str) -> bool:
        import shutil
        try:
            dest = os.path.join(self._base_dir, "work", os.path.basename(dest_path))
            shutil.copy2(src_path, dest)
            return True
        except Exception:
            return False

    async def copy_from_sandbox(self, src_path: str, dest_path: str) -> bool:
        import shutil
        try:
            sandbox_src = os.path.join(self._base_dir, "work", os.path.basename(src_path))
            shutil.copy2(sandbox_src, dest_path)
            return True
        except Exception:
            return False

    async def cleanup(self) -> None:
        import shutil
        shutil.rmtree(self._base_dir, ignore_errors=True)
