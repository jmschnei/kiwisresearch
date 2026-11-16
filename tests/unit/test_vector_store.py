"""ChromaStore behaviour and Librarian <-> vector store integration."""

import asyncio
import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
pytest.importorskip("chromadb")

from kiwis.agents import LibrarianAgent
from kiwis.memory.vector_store import ChromaStore, MemoryRecord
from kiwis.orchestrator.pipeline import PipelineState

VOCAB = ["graph", "neural", "molecule", "federated", "privacy", "vision"]


async def fake_embed(texts):
    """Deterministic bag-of-words embedding (no model download, no network)."""
    out = []
    for t in texts:
        low = t.lower()
        vec = [float(low.count(w)) for w in VOCAB]
        out.append(vec if any(vec) else [0.01] * len(VOCAB))
    return out


def make_store(tmp_path):
    return ChromaStore(persist_dir=str(tmp_path / "chroma"), embed_fn=fake_embed)


def test_chroma_roundtrip(tmp_path):
    async def run():
        store = make_store(tmp_path)
        await store.initialize()
        ids = await store.add_documents([
            MemoryRecord("a", "graph neural network for molecule", {"title": "A", "authors": ["X", "Y"], "year": 2023}),
            MemoryRecord("b", "federated privacy learning", {"title": "B"}),
        ])
        assert ids == ["a", "b"]

        hits = await store.search("molecule graph", top_k=5)
        assert hits[0][0] == "a" and hits[0][1] > hits[1][1]

        doc = await store.get_document("a")
        assert doc.metadata["authors"] == "X, Y" and doc.metadata["year"] == 2023
        assert await store.get_document("missing") is None

        # Re-adding the same id updates instead of failing
        await store.add_documents([MemoryRecord("a", "vision", {"title": "A2"})])
        assert (await store.get_document("a")).metadata["title"] == "A2"

        assert await store.delete_documents(["a"]) == 1
        assert await store.get_document("a") is None
        await store.close()

    asyncio.run(run())


def test_search_on_empty_store(tmp_path):
    async def run():
        store = make_store(tmp_path)
        await store.initialize()
        assert await store.search("anything") == []

    asyncio.run(run())


def test_uninitialized_store_raises(tmp_path):
    with pytest.raises(RuntimeError):
        asyncio.run(make_store(tmp_path).search("x"))


def _librarian(store, papers):
    lib = LibrarianAgent(vector_store=store)

    async def arxiv(*a, **k):
        return papers

    async def s2(*a, **k):
        return [{"error": "Semantic Scholar search failed: offline"}]

    lib._search_arxiv = arxiv
    lib._search_semantic_scholar = s2
    return lib


def test_librarian_indexes_and_recalls_across_runs(tmp_path):
    async def run():
        store = make_store(tmp_path)
        run1 = [{"id": "arxiv:1", "source": "arxiv", "title": "Graph neural molecule", "authors": ["A"],
                 "year": 2024, "summary": "graph neural networks for molecule properties"}]
        out1 = await _librarian(store, run1).execute(PipelineState(research_topic="graph molecule"))
        assert out1.data["num_papers_found"] == 1  # the error entry is not counted
        assert out1.data["num_related_from_memory"] == 0

        # Second run finds a different paper, and recalls the one from run 1
        run2 = [{"id": "arxiv:2", "source": "arxiv", "title": "Federated privacy", "authors": [],
                 "year": 2024, "summary": "federated privacy"}]
        state = PipelineState(research_topic="graph molecule")
        out2 = await _librarian(store, run2).execute(state)
        assert out2.data["num_related_from_memory"] >= 1
        assert "arxiv:1" in state.artifacts["literature_papers"]

    asyncio.run(run())


def test_librarian_survives_broken_store():
    class Broken:
        async def initialize(self):
            raise RuntimeError("boom")

    out = asyncio.run(_librarian(Broken(), []).execute(PipelineState(research_topic="x")))
    assert out.state.name == "COMPLETED"


def test_factory_wires_vector_store(tmp_path):
    from kiwis.config.settings import Settings
    from kiwis.orchestrator.agent_factory import AgentFactory

    s = Settings(memory={"persist_dir": str(tmp_path / "c")})
    lib = AgentFactory(s).create("librarian")
    assert isinstance(lib._store, ChromaStore)

    off = AgentFactory(Settings(memory={"enabled": False})).create("librarian")
    assert off._store is None
