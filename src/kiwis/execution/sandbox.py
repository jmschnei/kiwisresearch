"""Abstract base for sandboxed code execution."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ExecutionStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass
class ExecutionResult:
    """Result of executing code in a sandbox."""
    status: ExecutionStatus
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    execution_time_seconds: float = 0.0
    artifacts: list[str] = field(default_factory=list)  # Generated file paths
    error_traceback: Optional[str] = None
    memory_used_mb: float = 0.0


@abc.abstractmethod
class CodeSandbox(abc.ABC):
    """Abstract sandbox environment for code execution."""

    @abc.abstractmethod
    async def initialize(self) -> None:
        """Prepare the sandbox (pull images, create envs, etc.)."""
        ...

    @abc.abstractmethod
    async def execute_python(
        self,
        code: str,
        filename: Optional[str] = "script.py",
        timeout: Optional[int] = None,
        extra_args: list[str] | None = None,
    ) -> ExecutionResult:
        """Execute Python code in the sandbox."""
        ...

    @abc.abstractmethod
    async def compile_latex(
        self,
        tex_content: str,
        filename: Optional[str] = "document.tex",
        timeout: Optional[int] = None,
    ) -> ExecutionResult:
        """Compile LaTeX source to PDF."""
        ...

    @abc.abstractmethod
    async def copy_to_sandbox(self, src_path: str, dest_path: str) -> bool:
        """Copy a file from host to sandbox."""
        ...

    @abc.abstractmethod
    async def copy_from_sandbox(self, src_path: str, dest_path: str) -> bool:
        """Copy a file from sandbox to host."""
        ...

    @abc.abstractmethod
    async def cleanup(self) -> None:
        """Release resources and tear down the sandbox."""
        ...
