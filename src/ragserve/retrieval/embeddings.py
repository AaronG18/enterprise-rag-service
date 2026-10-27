"""Deterministic embedding provider.

This is a real dense vector index (fixed dimension, cosine similarity), but the vectors come
from the hashing trick instead of a hosted model. That is deliberate: the default path must be
hermetic and reproducible (INV-1), while the interface stays identical to what a real
embedding provider would expose, so swapping providers is a config change.
"""
from __future__ import annotations

import math
import zlib

from .text import tokenize


class HashingEmbeddings:
    """Signed hashing vectoriser. Deterministic, stateless, no training data."""

    def __init__(self, dim: int = 512, seed: int = 0):
        self.dim = dim
        self.seed = seed

    def _index_and_sign(self, token: str):
        digest = zlib.crc32(("%d:%s" % (self.seed, token)).encode("utf-8"))
        return digest % self.dim, 1.0 if (digest >> 20) & 1 else -1.0

    def embed_text(self, text: str) -> list:
        vec = [0.0] * self.dim
        for token in tokenize(text):
            idx, sign = self._index_and_sign(token)
            # Bigram/longer tokens are noisier; damp them slightly.
            weight = 1.0 if len(token) <= 2 else 0.7
            vec[idx] += sign * weight
        return _l2_normalize(vec)


def _l2_normalize(vec: list) -> list:
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        return vec
    return [v / norm for v in vec]


def cosine(a: list, b: list) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


class VectorIndex:
    """Brute-force cosine index. The corpus is small (tens to thousands of chunks); a fancy
    ANN structure would add complexity without changing any measured outcome."""

    def __init__(self, chunk_ids: list, vectors: list):
        self.chunk_ids = chunk_ids
        self.vectors = vectors

    def search(self, query_vector: list, top_n: int):
        scored = [(cid, cosine(query_vector, vec))
                  for cid, vec in zip(self.chunk_ids, self.vectors)]
        scored = [s for s in scored if s[1] > 0.0]
        scored.sort(key=lambda item: (-item[1], item[0]))
        return scored[:top_n]
