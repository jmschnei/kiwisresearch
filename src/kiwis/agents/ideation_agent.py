"""Ideation and Hypothesis Generation Agent.

Analyzes literature gaps and proposes novel, viable research questions.
"""

from __future__ import annotations

from .base import AgentContext, AgentOutput, AgentState, BaseAgent


class IdeationAgent(BaseAgent):
    ROLE = "ideation"
    DESCRIPTION = (
        "You propose novel, well-motivated research hypotheses by identifying gaps in the "
        "current literature. Each hypothesis must be: (1) grounded in existing work, "
        "(2) technically feasible with available datasets/methods, and (3) potentially impactful."
    )

    SYSTEM_PROMPT = """You are the Ideation Agent for a scientific research automation system.

Your task is to analyze gaps in the literature and propose concrete, testable hypotheses.

For each hypothesis you generate, include:
1. **Title**: Clear, specific title (10-20 words)
2. **Hypothesis**: One-sentence statement of the research claim
3. **Motivation**: Why this gap matters (cite prior work)
4. **Feasibility**: What datasets/methods make it testable
5. **Novelty**: How it differs from existing approaches
6. **Risk Level**: Low / Medium / High

Respond in structured JSON format:
```json
{
  "hypotheses": [
    {
      "title": "...",
      "hypothesis": "...",
      "motivation": "...",
      "feasibility": "...",
      "novelty": "...",
      "risk_level": "Low"
    }
  ],
  "top_hypothesis_index": 0,
  "rationale": "Why this hypothesis was selected"
}
```"""

    def __init__(self, llm_provider=None, model_config=None):
        super().__init__("ideation-agent")
        self._llm = llm_provider
        self._model_config = model_config

    async def execute(self, context: AgentContext) -> AgentOutput:
        self.state = AgentState.RUNNING
        
        # Build prompt from available context
        lit_summary = context.literature_review.get("summary", "No literature review yet.")
        current_knowledge = context.research_topic

        prompt = f"""Research Domain: {current_knowledge}

Current Literature Summary:
{lit_summary}

Identify research gaps and propose hypotheses. Generate 3-5 novel hypotheses."""

        if self._llm:
            from ..models.base import ChatMessage, ModelConfig
            config = self._model_config or ModelConfig(model_name="gpt-4o", temperature=0.7)
            msgs = [
                ChatMessage(role="system", content=self.SYSTEM_PROMPT),
                ChatMessage(role="user", content=prompt),
            ]
            response = await self._llm.chat(msgs, config)
        else:
            response_text = "# Placeholder: LLM not configured\n# Hypothesis generation requires an active LLM provider."
        
        # Parse output
        import json
        import re
        
        try:
            # Extract JSON from markdown code blocks
            match = re.search(r'```(?:json)?\s*\n(.*?)```', response_text, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
            else:
                data = {"hypotheses": [{"title": "N/A", "hypothesis": response_text, "motivation": "", "feasibility": "", "novelty": "", "risk_level": "Medium"}], "top_hypothesis_index": 0, "rationale": ""}
        except (json.JSONDecodeError, Exception):
            data = {
                "hypotheses": [{"title": "Generated from text", "hypothesis": response_text, "motivation": "", "feasibility": "", "novelty": "", "risk_level": "Medium"}],
                "top_hypothesis_index": 0,
                "rationale": "Extracted from LLM output"
            }

        # Update context with top hypothesis
        if data.get("hypotheses"):
            top = data["hypotheses"][data.get("top_hypothesis_index", 0)]
            context.hypothesis = top.get("hypothesis", "")
            context.research_topic = data.get("rationale", current_knowledge)

        self.state = AgentState.COMPLETED
        self.output = AgentOutput(
            agent_name=self.name,
            state=AgentState.COMPLETED,
            data={"hypotheses": data.get("hypotheses", []), "rationale": data.get("rationale", "")},
            metadata={"model": getattr(self._model_config, 'model_name', 'unknown') if self._model_config else 'n/a'},
        )
        return self.output
