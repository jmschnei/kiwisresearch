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
    """The largest JSON object embedded in ``text`` (not merely the first: when the outer object is broken, the first
    one that parses is usually a nested fragment such as a table)."""
    decoder = json.JSONDecoder(strict=False)
    best, best_len, i = None, 0, 0
    while i < len(text):
        if text[i] != "{":
            i += 1
            continue
        try:
            obj, end = decoder.raw_decode(text, i)
        except ValueError:
            i += 1
            continue
        if isinstance(obj, dict) and end - i > best_len:
            best, best_len = obj, end - i
        i = end
    return best


_TEXT_KEYS = ("text", "content", "body", "paragraph", "paragraphs")


def as_text(value) -> str:
    """Flatten a value that should have been a string. Small models write ``{"text": "..."}`` or a list of
    paragraphs where the schema asked for plain text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in _TEXT_KEYS:
            if key in value:
                return as_text(value[key])
        return "\n\n".join(as_text(v) for v in value.values() if as_text(v))
    if isinstance(value, (list, tuple)):
        return "\n\n".join(t for t in (as_text(v) for v in value) if t)
    return str(value)


def normalize_paper(paper: dict) -> dict:
    """Title, abstract and every section as plain strings (in place; also returned)."""
    paper["title"] = as_text(paper.get("title")).strip() or "Untitled"
    paper["abstract"] = as_text(paper.get("abstract"))
    sections = paper.get("sections")
    if isinstance(sections, list):  # [{"title"/"name": ..., "text": ...}, ...]
        sections = {as_text(s.get("title") or s.get("name") or f"section_{i}").lower().replace(" ", "_"): s
                    for i, s in enumerate(sections) if isinstance(s, dict)}
    paper["sections"] = {str(k): _section_text(v) for k, v in sections.items()} if isinstance(sections, dict) else {}
    return paper


_CITE_KEYS = re.compile(r"\\cite[tp]?\{([^}]*)\}")
MAX_LISTED_CITATIONS = 4


def _section_text(value) -> str:
    """Section text; citations a model listed separately (``{"text": ..., "references": ["\\cite{a}", ...]}``) are
    appended as one \\cite so they are not lost (unknown keys are removed later by the citation check)."""
    text = as_text(value)
    if isinstance(value, dict):
        listed = value.get("references") or value.get("citations") or []
        keys = []
        for item in listed if isinstance(listed, list) else []:
            found = _CITE_KEYS.findall(item) if isinstance(item, str) else []
            for group in (found or ([item] if isinstance(item, str) and re.fullmatch(r"[\w:.-]+", item) else [])):
                keys += [k.strip() for k in group.split(",") if k.strip() and k.strip() not in keys and k.strip() not in text]
        if 0 < len(keys) <= MAX_LISTED_CITATIONS:  # a long list is the whole bibliography pasted, not a citation
            text = text.rstrip() + " \\cite{" + ",".join(keys) + "}"
    return text


# LaTeX inside JSON strings: models write "\cite{x}" where JSON needs "\\cite{x}". Commands whose first letter is not
# a JSON escape are always invalid; those starting with b/f/n/r/t/u would silently decode as control characters, so
# the common ones are listed.
_BAD_ESCAPE = re.compile(r'(?<!\\)((?:\\\\)*)\\(?=[^"\\/bfnrtu]|(?:begin|beta|bar|bm|bf|boldsymbol|bigl?|bigr?|frac|footnote'
                         r'|forall|nabla|neq|nu|noindent|newline|right|rho|rangle|ref|tau|theta|textbf|textit|texttt|text'
                         r'|times|tilde|top|to|tabular|url|underline|usepackage)\b)')


def _repair_latex_escapes(text: str) -> str:
    return _BAD_ESCAPE.sub(lambda m: m.group(1) + "\\\\", text)


_TRAILING_COMMA = re.compile(r",(\s*[\]}])")
# a value followed on the next line by another key with no comma in between: "a": "x"\n "b": ...
_MISSING_COMMA = re.compile(r'("|\d|true|false|null|[\]}])(\s*\n\s*)(?="[^"\n]+"\s*:)')


def _parse_object(text: str) -> Optional[dict]:
    """The whole text as a JSON object (repairing LaTeX escapes and trailing commas if needed), else the first
    object inside it."""
    no_commas = _MISSING_COMMA.sub(r"\1,\2", _TRAILING_COMMA.sub(r"\1", text))
    for candidate in (text, _repair_latex_escapes(text), no_commas, _repair_latex_escapes(no_commas)):
        try:
            obj = json.loads(candidate, strict=False)  # tolerate raw newlines/tabs inside strings
        except ValueError:
            continue
        if isinstance(obj, dict):
            return obj
    return _first_object(text) or _first_object(_repair_latex_escapes(text))


def extract_json(text: str) -> Optional[dict]:
    """The JSON object in ``text``: from a fenced block if there is one that parses, else anywhere in the text."""
    text = strip_thinking(text)
    for block in _FENCE.findall(text):
        obj = _parse_object(block)
        if isinstance(obj, dict):
            return obj
    stripped = text.strip()
    if stripped.startswith("{"):
        obj = _parse_object(stripped)
        if obj is not None:
            return obj
    return _first_object(text) or _first_object(_repair_latex_escapes(text))


REFORMAT_PROMPT = ("Your answer did not contain the JSON object required by the instructions. Rewrite the SAME content "
                   "as that JSON object, with exactly the keys of the required format. Reply with ONLY the JSON in a "
                   "```json block: no prose, no Markdown headings.")


async def chat_json(llm, messages: list, config, required: tuple = ()) -> tuple[str, Optional[dict]]:
    """Chat and extract the JSON object; if there is none (a model answering in Markdown, for example) or it lacks a
    ``required`` key, ask the model once to convert its own answer. Returns ``(raw reply text, parsed object or None)``;
    the first parse is kept if the retry is not better."""
    from ..models.base import ChatMessage

    def complete(d):
        return d is not None and all(k in d for k in required)

    text = (await llm.chat(messages, config)).content
    data = extract_json(text)
    if not complete(data) and strip_thinking(text):
        retry = list(messages) + [ChatMessage(role="assistant", content=text), ChatMessage(role="user", content=REFORMAT_PROMPT)]
        again = extract_json((await llm.chat(retry, config)).content)
        if complete(again) or data is None:
            data = again
    return text, data


_CODE_FENCE = re.compile(r"```([a-zA-Z0-9_+-]*)[ \t]*\n(.*?)```", re.DOTALL)


def extract_code(text: str) -> Optional[str]:
    """Python source from a reply: the longest ```python (or unlabelled) block, else the ``code`` field of a JSON
    answer, else an unterminated ```python block (reply cut by the token limit is still better than nothing)."""
    text = strip_thinking(text)
    blocks = [body for lang, body in _CODE_FENCE.findall(text) if lang.lower() in ("python", "py", "python3", "")]
    blocks = [b for b in blocks if not b.lstrip().startswith(("{", "["))]  # unlabelled JSON is not code
    if blocks:
        return max(blocks, key=len)
    data = extract_json(text)
    if data and isinstance(data.get("code"), str) and data["code"].strip():
        return data["code"]
    match = re.search(r"```(?:python|py)[ \t]*\n(.*)", text, re.DOTALL)
    return match.group(1) if match else None
