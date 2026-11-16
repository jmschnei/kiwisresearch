"""Dashboard API: REST endpoints, WebSocket events and job lifecycle (fake agents, no LLM)."""

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from kiwis.agents.base import AgentOutput, AgentState
from kiwis.api import create_app
from kiwis.orchestrator.pipeline import ResearchPipeline


class FakeAgent:
    def __init__(self, role, tracker, out_dir, fail=False, delay=0.0):
        self.role, self.tracker, self.out_dir, self.fail, self.delay = role, tracker, out_dir, fail, delay

    async def execute(self, state):
        import asyncio
        await asyncio.sleep(self.delay)
        if self.fail:
            raise RuntimeError("boom")
        self.tracker.record(self.role, "gpt-4o", 1000, 500)
        data = {"summary": f"{self.role} done"}
        if self.role == "ideation":
            state.hypothesis = "H"
            data = {"rationale": "because", "hypotheses": [{"hypothesis": "H"}]}
        elif self.role == "engineer":
            state.artifacts["experiment_code"] = "print(1)"
        elif self.role == "writer":
            (self.out_dir / "paper.pdf").write_bytes(b"%PDF-1.4 fake")
            state.paper_draft = {"content": {"title": "Fake Paper", "sections": {"abstract": "Abs"}}}
        elif self.role == "reviewer":
            state.review_feedback.append({
                "overall_verdict": "Accept",
                "weaknesses": [{"category": "writing", "severity": "major", "description": "unclear"}],
            })
        return AgentOutput(agent_name=self.role, state=AgentState.COMPLETED, data=data)


def make_app(tmp_path, fail_role=None, delay=0.0):
    def builder(settings, tracker, out_dir):
        return ResearchPipeline(
            settings=settings,
            agent_factory=lambda role: FakeAgent(role, tracker, out_dir, fail=(role == fail_role), delay=delay),
        ).build_default_pipeline()
    return create_app(pipeline_builder=builder, jobs_dir=tmp_path / "jobs")


def wait_for(client, pid, statuses=("completed", "failed"), timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        job = client.get(f"/api/v1/pipelines/{pid}").json()["data"]
        if job["status"] in statuses:
            return job
        time.sleep(0.05)
    raise AssertionError("timeout waiting for pipeline")


def launch(client, **extra):
    r = client.post("/api/v1/pipelines", json={"title": "Graph nets", "hypothesis": "", **extra})
    assert r.status_code == 201
    return r.json()["data"]["pipelineId"]


def test_full_run_exposes_steps_results_and_costs(tmp_path):
    with TestClient(make_app(tmp_path)) as c:
        pid = launch(c)
        job = wait_for(c, pid)
        assert job["status"] == "completed" and job["progress"] == 100
        assert job["spentUsd"] > 0

        steps = c.get(f"/api/v1/pipelines/{pid}/steps").json()["data"]
        assert [s["status"] for s in steps] == ["done"] * 7
        assert steps[0]["justification"] == "H"
        assert steps[3]["codeSnippet"] == "print(1)"

        paper = c.get(f"/api/v1/results/{pid}/paper").json()["data"]
        assert paper["title"] == "Fake Paper" and paper["reviewConsensus"] == "accepted"
        assert paper["pdfUrl"].endswith("paper.pdf/download")
        writing = next(m for m in paper["metrics"] if m["name"] == "Escritura")
        assert writing["score"] == 8

        arts = {a["name"] for a in c.get(f"/api/v1/results/{pid}/artifacts").json()["data"]}
        assert {"paper.pdf", "experiment.py", "state.json"} <= arts
        dl = c.get(f"/api/v1/results/{pid}/artifacts/paper.pdf/download")
        assert dl.status_code == 200 and dl.content.startswith(b"%PDF")

        cost = c.get(f"/api/v1/costs?pipeline_id={pid}").json()["data"]
        assert cost["tokensUsed"] == 7 * 1500
        assert "ideador" in c.get(f"/api/v1/costs/breakdown/{pid}").json()["data"]
        assert len(c.get(f"/api/v1/costs/history?pipeline_id={pid}").json()["data"]) == 1
        assert c.get(f"/api/v1/pipelines/{pid}/logs").json()["data"]
        assert len(c.get("/api/v1/swarm/agents").json()["data"]) == 7
        assert c.get("/api/v1/swarm/health").json()["data"]["totalAgents"] == 7


def test_preset_hypothesis_skips_ideation(tmp_path):
    with TestClient(make_app(tmp_path)) as c:
        pid = launch(c, hypothesis="My own hypothesis")
        wait_for(c, pid)
        steps = c.get(f"/api/v1/pipelines/{pid}/steps").json()["data"]
        assert steps[0]["status"] == "done" and "hypothesis provided" in steps[0]["justification"]


def test_failed_step_marks_pipeline_failed_and_can_be_reexecuted(tmp_path):
    app = make_app(tmp_path, fail_role="engineer")
    with TestClient(app) as c:
        pid = launch(c)
        job = wait_for(c, pid)
        assert job["status"] == "failed" and "boom" in job["error"]
        steps = c.get(f"/api/v1/pipelines/{pid}/steps").json()["data"]
        assert steps[3]["status"] == "failed" and steps[4]["status"] == "waiting"
        assert c.get(f"/api/v1/results/{pid}/paper").status_code == 404

        r = c.post("/api/v1/pipelines/reexecute", json={"pipelineId": pid, "stepNum": 1})
        assert r.status_code == 200 and r.json()["data"]["newLogId"]
        wait_for(c, pid)


def test_pause_resume_and_delete(tmp_path):
    with TestClient(make_app(tmp_path, delay=0.15)) as c:
        pid = launch(c)
        r = c.patch(f"/api/v1/pipelines/{pid}/status", json={"status": "paused"})
        assert r.json()["data"]["status"] == "paused"
        time.sleep(0.6)  # running step may finish, but no further steps start
        done = c.get(f"/api/v1/pipelines/{pid}").json()["data"]["progress"]
        assert done < 100
        c.patch(f"/api/v1/pipelines/{pid}/status", json={"status": "active"})
        assert wait_for(c, pid)["status"] == "completed"

        assert c.delete(f"/api/v1/pipelines/{pid}").status_code == 200
        assert c.get(f"/api/v1/pipelines/{pid}").status_code == 404


def test_errors_use_dashboard_shape(tmp_path):
    with TestClient(make_app(tmp_path)) as c:
        r = c.get("/api/v1/pipelines/nope")
        assert r.status_code == 404 and r.json()["success"] is False and "message" in r.json()
        r = c.post("/api/v1/pipelines", json={"title": ""})
        assert r.status_code == 422 and r.json()["code"] == "VALIDATION_ERROR"
        assert c.get("/api/v1/search/suggest").status_code == 501
        assert c.post("/api/v1/swarm/ideador/restart").status_code == 501
        assert c.get("/api/v1/results/x/artifacts/..%2Fetc/download").status_code == 404


def test_artifact_download_rejects_traversal(tmp_path):
    with TestClient(make_app(tmp_path)) as c:
        pid = launch(c)
        wait_for(c, pid)
        assert c.get(f"/api/v1/results/{pid}/artifacts/..%2F..%2Fsecret.json/download").status_code == 404
        assert c.get(f"/api/v1/results/{pid}/artifacts/nothing.json/download").status_code == 404


def test_websocket_streams_events(tmp_path):
    with TestClient(make_app(tmp_path, delay=0.05)) as c:
        with c.websocket_connect("/ws/events") as ws:
            pid = launch(c)
            seen = set()
            for _ in range(200):
                ev = ws.receive_json()
                seen.add(ev["type"])
                assert "timestamp" in ev and "payload" in ev
                if ev["type"] == "pipeline_update" and ev["payload"]["status"] == "completed":
                    break
            assert {"pipeline_update", "step_update", "log_entry", "agent_status_change", "cost_update"} <= seen
        wait_for(c, pid)
