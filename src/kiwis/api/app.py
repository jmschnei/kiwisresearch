"""FastAPI application exposing the Kiwis pipeline to the dashboard (REST + WebSocket)."""

from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from fastapi.exceptions import RequestValidationError
from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from ..config.settings import Settings
from .catalog import PHASE_TABLE
from .events import EventBus, now_iso
from .jobs import JobManager, PipelineBuilder
from .schemas import CreateResearchRequest, ReexecuteStepRequest, UpdatePipelineStatusRequest
from . import views

logger = logging.getLogger(__name__)
API_VERSION = "0.1.0"
PREFIX = "/api/v1"


def _ok(data: Any = None) -> dict:
    return {"success": True, "data": data,
            "meta": {"requestId": uuid.uuid4().hex[:12], "timestamp": now_iso(), "version": API_VERSION}}


def _err(status: int, code: str, message: str) -> JSONResponse:
    # `code`/`message` are duplicated at top level because the dashboard's fetch wrapper reads them there.
    return JSONResponse(status_code=status, content={
        "success": False, "code": code, "message": message,
        "error": {"code": code, "message": message}})


def create_app(
    settings: Optional[Settings] = None,
    pipeline_builder: Optional[PipelineBuilder] = None,
    jobs_dir: Optional[Path] = None,
    cors_origins: Optional[list[str]] = None,
    restore: bool = True,
) -> FastAPI:
    settings = settings or Settings.default()
    bus = EventBus()
    manager = JobManager(settings, bus, builder=pipeline_builder, base_dir=jobs_dir)
    if restore:
        restored = manager.load()
        if restored:
            logger.info("Restored %d research job(s) from %s", restored, manager._base_dir)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await manager.shutdown()

    app = FastAPI(title="Kiwis Research API", version=API_VERSION, lifespan=lifespan)
    app.state.manager = manager
    app.state.bus = bus
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["http://localhost:3000", "http://127.0.0.1:3000",
                                       "http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"], allow_headers=["*"],
    )

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException):
        return _err(exc.status_code, f"HTTP_{exc.status_code}", str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        msg = "; ".join(f"{'.'.join(str(x) for x in e['loc'][1:])}: {e['msg']}" for e in exc.errors())
        return _err(422, "VALIDATION_ERROR", msg)

    def job_or_404(job_id: str):
        try:
            return manager.get(job_id)
        except KeyError as e:
            raise HTTPException(404, e.args[0])

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": API_VERSION}

    @app.get(f"{PREFIX}/config")
    async def get_config():
        return _ok(views.config_view(settings))

    # ------------------------------------------------------------- pipelines
    @app.get(f"{PREFIX}/pipelines")
    async def list_pipelines():
        jobs = sorted(manager.jobs.values(), key=lambda j: j.created_at, reverse=True)
        return _ok([views.pipeline_view(j) for j in jobs])

    @app.post(f"{PREFIX}/pipelines", status_code=201)
    async def create_pipeline(body: CreateResearchRequest):
        job = manager.create(body)
        return _ok({"pipelineId": job.id, "status": job.status})

    # NOTE: declared before /pipelines/{pipeline_id} so "reexecute" is not captured as an id.
    @app.post(f"{PREFIX}/pipelines/reexecute")
    async def reexecute(body: ReexecuteStepRequest):
        try:
            log_id = manager.reexecute(body.pipelineId, body.stepNum, cascade=body.cascade)
        except KeyError as e:
            raise HTTPException(404, e.args[0])
        except ValueError as e:
            raise HTTPException(409, str(e))
        return _ok({"success": True, "newLogId": log_id})

    @app.get(f"{PREFIX}/pipelines/{{pipeline_id}}")
    async def get_pipeline(pipeline_id: str):
        return _ok(views.pipeline_view(job_or_404(pipeline_id)))

    @app.patch(f"{PREFIX}/pipelines/{{pipeline_id}}/status")
    async def update_status(pipeline_id: str, body: UpdatePipelineStatusRequest):
        job_or_404(pipeline_id)
        try:
            job = manager.set_status(pipeline_id, body.status, body.reason)
        except ValueError as e:
            raise HTTPException(409, str(e))
        return _ok(views.pipeline_view(job))

    @app.delete(f"{PREFIX}/pipelines/{{pipeline_id}}")
    async def delete_pipeline(pipeline_id: str):
        job_or_404(pipeline_id)
        await manager.delete(pipeline_id)
        return _ok(None)

    @app.get(f"{PREFIX}/pipelines/{{pipeline_id}}/steps")
    async def get_steps(pipeline_id: str):
        return _ok(job_or_404(pipeline_id).steps)

    @app.get(f"{PREFIX}/pipelines/{{pipeline_id}}/logs")
    async def get_logs(pipeline_id: str, limit: int = Query(200, ge=1, le=1000)):
        return _ok(job_or_404(pipeline_id).logs[-limit:])

    # ------------------------------------------------------------- swarm
    @app.get(f"{PREFIX}/swarm/health")
    async def swarm_health():
        return _ok(views.health_view(manager))

    @app.get(f"{PREFIX}/swarm/agents")
    async def swarm_agents():
        return _ok(views.agents_view(manager))

    @app.post(f"{PREFIX}/swarm/{{agent_id}}/restart")
    async def restart_agent(agent_id: str):
        """Re-run the step of this agent in the most recent finished pipeline where it failed."""
        steps = {row[3]: i + 1 for i, row in enumerate(PHASE_TABLE)}
        if agent_id not in steps:
            return _err(404, "NOT_FOUND", f"Unknown agent '{agent_id}'")
        step_num = steps[agent_id]
        for job in sorted(manager.jobs.values(), key=lambda j: j.created_at, reverse=True):
            running = job.status == "active" or (job.task and not job.task.done())
            if not running and job.steps[step_num - 1]["status"] == "failed":
                manager.reexecute(job.id, step_num)
                return _ok({"success": True, "pipelineId": job.id, "stepNum": step_num})
        return _err(409, "NOTHING_TO_RESTART", f"No stopped pipeline has a failed '{agent_id}' step")

    # ------------------------------------------------------------- costs
    @app.get(f"{PREFIX}/costs")
    async def costs(pipeline_id: Optional[str] = None):
        if pipeline_id:
            job_or_404(pipeline_id)
        return _ok(views.cost_view(manager, pipeline_id))

    @app.get(f"{PREFIX}/costs/history")
    async def costs_history(pipeline_id: str, days: int = 30):
        return _ok(views.cost_history(job_or_404(pipeline_id)))

    @app.get(f"{PREFIX}/costs/breakdown/{{pipeline_id}}")
    async def costs_breakdown(pipeline_id: str):
        return _ok(views.cost_breakdown(job_or_404(pipeline_id)))

    # ------------------------------------------------------------- results
    @app.get(f"{PREFIX}/results/{{pipeline_id}}/paper")
    async def get_paper(pipeline_id: str):
        job = job_or_404(pipeline_id)
        paper = views.paper_view(manager, job)
        if paper is None:
            return _err(404, "NOT_READY", "The paper has not been written yet")
        return _ok(paper)

    @app.get(f"{PREFIX}/results/{{pipeline_id}}/artifacts")
    async def list_artifacts(pipeline_id: str):
        return _ok(manager.list_artifacts(job_or_404(pipeline_id)))

    @app.get(f"{PREFIX}/results/{{pipeline_id}}/artifacts/{{artifact_id}}/download")
    async def download_artifact(pipeline_id: str, artifact_id: str):
        job = job_or_404(pipeline_id)
        try:
            path = manager.artifact_path(job, artifact_id)
        except KeyError as e:
            raise HTTPException(404, e.args[0])
        return FileResponse(path, filename=path.name)

    @app.get(f"{PREFIX}/results/{{pipeline_id}}/review")
    async def get_review(pipeline_id: str):
        return _ok(views.review_view(job_or_404(pipeline_id)))

    # ------------------------------------------------------------- search
    @app.get(f"{PREFIX}/search/papers")
    async def search_papers(q: str = Query(min_length=1), n: int = Query(20, ge=1, le=50)):
        from ..agents import LibrarianAgent
        papers = await LibrarianAgent()._search_arxiv(q, max_results=n)
        if len(papers) == 1 and "error" in papers[0]:
            return _err(502, "UPSTREAM_ERROR", papers[0]["error"])
        return _ok(papers)

    @app.get(f"{PREFIX}/search/suggest")
    async def suggest(domain: str = "", topic: str = ""):
        """Research directions drawn from the latest arXiv papers on the domain/topic."""
        from ..agents import LibrarianAgent
        query = f"{domain} {topic}".strip()
        if not query:
            raise HTTPException(422, "Provide a domain or a topic")
        papers = await LibrarianAgent()._search_arxiv(query, max_results=5)
        if papers and "error" in papers[0]:
            return _err(502, "UPSTREAM_ERROR", papers[0]["error"])
        return _ok([{
            "title": p["title"], "year": p.get("year"), "url": p.get("url", ""),
            "rationale": f"Active research area: \"{p['title']}\" ({p.get('year') or 'n.d.'})",
        } for p in papers])

    # ------------------------------------------------------------- websocket
    @app.websocket("/ws/events")
    async def ws_events(ws: WebSocket):
        await ws.accept()
        queue = bus.subscribe()

        async def sender():
            while True:
                await ws.send_json(await queue.get())

        send_task = asyncio.create_task(sender())
        try:
            while True:
                await ws.receive_text()  # client commands are accepted but currently ignored
        except WebSocketDisconnect:
            pass
        finally:
            send_task.cancel()
            bus.unsubscribe(queue)

    return app
