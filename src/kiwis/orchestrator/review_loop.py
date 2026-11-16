"""Scoring and stop/continue decisions for the peer-review / revision loop."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

SEVERITY_PENALTY = {"fatal": 4, "major": 2, "minor": 1}
CATEGORIES = ["methodology", "novelty", "reproducibility", "writing", "ethics"]
KNOWN_VERDICTS = ("accept", "weak accept", "borderline", "reject")


def _weaknesses(review: dict) -> list[dict]:
    return [w for w in (review.get("weaknesses") or []) if isinstance(w, dict)]


def verdict_of(review: dict) -> str:
    return str(review.get("overall_verdict", "")).strip().lower()


def category_scores(review: dict) -> dict[str, int]:
    """Score per criterion: 10 minus severity penalties of the weaknesses filed under it."""
    weaknesses = _weaknesses(review)
    scores = {}
    for cat in CATEGORIES:
        penalty = sum(SEVERITY_PENALTY.get(w.get("severity"), 1) for w in weaknesses if w.get("category") == cat)
        scores[cat] = max(0, 10 - penalty)
    return scores


def overall_score(review: dict) -> float:
    """Mean criterion score on a 0-10 scale."""
    scores = category_scores(review)
    return round(sum(scores.values()) / len(scores), 2)


def is_actionable(review: dict) -> bool:
    """True if the review contains something the writer can act on (or a recognizable verdict).

    A placeholder or unparseable review (e.g. no LLM configured) is not actionable, so the loop stops
    instead of rewriting the paper against nothing.
    """
    return bool(
        _weaknesses(review)
        or review.get("required_changes")
        or any(verdict_of(review).startswith(v) for v in KNOWN_VERDICTS)
    )


def is_accepted(review: dict, threshold: Optional[float] = None) -> bool:
    """Accepted if the verdict says so (and nothing fatal is open) or the score reaches ``threshold`` (0-1)."""
    fatal = any(w.get("severity") == "fatal" for w in _weaknesses(review))
    verdict = verdict_of(review)
    verdict_ok = verdict.startswith(("accept", "weak accept")) and not fatal
    score_ok = threshold is not None and overall_score(review) / 10 >= threshold and not fatal
    return verdict_ok or score_ok


@dataclass
class ReviewDecision:
    revise: bool
    reason: str  # accepted | not_actionable | max_rounds | needs_revision
    score: float
    verdict: str


def decide(review: dict, round_no: int, max_rounds: int, threshold: Optional[float] = None) -> ReviewDecision:
    """Decide after review round ``round_no`` (1-based) whether the paper should be revised and re-reviewed."""
    score, verdict = overall_score(review), verdict_of(review) or "unknown"
    if not is_actionable(review):
        return ReviewDecision(False, "not_actionable", score, verdict)
    if is_accepted(review, threshold):
        return ReviewDecision(False, "accepted", score, verdict)
    if round_no >= max_rounds:
        return ReviewDecision(False, "max_rounds", score, verdict)
    return ReviewDecision(True, "needs_revision", score, verdict)


def round_summary(review: dict, round_no: int) -> dict:
    """Compact, JSON-friendly summary of one review round (used by the API and UI)."""
    weaknesses = _weaknesses(review)
    return {
        "round": round_no,
        "verdict": review.get("overall_verdict", "unknown"),
        "score": overall_score(review),
        "categoryScores": category_scores(review),
        "weaknesses": len(weaknesses),
        "fatal": sum(1 for w in weaknesses if w.get("severity") == "fatal"),
        "requiredChanges": [
            (c.get("description") if isinstance(c, dict) else str(c)) for c in (review.get("required_changes") or [])
        ],
        "rationale": review.get("decision_rationale", ""),
    }
