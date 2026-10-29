"""Deterministic embedding provider.

This is a real dense vector index (fixed dimension, cosine similarity), but the vectors come
from the hashing trick instead of a hosted model. That is deliberate: the default path must be
hermetic and reproducible (INV-1), while the interface stays identical to what a real
embedding provider would expose, so swapping providers is a config change.
"""
from __future__ import annotations

import json
import math
import os
import urllib.error
import urllib.request
import zlib

from .text import tokenize


class ProviderUnavailable(Exception):
    """Raised when a configured backend (e.g. an OpenAI-compatible embedding endpoint)
    cannot be reached or is missing its credential. Callers should surface this instead of
    silently falling back, so a misconfigured production path is never mistaken for a working one.
    """


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


class OpenAICompatibleEmbeddings:
    """Real dense embeddings from an OpenAI-compatible ``/v1/embeddings`` endpoint.

    Stdlib-only (urllib): no third-party dependency, so it satisfies the "no third-party
    package" half of R7. It is off the critical path by default - the pipeline only constructs
    it when the config selects ``embedding_provider: "openai-compatible"`` - and it raises
    :class:`ProviderUnavailable` when the key is missing, so a missing credential fails loudly
    instead of degrading to the deterministic backend.

    The interface (``embed_text(text) -> list[float]``) is identical to
    :class:`HashingEmbeddings`, so swapping providers is a config change, matching the
    generation provider pattern already used by ``OpenAICompatibleProvider``.
    """

    def __init__(self, endpoint: str, api_key_env: str = "OPENAI_API_KEY",
                 model: str = "text-embedding-3-small", dim: int = 1536,
                 timeout: float = 30.0):
        if not endpoint:
            raise ProviderUnavailable(
                "embedding provider %r requires an endpoint (set embedding_endpoint)" % model)
        self.endpoint = endpoint.rstrip("/")
        self.api_key_env = api_key_env
        self.model = model
        self.dim = dim
        self.timeout = timeout
        self._cache: dict = {}

    def _api_key(self) -> str:
        key = os.environ.get(self.api_key_env, "")
        if not key:
            raise ProviderUnavailable(
                "embedding provider %r needs %s (set it, or use embedding_provider=deterministic)"
                % (self.model, self.api_key_env))
        return key

    def embed_text(self, text: str) -> list:
        cached = self._cache.get(text)
        if cached is not None:
            return cached
        key = self._api_key()
        payload = json.dumps({"input": [text], "model": self.model}).encode("utf-8")
        req = urllib.request.Request(self.endpoint + "/embeddings", data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", "Bearer " + key)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ProviderUnavailable(
                "embedding request to %s failed: %s" % (self.endpoint, exc)) from exc
        except urllib.error.URLError as exc:
            raise ProviderUnavailable(
                "embedding request to %s failed: %s" % (self.endpoint, exc)) from exc
        vec = data["data"][0]["embedding"]
        if len(vec) != self.dim:
            # Honour whatever dimension the model actually returns.
            self.dim = len(vec)
        self._cache[text] = vec
        return vec
