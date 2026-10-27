"""Reranker providers.

The interface is the point: `rerank(query, candidates)` in, reordered candidates out. The
default implementation is deterministic and feature-based (term overlap, heading match,
phrase proximity, OCR penalty), which makes it testable and free; a cross-encoder or an LLM
reranker can be dropped in behind the same interface and toggled by config.
"""
from __future__ import annotations

from typing import List

from .text import tokenize

OCR_PENALTY = 0.12
WEIGHTS = {
    "overlap": 0.45,
    "heading": 0.25,
    "proximity": 0.20,
    "prior": 0.10,
}


class DeterministicReranker:
    """Feature-based reranker. No model, no network - and every score is explainable, which
    is what EPIC 8 diagnosis needs when a reranker causes a precision change."""

    def score(self, query: str, chunk) -> float:
        query_tokens = set(tokenize(query))
        if not query_tokens:
            return 0.0
        chunk_tokens = set(tokenize(chunk.text))
        overlap = len(query_tokens & chunk_tokens) / len(query_tokens)

        heading_tokens = set(tokenize(chunk.section))
        heading = len(query_tokens & heading_tokens) / len(query_tokens)

        return (WEIGHTS["overlap"] * overlap
                + WEIGHTS["heading"] * heading
                + WEIGHTS["proximity"] * _proximity(query, chunk.text)
                - (OCR_PENALTY if chunk.ocr else 0.0))

    def rerank(self, query: str, candidates: List) -> List:
        scored = [(candidate, self.score(query, candidate)) for candidate in candidates]
        # Tie-break on chunk_id: Chunk objects are not orderable, and an unstable tie-break
        # would make "deterministic ranking" a lie.
        scored.sort(key=lambda item: (-item[1], item[0].chunk_id))
        return scored


def _proximity(query: str, text: str) -> float:
    """How tightly the query terms occur together in the passage.

    A passage mentioning all query words in one sentence is far better evidence than one
    scattering them across unrelated sentences.
    """
    normalized = text.lower()
    positions = []
    for token in set(tokenize(query)):
        idx = normalized.find(token.lower())
        if idx >= 0:
            positions.append(idx)
    if len(positions) < 2:
        return 1.0 if positions else 0.0
    span = max(positions) - min(positions) + 1
    return 1.0 / (1.0 + span / 120.0)
