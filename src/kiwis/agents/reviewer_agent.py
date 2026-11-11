"""Reviewer Agent (Adversarial Peer Reviewer).

Simulates a rigorous NeurIPS/ICML reviewer to critique methodology, detect fallacies, and drive improvements.
"""

from __future__ import annotations

import json
import re
from .base import AgentContext, AgentOutput, AgentState, BaseAgent


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

{self.REVIEW_CRITERIA}

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
        
        paper_content = context.paper_draft.get("content", {})
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
{paper_content.get('abstract', sections_text[:1000] if sections_text else 'No abstract')[:500]}

Full Paper Content:
{sections_text[:5000]}

Results/Metrics:
{metrics_str[:2000]}

Analysis & Conclusions:
{json.dumps(analysis.get("conclusions", []), indent=2, default=str)[:1000]}

Provide a thorough, rigorous review covering ALL criteria. Be specific about what needs to be fixed."""

        if self._llm:
            from ..models.base import ChatMessage, ModelConfig
            config = self._model_config or ModelConfig(model_name="gpt-4o", temperature=0.1)
            msgs = [
                ChatMessage(role="system", content=self.SYSTEM_PROMPT),
                ChatMessage(role="user", content=prompt),
            ]
            response = await self._llm.chat(msgs, config)
        else:
            response_text = "# Reviewer placeholder"

        # Parse review JSON
        try:
            match = re.search(r'```(?:json)?\s*\n(.*?)```', response_text, re.DOTALL)
            review_data = json.loads(match.group(1)) if match else {}
        except Exception:
            review_data = {
                "overall_verdict": "Review requires LLM",
                "weaknesses": [],
                "required_changes": [],
                "confidence": 0.0,
            }

        # Store review in context
        context.review_feedback.append(review_data)

        self.state = AgentState.COMPLETED
        self.output = AgentOutput(
            agent_name=self.name,
            state=AgentState.COMPLETED,
            data={
                "verdict": review_data.get("overall_verdict", "unknown"),
                "num_weaknesses": len(review_data.get("weaknesses", [])),
                "fatal_issues": len([w for w in review_data.get("weaknesses", []) if w.get("severity") == "fatal"]),
                "required_changes": [c.get("description", "")[:100] for c in review_data.get("required_changes", [])],
            },
        )
        return self.output

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


