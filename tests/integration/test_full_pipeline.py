"""Integration test: Full research pipeline."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


def test_pipeline_initialization():
    """Verify pipeline can be initialized and built."""
    from kiwis.orchestrator.pipeline import ResearchPipeline
    
    pipeline = ResearchPipeline()
    pipeline.build_default_pipeline()
    
    assert len(pipeline._nodes) > 0, "Pipeline should have nodes"
    
    # Verify phases
    phases = [n.phase for n in pipeline._nodes]
    from kiwis.orchestrator.pipeline import PipelinePhase
    
    assert PipelinePhase.HYPOTHESIS in phases
    assert PipelinePhase.LITERATURE in phases
    assert PipelinePhase.EXECUTION in phases
    assert PipelinePhase.PAPER_WRITING in phases
    assert PipelinePhase.PEER_REVIEW in phases


def test_agent_instantiation():
    """Verify all agents can be instantiated."""
    from kiwis.agents import (
        IdeationAgent,
        LibrarianAgent,
        ExperimentArchitectAgent,
        EngineerAgent,
        DataAnalystAgent,
        WriterAgent,
        ReviewerAgent,
    )
    
    agents = [
        ("ideation", IdeationAgent()),
        ("librarian", LibrarianAgent()),
        ("architect", ExperimentArchitectAgent()),
        ("engineer", EngineerAgent()),
        ("analyst", DataAnalystAgent()),
        ("writer", WriterAgent()),
        ("reviewer", ReviewerAgent()),
    ]
    
    for name, agent in agents:
        assert agent.name is not None
        assert len(agent.name) > 0, f"Agent '{name}' should have a name"


def test_sandbox_instantiation():
    """Verify sandbox can be instantiated."""
    from kiwis.execution.isolated_sandbox import IsolatedSandbox
    from kiwis.execution.docker_sandbox import DockerSandbox
    
    isolated = IsolatedSandbox()
    assert isolated._timeout == 600
    
    docker = DockerSandbox()
    assert docker._image_name == "kiwis-sandbox:latest"


def test_paper_template_rendering():
    """Verify paper template generates valid LaTeX."""
    from kiwis.papers.latex_templates import PaperTemplate
    
    template = PaperTemplate(
        title="Test Paper",
        authors=["Author 1"],
        abstract="Test abstract.",
        sections={"introduction": "Test intro."},
    )
    
    latex = template.render()
    assert "\\documentclass" in latex
    assert "\\begin{document}" in latex
    assert "\\end{document}" in latex


def test_swarm_communication():
    """Verify agent swarm can communicate."""
    from kiwis.orchestrator.swarm import AgentSwarm
    
    swarm = AgentSwarm()
    swarm.register_agent("test", object())
    
    notified = asyncio.run(swarm.broadcast(
        content={"key": "value"},
        from_agent="system",
    ))
    
    assert "test" in notified


def test_visualization_functions_exist():
    """Verify visualization functions are accessible."""
    from kiwis.visualization.plots import (
        save_figure,
        create_comparison_bar_chart,
        create_learning_curve_plot,
        create_heatmap_visualization,
        create_boxplot_figure,
    )
    
    for func in [save_figure, create_comparison_bar_chart, 
                 create_learning_curve_plot, create_heatmap_visualization,
                 create_boxplot_figure]:
        assert callable(func)


if __name__ == "__main__":
    import asyncio
    
    test_pipeline_initialization()
    test_agent_instantiation()
    test_sandbox_instantiation()
    test_paper_template_rendering()
    test_visualization_functions_exist()
    asyncio.run(test_swarm_communication())
    
    print("\n✅ All integration tests passed!")
