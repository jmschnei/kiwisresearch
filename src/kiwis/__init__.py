"""
Kiwis Research - Multi-Agent Scientific Research Automation System

A modular system that orchestrates specialized AI agents through the complete
scientific research lifecycle: Hypothesis → Literature → Experiment → Analysis → Paper.
"""

__version__ = "0.1.0"
__author__ = "Kiwis Team"

from kiwis.config import Settings
from kiwis.models.base import LLMProvider, ModelConfig

__all__ = ["Settings", "LLMProvider", "ModelConfig"]
