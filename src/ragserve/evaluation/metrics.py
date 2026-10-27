"""Deterministic metric scorers.

Why deterministic scorers are the baseline and not a compromise: a metric that cannot be
reproduced from a cold clone cannot be a gate. LLM-judged scores are supported conceptually
(provider interface) but are always reported separately and tagged `model-backed`, never mixed
into the `deterministic` baseline.

Definitions (mirrored in `docs/metrics/metrics.md`):
"""
from __future__ import annotations

import math
import re
from typing import Dict, List, Sequence

from ..retrieval.text import tokenize

SENTENCE_SPLIT = re.compile(r"(?<=[。！？!?.])\s*")
SUPPORT_THRESHOLD = 0.6


def sentences(text: str) -> List[str]:
    """Answer claims. Fragments with no word characters (stray punctuation) are not claims."""
    out = []
    for part in SENTENCE_SPLIT.split(text or ""):
        candidate = part.strip()
        if candidate and re.search(r"[\w\u4e00-\u9fff]", candidate):
            out.append(candidate)
    return out


# -- faithfulness ----------------------------------------------------------
def _is_supported(sentence: str, cited_texts: Sequence[str]) -> bool:
    tokens = set(tokenize(sentence))
    if not tokens:
        return False
    for cited in cited_texts:
        if sentence in cited:
            return True
        overlap = len(tokens & set(tokenize(cited))) / len(tokens)
        if overlap >= SUPPORT_THRESHOLD:
            return True
    return False


def faithfulness(answer_text: str, cited_texts: Sequence[str]) -> float:
    """Claim-level: fraction of answer sentences supported by the cited chunks."""
    claims = sentences(answer_text)
    if not claims:
        return 0.0
    return sum(1 for c in claims if _is_supported(c, cited_texts)) / len(claims)


# -- context precision -----------------------------------------------------
def context_precision(retrieved_chunk_ids: Sequence[str], relevant_chunk_ids: Sequence[str]) -> float:
    """Rank-weighted context precision (ragas-style).

    CP = sum_k (precision@k * rel_k) / (number of relevant chunks retrieved)

    Why not the simpler "fraction of retrieved chunks that are relevant": in this corpus a
    document has only ~2 chunks, so with top_k=5 that fraction is structurally capped near 0.4
    and could never reach the required 0.70 no matter how good retrieval is. The rank-weighted
    form measures what we actually care about - whether relevant chunks sit at the top.
    """
    relevant = set(relevant_chunk_ids)
    if not retrieved_chunk_ids or not relevant:
        return 0.0
    weight = 0.0
    hits = 0
    for rank, chunk_id in enumerate(retrieved_chunk_ids, start=1):
        if chunk_id in relevant:
            hits += 1
            weight += hits / rank
    return weight / hits if hits else 0.0


# -- ranking quality ------------------------------------------------------
def reciprocal_rank(retrieved_doc_ids: Sequence[str], expected_doc_id: str) -> float:
    for rank, doc_id in enumerate(retrieved_doc_ids, start=1):
        if doc_id == expected_doc_id:
            return 1.0 / rank
    return 0.0


def ndcg(retrieved_doc_ids: Sequence[str], expected_doc_id: str) -> float:
    """Single-relevant-item nDCG: 1/log2(rank+1). The ideal is a hit at rank 1 (1.0)."""
    for rank, doc_id in enumerate(retrieved_doc_ids, start=1):
        if doc_id == expected_doc_id:
            return 1.0 / math.log2(rank + 1)
    return 0.0


# -- answer compliance ----------------------------------------------------
def answer_compliance(result, max_chars: int = 600) -> Dict[str, object]:
    """Fraction of the output contract that is satisfied.

    The contract: citations present, every claim grounded, length within bound, language
    matches the question, answer terminates cleanly.
    """
    answer = result.answer
    checks = {
        "has_citations": bool(answer.citations),
        "grounded": faithfulness(answer.text, _cited_texts(result)) >= 0.85,
        "within_length": len(answer.text) <= max_chars,
        "language_matches": _language_matches(answer.text, result.resolved_query),
        "terminates": answer.text.rstrip().endswith((".", "。", "!", "?", "...")),
    }
    score = sum(1 for ok in checks.values() if ok) / len(checks)
    return {"score": score, "checks": checks}


def _cited_texts(result) -> List[str]:
    by_id = {c.chunk_id: c.text for c in result.retrieved}
    return [by_id[cid] for cid in result.answer.citations if cid in by_id]


def _language_matches(text: str, query: str) -> bool:
    query_has_cjk = bool(re.search(r"[\u4e00-\u9fff]", query or ""))
    text_has_cjk = bool(re.search(r"[\u4e00-\u9fff]", text or ""))
    return query_has_cjk == text_has_cjk


# -- refusal appropriateness ----------------------------------------------
def refusal_appropriateness(predicted: Sequence[bool], expected: Sequence[bool]) -> float:
    """Refuse exactly when the case says it should - both false refusals and missed refusals are errors."""
    if not expected:
        return 0.0
    correct = sum(1 for p, e in zip(predicted, expected) if p == e)
    return correct / len(expected)


# -- style consistency -----------------------------------------------------
STYLE_MIN_CHARS = 40


def style_score(answer_text: str, has_citations: bool, max_chars: int = 600) -> float:
    """Per-answer style rubric; consistency is the aggregate over a run."""
    checks = {
        "no_markdown_bullets": not re.search(r"^\s*[-*#]\s", answer_text or "", re.MULTILINE),
        "no_shouting": not re.search(r"\b[A-Z]{6,}\b", answer_text or ""),
        "sentence_case_terminal": (answer_text or "").rstrip().endswith((".", "。", "!", "?")),
        "length_in_range": STYLE_MIN_CHARS <= len(answer_text or "") <= max_chars,
        "cites_sources": has_citations,
    }
    return sum(1 for ok in checks.values() if ok) / len(checks)


def style_consistency(scores: Sequence[float]) -> float:
    return sum(scores) / len(scores) if scores else 0.0


# -- latency ---------------------------------------------------------------
def percentile(values: Sequence[float], pct: float) -> float:
    """Nearest-rank percentile. Simple enough to audit, no interpolation surprises."""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(math.ceil(pct / 100.0 * len(ordered))) - 1))
    return ordered[index]
