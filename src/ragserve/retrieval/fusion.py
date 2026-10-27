"""Reciprocal Rank Fusion.

Why RRF and not a weighted sum of raw scores: cosine similarities and BM25 scores live on
different, incomparable scales. Fusing raw scores means the fusion weights have to be
re-tuned whenever either retriever changes. RRF only uses ranks, so both retrievers
contribute on equal footing and no calibration is needed.
"""
from __future__ import annotations

from typing import Dict, List, Sequence, Tuple


def reciprocal_rank_fusion(ranked_lists: Sequence[Sequence[Tuple[str, float]]],
                            k: int = 60) -> List[Tuple[str, float]]:
    """`ranked_lists` is a sequence of (chunk_id, score) lists, best first."""
    fused: Dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, (chunk_id, _score) in enumerate(ranked, start=1):
            fused[chunk_id] = fused.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return sorted(fused.items(), key=lambda item: (-item[1], item[0]))
