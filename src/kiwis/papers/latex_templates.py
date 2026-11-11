"""LaTeX templates for academic paper generation."""

from __future__ import annotations

import string
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ConferenceFormat:
    """Paper template matching NeurIPS/ICML style."""
    conference_name: str = "NeurIPS"
    year: int = 2024
    font_size: int = 10
    margin_inch: float = 1.0
    
    def get_preamble(self) -> str:
        return f"""\\documentclass[{"{font_size}"pt,letterpaper]{{article}}
\\usepackage[utf8]{{inputenc}}
\\usepackage[T1]{{fontenc}}
\\usepackage{{hyperref}}
\\usepackage{{natbib}}
\\usepackage{{amsmath,amssymb,bm}}
\\usepackage{{algorithm,algpseudocode,float,booktabs,multirow}}
\\usepackage{{pgfplots,subcaption,graphicx,geometry,caption,subfigure}}
\\usepackage{{enumitem,xcolor,mathtools,empheq,microtype,soul,tikz,adjustbox,paralist,makecell,textcomp,rotating,setspace}}
\\geometry{{margin={"{self.margin_inch}"in}}}
\\pagestyle{{fancy}}
\\renewcommand{{\\headrulewidth}}{{0pt}}
\\fancyhf{{}}
\\setlength{{\\parindent}}{{0pt}}}
\\setlength{{\\parskip}}{{6pt}}}"""

    def get_conf_specific(self) -> str:
        if "NeurIPS" in self.conference_name:
            return "\\usepackage{{{conference_neurips}}}  % NeurIPS style (loaded separately)"
        elif "ICML" in self.conference_name:
            return "\\usepackage{{{icml2024}}}  % ICML style (loaded separately)"
        return ""


@dataclass
class PaperTemplate:
    """Generates a complete paper LaTeX document from structured data."""

    title: str = "Untitled Research"
    authors: list[str] = field(default_factory=lambda: ["Author 1", "Author 2"])
    affiliations: list[str] = field(default_factory=list)
    abstract: str = ""
    sections: dict[str, str] = field(default_factory=dict)
    bibliography_entries: list[dict] = field(default_factory=list)
    tables: list[dict] = field(default_factory=list)
    figures: list[dict] = field(default_factory=list)
    format: ConferenceFormat = field(default_factory=ConferenceFormat)

    def render(self) -> str:
        """Render the complete paper as a LaTeX string."""
        
        authors_str = " & ".join(f"{{\\textbf{{{a}}}}}^{i+1}" for i, a in enumerate(self.authors))
        affiliations_str = "\n".join(
            f"{i+1} {{{aff}}}" for i, aff in enumerate(self.affiliations) if aff
        )

        bib_str = ""
        if self.bibliography_entries:
            entries = [f"@misc{{{e.get('key', 'x')},\\n  title={{{e.get('title', '')}}},\\n  year={{{e.get('year', '?')}}}\\n}}" 
                       for e in self.bibliography_entries[:20]]
            bib_str = "\\bibitem{{{no_bibs}}} Placeholder — replace with real BibTeX entries."

        tables_str = ""
        for i, tbl in enumerate(self.tables):
            caption = tbl.get("caption", f"Table {i+1}")
            content = tbl.get("content", "No data")
            tables_str += f"""\\begin{{table}}[ht]
\\centering
{content}
\\caption{{{caption}}}
\\label{{tab:{i+1}}}
\\end{{table}}

"""

        figures_str = ""
        for i, fig in enumerate(self.figures):
            caption = fig.get("caption", f"Figure {i+1}")
            placeholder = fig.get("placeholder", f"Figure {i+1}")
            figures_str += f"""\\begin{{figure}}[ht]
\\centering
\\fbox{{\\parbox{{0.8\\textwidth}}{{\\vfill\\centering{placeholder}\\vfill}}}
\\caption{{{caption}}}
\\label{{fig:{i+1}}}
\\end{{figure}}

"""

        sections_str = ""
        default_sections = ["introduction", "related_work", "methodology", "experiments", "results", "conclusion"]
        
        for section_name in default_sections:
            display_name = section_name.replace("_", " ").title()
            content = self.sections.get(section_name, f"\n\n[Section '{display_name}' — populate with analysis results.]\n")
            sections_str += f"\\section{{{display_name}}}\n{content}\n\n"

        return f"""{self.format.get_preamble()}

\\title{{{self.title}}}
\\author{{{authors_str}}}\n{{\\small\\textsuperscript{{1}}{affiliations_str} \\\\ {{{self.conference_name}, {self.format.year}}}}}

\\begin{{document}}
\\maketitle

\\begin{{abstract}}
{self.abstract or '[Abstract — fill from LLM output]'}
\\end{{abstract}}

{sections_str}
{tables_str}
{figures_str}
\\section{{Broader Impact}}
[Discuss potential positive and negative impacts of your work.]

\\begin{{thebibliography}}{{99}}
{bib_str}
\\end{{thebibliography}}

\\appendix
\\section{{Additional Materials}}
[Include proofs, extra experiments, ablation studies here.]

\\end{{document}}
"""
