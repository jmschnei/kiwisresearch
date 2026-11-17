"""Check that each cited reference supports the sentence that cites it.

``references.check_citations`` guarantees a cited paper *exists*. This module goes one step further with an
LLM acting as an independent judge: for every (claim sentence, cited reference) pair it reads the reference's
abstract and decides whether the abstract supports the claim.

Limits: the judge only sees the abstract (and title), so it cannot confirm details that live in the full text;
those come back as ``unverifiable`` rather than ``unsupported``. Verdicts are advisory: they are shown to the
reviewer and the writer, never used to delete text automatically.
"""

from __future__ import annotations

import json
import re
from typing import Awaitable, Callable, Optional

from .references import _CITE, _SENTENCE_SPLIT, extract_citations

VERDICTS = ("supported", "partial", "unsupported", "unverifiable")
MAX_CLAIMS = 30
BATCH_SIZE = 8

SYSTEM_PROMPT = """You are a meticulous citation checker for scientific papers. For each item you get a sentence
from a paper that cites a reference, plus that reference's title and abstract. Decide whether the abstract supports
what the sentence attributes to the reference.

Verdicts:
- supported: the abstract clearly states or directly implies the claim.
- partial: the abstract is related but supports only part of the claim, or the claim overstates it.
- unsupported: the abstract contradicts the claim or is about something different.
- unverifiable: the claim concerns details an abstract would not contain.

Judge only the part of the sentence that depends on the cited reference. Be strict, and do not use outside
knowledge about the paper. Answer ONLY with a JSON list: [{"id": <int>, "verdict": "<verdict>", "reason": "<one short sentence>"}]"""


def _plain(sentence: str) -> str:
    """Sentence without LaTeX cite commands, so the judge reads natural text."""
    return re.sub(r"\s+", " ", _CITE.sub("[REF]", sentence)).strip()


def extract_claims(paper: dict, references: list[dict]) -> list[dict]:
    """One claim per (sentence, cited key) for every citation of a known reference."""
    known = {r["key"] for r in references}
    claims: list[dict] = []
    texts = [("abstract", paper.get("abstract"))] + list((paper.get("sections") or {}).items())
    for where, text in texts:
        if not isinstance(text, str):
            continue
        for sentence in _SENTENCE_SPLIT.split(text):
            for key in extract_citations(sentence):
                if key in known:
                    claims.append({"key": key, "section": where, "sentence": _plain(sentence)})
    return claims


def _parse(text: str) -> list[dict]:
    match = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
    raw = match.group(1) if match else text
    try:
        data = json.loads(raw)
    except Exception:
        start, end = raw.find("["), raw.rfind("]")
        if start < 0 or end <= start:
            return []
        try:
            data = json.loads(raw[start:end + 1])
        except Exception:
            return []
    return [d for d in data if isinstance(d, dict)] if isinstance(data, list) else []


def _cache_key(claim: dict) -> str:
    return f"{claim['key']}|{claim['sentence']}"


async def verify_claims(
    claims: list[dict],
    references: list[dict],
    judge: Callable[[str, str], Awaitable[str]],
    cache: Optional[dict] = None,
    max_claims: int = MAX_CLAIMS,
) -> dict:
    """Judge ``claims`` and return ``{checked, supported, partial, unsupported, unverifiable, items}``.

    ``judge(system_prompt, user_prompt)`` returns the model's raw text. ``cache`` (claim -> verdict) lets later
    review rounds skip claims that were already judged and have not changed; it is updated in place.
    """
    cache = cache if cache is not None else {}
    by_key = {r["key"]: r for r in references}
    claims = claims[:max_claims]
    items: dict[str, dict] = {}
    todo: list[dict] = []
    for c in claims:
        k = _cache_key(c)
        if k in cache:
            items[k] = {**c, **cache[k]}
        elif not by_key[c["key"]].get("abstract"):
            items[k] = {**c, "verdict": "unverifiable", "reason": "The retrieved reference has no abstract."}
        else:
            todo.append(c)

    for i in range(0, len(todo), BATCH_SIZE):
        batch = todo[i:i + BATCH_SIZE]
        blocks = []
        for n, c in enumerate(batch):
            ref = by_key[c["key"]]
            blocks.append(f"[{n}]\nSentence: {c['sentence']}\nReference title: {ref['title']}\n"
                          f"Reference abstract: {ref['abstract'][:1200]}")
        try:
            verdicts = {d.get("id"): d for d in _parse(await judge(SYSTEM_PROMPT, "\n\n".join(blocks)))}
        except Exception:  # judge unavailable: leave the batch unjudged instead of failing the review
            verdicts = {}
        for n, c in enumerate(batch):
            d = verdicts.get(n) or {}
            verdict = d.get("verdict") if d.get("verdict") in VERDICTS else "unverifiable"
            result = {"verdict": verdict, "reason": str(d.get("reason") or "No judgement returned.")[:300]}
            if d.get("verdict") in VERDICTS:  # only real judgements are reused in later rounds
                cache[_cache_key(c)] = result
            items[_cache_key(c)] = {**c, **result}

    ordered = [items[_cache_key(c)] for c in claims]
    summary = {v: sum(1 for it in ordered if it["verdict"] == v) for v in VERDICTS}
    return {"checked": len(ordered), **summary, "items": ordered}


def format_problems(verification: Optional[dict], limit: int = 8) -> str:
    """Unsupported / partial claims as prompt text (empty when there is nothing to fix)."""
    if not verification:
        return ""
    bad = [it for it in verification.get("items", []) if it["verdict"] in ("unsupported", "partial")]
    bad.sort(key=lambda it: it["verdict"] != "unsupported")
    return "\n".join(f'- [{it["verdict"]}] ({it["section"]}, cites {it["key"]}) "{it["sentence"][:240]}" -> {it["reason"]}'
                     for it in bad[:limit])
