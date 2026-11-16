"""Peer-review / revision loop: decisions, pipeline orchestration and the writer's revision mode."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kiwis.agents import WriterAgent
from kiwis.agents.base import AgentOutput, AgentState
from kiwis.config.settings import Settings
from kiwis.orchestrator.pipeline import PipelinePhase, PipelineState, ResearchPipeline
from kiwis.orchestrator.review_loop import (decide, is_accepted, is_actionable, overall_score, round_summary)

REJECT = {
    "overall_verdict": "Reject",
    "weaknesses": [{"category": "methodology", "severity": "major", "description": "no baselines"}],
    "required_changes": [{"type": "must_change", "description": "add baselines"}],
}
ACCEPT = {"overall_verdict": "Accept", "weaknesses": [], "required_changes": []}


# ------------------------------------------------------------------ pure decisions

def test_scoring_and_acceptance():
    assert overall_score(ACCEPT) == 10
    assert overall_score(REJECT) == 9.6  # methodology 8, others 10
    assert is_accepted(ACCEPT) and not is_accepted(REJECT)
    fatal = {"overall_verdict": "Accept", "weaknesses": [{"category": "novelty", "severity": "fatal"}]}
    assert not is_accepted(fatal)  # a fatal issue overrides a lenient verdict
    assert is_accepted(REJECT, threshold=0.9)  # score 9.6/10 >= 0.9 even though the verdict is reject
    assert not is_accepted(REJECT, threshold=0.99)


def test_decide_stops_for_the_right_reason():
    assert decide(REJECT, 1, 2).revise and decide(REJECT, 1, 2).reason == "needs_revision"
    assert decide(REJECT, 2, 2).reason == "max_rounds"
    assert decide(ACCEPT, 1, 3).reason == "accepted"
    assert decide({}, 1, 3).reason == "not_actionable"  # placeholder/unparseable review: nothing to act on
    assert decide({"overall_verdict": "Review requires LLM"}, 1, 3).reason == "not_actionable"
    assert not is_actionable({"weaknesses": []})
    assert decide(REJECT, 1, 1).revise is False  # a single round never revises


def test_round_summary_shape():
    s = round_summary(REJECT, 1)
    assert s["round"] == 1 and s["weaknesses"] == 1 and s["fatal"] == 0
    assert s["requiredChanges"] == ["add baselines"]


# ------------------------------------------------------------------ pipeline loop

class LoopAgents:
    """Fake agents: the reviewer follows a script of reviews; the writer records revisions."""

    def __init__(self, reviews):
        self.reviews = list(reviews)
        self.calls = []

    def factory(self, role):
        outer = self

        class Agent:
            async def execute(self, state):
                outer.calls.append(role)
                if role == "reviewer":
                    state.review_feedback.append(outer.reviews.pop(0) if outer.reviews else ACCEPT)
                elif role == "writer":
                    state.paper_draft = {"content": {"title": f"v{state.revision_round + 1}"}}
                return AgentOutput(agent_name=role, state=AgentState.COMPLETED, data={})

        return Agent()


def run_review_phase(reviews, rounds=2, threshold=None):
    settings = Settings()
    settings.pipeline.peer_review_critique_rounds = rounds
    settings.pipeline.auto_submit_threshold = threshold
    agents = LoopAgents(reviews)
    pipe = ResearchPipeline(settings=settings, agent_factory=agents.factory).build_default_pipeline()
    events = []
    pipe.add_listener(events.append)
    state = PipelineState(research_topic="t", paper_draft={"content": {"title": "v1"}})
    pipe._state = state
    asyncio.run(pipe.rerun_phase(PipelinePhase.PEER_REVIEW))
    return agents, state, events


def test_accepted_on_first_review_does_not_revise():
    agents, state, events = run_review_phase([ACCEPT])
    assert agents.calls == ["reviewer"] and state.revision_round == 0
    assert [e["reason"] for e in events if e["type"] == "review_decision"] == ["accepted"]


def test_rejected_then_accepted_after_one_revision():
    agents, state, events = run_review_phase([REJECT, ACCEPT], rounds=3)
    assert agents.calls == ["reviewer", "writer", "reviewer"]
    assert state.revision_round == 1 and len(state.review_feedback) == 2
    assert state.paper_draft["content"]["title"] == "v2"
    kinds = [e["type"] for e in events]
    assert kinds.count("revision_started") == 1 and kinds.count("revision_finished") == 1
    assert "revision_writer_1" not in state.step_outputs and "writer_revision_1" in state.step_outputs
    assert "reviewer_round_2" in state.step_outputs


def test_loop_is_capped_by_max_rounds():
    agents, state, events = run_review_phase([REJECT] * 10, rounds=3)
    assert agents.calls.count("reviewer") == 3 and agents.calls.count("writer") == 2
    assert [e["reason"] for e in events if e["type"] == "review_decision"][-1] == "max_rounds"


def test_single_round_means_review_only():
    agents, _, _ = run_review_phase([REJECT], rounds=1)
    assert agents.calls == ["reviewer"]


def test_threshold_accepts_a_good_enough_paper():
    agents, _, events = run_review_phase([REJECT, ACCEPT], rounds=3, threshold=0.9)
    assert agents.calls == ["reviewer"]  # 9.6/10 >= 0.9 -> auto accepted
    assert [e["reason"] for e in events if e["type"] == "review_decision"] == ["accepted"]


def test_unactionable_review_stops_the_loop():
    agents, _, events = run_review_phase([{}, REJECT], rounds=3)
    assert agents.calls == ["reviewer"]
    assert [e["reason"] for e in events if e["type"] == "review_decision"] == ["not_actionable"]


def test_rewriting_the_paper_resets_review_history():
    agents = LoopAgents([])
    pipe = ResearchPipeline(settings=Settings(), agent_factory=agents.factory).build_default_pipeline()
    state = PipelineState(review_feedback=[REJECT], revision_round=2, paper_history=[{"version": 3}])
    pipe._state = state
    asyncio.run(pipe.rerun_phase(PipelinePhase.PAPER_WRITING))
    assert state.review_feedback == [] and state.revision_round == 0 and state.paper_history == []


# ------------------------------------------------------------------ writer revision mode

class ScriptedLLM:
    def __init__(self, reply):
        self.reply, self.prompts = reply, []

    async def chat(self, messages, config):
        from kiwis.models.base import ChatMessage
        self.prompts.append(messages)
        return ChatMessage(role="assistant", content=self.reply)


def paper_reply(title, **extra):
    data = {"title": title, "abstract": "a", "sections": {"introduction": "text"}, **extra}
    return "```json\n" + json.dumps(data) + "\n```"


def test_writer_revises_with_review_in_prompt_and_versions_files(tmp_path):
    llm = ScriptedLLM(paper_reply("Revised", revision_notes=[{"issue": "baselines", "response": "added"}]))
    writer = WriterAgent(llm_provider=llm, output_dir=tmp_path)
    state = PipelineState(research_topic="t", revision_round=1, review_feedback=[REJECT],
                          paper_draft={"content": {"title": "Original", "sections": {"introduction": "old"}}})
    out = asyncio.run(writer.execute(state))

    system, user = llm.prompts[0][0].content, llm.prompts[0][1].content
    assert "REVISION MODE" in system
    assert "Original" in user and "add baselines" in user
    assert state.paper_draft["content"]["title"] == "Revised"
    assert out.data["version"] == 2 and out.data["revision"] is True
    assert (tmp_path / "paper_draft_v2.json").exists() and (tmp_path / "paper_v2.tex").exists()
    assert state.paper_history[-1]["revisionNotes"][0]["response"] == "added"


def test_first_draft_is_not_in_revision_mode(tmp_path):
    llm = ScriptedLLM(paper_reply("First"))
    state = PipelineState(research_topic="t")
    out = asyncio.run(WriterAgent(llm_provider=llm, output_dir=tmp_path).execute(state))
    assert "REVISION MODE" not in llm.prompts[0][0].content
    assert out.data["version"] == 1 and (tmp_path / "paper_v1.tex").exists()


def test_unparseable_revision_keeps_the_previous_paper(tmp_path):
    llm = ScriptedLLM("I'm sorry, here is some prose without JSON")
    previous = {"title": "Keep me", "sections": {"introduction": "precious"}}
    state = PipelineState(research_topic="t", revision_round=1, review_feedback=[REJECT],
                          paper_draft={"content": previous})
    asyncio.run(WriterAgent(llm_provider=llm, output_dir=tmp_path).execute(state))
    content = state.paper_draft["content"]
    assert content["title"] == "Keep me" and content["sections"]["introduction"] == "precious"
    assert "could not be parsed" in content["revision_notes"][0]["response"]


def test_reviewer_is_told_what_it_asked_for_in_later_rounds():
    from kiwis.agents import ReviewerAgent

    llm = ScriptedLLM("```json\n" + json.dumps(ACCEPT) + "\n```")
    state = PipelineState(research_topic="t", revision_round=1, review_feedback=[REJECT],
                          paper_draft={"content": {"title": "P", "sections": {"introduction": "x"},
                                                   "revision_notes": [{"issue": "baselines", "response": "added"}]}})
    asyncio.run(ReviewerAgent(llm_provider=llm).execute(state))
    user = llm.prompts[0][1].content
    assert "REVISION ROUND 1" in user and "add baselines" in user and "added" in user
    assert len(state.review_feedback) == 2
