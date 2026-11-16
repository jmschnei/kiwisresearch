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
        return (
            f"\\documentclass[{self.font_size}pt,letterpaper]{{article}}\n"
            "\\usepackage[utf8]{inputenc}\n"
            "\\usepackage[T1]{fontenc}\n"
            "\\usepackage{hyperref}\n"
            "\\usepackage{natbib}\n"
            "\\usepackage{amsmath,amssymb,bm}\n"
            "\\usepackage{algorithm,algpseudocode,float,booktabs,multirow}\n"
            "\\usepackage{graphicx,geometry,caption,subcaption,fancyhdr,xcolor}\n"
            f"\\geometry{{margin={self.margin_inch}in}}\n"
            "\\pagestyle{fancy}\n"
            "\\renewcommand{\\headrulewidth}{0pt}\n"
            "\\fancyhf{}\n"
            "\\setlength{\\parindent}{0pt}\n"
            "\\setlength{\\parskip}{6pt}"
        )

    def get_conf_specific(self) -> str:
        if "NeurIPS" in self.conference_name:
            return "\\usepackage{conference_neurips}  % NeurIPS style (loaded separately)"
        elif "ICML" in self.conference_name:
            return "\\usepackage{icml2024}  % ICML style (loaded separately)"
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
        for i, e in enumerate(self.bibliography_entries[:50]):
            key = e.get("key", f"ref{i+1}")
            text = e.get("text") or f"{e.get('title', 'Untitled')} ({e.get('year', '?')})"
            bib_str += f"\\bibitem{{{key}}} {text}\n"
        if not bib_str:
            bib_str = "\\bibitem{placeholder} No bibliography entries provided.\n"

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
\\fbox{{\\parbox{{0.8\\textwidth}}{{\\centering {placeholder}}}}}
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
\\author{{{authors_str}}}\n{{\\small\\textsuperscript{{1}}{affiliations_str} \\\\ {{{self.format.conference_name}, {self.format.year}}}}}

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
