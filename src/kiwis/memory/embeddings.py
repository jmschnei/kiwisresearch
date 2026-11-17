"""Dependency-free fallback embedder.

Qdrant and pgvector do not embed text themselves. When no embedding provider is available (no OpenAI key),
stores fall back to this hashed bag-of-words embedder: deterministic, offline and fast, but lexical only
(no semantic similarity). Vectors from different embedders are not comparable, so the store factory puts an
embedder tag in the collection name.
"""

from __future__ import annotations

import hashlib
import math
import re

HASH_DIM = 384
_TOKEN = re.compile(r"\w+", re.UNICODE)


def hash_embed_one(text: str, dim: int = HASH_DIM) -> list[float]:
    vec = [0.0] * dim
    for token in _TOKEN.findall(text.lower()):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        n = int.from_bytes(digest, "big")
        vec[n % dim] += 1.0 if (n >> 63) & 1 else -1.0  # signed hashing reduces collision bias
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        vec[0] = 1.0  # empty/untokenizable text still needs a valid (non-zero) cosine vector
        return vec
    return [v / norm for v in vec]


async def hash_embed(texts: list[str]) -> list[list[float]]:
    return [hash_embed_one(t) for t in texts]
