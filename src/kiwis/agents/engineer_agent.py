"""Engineer Agent (Coder, Executor, Debugger).

Writes Python scripts, runs experiments, analyzes tracebacks, and fixes bugs iteratively.
"""

from __future__ import annotations

import json
import re
from .base import AgentContext, AgentOutput, AgentState, BaseAgent


class EngineerAgent(BaseAgent):
    ROLE = "engineer"
    DESCRIPTION = (
        "You are the Engineering agent. You write production-quality Python code for experiments, "
        "execute them in a sandbox, analyze any errors or tracebacks, and iteratively fix bugs until "
        "the experiment runs successfully."
    )

    SYSTEM_PROMPT = """You are the Engineer Agent for a scientific research system.

Your responsibilities:
1. Write clean, well-documented Python code implementing the experimental design
2. Execute code in the sandbox environment
3. Analyze any errors/tracebacks and propose fixes
4. Implement iterative debugging until experiments complete successfully
5. Generate artifacts (plots, metrics, results files)

Coding standards:
- Use type hints throughout
- Include docstrings for all public functions
- Log key information with descriptive messages
- Save intermediate results to disk
- Set random seeds for reproducibility
- Create proper experiment directory structure

When debugging:
1. Read the full traceback carefully
2. Identify the root cause (not just symptoms)
3. Propose a minimal fix
4. Test the fix in the next iteration
5. Document what was wrong and how it was fixed

Respond with code and analysis as needed. For errors, provide:
```json
{
  "action": "fix_bug" | "new_code" | "run_experiment",
  "code": "...",  // Python code to write (if applicable)
  "filename": "...",  // Target file path
  "error_analysis": "Explanation of the bug and fix",
  "next_action": "What to do after this step"
}
```"""

    def __init__(self, llm_provider=None, model_config=None, sandbox=None):
        super().__init__("engineer-agent")
        self._llm = llm_provider
        self._model_config = model_config
        self._sandbox = sandbox
        self._bug_count = 0
        self._max_debug_iterations = 5

    async def execute(self, context: AgentContext) -> AgentOutput:
        self.state = AgentState.RUNNING
        
        plan = context.experiment_plan
        hypothesis = context.hypothesis or "No hypothesis"
        
        # Generate the code based on experimental plan
        methodology = plan.get("methodology", {})
        datasets = plan.get("datasets", [])
        metrics = plan.get("metrics", [])
        
        prompt = f"""Implement this experiment. 

Hypothesis: {hypothesis}

Methodology steps: {json.dumps(methodology, indent=2)}
Datasets: {json.dumps(datasets[:3], indent=2)}
Metrics to track: {json.dumps([m.get('name') for m in metrics], indent=2)}

Write the complete experiment code with:
1. Data loading and preprocessing
2. Model/architecture implementation
3. Training loop
4. Evaluation
5. Result visualization and saving

Use standard practices: argparse configs, logging, checkpoints."""

        if self._llm:
            from ..models.base import ChatMessage, ModelConfig
            config = self._model_config or ModelConfig(model_name="gpt-4o", temperature=0.2)
            msgs = [
                ChatMessage(role="system", content=self.SYSTEM_PROMPT),
                ChatMessage(role="user", content=prompt),
            ]
            response = await self._llm.chat(msgs, config)
        else:
            response_text = "# Engineer placeholder"

        # Try to extract and execute code
        code_match = re.search(r'```(?:python)?\s*\n(.*?)```', response_text, re.DOTALL)
        
        if code_match:
            code = code_match.group(1)
            
            # Execute in sandbox
            if self._sandbox:
                result = await self._sandbox.execute_python(code, filename="experiment.py")
                
                if result.status.name == "SUCCESS":
                    context.execution_results["status"] = "success"
                    context.execution_results["stdout"] = result.stdout[:5000]
                    
                    # Try to extract metrics from output
                    metrics_found = self._extract_metrics(result.stdout)
                    if metrics_found:
                        context.execution_results["metrics"] = metrics_found
                    
                    self._bug_count = 0
                else:
                    # Debug and retry
                    context.execution_results["status"] = "failed"
                    context.execution_results["stderr"] = result.stderr[:5000]
                    
                    # Analyze error and generate fix
                    debug_code = await self._debug_and_fix(code, result)
                    if debug_code:
                        code = debug_code
                        result = await self._sandbox.execute_python(code, filename="experiment.py")
                        
                        context.execution_results["status"] = "completed_after_debug" if result.status.name == "SUCCESS" else "still_failed"
                        context.execution_results["debug_iterations"] = self._bug_count
            
            # Save artifacts
            context.artifacts["experiment_code"] = code
        else:
            response_text = f"# Engineer output:\n{response_text}"

        self.state = AgentState.COMPLETED
        self.output = AgentOutput(
            agent_name=self.name,
            state=AgentState.COMPLETED,
            data={
                "bug_count": self._bug_count,
                "experiment_status": context.execution_results.get("status", "unknown"),
                "artifacts_generated": len([a for a in context.artifacts.values() if a.endswith((".png", ".csv", ".json"))]),
            },
        )
        return self.output

    async def _debug_and_fix(self, code: str, result) -> str | None:
        """Generate a fix for the observed error."""
        self._bug_count += 1
        
        error = result.stderr or result.error_traceback or "Unknown error"
        
        debug_prompt = f"""The experiment code failed with this error:

```python
{code}
```

Error output:
```
{error[:3000]}
```

Debug the error and provide a fixed version of the code. Explain what was wrong and how you fixed it.
Return ONLY the corrected Python code inside a ```python block.
"""
        
        if self._llm:
            from ..models.base import ChatMessage, ModelConfig
            config = self._model_config or ModelConfig(model_name="gpt-4o", temperature=0.1)
            msgs = [
                ChatMessage(role="system", content=self.SYSTEM_PROMPT),
                ChatMessage(role="user", content=debug_prompt),
            ]
            response = await self._llm.chat(msgs, config)
            
            fix_match = re.search(r'```(?:python)?\s*\n(.*?)```', response, re.DOTALL)
            if fix_match:
                return fix_match.group(1)
        
        return None

    def _extract_metrics(self, stdout: str) -> dict:
        """Extract numeric metrics from experiment output."""
        import re as re_mod
        patterns = [
            (r'(?:val_?|test_?)?[a-z_]+[_-]?(?:acc(?:uracy)?|loss|f1|precision|recall|bleu|rouge|mse|mae|rmse|auc|r2)\s*[=:]\s*([0-9]+\.[0-9]+)', 'generic'),
            (r'(?:epoch|step)\s*(\d+)\s+loss\s+([0-9]+\.[0-9]+)\s+(?:val_loss\s+)?([0-9]+\.[0-9]+)?', 'training_loop'),
        ]
        
        metrics = {}
        for pattern, metric_type in patterns:
            matches = re_mod.findall(pattern, stdout, re_mod.IGNORECASE)
            if matches:
                for match in matches:
                    if isinstance(match, tuple):
                        for val in match:
                            if val and val != 'None':
                                try:
                                    key = f"{metric_type}_{len(metrics)}"
                                    metrics[key] = float(val)
                                except ValueError:
                                    pass
                    else:
                        try:
                            key = f"{metric_type}_{len(metrics)}"
                            metrics[key] = float(match)
                        except ValueError:
                            pass
        
        return metrics
