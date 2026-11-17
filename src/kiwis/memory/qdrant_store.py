"""Qdrant-backed vector store (server, or embedded local mode)."""

from __future__ import annotations

import uuid
from typing import Optional

from .embeddings import hash_embed
from .vector_store import EmbedFn, MemoryRecord, VectorStore, _clean_metadata

_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")  # fixed so ids are stable across runs


def _point_id(doc_id: str) -> str:
    """Qdrant ids must be UUIDs or unsigned ints; derive a stable UUID from the document id."""
    return str(uuid.uuid5(_NAMESPACE, doc_id))


class QdrantStore(VectorStore):
    """Qdrant store.

    Pass ``url`` for a Qdrant server, or ``path`` for embedded local storage (single process).
    Qdrant has no built-in embedder: ``embed_fn`` is used, with a hashed bag-of-words fallback.
    The collection is created on first write, with the dimension of the first embeddings.
    """

    def __init__(
        self,
        url: Optional[str] = None,
        path: Optional[str] = None,
        collection_name: str = "kiwis_papers",
        embed_fn: Optional[EmbedFn] = None,
        api_key: Optional[str] = None,
    ):
        if not url and not path:
            raise ValueError("QdrantStore needs a server `url` or a local `path`")
        self._url, self._path, self._api_key = url, path, api_key
        self._collection_name = collection_name
        self._embed_fn = embed_fn or hash_embed
        self._client = None

    async def initialize(self) -> None:
        if self._client is not None:
            return
        from qdrant_client import AsyncQdrantClient

        self._client = (
            AsyncQdrantClient(url=self._url, api_key=self._api_key) if self._url else AsyncQdrantClient(path=self._path)
        )

    def _require(self):
        if self._client is None:
            raise RuntimeError("QdrantStore not initialized; call initialize() first")
        return self._client

    async def _vector_size(self) -> Optional[int]:
        client = self._require()
        if not await client.collection_exists(self._collection_name):
            return None
        info = await client.get_collection(self._collection_name)
        vectors = info.config.params.vectors
        return vectors.size if hasattr(vectors, "size") else None

    async def _ensure_collection(self, dim: int) -> None:
        from qdrant_client import models

        existing = await self._vector_size()
        if existing is None:
            await self._require().create_collection(
                self._collection_name,
                vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE),
            )
        elif existing != dim:
            raise ValueError(
                f"Collection '{self._collection_name}' stores {existing}-dim vectors but the embedder produced {dim}. "
                "Use a different collection (or embedder) for this store."
            )

    async def add_documents(self, records: list[MemoryRecord], embeddings=None) -> list[str]:
        if not records:
            return []
        from qdrant_client import models

        client = self._require()
        if embeddings is None:
            embeddings = [r.embedding for r in records]
            if any(e is None for e in embeddings):
                embeddings = await self._embed_fn([r.text for r in records])
        await self._ensure_collection(len(embeddings[0]))

        points = [
            models.PointStruct(
                id=_point_id(r.id),
                vector=list(map(float, emb)),
                payload={**_clean_metadata(r.metadata), "_doc_id": r.id, "_text": r.text},
            )
            for r, emb in zip(records, embeddings)
        ]
        await client.upsert(self._collection_name, points=points)  # upsert: re-adding an id updates it
        return [r.id for r in records]

    @staticmethod
    def _filter(filters: Optional[dict]):
        if not filters:
            return None
        from qdrant_client import models

        return models.Filter(
            must=[models.FieldCondition(key=k, match=models.MatchValue(value=v)) for k, v in filters.items()]
        )

    async def search(self, query: str, top_k: int = 10, filters=None) -> list[tuple[str, float]]:
        client = self._require()
        if await self._vector_size() is None:
            return []
        (vector,) = await self._embed_fn([query])
        result = await client.query_points(
            self._collection_name, query=list(map(float, vector)), limit=top_k,
            query_filter=self._filter(filters), with_payload=["_doc_id"],
        )
        return [(p.payload["_doc_id"], float(p.score)) for p in result.points]  # cosine similarity

    async def get_document(self, doc_id: str) -> MemoryRecord | None:
        client = self._require()
        if await self._vector_size() is None:
            return None
        found = await client.retrieve(self._collection_name, ids=[_point_id(doc_id)], with_payload=True)
        if not found:
            return None
        payload = dict(found[0].payload)
        text = payload.pop("_text", "")
        payload.pop("_doc_id", None)
        return MemoryRecord(id=doc_id, text=text, metadata=payload)

    async def delete_documents(self, doc_ids: list[str]) -> int:
        client = self._require()
        if not doc_ids or await self._vector_size() is None:
            return 0
        from qdrant_client import models

        existing = await client.retrieve(
            self._collection_name, ids=[_point_id(d) for d in doc_ids], with_payload=False
        )
        await client.delete(
            self._collection_name, points_selector=models.PointIdsList(points=[_point_id(d) for d in doc_ids])
        )
        return len(existing)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
        self._client = None
