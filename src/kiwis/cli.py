"""Command-line interface for Kiwis Research."""

from __future__ import annotations

import asyncio
import argparse
import logging
import sys
from pathlib import Path

from .config.settings import Settings


def setup_logging(level: str = "INFO"):
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
        stream=sys.stdout,
    )


async def run_research(topic: str, config_path: str | None = None, iterations: int = 1):
    """Run the full research pipeline for a given topic."""
    from .config.settings import Settings
    from .orchestrator.pipeline import ResearchPipeline
    
    settings = Settings.from_file(config_path) if config_path else Settings.default()
    setup_logging(settings.logging.level)
    
    logger = logging.getLogger("kiwis.cli")
    logger.info(f"Starting research for: {topic}")
    
    pipeline = ResearchPipeline(settings=settings)
    pipeline.build_default_pipeline()
    
    for i in range(iterations):
        logger.info(f"Iteration {i+1}/{iterations}")
        state = await pipeline.run(topic)
        logger.info(f"Iteration {i+1} complete. Errors: {len(state.errors)}")
        if state.errors:
            logger.error("Errors encountered:")
            for err in state.errors:
                logger.error(f"  - {err}")
    
    return state


def main():
    parser = argparse.ArgumentParser(
        prog="kiwis",
        description="Multi-Agent Scientific Research Automation System",
    )
    subparsers = parser.add_subparsers(dest="command")
    
    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize a new Kiwis project")
    init_parser.add_argument("project_name", nargs="?", default="kiwis-project", help="Project name")
    
    # Research command
    research_parser = subparsers.add_parser("research", help="Run the research pipeline")
    research_parser.add_argument("topic", help="Research topic")
    research_parser.add_argument("-c", "--config", help="Path to config file", default=None)
    research_parser.add_argument("-n", "--iterations", type=int, default=1, help="Number of iterations")
    
    # Generate command
    gen_parser = subparsers.add_parser("generate", help="Generate code for a specific agent")
    gen_parser.add_argument("agent", choices=["ideation", "librarian", "architect", "engineer", "analyst", "writer", "reviewer"])
    gen_parser.add_argument("-o", "--output", help="Output directory", default=".")
    
    args = parser.parse_args()
    
    if args.command == "init":
        from pathlib import Path
        project_dir = Path(args.project_name)
        project_dir.mkdir(exist_ok=True)
        
        # Create default config
        config_file = project_dir / "kiwis_config.yaml"
        config_file.write_text("""# Kiwis Research Configuration
project_name: "{name}"

pipeline:
  max_iterations: 3
  hypothesis_generation_rounds: 3
  literature_review_papers_max: 20
  peer_review_critique_rounds: 2
  auto_submit_threshold: null

sandbox:
  mode: docker  # docker | isolated
  timeout_seconds: 600
  memory_mb: 4096
  network_isolated: true
  
logging:
  level: INFO
  format: "default"
""".format(name=args.project_name))
        
        logger = logging.getLogger("kiwis.cli")
        setup_logging()
        logger.info(f"Project initialized at {project_dir}")
        logger.info(f"Config written to {config_file}")
        
    elif args.command == "research":
        state = asyncio.run(run_research(args.topic, config_path=args.config, iterations=args.iterations))
    
    elif args.command == "generate":
        logger = logging.getLogger("kiwis.cli")
        setup_logging()
        agent_map = {
            "ideation": "IdeationAgent",
            "librarian": "LibrarianAgent", 
            "architect": "ExperimentArchitectAgent",
            "engineer": "EngineerAgent",
            "analyst": "DataAnalystAgent",
            "writer": "WriterAgent",
            "reviewer": "ReviewerAgent",
        }
        agent_class = agent_map.get(args.agent, "BaseAgent")
        logger.info(f"Code generation for {agent_class} -> {args.output}")
        
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
