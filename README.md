# Kiwis Research 🧪

**Multi-Agent Scientific Research Automation System**

A modular, production-ready framework that orchestrates specialized AI agents through the complete scientific research lifecycle: **Hypothesis → Literature Review → Experiment Design → Execution → Analysis → Paper Writing → Peer Review**.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1: High-Level Orchestration                      │
│  ResearchPipeline (DAG) + AgentSwarm (shared state bus) │
├─────────────────────────────────────────────────────────┤
│  Layer 2: Specialized Agents (Multi-Agent Swarm)        │
│  ┌──────────┐ ┌──────────┐ ┌──────────────┐           │
│  │ Ideation │→│Librarian │→│Architect      │           │
│  └──────────┘ └──────────┘ └──────────────┘           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │ Engineer │→│Analyst   │→│Writer    │→│Reviewer  │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ │
├─────────────────────────────────────────────────────────┤
│  Layer 3: Sandbox Execution                             │
│  DockerSandbox / IsolatedSandbox (Python + LaTeX)       │
├─────────────────────────────────────────────────────────┤
│  Layer 4: Data & Memory                                 │
│  VectorStore (ChromaDB) + ExperimentalDatabase (SQLite) │
├─────────────────────────────────────────────────────────┤
│  Layer 5: LLM Providers                                 │
│  OpenAI / Anthropic Claude / DeepSeek                    │
└─────────────────────────────────────────────────────────┘
```

## Agents

| Agent | Role | Model | Temperature | Description |
|-------|------|-------|-------------|-------------|
| **Ideation** | Hypothesis Generation | gpt-4o | 0.7 | Proposes novel, viable research questions |
| **Librarian** | RAG Literature Review | gpt-4o | 0.2 | Queries arXiv/Semantic Scholar, synthesizes SoTA |
| **Experiment Architect** | Methodology Design | gpt-4o | 0.4 | Designs experiments, defines metrics & baselines |
| **Engineer** | Code + Debugging | gpt-4o | 0.2 | Writes code, runs experiments, fixes bugs iteratively |
| **Data Analyst** | Results Analysis | gpt-4o | 0.3 | Statistical analysis, visualization, conclusions |
| **Writer** | Paper Writing | gpt-4o | 0.4 | Academic paper in NeurIPS/ICML format + LaTeX PDF |
| **Reviewer** | Adversarial Peer Review | claude-3.5s | 0.1 | Simulates NeurIPS/ICML reviewer for rigorous critique |

## Quick Start

### Installation

```bash
# Clone and install
git clone <repo-url>
cd kiwis-research
pip install -e ".[dev]"
```

### Initialize a Project

```bash
kiwis init my-research-project
cd my-research-project
```

### Run the Research Pipeline

```bash
# Basic run
kiwis research "Improving graph neural networks for molecular property prediction"

# With custom config and iterations
kiwis research -c kiwis_config.yaml -n 3 "Federated learning for medical imaging with non-IID data"
```

### Programmatic Usage

```python
from kiwis.orchestrator.pipeline import ResearchPipeline

pipeline = ResearchPipeline()
pipeline.build_default_pipeline()

state = await pipeline.run(
    research_topic="Transformer architectures for time series forecasting"
)

print(f"Hypothesis: {state.hypothesis}")
print(f"Papers reviewed: {len(state.literature_review.get('papers', []))}")
print(f"Paper PDF: {state.paper_draft.get('pdf_path')}")
```

## Project Structure

```
kiwis-research/
├── pyproject.toml              # Project configuration & dependencies
├── kiwis_config.yaml           # Default config (agent models, temperatures)
├── README.md
│
├── src/kiwis/
│   ├── __init__.py
│   ├── cli.py                  # CLI entry point
│   │
│   ├── config/                 # Layer: Configuration
│   │   ├── settings.py         # Global settings (PathsConfig, SandboxConfig)
│   │   ├── agents.py           # Agent configuration & registry
│   │   ├── llm_providers.py    # LLM provider registry
│   │   ├── llm_providers.yaml  # Provider config examples
│   │   └── agents.yaml         # Agent config examples
│   │
│   ├── models/                 # Layer: LLM Providers
│   │   ├── base.py             # Abstract LLMProvider interface
│   │   └── providers/
│   │       ├── openai_provider.py
│   │       ├── anthropic_provider.py
│   │       └── deepseek_provider.py
│   │
│   ├── memory/                 # Layer: Data & Memory
│   │   ├── vector_store.py     # VectorStore + ChromaStore
│   │   └── experimental_db.py  # SQLite-based experiment tracking
│   │
│   ├── execution/              # Layer: Sandboxed Execution
│   │   ├── sandbox.py          # Abstract CodeSandbox interface
│   │   ├── docker_sandbox.py   # Docker container sandbox
│   │   └── isolated_sandbox.py # Subprocess-based (no Docker needed)
│   │
│   ├── agents/                 # Layer: Specialized Agents
│   │   ├── base.py             # BaseAgent + AgentOutput + AgentContext
│   │   ├── ideation_agent.py
│   │   ├── librarian_agent.py
│   │   ├── experiment_architect_agent.py
│   │   ├── engineer_agent.py
│   │   ├── data_analyst_agent.py
│   │   ├── writer_agent.py
│   │   └── reviewer_agent.py
│   │
│   ├── orchestrator/           # Layer: High-Level Orchestration
│   │   ├── pipeline.py         # ResearchPipeline (DAG-based)
│   │   └── swarm.py            # AgentSwarm (shared state bus)
│   │
│   ├── papers/                 # Paper generation utilities
│   │   ├── latex_templates.py  # Conference format templates
│   │   └── formatter.py        # Result table formatting
│   │
│   └── visualization/          # Visualization tools
│       └── plots.py            # Bar charts, learning curves, heatmaps
│
├── tests/
│   ├── unit/                   # Unit tests (config, agents, execution)
│   └── integration/            # Integration tests (full pipeline)
│
├── examples/                    # Usage examples
│   ├── example_research.ipynb
│   └── example_pipeline.py
│
└── chroma_kiwis/               # Vector store persistence (gitignored)
```

## Configuration

Key configuration options in `kiwis_config.yaml`:

| Setting | Description | Default |
|---------|-------------|---------|
| `pipeline.max_iterations` | Max research iterations | 3 |
| `pipeline.literature_review_papers_max` | Max papers to retrieve | 20 |
| `sandbox.mode` | Execution mode (`docker` or `isolated`) | `docker` |
| `agents.*.model` | Model per agent | `gpt-4o` |
| `agents.*.temperature` | Creativity per agent (see table above) | varies |
| `memory.vector_store` | Vector database (`chroma`, `qdrant`, `pgvector`) | `chroma` |

## Environment Variables

Required API keys:

```bash
export OPENAI_API_KEY="sk-..."        # For OpenAI models
export ANTHROPIC_API_KEY="sk-ant-..." # For Claude (reviewer agent)
export DEEPSEEK_API_KEY="sk-..."      # Optional, for DeepSeek fallback
```

## Design Decisions

1. **Agent Swarm Pattern**: Agents communicate via a shared state bus (`AgentSwarm`), enabling decoupled collaboration without tight coupling.

2. **DAG-based Pipeline**: The `ResearchPipeline` uses topological sorting to ensure correct execution order: Hypothesis → Literature → Experiment → Execution → Analysis → Writing → Review.

3. **Sandbox Flexibility**: Two sandbox modes — Docker (full isolation) and Isolated (subprocess-based, no Docker required). Falls back gracefully.

4. **Multi-Provider LLM Support**: Abstract `LLMProvider` interface allows swapping between OpenAI, Anthropic, DeepSeek without changing agent code.

5. **Structured Agent Outputs**: Every agent returns an `AgentOutput` with standardized format, enabling predictable downstream processing.

6. **Peer Review Loop**: The reviewer runs adversarial critique; results feed back to the writer for revision (configurable number of rounds).

## Extending the System

### Adding a New Agent

```python
# 1. Create agent class in src/kiwis/agents/
class MyNewAgent(BaseAgent):
    ROLE = "my_new_role"
    
    async def execute(self, context: AgentContext) -> AgentOutput:
        # Implement your logic
        
# 2. Register in config/agents.yaml under agents.my_new_role

# 3. Add pipeline node in orchestrator/pipeline.py add_node()
```

### Adding a New LLM Provider

```python
# 1. Create provider class in src/kiwis/models/providers/
class MyProvider(LLMProvider):
    async def chat(self, messages, config) -> ChatMessage: ...
    async def generate_text(self, prompt, **kwargs) -> str: ...
    async def embed(self, texts) -> list[list[float]]: ...

# 2. Register in llm_providers.yaml under providers.my_provider
```

## Limitations & Future Work

- [ ] Full LangGraph integration for more sophisticated workflow control
- [ ] Distributed execution across multiple sandbox instances
- [ ] Model evaluation benchmarking suite
- [ ] Integration with HuggingFace Datasets API
- [ ] Automatic citation management (BibTeX import/export)
- [ ] Web UI for monitoring pipeline progress
- [ ] Experiment versioning and reproducibility tracking

## License

MIT

---

*Built with 🤖 by the Kiwis Research Team at DFKI/NFDI4DS*
