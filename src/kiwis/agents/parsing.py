"""Tolerant extraction of the JSON object an agent asked the model for.

Large models follow "answer in a ```json block" reliably; small local models often don't: they return bare JSON,
put prose around it, use a ``` fence without a language, or wrap the answer in <think>...</think>. This helper
accepts all of those and returns the first JSON *object* found, or ``None``.
"""

from __future__ import annotations

import json
import re
from typing import Optional

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE = re.compile(r"```[a-zA-Z]*\s*\n(.*?)```", re.DOTALL)


def strip_thinking(text: str) -> str:
    """Remove <think>...</think> reasoning that some local models (deepseek-r1, qwen3) put before the answer."""
    return _THINK.sub("", text or "").strip()


def _first_object(text: str) -> Optional[dict]:
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text, i)
        except ValueError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def extract_json(text: str) -> Optional[dict]:
    """The JSON object in ``text``: from a fenced block if there is one that parses, else anywhere in the text."""
    text = strip_thinking(text)
    for block in _FENCE.findall(text):
        try:
            obj = json.loads(block)
        except ValueError:
            obj = _first_object(block)
        if isinstance(obj, dict):
            return obj
    return _first_object(text)
