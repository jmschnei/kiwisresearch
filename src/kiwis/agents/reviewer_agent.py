"""Reviewer Agent (Adversarial Peer Reviewer).

Simulates a rigorous NeurIPS/ICML reviewer to critique methodology, detect fallacies, and drive improvements.
"""

from __future__ import annotations

import json
import re
from .base import AgentContext, AgentOutput, AgentState, BaseAgent
from ..models.defaults import DEFAULT_MODEL
from .parsing import extract_json


class ReviewerAgent(BaseAgent):
    ROLE = "reviewer"
    DESCRIPTION = (
        "You are a rigorous academic reviewer simulating the standards of top-tier conferences "
        "(NeurIPS/ICML/ICLR). You critically evaluate methodology, statistics, claims, novelty, and "
        "writing quality. You provide constructive but harsh feedback to push improvements."
    )

    REVIEW_CRITERIA = """Your review should cover these criteria:

**1. Methodology (Critical)**
- Is the experimental design sound?
- Are baselines appropriate and fairly compared?
- Is statistical significance tested?
- Are datasets split appropriately (train/val/test)?
- Any data leakage or contamination?
- Are assumptions of statistical tests validated?

**2. Novelty & Significance (Important)**
- Is the contribution truly novel vs. prior work?
- What is the practical/theoretical significance?
- How does this compare to SOTA methods?

**3. Reproducibility (Important)**
- Are hyperparameters fully reported?
- Is code/data availability addressed?
- Can others replicate results?

**4. Writing & Clarity (Strongly Consider)**
- Is the narrative clear and compelling?
- Are claims supported by evidence?
- Are figures/tables informative and properly labeled?
- Any overclaiming or understated contributions?

**5. Ethical Considerations (Consider)**
- Potential harms of the proposed method?
- Data privacy concerns?
- Bias in datasets or results?

Provide scores: Accept / Borderline / Reject
With a 1-page detailed justification."""

    SYSTEM_PROMPT = f"""You are a rigorous peer reviewer for a top-tier machine learning conference (NeurIPS/ICML level).

Your role is to critically evaluate the research quality and identify ALL weaknesses before publication.

{REVIEW_CRITERIA}

Be specific and constructive. For each issue found, explain:
- What is wrong or unclear
- Why it matters (impact on validity/significance)
- How to fix it concretely

Do not be gentle — researchers need tough but fair criticism.

Respond in structured JSON:
```json
{{
  "overall_verdict": "Accept | Borderline | Reject",
  "strengths": ["strength1", ...],
  "weaknesses": [
    {{
      "category": "methodology|novelty|reproducibility|writing|ethics|statistics",
      "severity": "fatal|major|minor",
      "description": "...",
      "recommendation": "How to address"
    }},
    ...
  ],
  "statistical_concerns": [
    "concern1 (e.g., inadequate statistical power, wrong test used)",
    ...
  ],
  "methodology_flaws": [
    "flaw1",
    ...
  ],
  "novelty_assessment": "Assessment of how novel this is vs. prior work",
  "required_changes": [
    "{{"type": "must_change", "description": "..."}},",
    ...,
    "{{"type": "should_improve", "description": "..."}},",
    ...
  ],
  "confidence": 0.85,
  "decision_rationale": "One paragraph explaining the verdict"
}}
```"""

    def __init__(self, llm_provider=None, model_config=None):
        super().__init__("reviewer-agent")
        self._llm = llm_provider
        self._model_config = model_config
        # Class method attribute fix
        if not hasattr(self.__class__, 'REVIEW_CRITERIA'):
            pass

    async def execute(self, context: AgentContext) -> AgentOutput:
        self.state = AgentState.RUNNING
        
        from .parsing import normalize_paper
        paper_content = normalize_paper(dict(context.paper_draft.get("content") or {}))
        results = context.execution_results
        analysis = context.analysis
        
        # Build the review prompt with all available content
        sections_text = "\n\n".join([
            f"## {k.replace('_', ' ').title()}\n{v}" 
            for k, v in paper_content.get("sections", {}).items()
        ])
        
        metrics_str = json.dumps(results.get("metrics", {}), indent=2) if isinstance(results.get("metrics"), dict) else str(results.get("stdout", "")[:3000])
        
        prompt = f"""Review the following research submission.

Title: {paper_content.get('title', 'Untitled')}

Abstract:
{(paper_content['abstract'] or sections_text[:1000] or 'No abstract')[:500]}

Full Paper Content:
{sections_text[:5000]}

Results/Metrics:
{metrics_str[:2000]}

Analysis & Conclusions:
{json.dumps(analysis.get("conclusions", []), indent=2, default=str)[:1000]}

{self._facts(context)}

Provide a thorough, rigorous review covering ALL criteria. Be specific about what needs to be fixed."""
        await self._verify_citations(context)
        prompt += self._citation_note(context)
        prompt += self._previous_round_note(context)

        if self._llm:
            from ..models.base import ChatMessage, ModelConfig
            config = self._model_config or ModelConfig(model_name=DEFAULT_MODEL, temperature=0.1)
            msgs = [
                ChatMessage(role="system", content=self.SYSTEM_PROMPT),
                ChatMessage(role="user", content=prompt),
            ]
            from .parsing import chat_json
            response_text, review_data = await chat_json(self._llm, msgs, config)
            if review_data is None:  # keep the prose review so it is not lost
                review_data = {"overall_verdict": "unparsed", "review_text": response_text[:8000]}
        else:
            review_data = {"overall_verdict": "Review requires LLM", "weaknesses": [], "required_changes": [],
                           "confidence": 0.0}
        review_data = self._clean(review_data)

        # Store review in context
        context.review_feedback.append(review_data)

        self.state = AgentState.COMPLETED
        self.output = AgentOutput(
            agent_name=self.name,
            state=AgentState.COMPLETED,
            data={
                "verdict": review_data.get("overall_verdict", "unknown"),
                "num_weaknesses": len(review_data.get("weaknesses", [])),
                "fatal_issues": len([w for w in review_data["weaknesses"] if str(w.get("severity", "")).lower() == "fatal"]),
                "required_changes": [c.get("description", "")[:100] for c in review_data["required_changes"]],
            },
        )
        return self.output

    @staticmethod
    def _facts(context: AgentContext) -> str:
        """What the experiment really did, so the review can catch a paper that contradicts it."""
        from .data_analyst_agent import data_source_note, has_results, metric_ranking
        results = context.execution_results
        if not has_results(results):
            facts = "The experiment produced NO results."
        else:
            facts = data_source_note(results) + "\n" + metric_ranking(results.get("metrics") or {})
        return ("=== GROUND TRUTH (from the experiment run, not from the paper) ===\n" + facts.strip() + "\n"
                "Compare the paper against it. Any dataset, number, table, comparison or \"outperforms\" claim that the "
                "ground truth does not support is fabricated: report it as a weakness with severity \"fatal\" and "
                "quote the claim.")

    @staticmethod
    def _clean(review: dict) -> dict:
        """Lists of dicts where the format says so (models also return strings), and a verdict of a known kind."""
        for key in ("weaknesses", "required_changes"):
            items = review.get(key)
            items = items if isinstance(items, list) else []
            review[key] = [i if isinstance(i, dict) else {"description": str(i)} for i in items]
        verdict = str(review.get("overall_verdict", "unknown"))
        if "|" in verdict:  # the template "Accept | Borderline | Reject" copied verbatim is not a verdict
            verdict = "unknown"
        for known in ("Reject", "Borderline", "Accept"):  # "Borderline - needs work" -> "Borderline"
            if verdict.strip().lower().startswith(known.lower()):
                verdict = known
                break
        review["overall_verdict"] = verdict
        return review

    async def _verify_citations(self, context: AgentContext) -> None:
        """Have the reviewer's own model judge whether cited abstracts support the sentences that cite them.

        The result is stored in ``citation_report["verification"]`` (shown in the UI and fed back to the writer).
        Skipped without a model. Earlier verdicts are reused so later review rounds only judge new claims.
        """
        report = (context.paper_draft or {}).get("citation_report")
        if not self._llm or report is None or not getattr(context, "references", None):
            return
        from ..models.base import ChatMessage, ModelConfig
        from ..papers.citation_verifier import extract_claims, verify_claims
        config = self._model_config or ModelConfig(model_name=DEFAULT_MODEL, temperature=0.0)

        async def judge(system: str, user: str) -> str:
            msgs = [ChatMessage(role="system", content=system), ChatMessage(role="user", content=user)]
            return (await self._llm.chat(msgs, config)).content

        claims = extract_claims(context.paper_draft.get("content", {}), context.references)
        cache = context.paper_draft.setdefault("claim_verdicts", {})
        report["verification"] = await verify_claims(claims, context.references, judge, cache)

    @staticmethod
    def _citation_note(context: AgentContext) -> str:
        """Facts about the paper's references, computed by the system (not by the writer)."""
        report = (context.paper_draft or {}).get("citation_report")
        if report is None:
            return ""
        titles = {r["key"]: r["title"] for r in getattr(context, "references", [])}
        cited = "; ".join(f"{k} = {titles.get(k, '?')}" for k in report.get("cited", [])[:25]) or "none"
        return f"""

=== REFERENCE CHECK (computed by the system) ===
References retrieved from scholarly indexes: {report.get("total", 0)}. Cited in the paper: {len(report.get("cited", []))}.
Invented citation keys removed automatically: {len(report.get("unknown", []))}.
Cited works: {cited}
{ReviewerAgent._verification_note(report)}Judge whether the related work is adequately covered and whether claims attributed to references are plausible for
those titles; flag claims without support. A paper with no or very few references has a literature problem."""

    @staticmethod
    def _verification_note(report: dict) -> str:
        from ..papers.citation_verifier import format_problems
        v = report.get("verification")
        if not v:
            return ""
        text = (f"Claim check (an LLM read each cited abstract; abstracts only): {v['checked']} citing sentences checked, "
                f"{v['supported']} supported, {v['partial']} partial, {v['unsupported']} unsupported, "
                f"{v['unverifiable']} unverifiable.\n")
        problems = format_problems(v)
        if problems:
            text += f"Problem claims:\n{problems}\nInclude the unsupported ones in required_changes.\n"
        return text

    @staticmethod
    def _previous_round_note(context: AgentContext) -> str:
        """In later rounds, tell the reviewer what it asked for and how the authors say they responded."""
        round_no = getattr(context, "revision_round", 0)
        if round_no <= 0 or not context.review_feedback:
            return ""
        prev = context.review_feedback[-1]
        notes = (context.paper_draft.get("content") or {}).get("revision_notes", [])
        return f"""

=== THIS IS REVISION ROUND {round_no} ===
Your previous verdict: {prev.get("overall_verdict", "unknown")}
Changes you required: {json.dumps(prev.get("required_changes", []), default=str, ensure_ascii=False)[:2000]}
Authors' response notes: {json.dumps(notes, default=str, ensure_ascii=False)[:2500]}
Verify whether each required change was actually made in the text above (do not trust the notes alone). Do not raise
new minor issues just to prolong the process; keep open only the problems that really remain."""

    def _get_system_prompt(self) -> str:
        return f"""You are a rigorous peer reviewer for NeurIPS/ICML.

Review criteria:
1. **Methodology**: Sound experimental design, appropriate baselines, statistical rigor
2. **Novelty**: Truly new contribution vs. prior work  
3. **Significance**: Practical/theoretical impact
4. **Reproducibility**: Complete reporting of methods and hyperparameters
5. **Writing**: Clear narrative, proper claims support, informative figures/tables

Be specific and constructive. Provide:
- Overall verdict (Accept/Borderline/Reject)
- Strengths (what works well)
- Weaknesses with severity (fatal/major/minor)
- Required changes with type (must_change/should_improve)
- Confidence in your assessment"""


