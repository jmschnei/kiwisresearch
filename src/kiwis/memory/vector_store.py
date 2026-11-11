"""Abstract vector store for literature embeddings and semantic search."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Optional


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


@abc.abstractmethod
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


class ChromaStore(VectorStore):
    """ChromaDB-backed vector store implementation."""

    def __init__(self, persist_dir: str = "./chroma_kiwis"):
        self._persist_dir = persist_dir
        self._collection = None
        self._embedding_fn = None

    async def initialize(self) -> None:
        import chromadb
        client = chromadb.PersistentClient(path=self._persist_dir)
        self._collection = client.get_or_create_collection(
            name="kiwis_papers",
            metadata={"hnsw:space": "cosine"},
        )
        self._embedding_fn = lambda x: [[float(v) for v in e] for e in x]

    async def add_documents(self, records: list[MemoryRecord], embeddings=None) -> list[str]:
        if embeddings is None:
            from openai import AsyncOpenAI
            client = AsyncOpenAI()
            emb_resp = await client.embeddings.create(
                model="text-embedding-3-small", input=[r.text for r in records]
            )
            embeddings = [d.embedding for d in emb_resp.data]

        ids = [r.id for r in records]
        await self._collection.add(
            documents=[r.text for r in records],
            metadatas=[r.metadata for r in records],
            ids=ids,
        )
        return ids

    async def search(self, query: str, top_k: int = 10, filters=None) -> list[tuple[str, float]]:
        results = await self._collection.query(
            query_texts=[query],
            n_results=top_k,
            where=filters,
        )
        return [
            (id, distance)
            for id, distance in zip(results["ids"][0], results["distances"][0])
        ]

    async def get_document(self, doc_id: str) -> MemoryRecord | None:
        result = await self._collection.get(ids=[doc_id])
        if not result["ids"]:
            return None
        data = result["ids"][0]
        return MemoryRecord(
            id=data,
            text=result["documents"][0][result["ids"].index(data)],
            metadata=result["metadatas"][0] if result["metadatas"] else {},
        )

    async def delete_documents(self, doc_ids: list[str]) -> int:
        if doc_ids:
            await self._collection.delete(ids=doc_ids)
        return len(doc_ids)

    async def close(self) -> None:
        self._collection = None
