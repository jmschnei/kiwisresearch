"""Build the configured code sandbox."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def make_sandbox(settings, output_dir: Path):
    """Sandbox for generated experiment code, as configured in ``settings.sandbox`` (``docker`` or ``isolated``)."""
    from .isolated_sandbox import IsolatedSandbox

    if settings.sandbox.mode == "docker":
        from .docker_sandbox import DockerSandbox, docker_available
        if docker_available():
            return DockerSandbox(base_dir=str(output_dir / "sandbox"), timeout=settings.sandbox.timeout_seconds,
                                 memory_mb=settings.sandbox.memory_mb, network=not settings.sandbox.network_isolated)
        logger.warning("Sandbox mode is 'docker' but no Docker daemon answers; falling back to the isolated "
                       "subprocess sandbox, which does NOT isolate network or filesystem")
    return IsolatedSandbox(base_dir=str(output_dir / "sandbox"), timeout=settings.sandbox.timeout_seconds,
                           network=not settings.sandbox.network_isolated)
