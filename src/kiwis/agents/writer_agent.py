"""Writer Agent.

Writes the final paper in standard academic format and compiles PDF via LaTeX.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from ..papers.citation_verifier import format_problems
from ..papers.references import apply_repairs, bibliography_items, bibtex_file, check_citations
from .base import AgentContext, AgentOutput, AgentState, BaseAgent
from ..models.defaults import DEFAULT_MODEL
from .parsing import extract_json


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

Citations: cite ONLY the references provided in the prompt, using \\cite{key} with the exact key (several: \\cite{a,b}).
Never invent references, authors or results, and do not write a bibliography: it is generated automatically from the
cited keys. Claims you cannot support with a provided reference or with the experiment results must be stated as
hypotheses or limitations.

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
  "tables": [
    {"caption": "...", "content": "LaTeX tabular code"}
  ],
  "figures": [
    {"caption": "...", "placeholder": "Figure X: ..."}
  ]
}
```"""

    REVISION_PROMPT = """

REVISION MODE
You are revising an existing paper after a peer review. Rewrite the COMPLETE paper in the same JSON structure,
and add a "revision_notes" list answering the reviewers:
  "revision_notes": [{"issue": "the reviewer's point", "response": "what you changed, or why you did not"}]
Rules: address every "must_change" item and as many "should_improve" items as possible; keep what the reviewers praised;
never invent experimental results or citations - if a requested analysis is impossible with the available evidence,
say so honestly in the limitations instead."""

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
Ensure the narrative is coherent and compelling.

{self._references_block(context.references)}"""

        revising = self._is_revision(context)
        system_prompt = self.SYSTEM_PROMPT
        if revising:
            prompt = self._revision_prompt(context, prompt)
            system_prompt = self.SYSTEM_PROMPT + self.REVISION_PROMPT

        if self._llm:
            from ..models.base import ChatMessage, ModelConfig
            config = self._model_config or ModelConfig(model_name=DEFAULT_MODEL, temperature=0.4)
            msgs = [
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=prompt),
            ]
            response_text = (await self._llm.chat(msgs, config)).content
        else:
            response_text = "# Writer placeholder"

        # Parse paper content
        try:
            paper_data = extract_json(response_text) or {}
        except Exception:
            paper_data = {}
        if revising and not paper_data.get("sections"):
            # Unusable LLM output must not wipe out the existing paper: keep it and record the failure.
            paper_data = dict(context.paper_draft.get("content") or {})
            paper_data["revision_notes"] = [{"issue": "revision", "response": "The revision could not be parsed; the previous version was kept."}]
        elif not paper_data:
            paper_data = {"title": "Untitled", "abstract": "", "sections": {}, "tables": [], "figures": []}

        # Only real references may be cited: drop invented keys, keep a report
        paper_data.pop("bibliography_entries", None)  # never trust an LLM-written bibliography
        paper_data, citation_report = check_citations(paper_data, context.references)
        citation_report["repaired"] = await self._repair_removed_citations(paper_data, citation_report, context.references)
        paper_data["citation_report"] = citation_report

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

        version = (context.revision_round if revising else 0) + 1
        for src, name in ((json_path, f"paper_draft_v{version}.json"), (paper_path, f"paper_v{version}.tex")):
            (output_dir / name).write_text(src.read_text())
        history = [h for h in context.paper_history if h.get("version") != version]
        history.append({"version": version, "title": paper_data.get("title", "Untitled"),
                        "latex": f"paper_v{version}.tex", "json": f"paper_draft_v{version}.json",
                        "revisionNotes": paper_data.get("revision_notes", [])})
        context.paper_history = history

        if context.references:
            (output_dir / "references.bib").write_text(bibtex_file(context.references))

        context.paper_draft.update({
            "citation_report": citation_report,
            "latex_path": str(paper_path),
            "json_path": str(json_path),
            "content": paper_data,
        })
        
        # Compile PDF if LaTeX compiler is available (drop any PDF left over from a previous version)
        context.paper_draft.pop("pdf_path", None)
        paper_path.with_suffix(".pdf").unlink(missing_ok=True)
        latex_compiled = False
        try:
            from ..execution.sandbox import ExecutionResult
            import subprocess
            for _ in range(2):  # second pass resolves \cite references against the bibliography
                result = subprocess.run(
                    ["pdflatex", "-interaction=nonstopmode", paper_path.name],
                    cwd=str(paper_path.parent),
                    capture_output=True, text=True, timeout=120,
                )
                if result.returncode != 0:
                    break
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
                "version": version,
                "citations": {"cited": len(citation_report["cited"]), "unknown_removed": len(citation_report["unknown"]),
                              "available": citation_report["total"]},
                "revision": revising,
                "latex_compiled": latex_compiled,
                "pdf_available": latex_compiled,
            },
        )
        return self.output

    async def _repair_removed_citations(self, paper_data: dict, report: dict, references: list[dict]) -> int:
        """Ask the model to reword sentences that lost an invented citation so they do not read as cut off."""
        repairs = report.get("repairs") or []
        if not self._llm or not repairs:
            return 0
        from ..models.base import ChatMessage, ModelConfig
        listing = "\n".join(f"[{i}] ({r['section']}) {r['cleaned']}" for i, r in enumerate(repairs[:30]))
        prompt = ("Each sentence below had a citation removed because it pointed to a reference that does not exist, "
                  "so it may now read as cut off or lean on an unsupported claim. Reword each so it reads naturally "
                  "and only states what the paper itself supports (drop or soften the part that relied on the "
                  "removed citation). Do NOT add citations, numbers or new facts. Keep LaTeX intact. If a sentence "
                  'is fine as it is, return it unchanged.\nAnswer with JSON: {"0": "new sentence", "1": "..."}\n\n'
                  + listing)
        config = self._model_config or ModelConfig(model_name=DEFAULT_MODEL, temperature=0.2)
        try:
            text = (await self._llm.chat([ChatMessage(role="system", content="You are a careful scientific copy editor."),
                                          ChatMessage(role="user", content=prompt)], config)).content
            rewrites = {int(k): v for k, v in (extract_json(text) or {}).items()}
        except Exception:
            return 0  # the deterministic cleanup stays
        return apply_repairs(paper_data, rewrites, repairs, references)

    @staticmethod
    def _references_block(references: list[dict]) -> str:
        if not references:
            return ("AVAILABLE REFERENCES: none were retrieved. Do not cite any literature and do not invent references; "
                    "say explicitly that the related-work coverage is limited.")
        lines = []
        for r in references:
            authors = ", ".join(r["authors"][:3]) + (" et al." if len(r["authors"]) > 3 else "")
            lines.append(f"- {r['key']}: {authors} ({r['year'] or 'n.d.'}). {r['title']}. "
                         f"{r['abstract'][:220]}{'...' if len(r['abstract']) > 220 else ''}")
        return "AVAILABLE REFERENCES (cite ONLY these, as \\cite{key}):\n" + "\n".join(lines)

    @staticmethod
    def _is_revision(context: AgentContext) -> bool:
        return bool(getattr(context, "revision_round", 0) > 0 and context.review_feedback
                    and (context.paper_draft or {}).get("content"))

    @staticmethod
    def _revision_prompt(context: AgentContext, base_prompt: str) -> str:
        review = context.review_feedback[-1]
        previous = json.dumps(context.paper_draft.get("content", {}), indent=1, default=str, ensure_ascii=False)
        required = json.dumps(review.get("required_changes", []), indent=1, default=str, ensure_ascii=False)
        weaknesses = json.dumps(review.get("weaknesses", []), indent=1, default=str, ensure_ascii=False)
        return f"""{base_prompt}

=== CURRENT VERSION OF THE PAPER (revision round {context.revision_round}) ===
{previous[:14000]}

=== PEER REVIEW ===
Verdict: {review.get("overall_verdict", "unknown")}
Strengths: {json.dumps(review.get("strengths", []), default=str, ensure_ascii=False)[:1500]}
Weaknesses:
{weaknesses[:5000]}
Required changes:
{required[:3000]}
Reviewer rationale: {str(review.get("decision_rationale", ""))[:1500]}
{WriterAgent._citation_problems(context)}
Rewrite the complete paper addressing this review, and include "revision_notes"."""

    @staticmethod
    def _citation_problems(context: AgentContext) -> str:
        problems = format_problems((context.paper_draft.get("citation_report") or {}).get("verification"))
        if not problems:
            return ""
        return ("\n=== CITATION CHECK ===\nAn independent judge read the abstracts of the cited papers and found these "
                "claims not (fully) supported. Reword each claim to match what the cited paper says, cite a better "
                "reference from the list, or remove the citation:\n" + problems + "\n")

    def _generate_latex(self, paper_data: dict, context: AgentContext) -> str:
        """Generate LaTeX document from parsed paper data."""
        
        sections = paper_data.get("sections", {})
        tables = paper_data.get("tables", [])
        
        # Bibliography: only references that are actually cited, rendered from the retrieved metadata
        report = paper_data.get("citation_report") or {}
        bib_items = bibliography_items(context.references, report.get("cited", []))
        bib_entries = "\n".join(bib_items)
        title = paper_data.get("title", "Untitled")
        abstract = sections.get("abstract", paper_data.get("abstract", ""))
        bib_block = (f"\\begin{{thebibliography}}{{99}}\n{bib_entries}\n\\end{{thebibliography}}\n\n"
                     if bib_entries else "")

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
            "\\usepackage[numbers]{natbib}\n"
            "\\usepackage{hyperref,amsmath,amssymb,bm}\n"
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
            f"{bib_block}"
            "\\end{document}\n"
        )
        return tex_content
