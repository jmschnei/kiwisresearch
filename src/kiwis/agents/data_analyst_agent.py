"""Data Analyst Agent.

Processes numerical results, generates high-quality visualizations, and extracts statistical conclusions.
"""

from __future__ import annotations

import json
import re
from .base import AgentContext, AgentOutput, AgentState, BaseAgent
from ..models.defaults import DEFAULT_MODEL
from .parsing import chat_json


def has_results(results: dict) -> bool:
    """True when the experiment ran to completion and printed something to analyse."""
    return results.get("status") in ("success", "completed_after_debug") and bool(results.get("metrics") or (results.get("stdout") or "").strip())


_LOWER_IS_BETTER = ("rmse", "mse", "mae", "loss", "error", "err", "mape", "nll", "perplexity")
_HIGHER_IS_BETTER = ("accuracy", "acc", "f1", "auc", "roc", "r2", "precision", "recall", "bleu", "rouge", "spearman",
                     "pearson", "score")


def _metric_kind(name: str) -> tuple[str, bool] | None:
    """(metric kind, lower_is_better) from a metric name such as ``test_mae_proposed`` or ``Random_Forest_RMSE``."""
    tokens = [t for t in re.split(r"[^a-z0-9]+", name.lower()) if t]
    for kind in _LOWER_IS_BETTER:
        if kind in tokens:
            return kind, True
    for kind in _HIGHER_IS_BETTER:
        if kind in tokens:
            return kind, False
    return None


def metric_ranking(metrics: dict) -> str:
    """Per metric kind, the results ordered best-first, computed here so no model has to compare numbers."""
    groups: dict[tuple[str, bool], dict[str, float]] = {}
    for name, value in (metrics or {}).items():
        kind = _metric_kind(name)
        if kind and isinstance(value, (int, float)):
            groups.setdefault(kind, {})[name] = float(value)
    lines = []
    for (kind, lower), values in groups.items():
        if len(values) < 2:
            continue
        ordered = sorted(values.items(), key=lambda kv: kv[1], reverse=not lower)
        best = [n for n, v in ordered if v == ordered[0][1]]
        parts = [f"{ordered[0][0]} = {ordered[0][1]:.4g}"]
        for (_, prev), (n, v) in zip(ordered, ordered[1:]):
            parts.append(("= " if v == prev else ("< " if lower else "> ")) + f"{n} = {v:.4g}")
        verdict = f"best: {best[0]}" if len(best) == 1 else "tie between " + ", ".join(best)
        lines.append(f"- {kind.upper()} ({'lower' if lower else 'higher'} is better), best first: "
                     + " ".join(parts) + f"  -> {verdict}")
    return ("Ranking computed from the metrics (authoritative; do not contradict it):\n" + "\n".join(lines)) if lines else ""


def data_source_note(results: dict) -> str:
    """The data the experiment really used, as the script reported it (``DATA_SOURCE:`` lines)."""
    sources = results.get("data_sources") or []
    if sources:
        note = "Data actually used (reported by the experiment script): " + "; ".join(sources) + "."
        if any("synthetic" in s.lower() for s in sources):
            note += " Synthetic data cannot show real-world performance: state this as a limitation."
        return note + " Describe the data exactly like this in the Experiments section; do not name other datasets."
    return ("The experiment did not report its data source: do not claim it used a specific real dataset; say the "
            "data source is unverified.")


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

    def _no_results(self, context: AgentContext, results: dict) -> AgentOutput:
        """No experiment output: report that honestly instead of asking the model to analyse nothing."""
        status = results.get("status", "not run")
        errors = [l.strip() for l in (results.get("stderr") or "").splitlines() if l.strip()]
        reason = results.get("error") or (errors[-1][:300] if errors else "no output")  # the exception, not the traceback
        limitation = (f"The experiment did not produce results (status: {status}; {reason.strip()}). "
                      "No quantitative claim about the hypothesis can be made from this run.")
        context.analysis.update({
            "results_available": False, "statistical_summary": {}, "conclusions": [],
            "limitations": [limitation], "recommendations": ["Fix the experiment code and run it again."],
            "visualization_code": None, "analysis_raw": "",
        })
        self.state = AgentState.COMPLETED
        self.output = AgentOutput(agent_name=self.name, state=AgentState.COMPLETED,
                                  data={"results_available": False, "conclusions": [], "visualization_code_available": False})
        return self.output

    def __init__(self, llm_provider=None, model_config=None):
        super().__init__("data-analyst-agent")
        self._llm = llm_provider
        self._model_config = model_config

    async def execute(self, context: AgentContext) -> AgentOutput:
        self.state = AgentState.RUNNING
        
        results = context.execution_results
        if not has_results(results):
            return self._no_results(context, results)

        metrics = results.get("metrics") or {}
        stdout_tail = "\n".join((results.get("stdout") or "").splitlines()[-50:])  # final metrics are printed last
        data_summary = (f"Final metrics (parsed from the run):\n{json.dumps(metrics, indent=2)}\n\n" if metrics else "")
        ranking = metric_ranking(metrics)
        if ranking:
            data_summary = ranking + "\n\n" + data_summary
        data_summary += f"Last lines of the experiment output:\n{stdout_tail}"

        prompt = f"""Analyze the experimental results below.

Hypothesis: {context.hypothesis}
{data_source_note(results)}

{data_summary[:4000]}

Rules: use ONLY the numbers above. Do not invent means, standard deviations, confidence intervals or p-values that
the output does not contain; if a statistic cannot be computed from it, say so in "limitations". A single run gives
no variance, so do not claim statistical significance from it. State whether the results support the hypothesis:
the proposed method only "outperforms" a baseline if the ranking above says so.
Optionally include Python visualization code that reads results.json."""

        if self._llm:
            from ..models.base import ChatMessage, ModelConfig
            config = self._model_config or ModelConfig(model_name=DEFAULT_MODEL, temperature=0.3)
            msgs = [
                ChatMessage(role="system", content=self.SYSTEM_PROMPT),
                ChatMessage(role="user", content=prompt),
            ]
            response_text, parsed = await chat_json(self._llm, msgs, config, required=("conclusions",))
            data = parsed or {}
        else:
            response_text, data = "# Data Analyst placeholder", {}

        # Visualization code comes from the first reply

        # Extract visualization code
        viz_code_match = re.search(r'```(?:python)?\s*\n(.*?)```', response_text, re.DOTALL)
        
        analysis_output = {
            "results_available": True,
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
