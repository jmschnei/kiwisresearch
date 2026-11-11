"""Example: Running the Kiwis Research pipeline programmatically."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


async def example_basic_run():
    """Run the full research pipeline for a given topic."""
    from kiwis.orchestrator.pipeline import ResearchPipeline
    
    print("=" * 60)
    print("Kiwis Research - Example Pipeline Run")
    print("=" * 60)
    
    # Create and build the pipeline
    pipeline = ResearchPipeline()
    pipeline.build_default_pipeline()
    
    # Define your research topic
    topic = (
        "Can contrastive learning improve few-shot generalization "
        "in vision-language models for medical imaging?"
    )
    
    print(f"\n📋 Research Topic: {topic}\n")
    print("🔄 Running pipeline...\n")
    
    # Run the pipeline
    state = await pipeline.run(topic)
    
    # Print results
    print("=" * 60)
    print("📊 Pipeline Results")
    print("=" * 60)
    print(f"Hypothesis: {state.hypothesis[:100]}...")
    print(f"Papers Reviewed: {len(state.literature_review.get('papers', []))}")
    print(f"Experiment Plan: {list(state.experiment_plan.keys())}")
    print(f"Execution Status: {state.execution_results.get('status', 'N/A')}")
    print(f"Analysis Conclusions: {state.analysis.get('conclusions', [])[:3]}")
    print(f"Paper PDF: {state.paper_draft.get('pdf_path', 'Not compiled')}")
    print(f"Timeline:")
    for step in state.timeline:
        print(f"  [{step['phase']}] {step['status']} ({step['duration_seconds']}s)")
    
    if state.errors:
        print(f"\n⚠️ Errors encountered: {len(state.errors)}")
        for err in state.errors[:3]:
            print(f"  - {err}")
    
    return state


async def example_custom_pipeline():
    """Create a custom pipeline with modified configuration."""
    from kiwis.orchestrator.pipeline import ResearchPipeline, PipelinePhase
    
    print("\n" + "=" * 60)
    print("Custom Pipeline Example")
    print("=" * 60)
    
    pipeline = ResearchPipeline()
    
    # Add only specific phases for a lighter run
    pipeline.add_node(
        "hypothesis_gen",
        PipelinePhase.HYPOTHESIS,
        lambda state: None,  # No-op placeholder
    )
    pipeline.add_node(
        "literature_only",
        PipelinePhase.LITERATURE,
        lambda state: None,
        depends_on=[PipelinePhase.HYPOTHESIS],
    )
    
    print("Custom pipeline built with hypothesis + literature phases only")


async def main():
    """Run all examples."""
    try:
        await example_basic_run()
        await example_custom_pipeline()
    except Exception as e:
        print(f"\n⚠️ Example execution error: {e}")
        print("This is expected if LLM API keys are not configured.")


if __name__ == "__main__":
    asyncio.run(main())
