# Retrieval configuration comparison

Run: `artifacts/eval/20261028-002744` - corpus `bea626ce863a0e44`, 30 labelled cases
(26 answerable, 4 refusal), provider `deterministic`, provenance `deterministic`.
Supersedes the 27-case run: three `ocr_target` cases were added after INC-002 showed the suite
could not detect scanned-document failures.

Reproduce with `python scripts/run_eval.py --all`.

## Results

| Metric | vector-only | hybrid | hybrid + rerank |
|---|---|---|---|
| recall@5 | 0.9231 | **0.9615** | 0.9231 |
| mrr | 0.8526 | 0.9167 | **0.9231** |
| ndcg | 0.8704 | **0.9281** | 0.9231 |
| context_precision | 0.9485 | **0.9529** | 0.9420 |
| faithfulness | 1.0 | 1.0 | 1.0 |
| refusal_appropriateness | 0.8667 | 0.9000 | 0.9000 |
| style_consistency | 1.0 | 1.0 | 1.0 |

## Conclusion, per axis

* **Recall no longer separates them cleanly and the winner depends on the axis**: hybrid has the
  best recall (0.9615) while hybrid+rerank has the best MRR (0.9231). With 53 chunks and
  `top_k=5`, recall is close to saturation and is the weakest signal of the three.
* **Ranking quality favours reranking**: MRR 0.8526 -> 0.9167 -> 0.9231. Fusion is the bigger
  step (+7.5%), reranking adds a further +0.7% - real but small on this corpus.
* **nDCG and context precision favour hybrid** (0.9281 / 0.9529 over hybrid+rerank's
  0.9231 / 0.9420). Part of this is INC-002: the reranker's OCR penalty, even after being made
  conditional, still costs something on scanned-document queries.
* **Refusal behaviour improves with fusion** (0.8667 -> 0.9000) and reranking adds nothing.
* **Recommendation:** default to `hybrid`. Enable reranking when top-1 accuracy is the priority
  and the corpus contains few scanned documents; measure before enabling it, because on this
  corpus it trades a small recall/precision loss for a small MRR gain. That trade is reported as
  a trade, not as a win.

## Operations (same run, cache disabled for latency)

| Field | Value |
|---|---|
| p50 latency | 4.568 ms |
| p95 latency | 6.528 ms |
| token usage (30 cases) | 1,588 |
| cache hit rate | 0.3833 (23 hits / 60 lookups, separate cached pass) |
| refusal rate | 0.2333 |
| answer compliance rate | 0.9000 |

## Honest reading of the quality numbers

Faithfulness 1.0, style 1.0 and compliance 0.90 are achieved with the **deterministic provider**,
which composes answers from verbatim retrieved sentences. Those numbers prove the pipeline never
fabricates and always obeys the output contract; they are **not** evidence about the generation
quality of a real model. Any model-backed run must be reported separately, tagged
`model-backed`, and compared against these as the pipeline floor.

Latency of a few milliseconds reflects a 53-chunk in-memory index on a developer machine; it is
not a production figure. See `docs/performance.md` for the load-bearing benchmark.
