"""``kiwis check``: verify that everything a research run needs is in place, before spending time on a run.

Checks, for the given settings: each agent's LLM provider (API key present, or Ollama reachable with the model
pulled), the Ollama embedding model, the code sandbox, LaTeX and the experiment libraries. With ``ping=True`` it
also sends a one-line prompt to every distinct (provider, model) in use; without it, no model is called.
"""

from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass
from importlib.util import find_spec


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    required: bool = True  # optional checks warn but do not fail the run


def _model_names(tags: list[str]) -> set[str]:
    """Ollama reports "llama3.2:3b" / "nomic-embed-text:latest"; a bare name means ":latest"."""
    names = set(tags)
    names.update(t[: -len(":latest")] for t in tags if t.endswith(":latest"))
    return names


async def _ollama_tags(base_url: str) -> list[str] | None:
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(base_url.rstrip("/") + "/api/tags")
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        return None


async def run_checks(settings, ping: bool = False) -> list[Check]:
    from .config.agents import AgentRole
    from .models.base import ChatMessage, ModelConfig
    from .models.factory import create_provider, infer_provider_name

    results: list[Check] = []
    registry = settings.providers
    in_use: dict[tuple[str, str], list[str]] = {}  # (provider, model) -> agents
    for role in AgentRole:
        cfg = settings.agents.get_agent(role)
        if not cfg.enabled:
            continue
        provider = cfg.provider or infer_provider_name(cfg.model)
        model = cfg.model.split("/", 1)[1] if cfg.model.lower().startswith("ollama/") else cfg.model
        in_use.setdefault((provider, model), []).append(role.value)

    tags_cache: dict[str, list[str] | None] = {}
    for (provider, model), roles in sorted(in_use.items()):
        label = f"{provider}:{model} ({', '.join(roles)})"
        pcfg = registry.providers.get(provider)
        if pcfg is None:
            results.append(Check(label, False, f"provider '{provider}' is not configured"))
            continue
        if pcfg.provider_type.value == "ollama":
            base = os.getenv("OLLAMA_BASE_URL") or pcfg.base_url or "http://localhost:11434"
            if base not in tags_cache:
                tags_cache[base] = await _ollama_tags(base)
            tags = tags_cache[base]
            if tags is None:
                results.append(Check(label, False, f"Ollama not reachable at {base}: start it with `ollama serve`"))
                continue
            if model not in _model_names(tags):
                results.append(Check(label, False, f"model not pulled: run `ollama pull {model}`"))
                continue
            detail = f"pulled; context window {pcfg.context_window or 'default'}, timeout {pcfg.timeout_seconds or 'default'}s"
        else:
            env = pcfg.api_key_env_var
            if env and not os.environ.get(env):
                results.append(Check(label, False, f"set {env}"))
                continue
            detail = "API key set" if env else "no key needed"
        if ping:
            try:
                llm = create_provider(provider, registry)
                t0 = time.monotonic()
                reply = await llm.chat([ChatMessage("user", "Reply with the single word: ready")],
                                       ModelConfig(model_name=model, temperature=0.0, max_tokens=256))
                detail += f"; ping {time.monotonic() - t0:.1f}s -> {reply.content.strip()[:40]!r}"
                if hasattr(llm, "close"):
                    await llm.close()
            except Exception as e:
                results.append(Check(label, False, f"ping failed: {e}"))
                continue
        results.append(Check(label, True, detail))

    # literature-memory embeddings through Ollama
    ollama = registry.providers.get("ollama")
    if settings.memory.enabled and ollama is not None and ollama.embedding_model:
        base = os.getenv("OLLAMA_BASE_URL") or ollama.base_url or "http://localhost:11434"
        tags = tags_cache.get(base) if base in tags_cache else await _ollama_tags(base)
        ok = tags is not None and ollama.embedding_model in _model_names(tags)
        results.append(Check(f"embeddings ollama:{ollama.embedding_model}", ok,
                             "pulled" if ok else f"run `ollama pull {ollama.embedding_model}` (or remove embedding_model)",
                             required=False))

    # sandbox for generated experiment code
    if not settings.sandbox.network_isolated:
        results.append(Check("sandbox network", False, "ENABLED: generated experiment code can access the internet "
                             "(and, in Docker's bridge network, your local network) to download data", required=False))
    if settings.sandbox.mode == "docker":
        from .execution.docker_sandbox import docker_available
        ok = docker_available()
        results.append(Check("sandbox docker", ok,
                             "Docker answers (the kiwis-sandbox image is built on first use)" if ok else
                             "no Docker daemon: start Docker/Colima, or the run falls back to the isolated sandbox",
                             required=False))
    else:
        missing = [m for m in ("numpy", "pandas", "sklearn", "matplotlib") if find_spec(m) is None]
        results.append(Check("sandbox isolated", not missing,
                             "experiment libraries installed (no network/filesystem isolation)" if not missing else
                             f"missing {', '.join(missing)}: pip install -e '.[experiments]'", required=False))

    results.append(Check("pdflatex", shutil.which("pdflatex") is not None,
                         "found" if shutil.which("pdflatex") else "not found: the paper is delivered as .tex only",
                         required=False))
    return results


def format_report(results: list[Check]) -> str:
    lines = []
    for r in results:
        mark = "OK  " if r.ok else ("FAIL" if r.required else "WARN")
        lines.append(f"[{mark}] {r.name}: {r.detail}")
    failed = [r for r in results if not r.ok and r.required]
    lines.append("Ready to run." if not failed else f"{len(failed)} required check(s) failed.")
    return "\n".join(lines)
