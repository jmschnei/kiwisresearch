"""Readiness for a local run with Ollama: provider wire format, tolerant JSON parsing, `kiwis check`, the
Ollama config file and the CLI run. Uses a fake Ollama server; no model is ever called."""

import asyncio
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from kiwis.agents.parsing import extract_json, strip_thinking
from kiwis.config.settings import Settings
from kiwis.models.base import ChatMessage, ModelConfig


class FakeOllama:
    """GET /api/tags lists ``models``; POST /api/chat and /api/embed answer from ``chat_reply`` / ``embed_reply``."""

    def __init__(self, models=("llama3.2:3b", "nomic-embed-text:latest")):
        self.models, self.requests = list(models), []
        self.chat_reply = {"message": {"role": "assistant", "content": "ready"}, "done": True, "done_reason": "stop"}
        self.embed_reply = {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def _send(self, code, payload):
                body = json.dumps(payload).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                self._send(200, {"models": [{"name": m} for m in outer.models]})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                outer.requests.append((self.path, body))
                if body.get("model") not in outer.models and body.get("model") + ":latest" not in outer.models:
                    return self._send(404, {"error": f"model '{body.get('model')}' not found"})
                self._send(200, outer.chat_reply if self.path == "/api/chat" else outer.embed_reply)

            def log_message(self, *a):
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()


@pytest.fixture
def ollama():
    s = FakeOllama()
    yield s
    s.httpd.shutdown()


def provider(server, **kw):
    from kiwis.models.providers.ollama_provider import OllamaProvider
    return OllamaProvider(base_url=server.url, **kw)


# ------------------------------------------------------------------ provider

def test_chat_uses_native_api_with_context_window_and_limits(ollama):
    p = provider(ollama, context_window=16384)
    cfg = ModelConfig(model_name="llama3.2:3b", temperature=0.3, max_tokens=2048, stop_sequences=["END"])
    out = asyncio.run(p.chat([ChatMessage("system", "s"), ChatMessage("user", "u")], cfg))
    path, body = ollama.requests[0]
    assert out.content == "ready" and path == "/api/chat" and body["stream"] is False
    assert body["options"] == {"temperature": 0.3, "num_predict": 2048, "num_ctx": 16384, "stop": ["END"]}
    assert [m["role"] for m in body["messages"]] == ["system", "user"]


def test_missing_model_says_how_to_pull_it(ollama):
    with pytest.raises(RuntimeError, match="ollama pull qwen9:1b"):
        asyncio.run(provider(ollama).chat([ChatMessage("user", "x")], ModelConfig(model_name="qwen9:1b")))


def test_truncated_reply_is_logged(ollama, caplog):
    ollama.chat_reply = {"message": {"content": '{"a": '}, "done": True, "done_reason": "length"}
    with caplog.at_level("WARNING"):
        asyncio.run(provider(ollama).chat([ChatMessage("user", "x")], ModelConfig(model_name="llama3.2:3b")))
    assert "truncated" in caplog.text


def test_embeddings_use_the_embedding_model(ollama):
    p = provider(ollama, default_model="llama3.2:3b", embedding_model="nomic-embed-text")
    assert asyncio.run(p.embed(["a", "b"])) == [[0.1, 0.2], [0.3, 0.4]]
    assert ollama.requests[-1] == ("/api/embed", {"model": "nomic-embed-text", "input": ["a", "b"]})
    with pytest.raises(RuntimeError):
        asyncio.run(provider(ollama, embedding_model="not-pulled").embed(["a"]))


# ------------------------------------------------------------------ tolerant JSON parsing

@pytest.mark.parametrize("text", [
    '```json\n{"a": 1}\n```',
    '```\n{"a": 1}\n```',
    '{"a": 1}',
    'Sure! Here is the result:\n{"a": 1}\nHope this helps.',
    '<think>first {"a": 0} maybe</think>\n```json\n{"a": 1}\n```',
    '```json\n{"a": 1,}\n```\nCorrected: {"a": 1}',
])
def test_extract_json_accepts_what_small_models_produce(text):
    assert extract_json(text) == {"a": 1}


def test_extract_json_returns_none_without_an_object():
    assert extract_json("no json here [1, 2]") is None and extract_json("") is None
    assert strip_thinking("<think>x</think> answer") == "answer"


def test_ideation_survives_bare_json_and_a_bad_index():
    from kiwis.agents import IdeationAgent
    from kiwis.orchestrator.pipeline import PipelineState

    class LLM:
        async def chat(self, messages, config):
            return ChatMessage("assistant", 'Here you go: {"hypotheses": [{"hypothesis": "H1"}], "top_hypothesis_index": 7}')

    state = PipelineState(research_topic="t")
    asyncio.run(IdeationAgent(llm_provider=LLM(), model_config=ModelConfig(model_name="m")).execute(state))
    assert state.hypothesis == "H1"


# ------------------------------------------------------------------ config + embeddings wiring

def test_ollama_config_file_loads_and_wires_every_agent(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from kiwis.orchestrator.agent_factory import AgentFactory
    s = Settings.from_file(ROOT / "kiwis_config.ollama.yaml")
    o = s.providers.providers["ollama"]
    assert (o.context_window, o.timeout_seconds, o.embedding_model) == (16384, 900, "nomic-embed-text")
    assert s.pipeline.peer_review_critique_rounds == 1 and s.sandbox.mode == "docker"
    factory = AgentFactory(s)
    for role in ("ideation", "librarian", "experiment_architect", "engineer", "data_analyst", "writer", "reviewer"):
        agent = factory.create(role)
        assert agent._model_config.model_name == "llama3.2:3b"
        assert type(agent._llm).__name__ == "OllamaProvider" and agent._llm._context_window == 16384
    embed_fn, tag = factory._embed_fn()
    assert tag == "ollama_nomic-embed-text" and embed_fn.__self__._embedding_model == "nomic-embed-text"


def test_openai_embeddings_win_when_a_key_is_set(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    from kiwis.orchestrator.agent_factory import AgentFactory
    assert AgentFactory(Settings.from_file(ROOT / "kiwis_config.ollama.yaml"))._embed_fn()[1] == "openai"
    monkeypatch.delenv("OPENAI_API_KEY")
    assert AgentFactory(Settings())._embed_fn() == (None, None)  # no key, no Ollama embedding model


# ------------------------------------------------------------------ kiwis check

def ollama_settings(server, **sandbox):
    s = Settings.from_file(ROOT / "kiwis_config.ollama.yaml")
    s.providers.providers["ollama"].base_url = server.url
    for k, v in sandbox.items():
        setattr(s.sandbox, k, v)
    return s


def test_check_passes_without_calling_the_model(ollama, monkeypatch):
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    from kiwis.preflight import format_report, run_checks
    results = asyncio.run(run_checks(ollama_settings(ollama)))
    model = [r for r in results if r.name.startswith("ollama:llama3.2:3b")]
    assert len(model) == 1 and model[0].ok and "writer" in model[0].name  # one entry for all 7 agents
    assert any(r.name.startswith("embeddings") and r.ok for r in results)
    assert not any(path == "/api/chat" for path, _ in ollama.requests)  # no generation without --ping
    assert "Ready to run." in format_report(results)


def test_check_ping_and_failures(ollama, monkeypatch):
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    from kiwis.preflight import format_report, run_checks
    results = asyncio.run(run_checks(ollama_settings(ollama), ping=True))
    assert "'ready'" in [r for r in results if r.name.startswith("ollama:")][0].detail

    ollama.models = ["nomic-embed-text:latest"]  # chat model not pulled
    report = format_report(asyncio.run(run_checks(ollama_settings(ollama))))
    assert "ollama pull llama3.2:3b" in report and "1 required check(s) failed" in report

    s = ollama_settings(ollama)
    s.providers.providers["ollama"].base_url = "http://127.0.0.1:9"  # nothing listens there
    assert "ollama serve" in format_report(asyncio.run(run_checks(s)))


def test_check_cli_exit_code(ollama, monkeypatch, tmp_path, capsys):
    from kiwis import cli
    cfg = tmp_path / "c.yaml"
    text = (ROOT / "kiwis_config.ollama.yaml").read_text().replace("http://localhost:11434", ollama.url)
    cfg.write_text(text)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    with pytest.raises(SystemExit) as e:
        cli.main(["check", "-c", str(cfg)])
    assert e.value.code == 0 and "Ready to run." in capsys.readouterr().out
    ollama.models = []
    with pytest.raises(SystemExit) as e:
        cli.main(["check", "-c", str(cfg)])
    assert e.value.code == 1


# ------------------------------------------------------------------ CLI research run

def test_cli_research_writes_a_run_folder_with_sandbox(tmp_path, monkeypatch):
    """`kiwis research` must wire the sandbox and the output folder (it used to run without either)."""
    from kiwis import cli
    from kiwis.orchestrator import pipeline as pl
    seen = {}

    async def fake_run(self, topic, hypothesis=""):
        factory = self._agent_factory.__self__
        seen.update(sandbox=factory._sandbox, out=factory._output_dir, topic=topic)
        return pl.PipelineState(research_topic=topic)

    monkeypatch.setattr(pl.ResearchPipeline, "run", fake_run)
    cfg = tmp_path / "c.yaml"
    cfg.write_text(f'paths:\n  output: "{tmp_path / "out"}"\nsandbox:\n  mode: "isolated"\nmemory:\n  enabled: false\n')
    state = asyncio.run(cli.run_research("graph nets", config_path=str(cfg)))
    assert state.research_topic == "graph nets" and seen["sandbox"] is not None
    run_dirs = list((tmp_path / "out" / "runs").iterdir())
    assert len(run_dirs) == 1 and seen["out"] == run_dirs[0] and (run_dirs[0] / "state.json").exists()


# ------------------------------------------------------------------ shapes seen in the first llama3.2:3b run

def test_paper_with_nested_text_is_flattened():
    from kiwis.agents.parsing import normalize_paper
    paper = normalize_paper({"title": {"text": "T"}, "abstract": {"text": "A \\cite{k}."},
                             "sections": {"introduction": {"text": "I"}, "method": ["p1", {"content": "p2"}]}})
    assert paper["title"] == "T" and paper["abstract"] == "A \\cite{k}."
    assert paper["sections"] == {"introduction": "I", "method": "p1\n\np2"}
    listed = normalize_paper({"sections": [{"title": "Related Work", "text": "R"}]})
    assert listed["sections"] == {"related_work": "R"} and listed["title"] == "Untitled"


def test_reviewer_accepts_a_nested_draft():
    from kiwis.agents import ReviewerAgent
    from kiwis.orchestrator.pipeline import PipelineState
    seen = {}

    class LLM:
        async def chat(self, messages, config):
            seen["prompt"] = messages[-1].content
            return ChatMessage("assistant", '{"overall_score": 5, "decision": "major_revision"}')

    state = PipelineState(research_topic="t")
    state.paper_draft = {"content": {"title": "T", "abstract": {"text": "Nested abstract"},
                                     "sections": {"introduction": {"text": "Intro"}}}}
    asyncio.run(ReviewerAgent(llm_provider=LLM(), model_config=ModelConfig(model_name="m")).execute(state))
    assert "Nested abstract" in seen["prompt"] and "Intro" in seen["prompt"]


def test_cli_saves_state_when_a_phase_fails(tmp_path, monkeypatch):
    from kiwis import cli
    from kiwis.orchestrator import pipeline as pl

    async def failing_run(self, topic, hypothesis=""):
        self._state = pl.PipelineState(research_topic=topic, hypothesis="kept")
        raise RuntimeError("Peer review failed")

    monkeypatch.setattr(pl.ResearchPipeline, "run", failing_run)
    cfg = tmp_path / "c.yaml"
    cfg.write_text(f'paths:\n  output: "{tmp_path / "out"}"\nsandbox:\n  mode: "isolated"\nmemory:\n  enabled: false\n')
    with pytest.raises(RuntimeError):
        asyncio.run(cli.run_research("t", config_path=str(cfg)))
    run_dir = next((tmp_path / "out" / "runs").iterdir())
    assert json.loads((run_dir / "state.json").read_text())["hypothesis"] == "kept"


def test_extract_json_repairs_latex_escapes():
    raw = '```json\n{"title": "T", "abstract": "GNNs \\cite{a} help \\textbf{a lot}.\\nNew line", "x": "\\frac{1}{2}"}\n```'
    data = extract_json(raw)
    assert data["abstract"] == "GNNs \\cite{a} help \\textbf{a lot}.\nNew line" and data["x"] == "\\frac{1}{2}"
    assert extract_json('{"a": "\\\\cite{k}"}') == {"a": "\\cite{k}"}  # already valid: untouched


@pytest.mark.parametrize("reply, expected", [
    ("Here:\n```python\nprint(1)\n```", "print(1)\n"),
    ("```\nprint(2)\n```", "print(2)\n"),
    ('```json\n{"action": "new_code", "code": "print(3)"}\n```', "print(3)"),
    ("```python\nimport numpy\nprint(4)", "import numpy\nprint(4)"),  # cut by the token limit
    ("I cannot do that.", None),
])
def test_extract_code(reply, expected):
    from kiwis.agents.parsing import extract_code
    assert extract_code(reply) == expected


def test_metrics_prefer_results_json():
    from kiwis.agents.engineer_agent import EngineerAgent
    out = "epoch 1\ntest_mae_proposed: 0.9\ntest_mae_proposed: 0.41\nbaseline mae = 0.5\nRESULTS_JSON: {\"mae\": 0.41, \"ok\": true}\n"
    assert EngineerAgent._extract_metrics(out) == {"mae": 0.41}
    assert EngineerAgent._extract_metrics(out.replace("RESULTS_JSON", "x")) == {"test_mae_proposed": 0.41, "baseline_mae": 0.5}
    assert EngineerAgent._extract_metrics("RESULTS_JSON: {'mae_rf': 0.03, 'n': 2}") == {"mae_rf": 0.03, "n": 2.0}


class _Sandbox:
    def __init__(self, outcomes):
        self.outcomes, self.codes = list(outcomes), []

    async def execute_python(self, code, filename="experiment.py"):
        from kiwis.execution.sandbox import ExecutionResult, ExecutionStatus
        self.codes.append(code)
        ok = self.outcomes.pop(0)
        return ExecutionResult(status=ExecutionStatus.SUCCESS if ok else ExecutionStatus.FAILED,
                               stdout='RESULTS_JSON: {"acc": 0.9}' if ok else "", stderr="" if ok else "NameError: x")


class _Coder:
    def __init__(self):
        self.prompts = []

    async def chat(self, messages, config):
        self.prompts.append(messages[-1].content)
        return ChatMessage("assistant", f"```python\nprint('v{len(self.prompts)}')\n```")


def test_engineer_debugs_until_it_runs():
    from kiwis.agents.engineer_agent import EngineerAgent
    from kiwis.orchestrator.pipeline import PipelineState
    sandbox, llm, state = _Sandbox([False, False, True]), _Coder(), PipelineState(research_topic="t")
    state.experiment_plan = {"metrics": ["MAE", {"name": "RMSE"}]}
    out = asyncio.run(EngineerAgent(llm_provider=llm, model_config=ModelConfig(model_name="m"), sandbox=sandbox).execute(state))
    assert out.data["experiment_status"] == "completed_after_debug" and out.data["bug_count"] == 2
    assert state.execution_results["metrics"] == {"acc": 0.9} and sandbox.codes[-1] == "print('v3')\n"
    assert "NameError" in llm.prompts[1] and "NO network" not in llm.prompts[0]  # limits live in the system prompt


def test_engineer_gives_up_after_max_iterations_and_analyst_does_not_invent():
    from kiwis.agents.data_analyst_agent import DataAnalystAgent
    from kiwis.agents.engineer_agent import EngineerAgent
    from kiwis.agents.writer_agent import WriterAgent
    from kiwis.orchestrator.pipeline import PipelineState
    state = PipelineState(research_topic="t")
    out = asyncio.run(EngineerAgent(llm_provider=_Coder(), model_config=ModelConfig(model_name="m"),
                                    sandbox=_Sandbox([False] * 4), max_debug_iterations=3).execute(state))
    assert out.data["experiment_status"] == "failed" and "NameError" in state.execution_results["stderr"]

    class NoCall:
        async def chat(self, *a):
            raise AssertionError("the analyst must not ask the model to analyse missing results")

    asyncio.run(DataAnalystAgent(llm_provider=NoCall(), model_config=ModelConfig(model_name="m")).execute(state))
    assert state.analysis["results_available"] is False and state.analysis["conclusions"] == []
    assert "NameError" in state.analysis["limitations"][0]
    assert "Execution Results: NONE" in WriterAgent._results_block(state)


def test_llm_transcripts_are_written(tmp_path):
    from kiwis.models.usage import MeteredProvider, UsageTracker

    class Echo:
        async def chat(self, messages, config):
            return ChatMessage("assistant", "raw reply")

    p = MeteredProvider(Echo(), UsageTracker(), agent="writer", transcript_dir=tmp_path / "llm")
    asyncio.run(p.chat([ChatMessage("system", "sys"), ChatMessage("user", "hello")], ModelConfig(model_name="m")))
    asyncio.run(p.chat([ChatMessage("user", "again")], ModelConfig(model_name="m")))
    files = sorted(f.name for f in (tmp_path / "llm").iterdir())
    assert files == ["01-writer.md", "02-writer.md"]
    text = (tmp_path / "llm" / "01-writer.md").read_text()
    assert "## system\n\nsys" in text and "## reply\n\nraw reply" in text


def test_trailing_commas_do_not_select_a_nested_object():
    """Seen with llama3.2:3b: a trailing comma made the outer object invalid and the first table was returned."""
    raw = '```json\n{"title": "T", "sections": {"intro": {"text": "I", "references": ["\\\\cite{a}", "\\\\cite{b}",]}},\n' \
          ' "tables": [{"caption": "c", "content": "x"}]}\n```'
    from kiwis.agents.parsing import normalize_paper
    paper = normalize_paper(extract_json(raw))
    assert paper["title"] == "T" and paper["sections"] == {"intro": "I \\cite{a,b}"}


def test_a_pasted_bibliography_is_not_turned_into_citations():
    from kiwis.agents.parsing import normalize_paper
    refs = [f"\\cite{{k{i}}}" for i in range(10)]
    assert normalize_paper({"sections": {"results": {"text": "R", "references": refs}}})["sections"] == {"results": "R"}


class _Scripted:
    """Replies in order; records each request."""

    def __init__(self, *replies):
        self.replies, self.requests = list(replies), []

    async def chat(self, messages, config):
        self.requests.append(messages)
        return ChatMessage("assistant", self.replies.pop(0))


def test_chat_json_asks_once_to_reformat_a_markdown_answer():
    from kiwis.agents.parsing import REFORMAT_PROMPT, chat_json
    llm = _Scripted("**Overall Verdict:** Borderline", '```json\n{"overall_verdict": "Borderline"}\n```')
    text, data = asyncio.run(chat_json(llm, [ChatMessage("user", "review")], ModelConfig(model_name="m")))
    assert data == {"overall_verdict": "Borderline"} and text.startswith("**Overall")
    assert [m.role for m in llm.requests[1]] == ["user", "assistant", "user"] and llm.requests[1][-1].content == REFORMAT_PROMPT
    ok = _Scripted('{"a": 1}')
    assert asyncio.run(chat_json(ok, [ChatMessage("user", "x")], ModelConfig(model_name="m")))[1] == {"a": 1}
    assert len(ok.requests) == 1  # no retry when the first answer parses


def test_reviewer_keeps_a_prose_review_and_cleans_fields():
    from kiwis.agents import ReviewerAgent
    from kiwis.orchestrator.pipeline import PipelineState
    state = PipelineState(research_topic="t")
    state.paper_draft = {"content": {"title": "T", "abstract": "A", "sections": {"introduction": "I"}}}
    agent = ReviewerAgent(llm_provider=_Scripted("Looks weak.", "still prose"), model_config=ModelConfig(model_name="m"))
    out = asyncio.run(agent.execute(state))
    assert out.data["verdict"] == "unparsed" and state.review_feedback[-1]["review_text"] == "Looks weak."
    cleaned = ReviewerAgent._clean({"overall_verdict": "Borderline - needs work", "weaknesses": ["vague"],
                                    "required_changes": "none"})
    assert cleaned == {"overall_verdict": "Borderline", "weaknesses": [{"description": "vague"}], "required_changes": []}
    assert ReviewerAgent._clean({"overall_verdict": "Accept | Borderline | Reject"})["overall_verdict"] == "unknown"
