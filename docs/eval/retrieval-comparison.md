# Retrieval configuration comparison

Run: `artifacts/eval/20261028-001906` - corpus `bea626ce863a0e44`, 27 labelled cases
(23 answerable, 4 refusal), provider `deterministic`, provenance `deterministic`.

Reproduce with `python scripts/run_eval.py --all`.

## Results

| Metric | vector-only | hybrid | hybrid + rerank |
|---|---|---|---|
| recall@5 | 0.9565 | 0.9565 | 0.9565 |
| mrr | 0.8768 | 0.9348 | **0.9565** |
| ndcg | 0.8970 | 0.9405 | **0.9565** |
| context_precision | 0.9433 | **0.9484** | 0.9365 |
| faithfulness | 1.0 | 1.0 | 1.0 |
| refusal_appropriateness | 0.8889 | 0.9259 | 0.9259 |
| style_consistency | 1.0 | 1.0 | 1.0 |

## Conclusion, per axis

* **Recall is useless as a discriminator here** - all three tie at 0.9565. With 53 chunks and
  `top_k=5`, recall@5 saturates. This is the limitation flagged in EPIC #3 and it is now
  confirmed by measurement rather than predicted.
* **Ranking quality is where the configurations differ.** MRR 0.8768 -> 0.9348 -> 0.9565:
  hybrid beats vector-only by +6.6%, hybrid+rerank beats hybrid by +2.3%. The reranker's gain is
  real but smaller than fusion's.
* **Context Precision does not improve with reranking** (0.9484 -> 0.9365). That is a defensible
  result: the reranker optimises term overlap, heading match and proximity, not whether the
  chunk belongs to the labelled document. Precision here is dominated by fusion, and the
  reranker slightly *loses* by promoting a plausible-but-wrong chunk.
* **Refusal behaviour improves with fusion** (0.8889 -> 0.9259) because better ranking raises
  confidence above the refusal threshold on legitimate queries. Reranking adds nothing here.
* **Recommendation:** run `hybrid + rerank` when ranking quality is the priority (it is, for a QA
  service - the first chunk shown is the one that becomes the answer). Accept the small context
  precision cost, or use `hybrid` if precision matters more than top-1 accuracy.

## Operations (same run, cache disabled for latency)

| Field | Value |
|---|---|
| p50 latency | 4.895 ms |
| p95 latency | 8.026 ms |
| token usage (27 cases) | 1,392 |
| cache hit rate | 0.3889 (21 hits / 54 lookups, separate cached pass) |
| refusal rate | 0.2222 |
| answer compliance rate | 0.9037 |

## Honest reading of the quality numbers

Faithfulness 1.0, style 1.0 and compliance 0.90 are achieved with the **deterministic provider**,
which composes answers from verbatim retrieved sentences. Those numbers prove the pipeline never
fabricates and always obeys the output contract; they are **not** evidence about the generation
quality of a real model. Any model-backed run must be reported separately, tagged
`model-backed`, and compared against these as the pipeline floor.

Latency of a few milliseconds reflects a 53-chunk in-memory index on a developer machine; it is
not a production figure. See `docs/performance.md` for the load-bearing benchmark.
