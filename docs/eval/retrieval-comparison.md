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

## Model-backed comparison (BGE-M3 embeddings + bge-reranker-v2-m3 cross-encoder)

Run: `artifacts/eval/20261031-050820` - corpus `a716676ca46bfa44`, 85 labelled cases,
provider `deterministic` (generation), provenance `model-backed-retrieval`. Embeddings are the
real BGE-M3 model served locally (1024-d, keyless); the reranker is the real
bge-reranker-v2-m3 cross-encoder. Reproduce with `scripts/setup_models.py` + the two server
commands in the README, then `python scripts/run_eval.py --all`. (This is the run the section
above said must be reported separately and tagged `model-backed`.)

| Metric | vector-only | hybrid | hybrid + rerank |
|---|---|---|---|
| recall@5 | 0.9747 | **1.0** | 1.0 |
| mrr | 0.9034 | **0.9610** | 0.9523 |
| ndcg | 0.9216 | **0.9708** | 0.9641 |
| context_precision | 0.8648 | **0.9212** | 0.8673 |
| faithfulness | 1.0 | 1.0 | 1.0 |
| refusal_appropriateness | 0.8588 | 0.9176 | **0.9294** |
| style_consistency | 1.0 | 1.0 | 1.0 |

### Honest conclusion (model-backed)

With **real semantic embeddings** (BGE-M3) instead of the hashing baseline, hybrid already
saturates `recall@5` at **1.0**, so there is no recall headroom for reranking to recover - the
same saturation effect seen in the deterministic run, now on genuine vectors. The cross-encoder
reranker (bge-reranker-v2-m3) does **not** improve ranking on this corpus: `mrr` 0.9610 -> 0.9523,
`ndcg` 0.9708 -> 0.9641, `context_precision` 0.9212 -> 0.8673 all move *down*. Its one genuine
effect is on safety: `refusal_appropriateness` rises 0.9176 -> 0.9294, because cross-attention
spots out-of-scope queries the bi-encoder scorer misses.

This is a measured result, reported as such - not a defect in the integration. The reranker is
verified to call the real `/v1/rerank` endpoint and return true cross-encoder scores (a relevant
passage scored +6.13 against -10.15 for an unrelated one in a direct probe), so the lack of
improvement is the model's behaviour on this corpus, not a wiring bug. **Recommendation: keep
`hybrid` as the default; treat the cross-encoder reranker as an optional, corpus-dependent stage -
enable it when a real measurement shows it helps (e.g. a corpus where top-1 precision is the
bottleneck), and leave it off otherwise, because here it costs ranking quality for a small safety
gain.**

## Operations (same run, cache disabled for latency)

| Field | Value |
|---|---|
| p50 latency | 7.504 ms |
| p95 latency | 10.946 ms |
| token usage (30 calls) | 7184 (195.7 input + 43.8 output per call, measured) |
| cache hit rate | 0.3833 (separate cached pass) |
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

**Why the token totals moved** (from 1,588 to 7184): the first implementation counted only the
question as input tokens, ignoring the retrieved context that dominates a RAG prompt. The
estimate understated input tokens by roughly 20x - enough to support a wrong capacity decision -
so it was fixed and pinned by a test; `calls_measured` and the input/output split are now
reported by the measurement itself rather than inferred.
