"""BM25 lexical retrieval.

Paired with dense vectors because dense retrieval alone loses exact-term matches: status
codes ("429"), identifiers, byte limits. Those are precisely the queries a policy corpus
gets wrong when it is only embedded.
"""
from __future__ import annotations

import math

from .text import tokenize


class BM25Index:
    def __init__(self, chunk_ids: list, documents: list, k1: float = 1.5, b: float = 0.75):
        self.chunk_ids = chunk_ids
        self.k1 = k1
        self.b = b
        self.tokens = [tokenize(doc) for doc in documents]
        self.lengths = [len(t) for t in self.tokens]
        self.avg_length = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0
        self.doc_freq: dict = {}
        for tokens in self.tokens:
            for token in set(tokens):
                self.doc_freq[token] = self.doc_freq.get(token, 0) + 1
        self.n = len(self.tokens)

    def _idf(self, token: str) -> float:
        df = self.doc_freq.get(token, 0)
        return math.log(1.0 + (self.n - df + 0.5) / (df + 0.5))

    def score(self, query_tokens: list, position: int) -> float:
        tokens = self.tokens[position]
        if not tokens:
            return 0.0
        length = self.lengths[position]
        counts: dict = {}
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1
        total = 0.0
        for token in set(query_tokens):
            freq = counts.get(token, 0)
            if not freq:
                continue
            denom = freq + self.k1 * (1 - self.b + self.b * length / max(1.0, self.avg_length))
            total += self._idf(token) * (freq * (self.k1 + 1)) / denom
        return total

    def search(self, query_tokens: list, top_n: int):
        scored = []
        for position, chunk_id in enumerate(self.chunk_ids):
            score = self.score(query_tokens, position)
            if score > 0.0:
                scored.append((chunk_id, score))
        scored.sort(key=lambda item: (-item[1], item[0]))
        return scored[:top_n]
