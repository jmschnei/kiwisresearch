"""Writer Agent.

Writes the final paper in standard academic format and compiles PDF via LaTeX.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from .base import AgentContext, AgentOutput, AgentState, BaseAgent


class WriterAgent(BaseAgent):
    ROLE = "writer"
    DESCRIPTION = (
        "You are the Writing agent. You write a complete academic paper in standard conference format "
        "(NeurIPS/ICML style) including Abstract, Introduction, Related Work, Methodology, Results, "
        "and Conclusion sections. You also compile the final PDF via LaTeX."
    )

    SYSTEM_PROMPT = """You are the Writer agent for a scientific research automation system.

Write a complete, publication-quality academic paper with the following structure:

1. **Abstract** (~200 words): Problem, approach, key results, impact
2. **Introduction**: Motivation, contributions (bullet list), paper organization
3. **Related Work**: Organized by theme, critical comparison to existing methods
4. **Methodology**: Detailed description, algorithms, theoretical guarantees if applicable
5. **Experiments**: Dataset description, baselines, implementation details, hyperparameters
6. **Results**: Quantitative results (tables), qualitative analysis, ablation studies
7. **Analysis/Discussion**: Why the method works, limitations, failure modes
8. **Conclusion**: Summary of contributions, future work

Writing standards:
- Formal academic tone
- Clear and precise language
- Proper section numbering and cross-references
- All claims supported by evidence or citations
- Consistent notation throughout
- Use LaTeX formatting for all math equations
- Generate properly formatted tables (LaTeX tabular)
- Figure captions describe findings, not just the plot

Citation format: Use numeric references [1], [2], etc. with a bibliography at the end.

Respond in this structure:
```json
{
  "title": "...",
  "abstract": "...",
  "sections": {
    "introduction": "...",
    "related_work": "...",
    "methodology": "...",
    "experiments": "...",
    "results": "...",
    "analysis": "...",
    "conclusion": "..."
  },
  "bibliography_entries": [
    {"key": "author_year", "text": "Full citation in conference format"}
  ],
  "tables": [
    {"caption": "...", "content": "LaTeX tabular code"}
  ],
  "figures": [
    {"caption": "...", "placeholder": "Figure X: ..."}
  ]
}
```"""

    def __init__(self, llm_provider=None, model_config=None, output_dir=None):
        super().__init__("writer-agent")
        self._output_dir = output_dir
        self._llm = llm_provider
        self._model_config = model_config

    async def execute(self, context: AgentContext) -> AgentOutput:
        self.state = AgentState.RUNNING
        
        paper_draft = {
            "hypothesis": context.hypothesis,
            "literature_summary": context.literature_review.get("summary", ""),
            "experiment_plan": context.experiment_plan,
            "execution_results": context.execution_results,
            "analysis": context.analysis,
        }
        
        prompt = f"""Write a complete academic paper based on the following research work.

Research Topic: {context.research_topic}
Hypothesis: {context.hypothesis}

Literature Summary:
{context.literature_review.get("summary", "N/A")[:2000]}

Experiment Plan:
{json.dumps(context.experiment_plan.get("methodology", {}), indent=2, default=str)[:1500]}

Execution Results:
{json.dumps(context.execution_results.get("metrics", context.execution_results), indent=2, default=str)[:2000]}

Analysis and Conclusions:
{json.dumps(context.analysis.get("conclusions", []), indent=2, default=str)[:1000]}

Generate a complete paper with all sections, properly formatted in LaTeX-compatible JSON structure.
Ensure the narrative is coherent and compelling."""

        if self._llm:
            from ..models.base import ChatMessage, ModelConfig
            config = self._model_config or ModelConfig(model_name="gpt-4o", temperature=0.4)
            msgs = [
                ChatMessage(role="system", content=self.SYSTEM_PROMPT),
                ChatMessage(role="user", content=prompt),
            ]
            response_text = (await self._llm.chat(msgs, config)).content
        else:
            response_text = "# Writer placeholder"

        # Parse paper content
        try:
            match = re.search(r'```(?:json)?\s*\n(.*?)```', response_text, re.DOTALL)
            paper_data = json.loads(match.group(1)) if match else {}
        except Exception:
            paper_data = {"title": "Untitled", "abstract": "", "sections": {}, "tables": [], "figures": []}

        # Generate LaTeX document
        latex_content = self._generate_latex(paper_data, context)
        
        # Save artifacts
        output_dir = Path(self._output_dir) if self._output_dir else Path("/tmp/kiwis_output")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        paper_path = output_dir / "paper.tex"
        with open(paper_path, "w") as f:
            f.write(latex_content)
        
        json_path = output_dir / "paper_draft.json"
        with open(json_path, "w") as f:
            json.dump(paper_data, f, indent=2, default=str)

        context.paper_draft.update({
            "latex_path": str(paper_path),
            "json_path": str(json_path),
            "content": paper_data,
        })
        
        # Compile PDF if LaTeX compiler is available
        latex_compiled = False
        try:
            from ..execution.sandbox import ExecutionResult
            import subprocess
            result = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", paper_path.name],
                cwd=str(paper_path.parent),
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0:
                pdf_path = paper_path.with_suffix(".pdf")
                latex_compiled = True
                context.paper_draft["pdf_path"] = str(pdf_path)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        self.state = AgentState.COMPLETED
        self.output = AgentOutput(
            agent_name=self.name,
            state=AgentState.COMPLETED,
            data={
                "title": paper_data.get("title", "Untitled"),
                "sections_written": list(paper_data.get("sections", {}).keys()),
                "num_tables": len(paper_data.get("tables", [])),
                "latex_compiled": latex_compiled,
                "pdf_available": latex_compiled,
            },
        )
        return self.output

    def _generate_latex(self, paper_data: dict, context: AgentContext) -> str:
        """Generate LaTeX document from parsed paper data."""
        
        sections = paper_data.get("sections", {})
        tables = paper_data.get("tables", [])
        bibliography = paper_data.get("bibliography_entries", [])
        
        # Build bibliography (thebibliography items)
        bib_entries = "\n".join(
            f"\\bibitem{{{entry.get('key', f'ref{i+1}')}}} {entry.get('text', '')}"
            for i, entry in enumerate(bibliography[:30])
        )
        title = paper_data.get("title", "Untitled")
        abstract = sections.get("abstract", paper_data.get("abstract", ""))
        bib_block = bib_entries or "\\bibitem{none} No bibliography entries provided."

        def sec(name: str, key: str) -> str:
            return f"\\section{{{name}}}\n{sections.get(key, '')}\n"

        body = "\n".join([
            sec("Introduction", "introduction"),
            sec("Related Work", "related_work"),
            sec("Methodology", "methodology"),
            sec("Experiments", "experiments"),
            sec("Results", "results"),
            sec("Analysis", "analysis"),
            sec("Conclusion", "conclusion"),
        ])
        tex_content = (
            "\\documentclass[10pt,letterpaper]{article}\n"
            "\\usepackage[utf8]{inputenc}\n"
            "\\usepackage[T1]{fontenc}\n"
            "\\usepackage{hyperref,natbib,amsmath,amssymb,bm}\n"
            "\\usepackage{algorithm,algpseudocode,float,booktabs,multirow}\n"
            "\\usepackage{graphicx,geometry,caption,subcaption,fancyhdr,xcolor}\n"
            "\\geometry{margin=1in}\n"
            "\\pagestyle{fancy}\n"
            "\\renewcommand{\\headrulewidth}{0pt}\n"
            "\\fancyhf{}\n"
            "\\setlength{\\parindent}{0pt}\n"
            "\\setlength{\\parskip}{6pt}\n\n"
            f"\\title{{{title}}}\n"
            "\\author{Kiwis Research System}\n"
            "\\date{\\today}\n\n"
            "\\begin{document}\n\\maketitle\n\n"
            f"\\begin{{abstract}}\n{abstract}\n\\end{{abstract}}\n\n"
            f"{body}\n"
            f"\\begin{{thebibliography}}{{99}}\n{bib_block}\n\\end{{thebibliography}}\n\n"
            "\\end{document}\n"
        )
        return tex_content
