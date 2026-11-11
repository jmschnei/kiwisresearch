"""Tests for visualization module."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


def test_save_figure_exists():
    from kiwis.visualization.plots import save_figure
    assert callable(save_figure)


def test_create_bar_chart_function_exists():
    from kiwis.visualization.plots import create_comparison_bar_chart
    assert callable(create_comparison_bar_chart)


def test_heatmap_function_exists():
    from kiwis.visualization.plots import create_heatmap_visualization
    assert callable(create_heatmap_visualization)
