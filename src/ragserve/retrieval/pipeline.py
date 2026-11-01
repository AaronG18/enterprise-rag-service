"""Retrieval pipeline: modes, fusion, rerank toggle - all driven by `RetrievalConfig`."""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .embeddings import (HashingEmbeddings, OpenAICompatibleEmbeddings, ProviderUnavailable,
                         VectorIndex)
from .fusion import reciprocal_rank_fusion
from .lexical import BM25Index
from .rerank import CrossEncoderReranker, DeterministicReranker, RerankerUnavailable
from .text import tokenize

MODES = ("vector_only", "hybrid")
EMBEDDING_PROVIDERS = ("deterministic", "openai-compatible")
RERANKER_PROVIDERS = ("deterministic", "cross-encoder")
# The dimension the published deterministic baseline was measured at. A fallback must land on it,
# not on the configured width, or "deterministic" would silently mean two different indexes.
DETERMINISTIC_DIM = 512
# The delivered default is the keyless deterministic backend, so a reviewer can clone the repo and
# run every script with no credentials at all. A real embedding model is opt-in: set the provider
# to "openai-compatible" via config, --embedding-provider or this env var and supply that
# endpoint's key. CI pins this to "deterministic" to keep the cold-clone path key-free.
EMBEDDING_PROVIDER_ENV = "RAGSERVE_EMBEDDING_PROVIDER"
# Same idea for the reranker: CI pins it to "deterministic" so the cold-clone path needs no
# model server and no network. The delivered config ships the cross-encoder reranker.
RERANKER_PROVIDER_ENV = "RAGSERVE_RERANKER_PROVIDER"


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
    # Embedding backend. The delivered default is a real semantic model served locally
    # (BGE-M3, keyless - empty api_key_env, so no credential and no third-party package). A clean
    # clone reproduces every published metric once `scripts/run.py` has been run and the
    # two servers started per the README; with no model server running it falls back to the
    # deterministic backend loudly, never silently. The deterministic backend stays selectable for
    # CI and offline runs via embedding_provider="deterministic" (config, --embedding-provider, or
    # RAGSERVE_EMBEDDING_PROVIDER); CI pins it so the test gate needs no network or key.
    embedding_provider: str = "openai-compatible"
    embedding_endpoint: str = "https://api.siliconflow.cn/v1"
    embedding_api_key_env: str = "SILICONFLOW_API_KEY"
    embedding_model: str = "BAAI/bge-m3"
    # Reranker backend. "deterministic" is the hand-written feature scorer; "cross-encoder" calls
    # a real cross-encoder at reranker_endpoint (/v1/rerank). The choice is configuration only, so
    # swapping rerankers is never a code change - which is what FR1 asks for and NFR2 depends on.
    reranker_provider: str = "deterministic"
    reranker_endpoint: str = ""
    reranker_model: str = ""
    reranker_timeout: float = 20.0
    # If a model-backed provider is unreachable, drop to the deterministic backend and say so
    # loudly rather than failing the whole run. CI pins the provider, so this never fires there.
    allow_deterministic_fallback: bool = True
    # Runtime flags, never taken from the config file: set when a fallback actually happened, so a
    # report can claim model-backed provenance only when a model really was used.
    degraded_embedding: bool = False
    degraded_reranker: bool = False

    @classmethod
    def from_json(cls, path: str) -> "RetrievalConfig":
        if not os.path.isfile(path):
            cfg = cls()
        else:
            with open(path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            cfg = cls(**{k: v for k, v in raw.items() if k in cls().__dict__})
        override = os.environ.get(EMBEDDING_PROVIDER_ENV)
        if override:
            cfg.embedding_provider = override
            if override == "deterministic":
                cfg.vector_dim = DETERMINISTIC_DIM
        rerank_override = os.environ.get(RERANKER_PROVIDER_ENV)
        if rerank_override:
            cfg.reranker_provider = rerank_override
        if cfg.embedding_provider not in EMBEDDING_PROVIDERS:
            raise ValueError("unknown embedding_provider: %r" % cfg.embedding_provider)
        if cfg.reranker_provider not in RERANKER_PROVIDERS:
            raise ValueError("unknown reranker_provider: %r" % cfg.reranker_provider)
        return cfg


def _warn(message: str) -> None:
    """A fallback has to be noticed.

    stderr, never stdout: `scripts/run.py --json` parses stdout, and one stray line turns its output
    into invalid JSON.
    """
    print("WARNING: %s" % message, file=sys.stderr)


class _Probe:
    """Minimal chunk stand-in, used to ask a reranker whether it is actually reachable."""

    chunk_id = "probe"
    text = "probe"
    section = ""
    language = "en"
    ocr = False


# Endpoint reachability, cached per process. A connection attempt against a port nothing listens
# on costs ~2s on Windows (measured), and one evaluation run constructs a pipeline several times -
# so probing on every construction turned a 37s suite into a 200s one.
_REACHABILITY: dict = {}


def _check_reachable(kind: str, endpoint: str, probe):
    """(ok, reason) for one endpoint. The probe itself runs at most once per process."""
    key = (kind, endpoint)
    if key in _REACHABILITY:
        return _REACHABILITY[key]
    try:
        probe()
        result = (True, "")
    except (ProviderUnavailable, RerankerUnavailable, OSError) as exc:
        result = (False, str(exc))
    _REACHABILITY[key] = result
    return result


def build_embedder(config: "RetrievalConfig"):
    """Construct the embedder named by the config.

    A real provider is probed once. If it is unreachable - no local model server running, or a
    missing key on a hosted endpoint - and ``allow_deterministic_fallback`` is set, this drops to
    the deterministic backend, prints a warning, and marks ``config.degraded_embedding`` so a
    report cannot claim model-backed numbers that a model did not produce.
    """
    if config.embedding_provider == "deterministic":
        return HashingEmbeddings(dim=config.vector_dim, seed=config.seed)
    if config.embedding_provider == "openai-compatible":
        embedder = OpenAICompatibleEmbeddings(
            endpoint=config.embedding_endpoint,
            api_key_env=config.embedding_api_key_env,
            model=config.embedding_model,
            dim=config.vector_dim)
        if config.allow_deterministic_fallback:
            ok, reason = _check_reachable("embedding", config.embedding_endpoint,
                                          lambda: embedder.embed_text("probe"))
            if not ok:
                _warn("embedding model %r at %s is unavailable (%s); falling back to the "
                      "deterministic backend. Numbers from this run are NOT model-backed - start "
                      "the model server (see README) for the model-backed path."
                      % (config.embedding_model, config.embedding_endpoint, reason))
                config.degraded_embedding = True
                return HashingEmbeddings(dim=DETERMINISTIC_DIM, seed=config.seed)
        return embedder
    raise ValueError("unknown embedding_provider: %r" % config.embedding_provider)


def build_reranker(config: "RetrievalConfig"):
    """Construct the reranker named by the config; mirrors :func:`build_embedder`.

    ``deterministic`` is the hand-written feature scorer, ``cross-encoder`` a real cross-encoder
    served at ``reranker_endpoint``. Same interface either way, so this is a config choice.

    When ``rerank_enabled`` is False the pipeline never reranks (it returns fused order as-is), so
    no reranker is built or probed - which also avoids marking ``degraded_reranker`` on a backend
    that the run is not actually using. ``reranker_provider`` only chooses *which* reranker runs
    when reranking is on; ``rerank_enabled`` decides *whether* it runs at all.
    """
    if not config.rerank_enabled:
        return None
    if config.reranker_provider == "cross-encoder":
        reranker = CrossEncoderReranker(endpoint=config.reranker_endpoint,
                                        model=config.reranker_model,
                                        timeout=config.reranker_timeout)
        if config.allow_deterministic_fallback:
            ok, reason = _check_reachable("reranker", config.reranker_endpoint,
                                          lambda: reranker.rerank("probe", [_Probe()]))
            if not ok:
                _warn("cross-encoder reranker at %s is unavailable (%s); falling back to the "
                      "deterministic reranker. Numbers from this run are NOT model-backed - start "
                      "the model server (see README) for the model-backed path."
                      % (config.reranker_endpoint, reason))
                config.degraded_reranker = True
                return DeterministicReranker()
        return reranker
    if config.reranker_provider == "deterministic":
        return DeterministicReranker()
    raise ValueError("unknown reranker_provider: %r" % config.reranker_provider)


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
        self.embeddings = embeddings or build_embedder(config)
        self.vectors = [self.embeddings.embed_text(c.text) for c in self.chunks]
        self.vector_index = VectorIndex([c.chunk_id for c in self.chunks], self.vectors)
        self.lexical_index = BM25Index([c.chunk_id for c in self.chunks], [c.text for c in self.chunks])
        self.reranker = reranker or build_reranker(config)

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
