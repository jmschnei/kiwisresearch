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


def test_config_endpoint_reports_availability_without_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-value")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with TestClient(make_app(tmp_path)) as c:
        r = c.get("/api/v1/config")
        data = r.json()["data"]
        assert data["providers"]["openai"]["available"] is True
        assert data["providers"]["anthropic"]["available"] is False
        assert data["providers"]["ollama"]["available"] is True
        assert data["agents"]["reviewer"]["provider"] in ("openai", "anthropic")
        assert "sk-secret-value" not in r.text


def test_config_never_exposes_the_vector_store_url(tmp_path):
    from kiwis.config.settings import Settings
    settings = Settings(memory={"vector_store": "pgvector", "url": "postgresql://user:hunter2@db/kiwis"})
    app = create_app(settings=settings, pipeline_builder=lambda *a: None, jobs_dir=tmp_path / "jobs")
    with TestClient(app) as c:
        r = c.get("/api/v1/config")
        assert "hunter2" not in r.text and "postgresql://" not in r.text
        memory = r.json()["data"]["memory"]
        assert memory["vector_store"] == "pgvector" and memory["urlConfigured"] is True


# ---------------------------------------------------------------- persistence

def test_jobs_survive_server_restart(tmp_path):
    with TestClient(make_app(tmp_path)) as c:
        pid = launch(c)
        before = wait_for(c, pid)
        steps_before = c.get(f"/api/v1/pipelines/{pid}/steps").json()["data"]
        logs_before = c.get(f"/api/v1/pipelines/{pid}/logs").json()["data"]

    with TestClient(make_app(tmp_path)) as c:  # a brand-new app over the same directory
        after = c.get(f"/api/v1/pipelines/{pid}").json()["data"]
        assert after["status"] == "completed" and after["progress"] == 100
        assert after["name"] == before["name"] and after["createdAt"] == before["createdAt"]
        assert after["spentUsd"] == before["spentUsd"] > 0
        assert c.get(f"/api/v1/pipelines/{pid}/steps").json()["data"] == steps_before
        assert len(c.get(f"/api/v1/pipelines/{pid}/logs").json()["data"]) == len(logs_before)
        assert c.get(f"/api/v1/results/{pid}/paper").json()["data"]["title"] == "Fake Paper"
        assert c.get(f"/api/v1/results/{pid}/review").json()["data"]["consensus"] == "accepted"
        assert c.get(f"/api/v1/costs?pipeline_id={pid}").json()["data"]["tokensUsed"] == 7 * 1500
        assert [p["id"] for p in c.get("/api/v1/pipelines").json()["data"]] == [pid]


def test_interrupted_job_is_marked_failed_and_can_resume(tmp_path):
    import json as _json

    with TestClient(make_app(tmp_path, delay=0.05)) as c:
        pid = launch(c)
        wait_for(c, pid)

    # Simulate a crash: the job was running step 7 when the server died.
    meta_path = tmp_path / "jobs" / pid / "job.json"
    meta = _json.loads(meta_path.read_text())
    meta["status"] = "active"
    meta["steps"][6].update(status="progress", justification="")
    meta_path.write_text(_json.dumps(meta))

    with TestClient(make_app(tmp_path, delay=0.05)) as c:
        job = c.get(f"/api/v1/pipelines/{pid}").json()["data"]
        assert job["status"] == "failed" and "reinici" in job["error"]
        steps = c.get(f"/api/v1/pipelines/{pid}/steps").json()["data"]
        assert steps[6]["status"] == "failed"

        # Re-executing the interrupted step resumes from the saved state
        assert c.post("/api/v1/pipelines/reexecute", json={"pipelineId": pid, "stepNum": 7}).status_code == 200
        final = wait_for(c, pid, statuses=("completed",))
        assert final["error"] is None
        assert c.get(f"/api/v1/pipelines/{pid}/steps").json()["data"][6]["status"] == "done"

    # ...and the recovery itself was persisted
    with TestClient(make_app(tmp_path)) as c:
        assert c.get(f"/api/v1/pipelines/{pid}").json()["data"]["status"] == "completed"


def test_delete_is_permanent(tmp_path):
    with TestClient(make_app(tmp_path)) as c:
        pid = launch(c)
        wait_for(c, pid)
        assert (tmp_path / "jobs" / pid / "job.json").exists()
        assert c.delete(f"/api/v1/pipelines/{pid}").status_code == 200
        assert not (tmp_path / "jobs" / pid).exists()
    with TestClient(make_app(tmp_path)) as c:
        assert c.get("/api/v1/pipelines").json()["data"] == []


def test_corrupt_job_file_does_not_block_startup(tmp_path):
    with TestClient(make_app(tmp_path)) as c:
        good = launch(c)
        wait_for(c, good)
    bad = tmp_path / "jobs" / "p-deadbeef"
    bad.mkdir()
    (bad / "job.json").write_text("{not json")
    with TestClient(make_app(tmp_path)) as c:
        ids = [p["id"] for p in c.get("/api/v1/pipelines").json()["data"]]
        assert ids == [good]


def test_continue_from_step_runs_all_following_steps(tmp_path):
    import json as _json

    with TestClient(make_app(tmp_path, delay=0.02)) as c:
        pid = launch(c)
        wait_for(c, pid)

    # Crash after step 3: steps 4-7 never ran
    meta_path = tmp_path / "jobs" / pid / "job.json"
    meta = _json.loads(meta_path.read_text())
    meta["status"] = "active"
    for step in meta["steps"][3:]:
        step.update(status="waiting", justification="", codeSnippet="")
    meta_path.write_text(_json.dumps(meta))

    with TestClient(make_app(tmp_path, delay=0.02)) as c:
        assert c.get(f"/api/v1/pipelines/{pid}").json()["data"]["status"] == "failed"
        r = c.post("/api/v1/pipelines/reexecute", json={"pipelineId": pid, "stepNum": 4, "cascade": True})
        assert r.status_code == 200
        final = wait_for(c, pid, statuses=("completed", "failed"))
        assert final["status"] == "completed" and final["progress"] == 100
        steps = c.get(f"/api/v1/pipelines/{pid}/steps").json()["data"]
        assert [s["status"] for s in steps] == ["done"] * 7


# ---------------------------------------------------------------- review loop through the API

class ReviewLoopAgent(FakeAgent):
    """Reviewer rejects until `accept_on_round`; writer produces versioned papers."""
    reviews_done = 0

    async def execute(self, state):
        if self.role == "reviewer":
            ReviewLoopAgent.reviews_done += 1
            accept = ReviewLoopAgent.reviews_done >= self.accept_on
            state.review_feedback.append(
                {"overall_verdict": "Accept", "weaknesses": []} if accept else
                {"overall_verdict": "Reject",
                 "weaknesses": [{"category": "methodology", "severity": "major", "description": "no baselines"}],
                 "required_changes": [{"type": "must_change", "description": "add baselines"}]})
            return AgentOutput(agent_name="reviewer", state=AgentState.COMPLETED, data={"verdict": "x"})
        if self.role == "writer":
            v = state.revision_round + 1
            (self.out_dir / "paper.pdf").write_bytes(b"%PDF-1.4 fake")
            state.references = [{"key": "smith2020graph", "title": "A Real Paper", "authors": ["Jane Smith"], "year": 2020,
                                 "venue": "arXiv preprint", "url": "https://arxiv.org/abs/2001.00001", "doi": "", "abstract": "",
                                 "id": "arxiv:2001.00001", "source": "arxiv"}]
            state.paper_draft = {"citation_report": {"total": 1, "cited": ["smith2020graph"], "unknown": [], "uncited": []},
                                 "content": {"title": f"Paper v{v}", "sections": {"abstract": f"abs v{v}"},
                                             "revision_notes": [{"issue": "baselines", "response": "added"}] if v > 1 else []}}
            state.paper_history.append({"version": v, "title": f"Paper v{v}", "latex": f"paper_v{v}.tex",
                                        "json": f"paper_draft_v{v}.json", "revisionNotes": []})
            return AgentOutput(agent_name="writer", state=AgentState.COMPLETED, data={"version": v})
        return await super().execute(state)


def make_loop_app(tmp_path, accept_on):
    ReviewLoopAgent.reviews_done = 0

    def builder(settings, tracker, out_dir):
        def factory(role):
            agent = ReviewLoopAgent(role, tracker, out_dir)
            agent.accept_on = accept_on
            return agent
        return ResearchPipeline(settings=settings, agent_factory=factory).build_default_pipeline()

    return create_app(pipeline_builder=builder, jobs_dir=tmp_path / "jobs")


def test_review_loop_runs_through_the_api(tmp_path):
    with TestClient(make_loop_app(tmp_path, accept_on=2)) as c:
        pid = launch(c)  # standard depth -> 2 review rounds
        assert wait_for(c, pid)["status"] == "completed"

        review = c.get(f"/api/v1/results/{pid}/review").json()["data"]
        assert [r["verdict"] for r in review["rounds"]] == ["Reject", "Accept"]
        assert review["rounds"][0]["score"] < review["rounds"][1]["score"] == 10
        assert review["revisionRound"] == 1 and review["consensus"] == "accepted"

        paper = c.get(f"/api/v1/results/{pid}/paper").json()["data"]
        assert paper["title"] == "Paper v2" and paper["revisionNotes"][0]["response"] == "added"
        assert [v["version"] for v in paper["versions"]] == [1, 2]
        assert paper["references"][0]["key"] == "smith2020graph" and paper["citationReport"]["cited"] == ["smith2020graph"]

        steps = c.get(f"/api/v1/pipelines/{pid}/steps").json()["data"]
        assert steps[6]["status"] == "done" and "aceptado" in steps[6]["justification"]
        texts = [l["text"] for l in c.get(f"/api/v1/pipelines/{pid}/logs").json()["data"]]
        assert any("Ronda de revisión 1/2" in t for t in texts) and any("Revisando el artículo" in t for t in texts)


def test_revision_progress_is_visible_while_the_writer_rewrites(tmp_path):
    from kiwis.api.jobs import Job  # noqa: F401  (type only)

    app = make_loop_app(tmp_path, accept_on=2)
    with TestClient(app) as c:
        pid = launch(c)
        wait_for(c, pid)
        job = app.state.manager.get(pid)
        # transient flags are reset once the review step is over
        assert job.revising is False and job.review_round == 0
        job.revising, job.review_round, job.review_max = True, 1, 2
        view = c.get(f"/api/v1/pipelines/{pid}").json()["data"]
        assert view["revising"] is True and view["reviewRound"] == 1 and view["reviewMax"] == 2
        assert job.running_agent_ids() == ["latex"]


def test_depth_controls_the_number_of_review_rounds(tmp_path):
    with TestClient(make_loop_app(tmp_path, accept_on=99)) as c:  # never accepted
        fast = launch(c, depthLevel="fast")
        wait_for(c, fast)
        assert len(c.get(f"/api/v1/results/{fast}/review").json()["data"]["rounds"]) == 1

        ReviewLoopAgent.reviews_done = 0
        deep = launch(c, depthLevel="deep")  # config default 2 + 1
        wait_for(c, deep)
        assert len(c.get(f"/api/v1/results/{deep}/review").json()["data"]["rounds"]) == 3

    # the whole history is restored after a restart
    with TestClient(make_loop_app(tmp_path, accept_on=99)) as c:
        assert len(c.get(f"/api/v1/results/{deep}/review").json()["data"]["rounds"]) == 3
