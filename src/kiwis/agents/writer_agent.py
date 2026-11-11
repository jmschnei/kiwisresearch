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

    def __init__(self, llm_provider=None, model_config=None):
        super().__init__("writer-agent")
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
            response = await self._llm.chat(msgs, config)
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
        output_dir = Path("/tmp/kiwis_output")
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
                ["pdflatex", "-interaction=nonstopmode", str(paper_path)],
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
        
        # Build bibliography string
        bib_entries = "\n".join([
            f"@misc{{{entry['key']},\n  title={{{entry['text'].split('.')[0]}}},\n}}" 
            for entry in bibliography[:30]
        ])

        tex_content = f"""\\documentclass[10pt,letterpaper]{{"article"}}
\\usepackage[utf8]{{{{"inputenc"}}}}
\\usepackage[T1]{{{{"fontenc"}}}}
\\usepackage{{{{hyperref}}}}
\\usepackage{{{{natbib}}}}
\\usepackage{{{{amsmath}},{ "amssymb" }, { "bm" }}}
\\usepackage{{{{algorithm}},{ "algpseudocode}},{ "float}},{ "booktabs}},{ "multirow}},{ "pgfplots}},{ "subcaption}},{ "graphicx}},{ "geometry}},{ "caption}},{ "subfigure}},{ "enumitem}},{ "xcolor}}
\\usepackage{{{{threeparttable}},{ "mathtools}},{ "empheq}},{ "microtype}},{ "soul}},{ "tikz}},{ "adjustbox}},{ "paralist}},{ "makecell}},{ "textcomp}},{ "rotating}},{ "setspace}},{ "hyperref}},{ "url}},{ "fancyhdr}},{ "titlesec}},{ "xurl}},{ "lineno}},{ "footmisc}},{ "csquotes}}

\\geometry{{margin=1in}}
\\pagestyle{{{{"fancy"}}}}
\\renewcommand{{\\headrulewidth}}{{0pt}}
\\fancyhf{{}}
\\setlength{{\\parindent}}{{0pt}}}
\\setlength{{\\parskip}}{{6pt}}}

\\title{{{paper_data.get('title', 'Untitled')}}}
\\author{{Kiwis Research System}}
\\date{{2024}}

\\begin{{document}}
\\maketitle

\\begin{{abstract}}
{sections.get('abstract', paper_data.get('abstract', ''))}
\\end{{abstract}}

\\section{{Introduction}}
{sections.get('introduction', '')}

\\section{{Related Work}}
{sections.get('related_work', '')}

\\section{{Methodology}}
{sections.get('methodology', '')}

\\section{{Experiments}}
{sections.get('experiments', '')}

\\section{{Results}}
{sections.get('results', '')}

\\section{{Analysis}}
{sections.get('analysis', '')}

\\section{{Conclusion}}
{sections.get('conclusion', '')}

\\begin{{thebibliography}}{{99}}
{bib_entries if bib_entries else '\\bibitem{{{no_bibs}}} No bibliography entries provided.'}
\\end{{thebibliography}}

\\end{{document}}
"""
        return tex_content
