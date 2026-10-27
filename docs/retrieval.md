# Retrieval design (EPIC #3)

## Pipeline

```
query -> tokenise (CN chars+bigrams / EN words, numbers kept)
      -> dense:  hashing embeddings (512d, seeded) + cosine
      -> lexical: BM25 over the same tokeniser
      -> fusion:  Reciprocal Rank Fusion (rank-based, k=60)
      -> rerank:  deterministic feature reranker (config-gated)
      -> top_k results with per-source scores attached
```

Every stage is behind a provider interface, so a real embedding model or a cross-encoder
reranker replaces the default without callers changing (INV-2).

## Decisions

| Decision | Alternative rejected | Why | Cost accepted |
|---|---|---|---|
| Hashing embeddings as the default provider | hosted embedding API | the default path must be hermetic and reproducible (INV-1); a hosted API makes every quality number unreproducible and untestable in CI | semantic quality is lower than a trained embedder; the corpus is synthetic and small, so the gap is not the limiting factor |
| Brute-force cosine scan | ANN index (HNSW/IVF) | the corpus is tens of chunks; ANN would add recall approximation to a system whose whole point is measurable retrieval quality | O(n) per query - irrelevant at this corpus size, would need revisiting at millions of chunks |
| Reciprocal Rank Fusion | weighted sum of raw scores | cosine and BM25 scores are on incomparable scales; raw-score fusion needs re-calibration whenever either retriever changes | RRF discards score magnitude, so a very strong single hit counts the same as a marginal one |
| Deterministic feature reranker | cross-encoder / LLM reranker | testable offline, and every score is explainable - EPIC 8 needs to attribute a precision change to a cause | weaker than a learned reranker; the interface exists so a stronger one can be dropped in |
| Reranker retains a 0.10 fused prior | rerank score alone | a weak reranker must not be able to discard a strong fused hit on its own | the reranker cannot fully override retrieval |

## Configuration (no code change to switch)

`configs/retrieval.json`:

| Field | Effect |
|---|---|
| `mode` | `vector_only` or `hybrid` |
| `rerank_enabled` | reranker on/off |
| `top_k`, `candidate_k`, `rerank_candidates` | result depth, candidate depth, rerank window |
| `rrf_k` | RRF damping constant |
| `vector_dim`, `seed` | embedding dimension and hashing seed |

## Measured behaviour (labelled cases)

`tests/data/retrieval_cases.json` - 10 cases, 5 EN / 5 ZH, expected `doc_id` known:

| Configuration | Recall@5 | Top-1 |
|---|---|---|
| vector-only | 9/10 | 9/10 |
| hybrid | 9/10 | 9/10 |
| hybrid + rerank | 9/10 | 9/10 |

Provenance: `deterministic`. The three configurations tie on this set, and the single miss is
the same in all three ("maximum payload size accepted by the ingest endpoint").

**Measured caveat about the embeddings:** hashing vectors collide, so an unrelated query still
scores ~0.11 against unrelated chunks while true matches start around 0.14. That margin is too
thin to threshold on, so no score cut-off is applied here; weak collision hits are handled
downstream by the coverage gate in EPIC 4.

**That tie is the honest result, not a bug being hidden.** With 10 cases the set cannot
discriminate between configurations - a tie is the expected outcome. EPIC #6 must expand the
labelled set and switch to graded metrics (MRR / nDCG) before any claim like "hybrid beats
vector-only" is published. Claiming a winner from 10 cases would be exactly the kind of
number this repository forbids (RULES R3).
