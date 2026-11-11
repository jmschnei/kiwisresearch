"""Tests for paper generation."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kiwis.papers.latex_templates import PaperTemplate, ConferenceFormat
from kiwis.papers.formatter import format_results_table


def test_conference_format_preamble():
    fmt = ConferenceFormat(conference_name="NeurIPS", year=2024)
    preamble = fmt.get_preamble()
    assert "\\documentclass" in preamble
    assert "article" in preamble


def test_paper_template_render():
    template = PaperTemplate(
        title="My Cool Research",
        authors=["Alice", "Bob"],
        abstract="We propose a novel method.",
        sections={
            "introduction": "Introduction text here.",
            "methodology": "Method described.",
            "results": "Results show improvement.",
        },
    )
    
    latex = template.render()
    assert "\\documentclass" in latex
    assert "My Cool Research" in latex
    assert "Alice" in latex
    assert "\\section{Introduction}" in latex


def test_results_table_formatting():
    methods = ["Our Method", "Baseline A", "Baseline B"]
    metrics = {
        "accuracy": [0.95, 0.87, 0.82],
        "f1_score": [0.93, 0.85, 0.79],
    }
    
    table = format_results_table(methods, metrics)
    assert "\\begin{table}" in table
    assert "\\toprule" in table
    assert "Our Method" in table
