"""Pipeline job management: runs research pipelines in the background and tracks their progress."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from ..config.settings import Settings
from ..models.usage import UsageRecord, UsageTracker
from ..orchestrator.pipeline import PipelinePhase, PipelineState, ResearchPipeline
from .catalog import PHASE_INDEX, PHASE_TABLE, ROLE_TO_UI_AGENT, UI_AGENT_BY_ID
from .events import EventBus, now_iso
from .schemas import CreateResearchRequest

logger = logging.getLogger(__name__)

# (settings, tracker, output_dir) -> ResearchPipeline. Replaceable for tests.
PipelineBuilder = Callable[[Settings, UsageTracker, Path], ResearchPipeline]

ARTIFACT_SUFFIXES = {".pdf", ".png", ".svg", ".csv", ".json", ".md", ".tex", ".py"}


def default_pipeline_builder(settings: Settings, tracker: UsageTracker, output_dir: Path) -> ResearchPipeline:
    from ..orchestrator.agent_factory import AgentFactory

    sandbox = _make_sandbox(settings, output_dir)
    factory = AgentFactory(settings, sandbox=sandbox, usage_tracker=tracker, output_dir=output_dir)
    return ResearchPipeline(settings=settings, agent_factory=factory.create, sandbox=sandbox).build_default_pipeline()


def _make_sandbox(settings: Settings, output_dir: Path):
    from ..execution.isolated_sandbox import IsolatedSandbox

    if settings.sandbox.mode == "docker":
        try:
            import docker
            docker.from_env().ping()
            from ..execution.docker_sandbox import DockerSandbox
            return DockerSandbox(timeout=settings.sandbox.timeout_seconds)
        except Exception as e:
            logger.warning(f"Docker sandbox unavailable ({e}); using isolated subprocess sandbox")
    return IsolatedSandbox(base_dir=str(output_dir / "sandbox"), timeout=settings.sandbox.timeout_seconds)


def format_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


def format_elapsed(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


@dataclass
class Job:
    id: str
    request: CreateResearchRequest
    tracker: UsageTracker
    output_dir: Path
    # Built eagerly for new jobs; lazily (on first use) for jobs restored from disk.
    pipeline: Optional[ResearchPipeline] = None
    restored_state: Optional[PipelineState] = None
    status: str = "active"  # active | paused | completed | failed
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    started: float = field(default_factory=time.monotonic)
    finished: Optional[float] = None
    error: Optional[str] = None
    task: Optional[asyncio.Task] = None
    steps: list[dict] = field(default_factory=list)
    logs: list[dict] = field(default_factory=list)
    budget_usd: float = 0.0

    @property
    def state(self) -> PipelineState:
        if self.pipeline is not None:
            return self.pipeline.state
        return self.restored_state or PipelineState()

    @property
    def elapsed_seconds(self) -> float:
        return (self.finished or time.monotonic()) - self.started

    @property
    def progress(self) -> int:
        done = sum(1 for s in self.steps if s["status"] == "done")
        return round(100 * done / len(self.steps)) if self.steps else 0

    def running_agent_ids(self) -> list[str]:
        return [PHASE_TABLE[i][3] for i, s in enumerate(self.steps) if s["status"] == "progress"]


class JobManager:
    def __init__(self, settings: Settings, bus: EventBus, builder: Optional[PipelineBuilder] = None,
                 base_dir: Optional[Path] = None):
        self.settings = settings
        self.bus = bus
        self._builder = builder or default_pipeline_builder
        self._base_dir = Path(base_dir) if base_dir else Path(settings.paths.output) / "jobs"
        self.jobs: dict[str, Job] = {}
        self.started_at = time.monotonic()

    # ------------------------------------------------------------------ lifecycle
    def create(self, req: CreateResearchRequest) -> Job:
        job_id = "p-" + uuid.uuid4().hex[:8]
        output_dir = self._base_dir / job_id
        output_dir.mkdir(parents=True, exist_ok=True)

        tracker = UsageTracker(on_record=lambda rec, jid=job_id: self._on_usage(jid, rec))
        job = Job(id=job_id, request=req, tracker=tracker, output_dir=output_dir,
                  budget_usd=req.budgetUsd,
                  steps=[{"num": i + 1, "name": row[2], "agent": UI_AGENT_BY_ID[row[3]][1], "status": "waiting",
                          "justification": "", "codeSnippet": "", "artifacts": []}
                         for i, row in enumerate(PHASE_TABLE)])
        self._ensure_pipeline(job)
        self.jobs[job_id] = job
        self._persist(job)
        job.task = asyncio.create_task(self._run(job))
        self._log(job, "Sistema", "pipeline", f"Investigación '{req.title}' iniciada", "info")
        return job

    def _ensure_pipeline(self, job: Job) -> ResearchPipeline:
        """Build the job's pipeline if needed (restored jobs), resuming from the saved state."""
        if job.pipeline is None:
            pipeline = self._builder(self._settings_for(job.request), job.tracker, job.output_dir)
            if job.restored_state is not None:
                pipeline._state = job.restored_state
            job.pipeline = pipeline
        if not getattr(job, "_listening", False):
            job.pipeline.add_listener(lambda ev, j=job: self._on_pipeline_event(j, ev))
            job._listening = True  # type: ignore[attr-defined]
        return job.pipeline

    # ------------------------------------------------------------------ persistence
    def load(self) -> int:
        """Restore persisted jobs from disk. Jobs that were running when the server stopped are marked failed."""
        loaded = 0
        for meta_path in sorted(self._base_dir.glob("p-*/job.json")):
            try:
                self._restore(meta_path)
                loaded += 1
            except Exception:
                logger.exception("Could not restore job from %s", meta_path)
        return loaded

    def _restore(self, meta_path: Path) -> None:
        meta = json.loads(meta_path.read_text())
        job_id = meta["id"]
        d = meta_path.parent
        tracker = UsageTracker(on_record=lambda rec, jid=job_id: self._on_usage(jid, rec))
        tracker.records = [UsageRecord(**r) for r in meta.get("usage", [])]
        state = None
        state_path = d / "state.json"
        if state_path.exists():
            state = PipelineState.from_dict(json.loads(state_path.read_text()))
        elapsed = float(meta.get("elapsed", 0))
        now = time.monotonic()
        job = Job(
            id=job_id, request=CreateResearchRequest(**meta["request"]), tracker=tracker, output_dir=d,
            restored_state=state, status=meta["status"], created_at=meta["createdAt"], updated_at=meta["updatedAt"],
            started=now - elapsed, finished=now, error=meta.get("error"), steps=meta["steps"], logs=meta.get("logs", []),
            budget_usd=meta.get("budgetUsd", 0.0),
        )
        if job.status in ("active", "paused"):
            job.status = "failed"
            job.error = "El servidor se reinició durante la ejecución; puedes re-ejecutar los pasos pendientes."
            for step in job.steps:
                if step["status"] == "progress":
                    step.update(status="failed", justification="Interrumpido por el reinicio del servidor")
            self._log(job, "Sistema", "pipeline", job.error, "warning")
            self._persist(job)
        self.jobs[job_id] = job

    def _persist(self, job: Job) -> None:
        """Write job.json (metadata, steps, logs, usage) and the artifacts. Never raises."""
        try:
            meta = {
                "version": 1, "id": job.id, "request": job.request.model_dump(), "status": job.status,
                "createdAt": job.created_at, "updatedAt": job.updated_at, "elapsed": job.elapsed_seconds,
                "error": job.error, "budgetUsd": job.budget_usd, "steps": job.steps, "logs": job.logs,
                "usage": [asdict(r) for r in job.tracker.records],
            }
            self._write_json(job.output_dir / "job.json", meta)
            self._save_artifacts(job)
        except Exception:
            logger.exception("Failed to persist job %s", job.id)

    @staticmethod
    def _write_json(path: Path, data) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, default=str, ensure_ascii=False))
        os.replace(tmp, path)  # atomic: a crash never leaves a half-written file

    def _settings_for(self, req: CreateResearchRequest) -> Settings:
        """Per-job copy of the settings with the request's model/token overrides applied."""
        s = self.settings.model_copy(deep=True)
        for name in type(s.agents).model_fields:
            cfg = getattr(s.agents, name)
            if req.model and req.model.lower() not in ("auto", "default"):
                cfg.model = req.model
                cfg.provider = None  # re-infer from the new model name
            if req.maxTokensPerIteration:
                cfg.max_tokens = min(cfg.max_tokens, max(256, req.maxTokensPerIteration))
        return s

    async def _run(self, job: Job) -> None:
        try:
            await job.pipeline.run(job.request.title, hypothesis=job.request.hypothesis)
            job.status = "completed"
            self._log(job, "Sistema", "pipeline", "Investigación completada", "success")
        except asyncio.CancelledError:
            job.status = "failed"
            job.error = job.error or "Cancelled"
            raise
        except Exception as e:
            job.status = "failed"
            job.error = job.error or str(e)
            self._log(job, "Sistema", "pipeline", f"Pipeline fallido: {e}", "error")
        finally:
            job.finished = time.monotonic()
            self._publish_pipeline_update(job)
            await asyncio.to_thread(self._persist, job)

    async def delete(self, job_id: str) -> None:
        job = self.get(job_id)
        if job.task and not job.task.done():
            job.task.cancel()
            await asyncio.gather(job.task, return_exceptions=True)
        del self.jobs[job_id]
        base = self._base_dir.resolve()
        if job.output_dir.resolve().parent == base:  # only ever remove a direct child of the jobs dir
            await asyncio.to_thread(shutil.rmtree, job.output_dir, True)

    def set_status(self, job_id: str, status: str, reason: Optional[str] = None) -> Job:
        job = self.get(job_id)
        if job.status in ("completed", "failed"):
            raise ValueError(f"Pipeline already {job.status}")
        if status == "paused":
            job.pipeline.pause()
            job.status = "paused"
        elif status == "active":
            job.pipeline.resume()
            job.status = "active"
        elif status == "failed":  # stop
            job.error = reason or "Stopped by user"
            if job.task:
                job.task.cancel()
        else:
            raise ValueError(f"Cannot set status '{status}'")
        self._log(job, "Sistema", "pipeline", f"Estado → {status}" + (f" ({reason})" if reason else ""), "info")
        self._publish_pipeline_update(job)
        return job

    def reexecute(self, job_id: str, step_num: int, cascade: bool = False) -> str:
        job = self.get(job_id)
        if job.status == "active" or (job.task and not job.task.done()):
            raise ValueError("Pipeline is still running; pause or wait for it to finish")
        if not 1 <= step_num <= len(PHASE_TABLE):
            raise KeyError(f"Unknown step {step_num}")
        phases = [row[0] for row in PHASE_TABLE[step_num - 1:]] if cascade else [PHASE_TABLE[step_num - 1][0]]
        log_id = uuid.uuid4().hex[:8]
        job.status = "active"
        job.finished = None
        job.error = None

        async def run():
            try:
                pipeline = self._ensure_pipeline(job)
                for phase in phases:
                    await pipeline.rerun_phase(phase)
                job.status = "completed" if all(s["status"] == "done" for s in job.steps) else "failed"
            except Exception as e:
                job.status, job.error = "failed", str(e)
            finally:
                job.finished = time.monotonic()
                self._publish_pipeline_update(job)
                await asyncio.to_thread(self._persist, job)

        job.task = asyncio.create_task(run())
        self._log(job, "Sistema", "pipeline", f"{'Continuando desde' if cascade else 'Re-ejecutando'} el paso {step_num}", "info")
        return log_id

    def get(self, job_id: str) -> Job:
        try:
            return self.jobs[job_id]
        except KeyError:
            raise KeyError(f"Pipeline '{job_id}' not found") from None

    async def shutdown(self) -> None:
        tasks = [j.task for j in self.jobs.values() if j.task and not j.task.done()]
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    # ------------------------------------------------------------------ events
    def _log(self, job: Job, agent: str, tag: str, text: str, type_: str) -> None:
        entry = {"id": uuid.uuid4().hex[:8], "timestamp": now_iso(), "agent": agent, "tag": tag,
                 "text": text, "type": type_, "pipelineId": job.id}
        job.logs.append(entry)
        del job.logs[:-1000]
        self.bus.publish("log_entry", entry)

    def _publish_pipeline_update(self, job: Job) -> None:
        job.updated_at = now_iso()
        self.bus.publish("pipeline_update", {
            "pipelineId": job.id, "progress": job.progress, "status": job.status,
            "activeAgents": job.running_agent_ids(),
        })

    def _on_usage(self, job_id: str, rec) -> None:
        job = self.jobs.get(job_id)
        if job is None:
            return
        self.bus.publish("cost_update", {
            "pipelineId": job_id, "tokensSinceLastUpdate": rec.total_tokens,
            "totalTokens": job.tracker.total_tokens, "costUsd": f"{job.tracker.total_cost:.4f}",
        })

    def _on_pipeline_event(self, job: Job, ev: dict) -> None:
        phase: PipelinePhase = ev["phase"]
        idx = PHASE_INDEX[phase]
        _, role, name, ui_id, running_status = PHASE_TABLE[idx]
        step = job.steps[idx]
        agent_name = UI_AGENT_BY_ID[ui_id][1]
        kind = ev["type"]

        if kind == "step_started":
            step.update(status="progress", startTime=now_iso())
            self._status_change(ui_id, "waiting", running_status)
            self._log(job, agent_name, role, f"{name}: iniciado", "thinking")
        elif kind == "step_finished":
            step.update(status="done", endTime=now_iso(), **self._step_details(job, role, phase))
            self._status_change(ui_id, running_status, "idle")
            self._log(job, agent_name, role, f"{name}: completado en {ev['duration']:.1f}s", "success")
            self._enforce_budget(job)
        elif kind == "step_failed":
            step.update(status="failed", endTime=now_iso(), justification=ev["error"])
            self._status_change(ui_id, running_status, "idle", reason=ev["error"])
            self._log(job, agent_name, role, f"{name}: fallo — {ev['error']}", "error")
        elif kind == "step_skipped":
            step.update(status="done", justification=ev.get("reason", ""))
            self._log(job, agent_name, role, f"{name}: omitido ({ev.get('reason', '')})", "info")

        self.bus.publish("step_update", {
            "pipelineId": job.id, "stepNum": step["num"], "agent": agent_name, "status": step["status"],
            "output": job.state.step_outputs.get(role),
        })
        self._publish_pipeline_update(job)
        if kind in ("step_finished", "step_failed", "step_skipped"):
            self._persist(job)

    def _status_change(self, agent_id: str, prev: str, new: str, reason: Optional[str] = None) -> None:
        self.bus.publish("agent_status_change",
                         {"agentId": agent_id, "previousStatus": prev, "newStatus": new, "reason": reason})

    def _enforce_budget(self, job: Job) -> None:
        if job.budget_usd > 0 and job.tracker.total_cost > job.budget_usd and job.task:
            job.error = f"Budget exceeded (${job.tracker.total_cost:.2f} > ${job.budget_usd:.2f})"
            job.task.cancel()

    @staticmethod
    def _step_details(job: Job, role: str, phase: PipelinePhase) -> dict:
        data = (job.state.step_outputs.get(role) or {}).get("data", {})
        text = next((str(data[k]) for k in ("rationale", "summary", "verdict", "title") if data.get(k)), "")
        if phase == PipelinePhase.HYPOTHESIS and job.state.hypothesis:
            text = job.state.hypothesis
        if not text and data:
            text = json.dumps(data, default=str, ensure_ascii=False)
        code = job.state.artifacts.get("experiment_code", "") if phase == PipelinePhase.EXECUTION else ""
        return {"justification": text[:800], "codeSnippet": code[:2000]}

    # ------------------------------------------------------------------ artifacts
    def _save_artifacts(self, job: Job) -> None:
        try:
            state = job.state
            d = job.output_dir
            if code := state.artifacts.get("experiment_code"):
                (d / "experiment.py").write_text(code)
            if papers := state.artifacts.get("literature_papers"):
                (d / "literature.json").write_text(papers)
            (d / "state.json").write_text(json.dumps(state.to_dict(), indent=2, default=str))
        except Exception:
            logger.exception("Failed to save artifacts for %s", job.id)

    def list_artifacts(self, job: Job) -> list[dict]:
        if not job.output_dir.exists():
            return []
        out = []
        for p in sorted(job.output_dir.iterdir()):
            if p.is_file() and p.suffix in ARTIFACT_SUFFIXES:
                size = p.stat().st_size
                out.append({"id": p.name, "type": p.suffix[1:], "name": p.name,
                            "size": f"{size / 1024:.1f} KB" if size >= 1024 else f"{size} B"})
        return out

    def artifact_path(self, job: Job, artifact_id: str) -> Path:
        if artifact_id != Path(artifact_id).name or Path(artifact_id).suffix not in ARTIFACT_SUFFIXES:
            raise KeyError(f"Artifact '{artifact_id}' not found")
        p = job.output_dir / artifact_id
        if not p.is_file():
            raise KeyError(f"Artifact '{artifact_id}' not found")
        return p
