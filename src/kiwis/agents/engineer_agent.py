"""Engineer Agent (Coder, Executor, Debugger).

Writes Python scripts, runs experiments, analyzes tracebacks, and fixes bugs iteratively.
"""

from __future__ import annotations

import json
import os
import re
from .base import AgentContext, AgentOutput, AgentState, BaseAgent
from ..models.defaults import DEFAULT_MODEL
from .parsing import extract_code, strip_thinking


class EngineerAgent(BaseAgent):
    ROLE = "engineer"
    DESCRIPTION = (
        "You are the Engineering agent. You write production-quality Python code for experiments, "
        "execute them in a sandbox, analyze any errors or tracebacks, and iteratively fix bugs until "
        "the experiment runs successfully."
    )

    SYSTEM_PROMPT = """You are the Engineer Agent for a scientific research system. You write one self-contained
Python script that runs the experiment, and you fix it when it fails.

The script runs in an isolated sandbox with these hard limits:
- NO network access: nothing can be downloaded (no pip install, no dataset downloads, no URLs, no APIs).
- Available libraries ONLY: Python standard library, numpy, pandas, scipy, scikit-learn, matplotlib, seaborn.
  There is no torch, tensorflow, jax, rdkit or torch_geometric: implement models with numpy / scikit-learn.
- CPU only, limited memory, and a time limit of a few minutes: keep data small and training short.
- Data: generate a synthetic dataset with numpy (fixed random seed) that mimics the real setting, or use a
  dataset bundled with scikit-learn that needs no download (load_diabetes, load_breast_cancer, load_wine, load_iris,
  load_digits). State in a comment which real dataset the synthetic data stands in for.

Script requirements:
- Compare the proposed method against at least one baseline on the same data split; set random seeds.
- Print each final metric on its own line as `name: value` (for example `test_mae_proposed: 0.4123`).
- At the end print exactly one line `RESULTS_JSON: {...}` with all final metrics as a flat JSON object.
- Save figures as PNG files in the current directory (use matplotlib.use("Agg")) and results to results.json.
- Never invent numbers: every reported value must be computed by the script.

Answer with the complete script in ONE ```python code block and nothing else."""

    def __init__(self, llm_provider=None, model_config=None, sandbox=None, max_debug_iterations: int = 3):
        super().__init__("engineer-agent")
        self._llm = llm_provider
        self._model_config = model_config
        self._sandbox = sandbox
        self._bug_count = 0
        self._max_debug_iterations = max_debug_iterations

    async def _ask(self, prompt: str) -> str:
        from ..models.base import ChatMessage, ModelConfig
        config = self._model_config or ModelConfig(model_name=DEFAULT_MODEL, temperature=0.2)
        msgs = [ChatMessage(role="system", content=self.SYSTEM_PROMPT), ChatMessage(role="user", content=prompt)]
        return strip_thinking((await self._llm.chat(msgs, config)).content)

    async def execute(self, context: AgentContext) -> AgentOutput:
        self.state = AgentState.RUNNING
        self._bug_count = 0
        plan = context.experiment_plan or {}
        metrics = [m.get("name") if isinstance(m, dict) else str(m) for m in (plan.get("metrics") or [])]

        prompt = f"""Implement this experiment as a single runnable Python script.

Hypothesis: {context.hypothesis or "No hypothesis"}

Methodology: {json.dumps(plan.get("methodology", {}), indent=2, default=str)[:2000]}
Datasets in the plan (NOT downloadable here - simulate them or use a bundled scikit-learn dataset):
{json.dumps((plan.get("datasets") or [])[:3], indent=2, default=str)[:1200]}
Baselines: {json.dumps((plan.get("baselines") or [])[:3], default=str)[:600]}
Metrics to report: {json.dumps(metrics)}

The script must: build the data, implement the proposed method and the baseline(s), train, evaluate on a held-out
split, print the metrics and the RESULTS_JSON line, and save at least one PNG figure."""

        results = context.execution_results
        code = extract_code(await self._ask(prompt)) if self._llm else None
        if not code:
            results.update(status="no_code", error="The model did not return a Python script.")
        elif not self._sandbox:
            results.update(status="not_run", error="No sandbox configured.")
            context.artifacts["experiment_code"] = code
        else:
            result = await self._sandbox.execute_python(code, filename="experiment.py")
            while result.status.name != "SUCCESS" and self._bug_count < self._max_debug_iterations:
                fixed = await self._debug_and_fix(code, result)
                if not fixed:
                    break
                code = fixed
                result = await self._sandbox.execute_python(code, filename="experiment.py")
            self._store_result(results, result)
            context.artifacts["experiment_code"] = code
            for path in result.artifacts:
                context.artifacts[os.path.basename(path)] = path

        self.state = AgentState.COMPLETED
        self.output = AgentOutput(
            agent_name=self.name,
            state=AgentState.COMPLETED,
            data={
                "bug_count": self._bug_count,
                "experiment_status": results.get("status", "unknown"),
                "metrics": results.get("metrics", {}),
                "artifacts_generated": len([a for a in context.artifacts.values()
                                            if isinstance(a, str) and a.endswith((".png", ".csv", ".json"))]),
            },
        )
        return self.output

    def _store_result(self, results: dict, result) -> None:
        ok = result.status.name == "SUCCESS"
        results["status"] = ("success" if self._bug_count == 0 else "completed_after_debug") if ok else "failed"
        results["debug_iterations"] = self._bug_count
        results["stdout"] = result.stdout[-5000:]
        if not ok:
            results["stderr"] = (result.stderr or result.error_traceback or "")[-5000:]
        metrics = self._extract_metrics(result.stdout) if ok else {}
        if metrics:
            results["metrics"] = metrics

    async def _debug_and_fix(self, code: str, result) -> str | None:
        """Ask for a corrected script given the error; None if the model returns no code."""
        self._bug_count += 1
        error = result.stderr or result.error_traceback or f"Execution status: {result.status.name}"
        if result.status.name == "TIMEOUT":
            error += "\nThe script exceeded the time limit: use less data, fewer epochs and smaller models."
        simplify = ""
        if self._bug_count >= self._max_debug_iterations:  # last chance: a simpler script that runs beats a failed one
            simplify = ("\nThis is the last attempt. SIMPLIFY: replace hand-written networks, layers and optimizers with "
                        "scikit-learn estimators and say so in a comment. Exact imports: "
                        "`from sklearn.neural_network import MLPRegressor, MLPClassifier` (proposed method), "
                        "`from sklearn.linear_model import LinearRegression, LogisticRegression` and "
                        "`from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier` (baselines).")
        debug_prompt = f"""The experiment script failed.

```python
{code}
```

Error output (last part):
```
{error[-3000:]}
```

Fix the root cause. Remember: no network, no downloads, only numpy/pandas/scipy/scikit-learn/matplotlib/seaborn.{simplify}
Return the COMPLETE corrected script in ONE ```python code block."""
        if not self._llm:
            return None
        return extract_code(await self._ask(debug_prompt))

    @staticmethod
    def _extract_metrics(stdout: str) -> dict:
        """Final metrics printed by the script: the ``RESULTS_JSON: {...}`` line if present (last one wins), else
        every ``name: number`` / ``name = number`` line (a later value overwrites an earlier one, e.g. per epoch)."""
        for line in reversed((stdout or "").splitlines()):
            if line.strip().startswith("RESULTS_JSON:"):
                payload = line.split(":", 1)[1].strip()
                try:
                    data = json.loads(payload)
                except ValueError:
                    try:  # print(dict) instead of json.dumps: single quotes, True/None
                        import ast
                        data = ast.literal_eval(payload)
                    except (ValueError, SyntaxError):
                        break
                if isinstance(data, dict):
                    flat = {str(k): float(v) for k, v in data.items()
                            if isinstance(v, (int, float)) and not isinstance(v, bool)}
                    if flat:
                        return flat
                break
        metrics: dict[str, float] = {}
        for name, value in _METRIC_LINE.findall(stdout or ""):
            try:
                metrics[name.strip().replace(" ", "_")] = float(value)
            except ValueError:
                pass
        return metrics


_METRIC_LINE = re.compile(r"^\s*([A-Za-z][\w \-./()]{0,60}?)\s*[:=]\s*(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*$", re.MULTILINE)
