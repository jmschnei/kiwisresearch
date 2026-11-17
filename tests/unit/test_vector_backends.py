"""Contract tests run against every vector store backend, plus the embedder fallback and store factory.

Chroma and Qdrant (embedded local mode) run anywhere they are installed. pgvector needs a PostgreSQL with the
pgvector extension: set KIWIS_TEST_PG_DSN, e.g.
    docker run -d -p 55432:5432 -e POSTGRES_PASSWORD=kiwis -e POSTGRES_DB=kiwis pgvector/pgvector:pg16
    KIWIS_TEST_PG_DSN=postgresql://postgres:kiwis@localhost:55432/kiwis pytest tests/unit/test_vector_backends.py
"""

import asyncio
import os
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kiwis.config.settings import MemoryConfig, Settings
from kiwis.memory.embeddings import HASH_DIM, hash_embed, hash_embed_one
from kiwis.memory.factory import create_vector_store
from kiwis.memory.vector_store import MemoryRecord

VOCAB = ["graph", "neural", "molecule", "federated", "privacy", "vision"]
PG_DSN = os.environ.get("KIWIS_TEST_PG_DSN")


async def fake_embed(texts):
    out = []
    for t in texts:
        vec = [float(t.lower().count(w)) for w in VOCAB]
        out.append(vec if any(vec) else [0.01] * len(VOCAB))
    return out


async def fake_embed_other_dim(texts):
    return [[1.0, 0.0] for _ in texts]


def build(backend, tmp_path, embed_fn=fake_embed):
    if backend == "chroma":
        pytest.importorskip("chromadb")
        from kiwis.memory.vector_store import ChromaStore
        return ChromaStore(persist_dir=str(tmp_path / "chroma"), embed_fn=embed_fn)
    if backend == "qdrant":
        pytest.importorskip("qdrant_client")
        from kiwis.memory.qdrant_store import QdrantStore
        return QdrantStore(path=str(tmp_path / "qdrant"), embed_fn=embed_fn)
    if backend == "pgvector":
        pytest.importorskip("asyncpg")
        if not PG_DSN:
            pytest.skip("KIWIS_TEST_PG_DSN not set")
        from kiwis.memory.pgvector_store import PgVectorStore
        return PgVectorStore(PG_DSN, table="t_" + uuid.uuid4().hex[:10], embed_fn=embed_fn)
    raise AssertionError(backend)


BACKENDS = ["chroma", "qdrant", "pgvector"]


def run(coro):
    return asyncio.run(coro)


async def cleanup(store):
    if hasattr(store, "_pool") and store._pool is not None:  # drop the throwaway pgvector table
        async with store._pool.acquire() as conn:
            await conn.execute(f"DROP TABLE IF EXISTS {store._table}")
    await store.close()


@pytest.mark.parametrize("backend", BACKENDS)
def test_roundtrip(backend, tmp_path):
    async def go():
        store = build(backend, tmp_path)
        await store.initialize()
        try:
            ids = await store.add_documents([
                MemoryRecord("arxiv:1", "graph neural network for molecule", {"title": "A", "authors": ["X", "Y"], "year": 2023}),
                MemoryRecord("s2:abc", "federated privacy learning", {"title": "B", "source": "s2"}),
            ])
            assert ids == ["arxiv:1", "s2:abc"]

            hits = await store.search("molecule graph", top_k=5)
            assert hits[0][0] == "arxiv:1" and hits[0][1] > hits[1][1]  # most similar first, higher = closer

            doc = await store.get_document("arxiv:1")
            assert doc.text == "graph neural network for molecule"
            assert doc.metadata["authors"] == "X, Y" and doc.metadata["year"] == 2023
            assert await store.get_document("missing") is None

            await store.add_documents([MemoryRecord("arxiv:1", "vision", {"title": "A2"})])  # upsert
            assert (await store.get_document("arxiv:1")).metadata["title"] == "A2"

            assert await store.delete_documents(["arxiv:1", "never-existed"]) == 1
            assert await store.get_document("arxiv:1") is None
            assert [h[0] for h in await store.search("privacy", top_k=5)] == ["s2:abc"]
        finally:
            await cleanup(store)

    run(go())


@pytest.mark.parametrize("backend", BACKENDS)
def test_metadata_filter(backend, tmp_path):
    async def go():
        store = build(backend, tmp_path)
        await store.initialize()
        try:
            await store.add_documents([
                MemoryRecord("a", "graph neural", {"source": "arxiv"}),
                MemoryRecord("b", "graph neural", {"source": "s2"}),
            ])
            assert [h[0] for h in await store.search("graph", filters={"source": "s2"})] == ["b"]
        finally:
            await cleanup(store)

    run(go())


@pytest.mark.parametrize("backend", BACKENDS)
def test_empty_store_is_safe(backend, tmp_path):
    async def go():
        store = build(backend, tmp_path)
        await store.initialize()
        try:
            assert await store.search("anything") == []
            assert await store.get_document("x") is None
            assert await store.delete_documents(["x"]) == 0
            assert await store.add_documents([]) == []
        finally:
            await cleanup(store)

    run(go())


@pytest.mark.parametrize("backend", ["qdrant", "pgvector"])
def test_dimension_mismatch_is_a_clear_error(backend, tmp_path):
    async def go():
        store = build(backend, tmp_path)
        await store.initialize()
        try:
            await store.add_documents([MemoryRecord("a", "graph")])
            store._embed_fn = fake_embed_other_dim  # simulate switching embedder on an existing collection
            with pytest.raises(ValueError, match="dim"):
                await store.add_documents([MemoryRecord("b", "graph")])
        finally:
            await cleanup(store)

    run(go())


@pytest.mark.parametrize("backend", ["qdrant", "pgvector"])
def test_uninitialized_store_raises(backend, tmp_path):
    with pytest.raises(RuntimeError):
        run(build(backend, tmp_path).search("x"))


@pytest.mark.parametrize("backend", ["qdrant", "pgvector"])
def test_default_hash_embedder_finds_lexical_matches(backend, tmp_path):
    async def go():
        store = build(backend, tmp_path, embed_fn=None)  # no embedding provider configured
        await store.initialize()
        try:
            await store.add_documents([
                MemoryRecord("a", "graph neural networks for molecular property prediction"),
                MemoryRecord("b", "federated learning with differential privacy for hospitals"),
            ])
            assert (await store.search("molecular graph networks", top_k=2))[0][0] == "a"
            assert (await store.search("privacy in federated hospitals", top_k=2))[0][0] == "b"
        finally:
            await cleanup(store)

    run(go())


# ------------------------------------------------------------------ embedder + factory

def test_hash_embedder_is_deterministic_normalized_and_nonzero():
    v1, v2 = hash_embed_one("Graph neural networks"), hash_embed_one("graph NEURAL networks")
    assert v1 == v2 and len(v1) == HASH_DIM
    assert abs(sum(x * x for x in v1) - 1) < 1e-9
    assert any(hash_embed_one(""))  # empty text still yields a valid vector
    assert run(hash_embed(["a b", "c"]))[0] == hash_embed_one("a b")


def test_factory_builds_each_backend_with_embedder_tag(tmp_path):
    mem = MemoryConfig(persist_dir=str(tmp_path), collection="papers")

    chroma = create_vector_store(mem)
    assert chroma._collection_name == "papers_default"
    assert create_vector_store(mem, embed_fn=fake_embed, embed_tag="openai")._collection_name == "papers_openai"

    q = create_vector_store(MemoryConfig(vector_store="qdrant", persist_dir=str(tmp_path), collection="papers"))
    assert q._path == os.path.join(str(tmp_path), "qdrant") and q._url is None and q._collection_name == "papers_hash"
    server = create_vector_store(MemoryConfig(vector_store="qdrant", url="http://qdrant:6333"))
    assert server._url == "http://qdrant:6333" and server._path is None

    pg = create_vector_store(MemoryConfig(vector_store="pgvector", url="postgresql://u:p@h/db", collection="my-papers"))
    assert pg._table == "my_papers_hash"  # sanitized into a valid SQL identifier


def test_factory_shares_one_store_per_configuration(tmp_path):
    """Embedded Qdrant allows one client per folder, so every research job must reuse the same store."""
    mem = MemoryConfig(vector_store="qdrant", persist_dir=str(tmp_path))
    a, b = create_vector_store(mem), create_vector_store(mem)
    assert a is b
    assert create_vector_store(MemoryConfig(vector_store="qdrant", persist_dir=str(tmp_path), collection="other")) is not a
    assert create_vector_store(mem, embed_fn=fake_embed, embed_tag="openai") is not a  # different embedder, different collection


def test_two_research_jobs_share_embedded_qdrant(tmp_path, monkeypatch):
    """Regression: the 2nd job used to fail with 'storage folder is already accessed by another instance'."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    pytest.importorskip("qdrant_client")
    from kiwis.agents import LibrarianAgent
    from kiwis.orchestrator.agent_factory import AgentFactory
    from kiwis.orchestrator.pipeline import PipelineState

    settings = Settings(memory={"vector_store": "qdrant", "persist_dir": str(tmp_path)})
    paper = {"id": "arxiv:1", "title": "Graph neural networks", "authors": ["A B"], "year": 2020, "summary": "graph networks"}

    async def stub(*_a, **_k):
        return [paper]

    async def none(*_a, **_k):
        return []

    async def go():
        first = AgentFactory(settings).create("librarian")  # job 1
        first._search_arxiv, first._search_semantic_scholar = stub, none
        await first.execute(PipelineState(research_topic="graph networks"))

        second = AgentFactory(settings).create("librarian")  # job 2, separate factory like a new research job
        second._search_arxiv, second._search_semantic_scholar = none, none
        state = PipelineState(research_topic="graph networks")
        out = await second.execute(state)
        assert out.data["num_related_from_memory"] == 1  # recalled from job 1 through the shared store
        assert state.references[0]["title"] == "Graph neural networks"

    run(go())


def test_factory_reports_misconfiguration(monkeypatch):
    monkeypatch.delenv("KIWIS_VECTOR_URL", raising=False)
    with pytest.raises(ValueError, match="Unknown vector store"):
        create_vector_store(MemoryConfig(vector_store="nope"))
    with pytest.raises(ValueError, match="DSN"):
        create_vector_store(MemoryConfig(vector_store="pgvector"))
    monkeypatch.setenv("KIWIS_VECTOR_URL", "postgresql://u:p@h/db")
    assert create_vector_store(MemoryConfig(vector_store="pgvector"))._dsn == "postgresql://u:p@h/db"


def test_pgvector_rejects_unsafe_table_names():
    from kiwis.memory.pgvector_store import PgVectorStore
    with pytest.raises(ValueError):
        PgVectorStore("postgresql://x", table="papers; DROP TABLE users")


def test_agent_factory_selects_backend_and_degrades_gracefully(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    pytest.importorskip("qdrant_client")
    from kiwis.memory.qdrant_store import QdrantStore
    from kiwis.orchestrator.agent_factory import AgentFactory

    ok = AgentFactory(Settings(memory={"vector_store": "qdrant", "persist_dir": str(tmp_path)})).create("librarian")
    assert isinstance(ok._store, QdrantStore)

    for bad in ({"vector_store": "nope"}, {"vector_store": "pgvector"}):  # unknown backend / missing DSN
        monkeypatch.delenv("KIWIS_VECTOR_URL", raising=False)
        assert AgentFactory(Settings(memory=bad)).create("librarian")._store is None
