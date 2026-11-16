"""Abstract vector store for literature embeddings and semantic search."""

from __future__ import annotations

import abc
import asyncio
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional


@dataclass
class MemoryRecord:
    """A single entry in the knowledge base (e.g., a paper abstract)."""
    id: str
    text: str
    metadata: dict = field(default_factory=dict)
    embedding: Optional[list[float]] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class VectorStore(abc.ABC):
    """Abstract interface for a vector database."""

    @abc.abstractmethod
    async def initialize(self) -> None:
        """Set up connections and collections."""
        ...

    @abc.abstractmethod
    async def add_documents(
        self,
        records: list[MemoryRecord],
        embeddings: Optional[list[list[float]]] = None,
    ) -> list[str]:
        """Add documents to the store. Returns their IDs."""
        ...

    @abc.abstractmethod
    async def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[dict] = None,
    ) -> list[tuple[str, float]]:
        """Search by embedding. Returns (doc_id, similarity_score) tuples."""
        ...

    @abc.abstractmethod
    async def get_document(self, doc_id: str) -> MemoryRecord | None:
        """Retrieve a single document by ID."""
        ...

    @abc.abstractmethod
    async def delete_documents(self, doc_ids: list[str]) -> int:
        """Delete documents. Returns count deleted."""
        ...

    @abc.abstractmethod
    async def close(self) -> None:
        """Close connections and free resources."""
        ...


EmbedFn = Callable[[list[str]], Awaitable[list[list[float]]]]


def _clean_metadata(meta: dict) -> dict:
    """Chroma only accepts str/int/float/bool metadata values."""
    out = {}
    for k, v in (meta or {}).items():
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            out[k] = v
        elif isinstance(v, (list, tuple)):
            out[k] = ", ".join(str(x) for x in v)
        else:
            out[k] = str(v)
    return out


class ChromaStore(VectorStore):
    """ChromaDB-backed vector store.

    Chroma's client is synchronous, so every call runs in a worker thread.
    If ``embed_fn`` (e.g. ``provider.embed``) is given it is used for documents and
    queries; otherwise Chroma's built-in default embedding model is used.
    """

    def __init__(
        self,
        persist_dir: str = "./chroma_kiwis",
        collection_name: str = "kiwis_papers",
        embed_fn: Optional[EmbedFn] = None,
    ):
        self._persist_dir = persist_dir
        self._collection_name = collection_name
        self._embed_fn = embed_fn
        self._client = None
        self._collection = None

    async def initialize(self) -> None:
        if self._collection is not None:
            return

        def _init():
            import chromadb
            client = chromadb.PersistentClient(path=self._persist_dir)
            coll = client.get_or_create_collection(
                name=self._collection_name, metadata={"hnsw:space": "cosine"}
            )
            return client, coll

        self._client, self._collection = await asyncio.to_thread(_init)

    def _require(self):
        if self._collection is None:
            raise RuntimeError("ChromaStore not initialized; call initialize() first")
        return self._collection

    async def add_documents(self, records: list[MemoryRecord], embeddings=None) -> list[str]:
        """Insert or update (upsert) documents. Returns their IDs."""
        if not records:
            return []
        coll = self._require()
        if embeddings is None:
            embeddings = [r.embedding for r in records]
            if any(e is None for e in embeddings):
                embeddings = await self._embed_fn([r.text for r in records]) if self._embed_fn else None

        ids = [r.id for r in records]
        kwargs = dict(
            ids=ids,
            documents=[r.text for r in records],
            metadatas=[_clean_metadata(r.metadata) or None for r in records],
        )
        if embeddings is not None:
            kwargs["embeddings"] = embeddings
        await asyncio.to_thread(lambda: coll.upsert(**kwargs))
        return ids

    async def search(self, query: str, top_k: int = 10, filters=None) -> list[tuple[str, float]]:
        """Return (doc_id, similarity) pairs, most similar first (similarity = 1 - cosine distance)."""
        coll = self._require()
        count = await asyncio.to_thread(coll.count)
        if count == 0:
            return []
        kwargs = dict(n_results=min(top_k, count), where=filters or None)
        if self._embed_fn:
            kwargs["query_embeddings"] = await self._embed_fn([query])
        else:
            kwargs["query_texts"] = [query]
        results = await asyncio.to_thread(lambda: coll.query(**kwargs))
        return [
            (doc_id, 1.0 - float(dist))
            for doc_id, dist in zip(results["ids"][0], results["distances"][0])
        ]

    async def get_document(self, doc_id: str) -> MemoryRecord | None:
        coll = self._require()
        result = await asyncio.to_thread(lambda: coll.get(ids=[doc_id]))
        if not result["ids"]:
            return None
        return MemoryRecord(
            id=result["ids"][0],
            text=result["documents"][0],
            metadata=(result["metadatas"] or [{}])[0] or {},
        )

    async def delete_documents(self, doc_ids: list[str]) -> int:
        coll = self._require()
        if not doc_ids:
            return 0
        await asyncio.to_thread(lambda: coll.delete(ids=doc_ids))
        return len(doc_ids)

    async def close(self) -> None:
        self._collection = None
        self._client = None
