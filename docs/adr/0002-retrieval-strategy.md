# ADR 0002: retrieval strategy - hybrid with Reciprocal Rank Fusion

## Status

Accepted. Default configuration is `hybrid` with reranking available behind a config flag.

## Context

At least two retrieval modes are required, and the three configurations (vector-only, hybrid,
hybrid+rerank) must be compared quantitatively. Dense retrieval alone loses exact-term matches
(status codes, byte limits, identifiers), which are common in policy and specification corpora.

## Decision

* Two retrievers run in hybrid mode: hashing-based dense vectors (cosine) and BM25.
* Fusion by **Reciprocal Rank Fusion** (k=60), rank-based.
* Reranking is a separate, independently toggleable stage behind a provider interface.
* Default shipped configuration: `hybrid` (reranking on is supported; measured trade-off below).

## Alternatives rejected

| Alternative | Why rejected |
|---|---|
| Weighted sum of raw cosine and BM25 scores | the two scores are on incomparable scales; every change to either retriever forces re-calibration of the weight |
| Dense-only with a stronger embedder | does not fix exact-term matching, and a hosted embedder breaks the hermetic requirement (INV-1) |
| BM25 only | no semantic matching; paraphrases and cross-lingual queries fail |
| ANN index instead of brute force | corpus is tens of chunks; approximation adds recall risk with no measurable benefit here |

## Measured consequences

| Configuration | recall@5 | mrr | ndcg | context_precision |
|---|---|---|---|---|
| vector-only | 0.9231 | 0.8526 | 0.8704 | 0.9485 |
| hybrid | **0.9615** | 0.9167 | **0.9281** | **0.9529** |
| hybrid + rerank | 0.9231 | **0.9231** | 0.9231 | 0.9420 |

Fusion is the large win (MRR 0.8526 -> 0.9167). Reranking adds a small MRR gain and a small
recall/precision loss on this corpus, partly because of the OCR penalty interaction documented in
INC-002.

## Cost accepted

* RRF discards score magnitude, so a very strong single hit does not outrank two mediocre ones.
* Two indexes are held in memory; irrelevant at this corpus size, relevant at millions of chunks.
* Ranking quality on this corpus is close to saturation, so differences between configurations
  are small and some are within noise. Conclusions are reported per metric axis rather than as a
  single winner.
