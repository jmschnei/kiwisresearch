"""Create the configured vector store backend."""

from __future__ import annotations

import os
import re
from typing import Optional

from .vector_store import EmbedFn, VectorStore

BACKENDS = ("chroma", "qdrant", "pgvector")
VECTOR_URL_ENV = "KIWIS_VECTOR_URL"  # server URL (qdrant) or DSN (pgvector); keeps credentials out of YAML


# One store per (backend, location, collection) for the whole process. Embedded Qdrant allows a single client
# per folder, and every other backend would otherwise open a new connection pool for each research job.
_STORES: dict[tuple, VectorStore] = {}


def reset_store_cache() -> None:
    """Forget cached stores (tests). Open stores are not closed."""
    _STORES.clear()


def create_vector_store(memory, embed_fn: Optional[EmbedFn] = None, embed_tag: Optional[str] = None) -> VectorStore:
    """Build the store selected by ``memory.vector_store`` (a ``MemoryConfig``).

    Vectors from different embedders are not comparable (different meaning, often different dimensions), so
    the collection/table name carries an embedder tag: ``<collection>_<tag>``. ``embed_tag`` names the embedder
    behind ``embed_fn`` (e.g. "openai"); without ``embed_fn`` the store's own default is tagged instead.
    """
    backend = memory.vector_store.lower()
    if backend not in BACKENDS:
        raise ValueError(f"Unknown vector store '{memory.vector_store}'. Supported: {', '.join(BACKENDS)}")
    tag = embed_tag or ("default" if backend == "chroma" else "hash")
    name = re.sub(r"[^A-Za-z0-9_]", "_", f"{memory.collection}_{tag}")
    url = memory.url or os.environ.get(VECTOR_URL_ENV)
    if backend == "pgvector" and not url:
        raise ValueError(f"pgvector needs a PostgreSQL DSN: set memory.url or the {VECTOR_URL_ENV} environment variable")

    location = url or os.path.abspath(memory.persist_dir)
    cache_key = (backend, location, name)
    if cache_key in _STORES:
        return _STORES[cache_key]

    if backend == "chroma":
        from .vector_store import ChromaStore
        store: VectorStore = ChromaStore(persist_dir=memory.persist_dir, collection_name=name, embed_fn=embed_fn)
    elif backend == "qdrant":
        from .qdrant_store import QdrantStore
        store = QdrantStore(
            url=url, path=None if url else os.path.join(memory.persist_dir, "qdrant"),
            collection_name=name, embed_fn=embed_fn, api_key=os.environ.get("QDRANT_API_KEY"),
        )
    else:
        from .pgvector_store import PgVectorStore
        store = PgVectorStore(dsn=url, table=name, embed_fn=embed_fn)
    _STORES[cache_key] = store
    return store
