"""Experiment Architect Agent.

Designs methodologies, defines metrics, selects datasets, and structures the codebase.
"""

from __future__ import annotations

import json
import re
from .base import AgentContext, AgentOutput, AgentState, BaseAgent


class ExperimentArchitectAgent(BaseAgent):
    ROLE = "experiment_architect"
    DESCRIPTION = (
        "You design the experimental methodology for a research hypothesis. You define evaluation metrics, "
        "select appropriate datasets, determine baselines to compare against, and structure the codebase "
        "for reproducible experiments."
    )

    SYSTEM_PROMPT = """You are the Experiment Architect agent. Your job is to translate a research hypothesis into an actionable experimental plan.

For each experiment design, provide:
1. **Methodology**: Step-by-step experimental procedure
2. **Datasets**: Which datasets to use and why (with links/huggingface names)
3. **Baselines**: Which existing methods to compare against
4. **Metrics**: Evaluation metrics (accuracy, F1, BLEU, etc.) with justification
5. **Hyperparameters**: Suggested configurations for ablation studies
6. **Code Structure**: Directory layout and key files
7. **Reproducibility Plan**: How to ensure others can replicate the work

Respond in structured JSON:
```json
{
  "methodology": {
    "steps": ["step1", "step2", ...],
    "data_preprocessing": "...",
    "model_architecture": "..."
  },
  "datasets": [
    {"name": "...", "source": "...", "size": "...", "splits": {"train": N, "val": N, "test": N}}
  ],
  "baselines": [
    {"name": "...", "implementation": "...", "reason": "..."}
  ],
  "metrics": [
    {"name": "...", "type": "higher_is_better|lower_is_better", "justification": "..."}
  ],
  "hyperparameters": {
    "learning_rate": "range",
    "batch_size": "value",
    "num_epochs": "value",
    "ablation_study": [
      {"variant": "...", "parameter": "...", "values": [...]}
    ]
  },
  "code_structure": {
    "directories": ["src/", "configs/", "data/", "experiments/", "results/"],
    "key_files": ["train.py", "evaluate.py", "config.yaml"]
  },
  "reproducibility": {
    "dependencies": "...",
    "random_seeds": [42, 123, 456],
    "compute_requirements": "..."
  }
}
```"""

    def __init__(self, llm_provider=None, model_config=None):
        super().__init__("experiment-architect-agent")
        self._llm = llm_provider
        self._model_config = model_config

    async def execute(self, context: AgentContext) -> AgentOutput:
        self.state = AgentState.RUNNING
        
        hypothesis = context.hypothesis or "No hypothesis provided"
        lit_summary = context.literature_review.get("summary", "No literature review.")
        
        prompt = f"""Hypothesis to test: {hypothesis}

Literature Context:
{lit_summary[:2000]}

Design a comprehensive experimental plan for testing this hypothesis. Consider:
- What kind of data is needed?
- Which baselines are most relevant?
- How should we fairly compare methods?
- What ablations would validate the key claims?"""

        if self._llm:
            from ..models.base import ChatMessage, ModelConfig
            config = self._model_config or ModelConfig(model_name="gpt-4o", temperature=0.4)
            msgs = [
                ChatMessage(role="system", content=self.SYSTEM_PROMPT),
                ChatMessage(role="user", content=prompt),
            ]
            response = await self._llm.chat(msgs, config)
        else:
            response_text = "# Experiment Architect placeholder"

        try:
            match = re.search(r'```(?:json)?\s*\n(.*?)```', response_text, re.DOTALL)
            data = json.loads(match.group(1)) if match else {}
        except Exception:
            data = {"methodology": {"steps": []}, "datasets": [], "baselines": [], "metrics": [], "hyperparameters": {}, "code_structure": {}, "reproducibility": {}}

        # Store in context
        context.experiment_plan.update(data)

        self.state = AgentState.COMPLETED
        self.output = AgentOutput(
            agent_name=self.name,
            state=AgentState.COMPLETED,
            data={
                "methodology_summary": str(data.get("methodology", {})),
                "num_datasets": len(data.get("datasets", [])),
                "num_baselines": len(data.get("baselines", [])),
                "metrics": [m.get("name") for m in data.get("metrics", [])],
            },
        )
        return self.output
