"""Docker-based isolated execution environment."""

from __future__ import annotations

import asyncio
from typing import Optional

from .sandbox import CodeSandbox, ExecutionResult, ExecutionStatus


class DockerSandbox(CodeSandbox):
    """Docker container sandbox for safe code execution.
    
    Creates an ephemeral Docker container per execution with:
    - Isolated filesystem
    - No network access (by default)
    - CPU/memory limits
    - Pre-installed scientific Python stack
    """

    DOCKERFILE = """
FROM python:3.11-slim
RUN pip install --no-cache-dir numpy pandas matplotlib seaborn scipy scikit-learn plotly
WORKDIR /workspace
"""

    def __init__(self, image_name: str = "kiwis-sandbox:latest", timeout: int = 600):
        self._image_name = image_name
        self._timeout = timeout
        self._docker_api = None

    async def initialize(self) -> None:
        """Build or pull the sandbox Docker image."""
        try:
            import docker
            client = docker.from_env()
            
            # Check if image exists
            images = client.images.list(name=self._image_name)
            if not images:
                # Build from Dockerfile
                import tempfile, os
                with tempfile.TemporaryDirectory() as td:
                    dockerfile_path = os.path.join(td, "Dockerfile")
                    with open(dockerfile_path, "w") as f:
                        f.write(self.DOCKERFILE.strip())
                    
                    _, build_logs = client.images.build(
                        path=td,
                        tag=self._image_name,
                        rm=True,
                    )
        except ImportError:
            self._docker_api = None  # Docker not available, fall back to isolated

    async def execute_python(
        self,
        code: str,
        filename: Optional[str] = "script.py",
        timeout: Optional[int] = None,
        extra_args: list[str] | None = None,
    ) -> ExecutionResult:
        """Execute Python code in a Docker container."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            import docker
            client = docker.from_env()
            
            # Write code to temp file
            import tempfile
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(code)
                code_path = f.name
            
            container = client.containers.run(
                self._image_name,
                command=f"python {code_path}",
                volumes={code_path: {"bind": f"/workspace/{filename}", "mode": "ro"}},
            working_dir="/workspace",
                network_disabled=True,
                mem_limit="4g",
                cpu_quota=80000,
                timeout=(timeout or self._timeout),
                remove=True,
            )
            
            exec_time = asyncio.get_event_loop().time() - start_time
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                stdout=container.decode("utf-8", errors="replace"),
                execution_time_seconds=exec_time,
            )
        except (ImportError, Exception) as e:
            exec_time = asyncio.get_event_loop().time() - start_time
            if isinstance(e, asyncio.TimeoutError):
                status = ExecutionStatus.TIMEOUT
            else:
                status = ExecutionStatus.ERROR
            
            return ExecutionResult(
                status=status,
                stderr=str(e),
                execution_time_seconds=exec_time,
                error_traceback=self._format_traceback(str(e)),
            )

    @staticmethod
    def _format_traceback(error: str) -> str:
        """Extract traceback-like formatting from Python errors."""
        if "Traceback (most recent call last):" in error:
            return error
        # Wrap simple errors
        lines = error.split("\n")
        if len(lines) > 0:
            return f"Traceback (most recent call last):\n  <exec>\n    File \"<script>\", line 1\n{lines[-1]}"
        return f"<error>: {error}"

    async def compile_latex(
        self,
        tex_content: str,
        filename: Optional[str] = "document.tex",
        timeout: Optional[int] = None,
    ) -> ExecutionResult:
        """Compile LaTeX to PDF inside Docker."""
        start_time = asyncio.get_event_loop().time()
        try:
            import docker
            client = docker.from_env()
            
            import tempfile, os
            with tempfile.TemporaryDirectory() as td:
                tex_path = os.path.join(td, filename)
                with open(tex_path, "w") as f:
                    f.write(tex_content)
                
                container = client.containers.run(
                    "latex/latexmk:latest",
                    command=f"latexmk -pdf -outdir=/output {filename}",
                    volumes={td: {"bind": "/input", "mode": "rw"}},
                    working_dir="/input",
                    mem_limit="2g",
                    timeout=(timeout or self._timeout),
                    remove=True,
                )
            
            exec_time = asyncio.get_event_loop().time() - start_time
            pdf_path = os.path.join(td, "output", "document.pdf")
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                stdout=container.decode("utf-8", errors="replace"),
                execution_time_seconds=exec_time,
                artifacts=[pdf_path],
            )
        except Exception as e:
            exec_time = asyncio.get_event_loop().time() - start_time
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                stderr=str(e),
                execution_time_seconds=exec_time,
                error_traceback=str(e),
            )

    async def copy_to_sandbox(self, src_path: str, dest_path: str) -> bool:
        return False  # Container-level copy not directly supported
    
    async def copy_from_sandbox(self, src_path: str, dest_path: str) -> bool:
        return False

    async def cleanup(self) -> None:
        pass
