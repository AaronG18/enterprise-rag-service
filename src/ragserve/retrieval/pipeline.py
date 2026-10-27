"""Retrieval pipeline: modes, fusion, rerank toggle - all driven by `RetrievalConfig`."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .embeddings import HashingEmbeddings, VectorIndex
from .fusion import reciprocal_rank_fusion
from .lexical import BM25Index
from .rerank import DeterministicReranker
from .text import tokenize

MODES = ("vector_only", "hybrid")


@dataclass
class RetrievalConfig:
    mode: str = "hybrid"
    top_k: int = 5
    candidate_k: int = 20
    rerank_enabled: bool = True
    rerank_candidates: int = 10
    rrf_k: int = 60
    vector_dim: int = 512
    seed: int = 20261027

    @classmethod
    def from_json(cls, path: str) -> "RetrievalConfig":
        if not os.path.isfile(path):
            return cls()
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        return cls(**{k: v for k, v in raw.items() if k in cls().__dict__})


@dataclass
class Retrieved:
    chunk_id: str
    doc_id: str
    family: str
    language: str
    section: str
    text: str
    ocr: bool
    vector_score: Optional[float]
    lexical_score: Optional[float]
    fused_score: float
    rerank_score: Optional[float] = None


class RetrievalPipeline:
    """Builds indexes from corpus chunks and serves queries in the configured mode."""

    def __init__(self, corpus, config: RetrievalConfig,
                 reranker=None, embeddings=None):
        if config.mode not in MODES:
            raise ValueError("unknown retrieval mode: %r" % config.mode)
        self.config = config
        self.chunks = list(corpus.chunks)
        self.by_id: Dict[str, object] = {c.chunk_id: c for c in self.chunks}
        self.embeddings = embeddings or HashingEmbeddings(dim=config.vector_dim, seed=config.seed)
        self.vectors = [self.embeddings.embed_text(c.text) for c in self.chunks]
        self.vector_index = VectorIndex([c.chunk_id for c in self.chunks], self.vectors)
        self.lexical_index = BM25Index([c.chunk_id for c in self.chunks], [c.text for c in self.chunks])
        self.reranker = reranker or DeterministicReranker()

    # -- internals ---------------------------------------------------------
    def _vector_ranked(self, query: str):
        return self.vector_index.search(self.embeddings.embed_text(query), self.config.candidate_k)

    def _lexical_ranked(self, query: str):
        return self.lexical_index.search(tokenize(query), self.config.candidate_k)

    # -- public ------------------------------------------------------------
    def retrieve(self, query: str) -> List[Retrieved]:
        vector_ranked = self._vector_ranked(query)
        vector_scores = dict(vector_ranked)

        ranked_lists = [vector_ranked]
        lexical_scores: Dict[str, float] = {}
        if self.config.mode == "hybrid":
            lexical_ranked = self._lexical_ranked(query)
            lexical_scores = dict(lexical_ranked)
            ranked_lists.append(lexical_ranked)
        else:
            lexical_scores = {}

        fused = reciprocal_rank_fusion(ranked_lists, k=self.config.rrf_k)
        fused_scores = dict(fused)

        ordered_ids = [chunk_id for chunk_id, _ in fused][:self.config.rerank_candidates]
        candidates = [self.by_id[cid] for cid in ordered_ids]

        rerank_scores: Dict[str, float] = {}
        if self.config.rerank_enabled:
            reranked = self.reranker.rerank(query, candidates)
            # Rerank score dominates, but the fused rank stays as a tie-breaker prior so a
            # weak reranker cannot silently discard a strong fused hit.
            ordered = sorted(
                [(chunk, score + WEIGHT_PRIOR * fused_scores.get(chunk.chunk_id, 0.0))
                 for chunk, score in reranked],
                key=lambda item: (-item[1], item[0].chunk_id),
            )
            rerank_scores = {chunk.chunk_id: score for chunk, score in reranked}
            candidates = [chunk for chunk, _ in ordered]
        else:
            candidates = [self.by_id[cid] for cid in
                          [chunk_id for chunk_id, _ in fused][:self.config.top_k]]

        results: List[Retrieved] = []
        for chunk in candidates[:self.config.top_k]:
            results.append(Retrieved(
                chunk_id=chunk.chunk_id,
                doc_id=chunk.doc_id,
                family=chunk.family,
                language=chunk.language,
                section=chunk.section,
                text=chunk.text,
                ocr=chunk.ocr,
                vector_score=vector_scores.get(chunk.chunk_id),
                lexical_score=lexical_scores.get(chunk.chunk_id),
                fused_score=fused_scores.get(chunk.chunk_id, 0.0),
                rerank_score=rerank_scores.get(chunk.chunk_id),
            ))
        return results


# How much of the fused ranking survives reranking. Kept small on purpose: if this were 1.0
# the reranker would be decoration.
WEIGHT_PRIOR = 0.10


def retrieved_to_dict(item: "Retrieved") -> Dict:
    return {
        "chunk_id": item.chunk_id,
        "doc_id": item.doc_id,
        "family": item.family,
        "language": item.language,
        "section": item.section,
        "text": item.text,
        "ocr": item.ocr,
        "vector_score": item.vector_score,
        "lexical_score": item.lexical_score,
        "fused_score": item.fused_score,
        "rerank_score": item.rerank_score,
    }


def retrieved_from_dict(data: Dict) -> "Retrieved":
    return Retrieved(**{k: v for k, v in data.items() if k in Retrieved.__dataclass_fields__})
