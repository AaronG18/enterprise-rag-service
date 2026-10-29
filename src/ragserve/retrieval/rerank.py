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
# Only demote a scanned chunk when a clean chunk is comparably strong. An unconditional
# penalty demotes the *only* copy of a scanned document, which measurably dropped MRR on
# scanned-document queries from 0.78 to 0.33 and produced refusals (see docs/diagnosis/).
OCR_COMPARABLE_MARGIN = 0.08
# Applied when the chunk's language does not match the question's. Measured: after the corpus
# grew, an English question about rate limits was answered from the Chinese copy of the same
# specification, because shared numerals gave the wrong-language chunk a higher feature score.
# A soft penalty rather than a filter: a Chinese answer can legitimately contain the codes an
# English question asks for.
LANGUAGE_MISMATCH_PENALTY = 0.22
WEIGHTS = {
    "overlap": 0.45,
    "heading": 0.25,
    "proximity": 0.20,
    "prior": 0.10,
}


def detect_language(text: str) -> str:
    """Which language a question is written in, by CJK share."""
    if not text:
        return "en"
    cjk = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    return "zh" if cjk / len(text) > 0.2 else "en"


class DeterministicReranker:
    """Feature-based reranker. No model, no network - and every score is explainable, which
    is what EPIC 8 diagnosis needs when a reranker causes a precision change."""

    def score(self, query: str, chunk) -> float:
        query_tokens = set(_stem_all(tokenize(query)))
        if not query_tokens:
            return 0.0
        chunk_tokens = set(_stem_all(tokenize(chunk.text)))
        overlap = len(query_tokens & chunk_tokens) / len(query_tokens)

        heading_tokens = set(_stem_all(tokenize(chunk.section)))
        heading = len(query_tokens & heading_tokens) / len(query_tokens)

        return (WEIGHTS["overlap"] * overlap
                + WEIGHTS["heading"] * heading
                + WEIGHTS["proximity"] * _proximity(query, chunk.text))

    def rerank(self, query: str, candidates: List) -> List:
        scores = [(candidate, self.score(query, candidate)) for candidate in candidates]
        question_language = detect_language(query)

        def penalty_for(chunk, base: float) -> float:
            penalty = 0.0
            if getattr(chunk, "language", None) and chunk.language != question_language:
                penalty += LANGUAGE_MISMATCH_PENALTY
            return penalty + self._ocr_penalty(chunk, base, scores)

        adjusted = [(chunk, base - penalty_for(chunk, base)) for chunk, base in scores]
        # Tie-break on chunk_id: Chunk objects are not orderable, and an unstable tie-break
        # would make "deterministic ranking" a lie.
        adjusted.sort(key=lambda item: (-item[1], item[0].chunk_id))
        return adjusted

    def _ocr_penalty(self, chunk, base: float, scores) -> float:
        """Demote a scanned chunk only when a clean chunk is comparably strong.

        An unconditional penalty demotes the *only* copy of a scanned document, which measurably
        dropped MRR on scanned-document queries (see docs/diagnosis/).
        """
        if not chunk.ocr:
            return 0.0
        comparable_clean = any(
            other is not chunk and not other.ocr and abs(other_base - base) <= OCR_COMPARABLE_MARGIN
            for other, other_base in scores)
        return OCR_PENALTY if comparable_clean else 0.0


_SUFFIXES = ("ies", "ing", "ed", "es", "s")


def _stem(token: str) -> str:
    """Crude suffix stripping for the reranker only.

    Measured reason: without it, a question asking "how often are vendors reassessed" did not
    match the section heading "Reassessment", so a document that merely mentioned "third
    parties" outranked the document that actually answers the question. The embeddings and the
    lexical index are left untouched, so this changes reranking only.
    """
    if len(token) <= 4:
        return token
    for suffix in _SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: -len(suffix)]
    return token


def _stem_all(tokens) -> List[str]:
    return [_stem(token) for token in tokens]


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
