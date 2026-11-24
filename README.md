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
│  OpenAI · Anthropic Claude · DeepSeek · Ollama (local) ││
└─────────────────────────────────────────────────────────┘
```

## Agents

| Agent | Role | Model | Temperature | Description |
|-------|------|-------|-------------|-------------|
| **Ideation** | Hypothesis Generation | gpt-6.2-sol | 0.7 | Proposes novel, viable research questions |
| **Librarian** | RAG Literature Review | gpt-6.2-sol | 0.2 | Queries arXiv/Semantic Scholar, synthesizes SoTA |
| **Experiment Architect** | Methodology Design | gpt-6.2-sol | 0.4 | Designs experiments, defines metrics & baselines |
| **Engineer** | Code + Debugging | gpt-6.2-sol | 0.2 | Writes code, runs experiments, fixes bugs iteratively |
| **Data Analyst** | Results Analysis | gpt-6.2-sol | 0.3 | Statistical analysis, visualization, conclusions |
| **Writer** | Paper Writing | gpt-6.2-sol | 0.4 | Academic paper in NeurIPS/ICML format + LaTeX PDF |
| **Reviewer** | Adversarial Peer Review | claude-opus-5-5 | 0.1 | Simulates NeurIPS/ICML reviewer for rigorous critique |

Model IDs are defaults in `kiwis_config.yaml` (central list: `src/kiwis/models/defaults.py`). Temperatures only reach
models that support sampling (DeepSeek, Ollama, older OpenAI models); current OpenAI gpt-6.x and Claude models are
reasoning models with fixed sampling, so it is not sent to them, and their `max_tokens` (default 32000) also covers
their reasoning.


> 💡 **Hybrid mode**: Assign cloud models to creative tasks (writing, ideation) and local Ollama models to analytical tasks (code generation, analysis) — cutting API costs by 60-80%.

## Quick Start

### Installation

```bash
# Clone and install
git clone <repo-url>
cd kiwis-research
pip install -e ".[dev]"
```

Extras: `api` (dashboard backend), `pgvector` (PostgreSQL memory), `experiments` (pandas, scipy, scikit-learn,
seaborn, plotly: libraries the generated experiment code may import when it runs in the `isolated` sandbox; the
`docker` sandbox image already has them), `dev` (tests and linters).

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

### Web Dashboard

```bash
pip install -e ".[api]"
kiwis serve -c kiwis_config.yaml      # FastAPI backend on http://localhost:8000
cd ui && npm install && npm run dev   # dashboard on http://localhost:3000
```

Launch a research from the home page, follow the agents live, and read the paper, review scores and artifacts on the
results page. See [`ui/README.md`](ui/README.md) for the pages and the data flow.

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
| `agents.*.model` | Model per agent | `gpt-6.2-sol` |
| `agents.*.temperature` | Creativity per agent (see table above) | varies |
| `memory.vector_store` | Vector database (`chroma`, `qdrant`, `pgvector`) | `chroma` |

## Environment Variables

Required API keys:

```bash
export OPENAI_API_KEY="sk-..."        # For OpenAI models
export ANTHROPIC_API_KEY="sk-ant-..." # For Claude (reviewer agent)
export DEEPSEEK_API_KEY="sk-..."      # Optional, for DeepSeek fallback
```

Optional:

```bash
export SEMANTIC_SCHOLAR_API_KEY="..."  # Semantic Scholar rate-limits anonymous clients (HTTP 429)
export KIWIS_VECTOR_URL="..."          # Qdrant server URL or PostgreSQL DSN (pgvector); keeps credentials out of YAML
export QDRANT_API_KEY="..."            # For a protected Qdrant server
```

## Literature Memory (vector store)

Retrieved papers are indexed so later research runs can recall related work. Choose the backend with `memory.vector_store`:

| Backend | Setup |
|---------|-------|
| `chroma` (default) | Embedded, data in `memory.persist_dir`. Uses Chroma's built-in embedder unless OpenAI is available. |
| `qdrant` | Embedded (`<persist_dir>/qdrant`) or a server via `memory.url` / `KIWIS_VECTOR_URL`. |
| `pgvector` | PostgreSQL with the `vector` extension: `pip install -e ".[pgvector]"` and `KIWIS_VECTOR_URL=postgresql://user:pass@host/db`. |

Embeddings come from OpenAI when `OPENAI_API_KEY` is set. Without it, Qdrant/pgvector fall back to a built-in
hashed bag-of-words embedder (offline, lexical matching only), and Chroma to its default embedder. Collections are
named `<collection>_<embedder>` so vectors from different embedders are never mixed. All backends are covered by the same
contract tests (`tests/unit/test_vector_backends.py`; set `KIWIS_TEST_PG_DSN` to include pgvector).

## References

The paper's bibliography is built **only from papers the Librarian actually retrieved** (arXiv, Semantic Scholar, and
earlier runs recalled from the vector store). The writer is given the list with stable citation keys and may only
`\cite{key}` them; any invented key is removed automatically, and the bibliography and `references.bib` are rendered
from the retrieved metadata. The results page shows which references were cited and which invented citations were
dropped. This guarantees the references exist.

Two further passes improve quality:

- **Repair.** Sentences that lost an invented citation are reworded by the writer's model so they do not read as cut
  off (no new citations or facts allowed; if a rewrite is unsafe the plain removal is kept).
- **Claim check.** The reviewer's model reads the abstract of each cited reference and judges whether it supports the
  sentence citing it (`supported` / `partial` / `unsupported` / `unverifiable`). Problem claims go into the review
  prompt and into the writer's next revision. Only abstracts are read, so details from a paper's full text come back
  as `unverifiable`, and verdicts are advisory: nothing is deleted automatically. Skipped when no LLM is configured.

## Sandbox

Generated experiment code runs in one of two sandboxes (`sandbox.mode`):

- **`docker`**: each run is a throw-away container built from `kiwis-sandbox` (numpy, pandas, scikit-learn, matplotlib, ...;
  built automatically on first use). No network (unless `network_isolated: false`), `memory_mb` limit, 1 CPU, PID limit,
  no Linux capabilities, `no-new-privileges`; files are copied in/out, no host folder is mounted. Needs a running Docker
  daemon (the `docker` CLI; the Python SDK is not required).
- **`isolated`**: a plain subprocess with a timeout. It does **not** restrict network or filesystem access, so use it
  only with models and topics you trust.

**Network access.** With `network_isolated: true` (default) experiment code is offline and the engineer generates
synthetic data or uses datasets bundled with scikit-learn. With `network_isolated: false` the engineer is told to download
the real public dataset of the plan (direct CSV/ZIP URLs, `fetch_openml`, ...), cache it in `./data/` and print a
`DATA_SOURCE:` line; the analyst and the writer only describe the data that line reports. Packages still cannot be
installed. Be aware that model-written code then runs with internet access: in Docker it uses the default `bridge`
network, which can also reach your local network and services on the host. Use it on a machine/network where that is
acceptable; `kiwis check` warns when it is enabled. In `isolated` mode the flag only changes what the engineer is
told: nothing is blocked either way.

If `docker` is configured but no daemon answers, Kiwis logs a warning and falls back to `isolated`. LaTeX compilation
inside Docker (`DockerSandbox.compile_latex`, image `texlive/texlive:latest-small`) is implemented but not exercised by
the tests; the writer compiles the paper with the local `pdflatex`.

## Storage cleanup

Every research job keeps its files in `output/jobs/<id>/`. Nothing is deleted unless you ask:

- **Settings page → Almacenamiento** shows the space used and deletes finished jobs older than N days (or all but the
  newest N), with a preview first. API: `GET /api/v1/storage`, `POST /api/v1/storage/cleanup`.
- **Automatic retention** in `kiwis_config.yaml`: `retention: {max_age_days: 90, max_jobs: 50}`. Applied at startup and
  whenever a job is created. Only completed/failed jobs are ever removed; running and paused ones never are.

## Deployment (Docker Compose)

```bash
echo "OPENAI_API_KEY=sk-..." > .env       # any of OPENAI/ANTHROPIC/DEEPSEEK/SEMANTIC_SCHOLAR_API_KEY
docker compose up --build                 # dashboard on http://localhost:8080 (KIWIS_PORT to change)
docker compose --profile pgvector up      # also PostgreSQL + pgvector (see below)
```

- `api` (FastAPI, includes TeX Live to build the PDF; `--build-arg WITH_LATEX=0` for a slim image without PDFs) and
  `ui` (nginx serving the dashboard and proxying `/api`, `/ws`, `/health`). State lives in the `kiwis-data` volume.
  `kiwis_config.yaml` is mounted read-only: edit it and restart.
- **pgvector:** set `POSTGRES_PASSWORD` and `KIWIS_VECTOR_URL=postgresql://postgres:<password>@postgres:5432/kiwis` in
  `.env` and `memory.vector_store: pgvector` in `kiwis_config.yaml`.
- Inside the container the sandbox is `isolated` (the container is the isolation boundary). Using the `docker` sandbox
  from a container would require mounting the host's Docker socket, which gives the container root on the host, so it is
  deliberately not set up.
- **There is no authentication.** Anyone who can reach the API can spend your LLM keys and run generated code. The
  compose file publishes the dashboard on `127.0.0.1` only; put an authenticating reverse proxy in front before exposing it.

## Design Decisions

1. **Agent Swarm Pattern**: Agents communicate via a shared state bus (`AgentSwarm`), enabling decoupled collaboration without tight coupling.

2. **DAG-based Pipeline**: The `ResearchPipeline` uses topological sorting to ensure correct execution order: Hypothesis → Literature → Experiment → Execution → Analysis → Writing → Review.

3. **Sandbox Flexibility**: Two sandbox modes — Docker (full isolation) and Isolated (subprocess-based, no Docker required). Falls back gracefully.

4. **Multi-Provider LLM Support**: Abstract `LLMProvider` interface allows swapping between OpenAI, Anthropic, DeepSeek without changing agent code.

5. **Structured Agent Outputs**: Every agent returns an `AgentOutput` with standardized format, enabling predictable downstream processing.

6. **Peer Review Loop**: The reviewer runs an adversarial critique; unless the paper is accepted, the writer revises it against the review (answering each point in `revision_notes`) and the reviewer checks again. It stops when the paper is accepted, the score reaches `auto_submit_threshold`, the review gives nothing actionable, or `pipeline.peer_review_critique_rounds` reviews were done (1 = review only). Every paper version is kept (`paper_v1.tex`, `paper_v2.tex`...).

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

- [ ] Distributed execution across multiple sandbox instances
- [ ] Model evaluation benchmarking suite
- [ ] Integration with HuggingFace Datasets API
- [ ] Automatic citation management (BibTeX import/export)
- [ ] Web UI for monitoring pipeline progress
- [ ] Experiment versioning and reproducibility tracking


## Local Models with Ollama 🏠

### Quick local test run

`kiwis_config.ollama.yaml` runs every agent on a small local model (`llama3.2:3b`) with local embeddings
(`nomic-embed-text`), one review round and short replies, to check the whole pipeline end to end quickly and for free
(the output quality of a 3B model is modest):

```bash
ollama pull llama3.2:3b && ollama pull nomic-embed-text      # if not pulled yet
kiwis check    -c kiwis_config.ollama.yaml          # Ollama up? models pulled? sandbox, LaTeX? (calls no model)
kiwis check    -c kiwis_config.ollama.yaml --ping   # also loads the model once and gets a one-word reply
kiwis research -c kiwis_config.ollama.yaml "graph neural networks for molecular property prediction"
# or: kiwis serve -c kiwis_config.ollama.yaml  and start the research from the dashboard
```

CLI runs are written to `output/runs/<timestamp>-1/` (paper `.tex`/`.pdf`, `references.bib`, sandbox files,
`state.json`). For Ollama the provider settings `context_window` (Ollama's default would truncate the agents' long
prompts), `timeout_seconds` and `embedding_model` can be set under `providers.ollama`. Small models often answer with
bare JSON or prose around it; the agents accept that.

Run any model locally — no API keys, no per-token costs. Just install [Ollama](https://ollama.ai) and start a model:

```bash
# 1. Install (macOS)
brew install ollama
ollama serve

# 2. Pull your preferred models
ollama pull llama3.2          # 8B — fast, balanced quality
ollama pull mistral-nemo      # 12B — strong reasoning
ollama pull deepseek-r1       # 70B quantized — excellent for analysis
ollama pull qwen2.5-coder:7b  # 7B — code generation specialist

# 3. Use in Kiwis (set in kiwis_config.yaml)
ollama:
  enabled: true
  default_model: "llama3.2"
```

### Recommended model tiers

| Tier | Model | RAM needed | Best for |
|------|-------|-----------|----------|
| Lightweight | phi3-mini, gemma2:2b | <5 GB | Prototyping, fast iterations |
| Balanced | llama3.2, mistral-nemo, qwen2.5-coder:7b | 8-12 GB | Production use (code gen, analysis) |
| Powerful | llama3.3, deepseek-r1 | 32GB+ + GPU | Top-tier quality (reviewer, writer) |

### Cost comparison (per 1M input tokens)

| Provider | Cost | Quality tier | Best for |
|----------|------|-------------|----------|
| **OpenAI gpt-6.2-sol** | $2.00 | Production-grade | Writing, ideation |
| **Anthropic Claude Opus 5.5** | $4.00 | Reasoning champion | Adversarial review |
| **DeepSeek V4 Pro / Flash** | $0.66–1.32 / $0.15–0.30 | Near-Parity | Budget cloud fallback |
| **Ollama (any model)** | **FREE** | Depends on model | Code gen, analysis, all local |

### Suggested hybrid configurations

**Cost-conscious (80% local):**
```yaml
engineer:    llama3.2        # Code gen — local ✓
analyst:     mistral-nemo    # Stats reasoning — local ✓  
reviewer:    deepseek-r1     # Critical analysis — local ✓
ideation:    gpt-6.2-sol     # Creative — cloud (few calls)
writer:      claude-opus-5-5 # Long-form writing quality — cloud
```

**Maximum privacy (100% local):**
```yaml
engineer:    codellama:34b   # Code specialist
analyst:     llama3.3        # Strong reasoning
reviewer:    deepseek-r1     # Best local analysis
writer:      qwen2.5:72b     # Long-form generation
ideation:    mistral-nemo    # Creative reasoning
librarian:   llama3.3        # Literature synthesis
```


## License

MIT

---

*Built with 🤖 by the Kiwis Research Team at DFKI/NFDI4DS*
