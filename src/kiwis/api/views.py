"""Serialization of backend state into the dashboard's DTO shapes."""

from __future__ import annotations

import os
import time
from collections import defaultdict
from datetime import datetime, timezone

from .catalog import PHASE_TABLE, ROLE_TO_UI_AGENT, UI_AGENTS
from ..orchestrator.review_loop import category_scores, round_summary, verdict_of
from .events import now_iso
from .jobs import Job, JobManager, format_elapsed, format_tokens

VERDICT_TO_CONSENSUS = {"accept": "accepted", "weak accept": "weak_accept", "borderline": "borderline",
                        "reject": "rejected"}
REVIEW_CATEGORIES = [
    ("methodology", "Metodología", "#3b82f6"),
    ("novelty", "Novedad", "#a855f7"),
    ("reproducibility", "Reproducibilidad", "#10b981"),
    ("writing", "Escritura", "#f97316"),
    ("ethics", "Ética", "#ef4444"),
]


def pipeline_view(job: Job) -> dict:
    req = job.request
    return {
        "id": job.id, "name": req.title, "description": req.hypothesis or req.title,
        "status": job.status, "progress": job.progress, "type": req.type, "domain": req.domain,
        "tokensUsed": format_tokens(job.tracker.total_tokens),
        "elapsedTime": format_elapsed(job.elapsed_seconds),
        "budgetUsd": job.budget_usd, "spentUsd": round(job.tracker.total_cost, 4),
        "agents": [{"agentId": a[0], "active": True, "priority": i} for i, a in enumerate(UI_AGENTS)],
        "createdAt": job.created_at, "updatedAt": job.updated_at,
        "error": job.error,
        "revising": job.revising,
        "reviewRound": job.review_round,
        "reviewMax": job.review_max,
    }


def agents_view(manager: JobManager) -> list[dict]:
    """Current state of each dashboard agent, aggregated across all pipelines."""
    status: dict[str, str] = defaultdict(lambda: "idle")
    errors: dict[str, int] = defaultdict(int)
    tokens: dict[str, int] = defaultdict(int)
    cost: dict[str, float] = defaultdict(float)
    for job in manager.jobs.values():
        for i, step in enumerate(job.steps):
            _, role, _, ui_id, running = PHASE_TABLE[i]
            if step["status"] == "progress":
                status[ui_id] = running
            elif step["status"] == "waiting" and job.status == "active" and status[ui_id] == "idle":
                status[ui_id] = "waiting"
            elif step["status"] == "failed":
                errors[ui_id] += 1
        if job.revising:  # writer is rewriting the paper after a review round
            status["latex"] = "executing"
            if status["revisor"] == "reviewing":
                status["revisor"] = "waiting"
        for role, usage in job.tracker.by_agent().items():
            ui_id = ROLE_TO_UI_AGENT.get(role)
            if ui_id:
                tokens[ui_id] += usage["tokens"]
                cost[ui_id] += usage["costUsd"]
    now = now_iso()
    return [{
        "id": id_, "name": name, "icon": icon, "color": color, "status": status[id_],
        "metadata": {"tokensUsed": tokens[id_], "costUsd": round(cost[id_], 4), "startTime": now,
                     "lastActivity": now, "outputItems": 0, "errorCount": errors[id_],
                     "isHealthy": errors[id_] == 0},
    } for id_, name, icon, color in UI_AGENTS]


def health_view(manager: JobManager) -> dict:
    agents = agents_view(manager)
    return {
        "totalAgents": len(agents),
        "activeAgents": sum(1 for a in agents if a["status"] not in ("idle", "waiting")),
        "healthyAgents": sum(1 for a in agents if a["metadata"]["isHealthy"]),
        "unhealthyAgents": sum(1 for a in agents if not a["metadata"]["isHealthy"]),
        "lastHeartbeat": now_iso(),
    }


def cost_view(manager: JobManager, pipeline_id: str | None) -> dict:
    jobs = [manager.get(pipeline_id)] if pipeline_id else list(manager.jobs.values())
    uptime = jobs[0].elapsed_seconds if pipeline_id and jobs else time.monotonic() - manager.started_at
    return {
        "tokensUsed": sum(j.tracker.total_tokens for j in jobs),
        "costUsd": f"{sum(j.tracker.total_cost for j in jobs):.4f}",
        "uptime": format_elapsed(uptime), "snapshotAt": now_iso(),
        "estimated": True,
    }


def cost_history(job: Job) -> list[dict]:
    days: dict[str, dict] = {}
    for r in job.tracker.records:
        day = datetime.fromtimestamp(r.timestamp, timezone.utc).date().isoformat()
        d = days.setdefault(day, {"date": day, "tokens": 0, "cost": 0.0})
        d["tokens"] += r.total_tokens
        d["cost"] += r.cost_usd
    return [{"date": d["date"], "tokens": d["tokens"], "costUsd": f"{d['cost']:.4f}"} for _, d in sorted(days.items())]


def cost_breakdown(job: Job) -> dict:
    return {ROLE_TO_UI_AGENT.get(role, role): {"tokens": u["tokens"], "costUsd": f"{u['costUsd']:.4f}"}
            for role, u in job.tracker.by_agent().items()}


def paper_view(manager: JobManager, job: Job) -> dict | None:
    state = job.state
    if not state.paper_draft:
        return None
    content = state.paper_draft.get("content", {}) or {}
    review = review_view(job)
    pdf = (job.output_dir / "paper.pdf")
    return {
        "title": content.get("title", "Untitled"),
        "authors": ["Kiwis Research System"],
        "abstract": (content.get("sections", {}) or {}).get("abstract") or content.get("abstract", ""),
        "pdfUrl": f"/api/v1/results/{job.id}/artifacts/paper.pdf/download" if pdf.exists() else None,
        "metrics": review["metrics"],
        "overallScore": round(sum(m["score"] for m in review["metrics"]) / len(review["metrics"]), 1)
        if review["metrics"] else 0,
        "reviewConsensus": review["consensus"],
        "artifacts": manager.list_artifacts(job),
        "versions": job.state.paper_history,
        "revisionNotes": content.get("revision_notes", []),
    }


def review_view(job: Job) -> dict:
    """Peer-review scores of the latest round plus the history of all rounds."""
    reviews = [r for r in job.state.review_feedback if isinstance(r, dict)]
    feedback = reviews[-1] if reviews else {}
    metrics = []
    if feedback:
        weaknesses = [w for w in feedback.get("weaknesses", []) if isinstance(w, dict)]
        scores = category_scores(feedback)
        for key, label, color in REVIEW_CATEGORIES:
            related = [w for w in weaknesses if w.get("category") == key]
            metrics.append({"name": label, "score": scores[key], "maxScore": 10, "color": color,
                            "description": "; ".join(w.get("description", "") for w in related)[:300]
                            or "Sin objeciones"})
    verdict = verdict_of(feedback)
    return {
        "metrics": metrics,
        "consensus": VERDICT_TO_CONSENSUS.get(verdict, "borderline"),
        "rounds": [round_summary(r, i + 1) for i, r in enumerate(reviews)],
        "revisionRound": job.state.revision_round,
    }


def config_view(settings) -> dict:
    """Effective (non-secret) configuration: agents, provider availability, sandbox and memory."""
    from ..models.factory import infer_provider_name

    providers = {}
    for name, cfg in settings.providers.providers.items():
        env = cfg.api_key_env_var
        providers[name] = {
            "name": cfg.name, "type": cfg.provider_type.value, "defaultModel": cfg.default_model,
            "baseUrl": cfg.base_url, "models": cfg.supported_models,
            # Only report whether a key is present, never its value
            "available": True if env is None else bool(os.environ.get(env)),
            "apiKeyEnvVar": env,
        }
    agents = {}
    for role in type(settings.agents).model_fields:
        a = getattr(settings.agents, role)
        agents[role] = {"model": a.model, "provider": a.provider or infer_provider_name(a.model),
                        "temperature": a.temperature, "maxTokens": a.max_tokens, "enabled": a.enabled}
    return {
        "project": settings.project_name,
        "agents": agents,
        "providers": providers,
        "sandbox": settings.sandbox.model_dump(),
        "memory": settings.memory.model_dump(),
        "pipeline": settings.pipeline.model_dump(),
    }
