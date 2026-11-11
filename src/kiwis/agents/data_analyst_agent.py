"""Data Analyst Agent.

Processes numerical results, generates high-quality visualizations, and extracts statistical conclusions.
"""

from __future__ import annotations

import json
import re
from .base import AgentContext, AgentOutput, AgentState, BaseAgent


class DataAnalystAgent(BaseAgent):
    ROLE = "data_analyst"
    DESCRIPTION = (
        "You are the Data Analyst agent. You process numerical results from experiments, generate "
        "high-quality publication-ready visualizations, perform statistical analysis, and extract "
        "actionable conclusions."
    )

    SYSTEM_PROMPT = """You are the Data Analyst agent for a scientific research system.

Your responsibilities:
1. Process experimental results (CSV, JSON, or raw numbers)
2. Generate statistical summaries (means, standard deviations, confidence intervals)
3. Perform significance testing (t-tests, ANOVA, etc.) when applicable
4. Create publication-quality visualizations (bar charts, line plots, heatmaps, boxplots)
5. Extract conclusions from the data

Visualization standards:
- Use matplotlib/seaborn/plotly for high-quality figures
- Include proper labels, titles, legends, and error bars
- Use colorblind-friendly palettes
- Export figures as both PNG (publication) and SVG (vector) when possible
- Save analysis code for reproducibility

Statistical reporting standards:
- Report means ± standard deviations
- Report p-values with significance markers (* p<0.05, ** p<0.01, *** p<0.001)
- Report effect sizes where applicable
- Note assumptions and limitations of statistical tests

Respond in structured format when providing analysis:
```json
{
  "statistical_summary": {
    "mean_values": {...},
    "std_deviations": {...},
    "confidence_intervals": {..."95% CI lower, upper"},
    "significance_tests": [...]
  },
  "visualizations": [
    {"type": "bar_chart|line_plot|heatmap|boxplot", "title": "...", "data_ref": "...", "filename": "..."}
  ],
  "conclusions": ["conclusion1", ...],
  "limitations": ["limitation1", ...],
  "recommendations": ["recommendation1", ...]
}
```"""

    def __init__(self, llm_provider=None, model_config=None):
        super().__init__("data-analyst-agent")
        self._llm = llm_provider
        self._model_config = model_config

    async def execute(self, context: AgentContext) -> AgentOutput:
        self.state = AgentState.RUNNING
        
        results = context.execution_results
        metrics = results.get("metrics", {})
        stdout = results.get("stdout", "")
        
        # Prepare analysis prompt
        data_summary = ""
        if isinstance(results.get("stdout"), str):
            lines = stdout.split("\n")[-50:]  # Last 50 lines often contain final metrics
            data_summary = "\n".join(lines)
        elif isinstance(results.get("metrics"), dict):
            data_summary = json.dumps(results["metrics"], indent=2)
        
        prompt = f"""Analyze the experimental results below.

Hypothesis: {context.hypothesis}

Results/Metrics:
{data_summary[:3000]}

Perform statistical analysis and generate conclusions. Create visualization code for key findings.
Provide significance testing where appropriate."""

        if self._llm:
            from ..models.base import ChatMessage, ModelConfig
            config = self._model_config or ModelConfig(model_name="gpt-4o", temperature=0.3)
            msgs = [
                ChatMessage(role="system", content=self.SYSTEM_PROMPT),
                ChatMessage(role="user", content=prompt),
            ]
            response = await self._llm.chat(msgs, config)
        else:
            response_text = "# Data Analyst placeholder"

        # Try to extract analysis JSON and visualization code
        try:
            match = re.search(r'```(?:json)?\s*\n(.*?)```', response_text, re.DOTALL)
            data = json.loads(match.group(1)) if match else {}
        except Exception:
            data = {"conclusions": [], "limitations": [], "recommendations": []}

        # Extract visualization code
        viz_code_match = re.search(r'```(?:python)?\s*\n(.*?)```', response_text, re.DOTALL)
        
        analysis_output = {
            "analysis_raw": response_text,
            "statistical_summary": data.get("statistical_summary", {}),
            "conclusions": data.get("conclusions", []),
            "limitations": data.get("limitations", []),
            "recommendations": data.get("recommendations", []),
            "visualization_code": viz_code_match.group(1) if viz_code_match else None,
        }

        # Store in context
        context.analysis.update(analysis_output)

        self.state = AgentState.COMPLETED
        self.output = AgentOutput(
            agent_name=self.name,
            state=AgentState.COMPLETED,
            data={
                "conclusions": analysis_output["conclusions"],
                "visualization_code_available": analysis_output["visualization_code"] is not None,
            },
        )
        return self.output
