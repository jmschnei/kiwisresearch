"""PostgreSQL + pgvector vector store (via asyncpg)."""

from __future__ import annotations

import json
import re
from typing import Optional

from .embeddings import hash_embed
from .vector_store import EmbedFn, MemoryRecord, VectorStore, _clean_metadata

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,62}")


def _vector_literal(vec) -> str:
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"


class PgVectorStore(VectorStore):
    """Stores documents in one PostgreSQL table with a ``vector`` column (pgvector, cosine distance).

    The table is created on first write with the dimension of the first embeddings. Embeddings come from
    ``embed_fn`` (hashed bag-of-words fallback). ``table`` is interpolated into SQL, so it must be a plain
    identifier.
    """

    def __init__(self, dsn: str, table: str = "kiwis_papers", embed_fn: Optional[EmbedFn] = None):
        if not _IDENT.fullmatch(table):
            raise ValueError(f"Invalid table name: {table!r}")
        self._dsn = dsn
        self._table = table
        self._embed_fn = embed_fn or hash_embed
        self._pool = None

    async def initialize(self) -> None:
        if self._pool is not None:
            return
        import asyncpg

        self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=4)
        async with self._pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

    def _require(self):
        if self._pool is None:
            raise RuntimeError("PgVectorStore not initialized; call initialize() first")
        return self._pool

    async def _dimension(self, conn) -> Optional[int]:
        """Dimension of the existing embedding column, or None if the table does not exist yet."""
        row = await conn.fetchrow(
            "SELECT a.atttypmod AS dim FROM pg_attribute a "
            "WHERE a.attrelid = to_regclass($1) AND a.attname = 'embedding' AND NOT a.attisdropped",
            self._table,
        )
        return None if row is None else row["dim"]

    async def _ensure_table(self, conn, dim: int) -> None:
        existing = await self._dimension(conn)
        if existing is None:
            await conn.execute(
                f"CREATE TABLE IF NOT EXISTS {self._table} ("
                f"id TEXT PRIMARY KEY, text TEXT NOT NULL, metadata JSONB NOT NULL DEFAULT '{{}}', "
                f"embedding vector({int(dim)}) NOT NULL)"
            )
            try:  # approximate index; optional (pgvector limits HNSW to 2000 dims)
                await conn.execute(
                    f"CREATE INDEX IF NOT EXISTS {self._table}_embedding_idx "
                    f"ON {self._table} USING hnsw (embedding vector_cosine_ops)"
                )
            except Exception:
                pass
        elif existing != dim:
            raise ValueError(
                f"Table '{self._table}' stores {existing}-dim vectors but the embedder produced {dim}. "
                "Use a different table (or embedder) for this store."
            )

    async def add_documents(self, records: list[MemoryRecord], embeddings=None) -> list[str]:
        if not records:
            return []
        pool = self._require()
        if embeddings is None:
            embeddings = [r.embedding for r in records]
            if any(e is None for e in embeddings):
                embeddings = await self._embed_fn([r.text for r in records])
        async with pool.acquire() as conn:
            await self._ensure_table(conn, len(embeddings[0]))
            await conn.executemany(
                f"INSERT INTO {self._table} (id, text, metadata, embedding) VALUES ($1, $2, $3::jsonb, $4::vector) "
                "ON CONFLICT (id) DO UPDATE SET text = EXCLUDED.text, metadata = EXCLUDED.metadata, "
                "embedding = EXCLUDED.embedding",
                [(r.id, r.text, json.dumps(_clean_metadata(r.metadata)), _vector_literal(e))
                 for r, e in zip(records, embeddings)],
            )
        return [r.id for r in records]

    async def search(self, query: str, top_k: int = 10, filters=None) -> list[tuple[str, float]]:
        pool = self._require()
        async with pool.acquire() as conn:
            if await self._dimension(conn) is None:
                return []
            (vector,) = await self._embed_fn([query])
            args = [_vector_literal(vector), int(top_k)]
            where = ""
            if filters:
                args.append(json.dumps(filters))
                where = "WHERE metadata @> $3::jsonb"
            rows = await conn.fetch(
                f"SELECT id, 1 - (embedding <=> $1::vector) AS similarity FROM {self._table} {where} "
                "ORDER BY embedding <=> $1::vector LIMIT $2",
                *args,
            )
        return [(r["id"], float(r["similarity"])) for r in rows]

    async def get_document(self, doc_id: str) -> MemoryRecord | None:
        pool = self._require()
        async with pool.acquire() as conn:
            if await self._dimension(conn) is None:
                return None
            row = await conn.fetchrow(f"SELECT id, text, metadata FROM {self._table} WHERE id = $1", doc_id)
        if row is None:
            return None
        meta = row["metadata"]
        return MemoryRecord(id=row["id"], text=row["text"], metadata=json.loads(meta) if isinstance(meta, str) else dict(meta))

    async def delete_documents(self, doc_ids: list[str]) -> int:
        pool = self._require()
        if not doc_ids:
            return 0
        async with pool.acquire() as conn:
            if await self._dimension(conn) is None:
                return 0
            status = await conn.execute(f"DELETE FROM {self._table} WHERE id = ANY($1::text[])", list(doc_ids))
        return int(status.split()[-1])  # "DELETE n"

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
        self._pool = None
