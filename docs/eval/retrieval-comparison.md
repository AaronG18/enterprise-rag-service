# Retrieval configuration comparison

Two runs are reported, because they answer different questions and **must not be mixed**: the
offline deterministic backend (what CI verifies, reproducible by anyone) and the model-backed
backend (what the shipped default actually uses). Provenance is stated with each.

## Deterministic backend (the CI baseline)

Run: `artifacts/eval/20261031-232855` - corpus `a716676ca46bfa44`, 85 labelled cases, provider
`deterministic`, provenance `deterministic`.

This supersedes the 30-case run against corpus `bea626ce863a0e44` that this document used to
report. The corpus grew in EPIC 15 (#75) and the document was not refreshed, which left a
recommendation standing on numbers from a corpus the repository no longer ships - tracked and
fixed in #92. The measurement below is against the corpus the repository ships today.

Reproduce with `python scripts/run_eval.py --all` (CI pins both stages to `deterministic`).

| Metric | vector-only | hybrid | hybrid + rerank |
|---|---|---|---|
| recall@5 | 0.7722 | 0.8987 | **0.9620** |
| mrr | 0.7114 | 0.8006 | **0.8911** |
| ndcg | 0.7266 | 0.8254 | **0.9088** |
| context_precision | 0.8376 | 0.8262 | **0.8814** |
| faithfulness | 1.0 | 1.0 | 1.0 |
| refusal_appropriateness | 0.8000 | 0.9059 | **0.9529** |
| style_consistency | 1.0 | 1.0 | 1.0 |

## Conclusion, per axis (deterministic)

* **Every axis favours `hybrid+rerank`** on this corpus: it leads `hybrid` on recall@5 (0.9620 vs
  0.8987), mrr (0.8911 vs 0.8006), ndcg (0.9088 vs 0.8254), context_precision (0.8814 vs 0.8262)
  and refusal appropriateness (0.9529 vs 0.9059). Unlike the old, smaller corpus, reranking does
  not cost recall here - there is no trade to report.
* **Fusion is the largest single step**: vector-only -> hybrid is +12.7 recall@5 and +8.9 mrr
  points; reranking then adds +6.3 and +9.1. Both stages earn their place.
* **`vector_only` is worst on every ranking metric**, which is why it exists only as the
  comparison arm the brief asks for, never as a default.
* **Refusal improves with each stage** (0.8000 -> 0.9059 -> 0.9529): better retrieval means fewer
  low-confidence answers that should have been refused.
* **Recommendation:** default to `hybrid+rerank` on the deterministic backend.

## Model-backed comparison (BGE-M3 embeddings + bge-reranker-v2-m3 cross-encoder)

Run: `artifacts/eval/20261031-050820` - corpus `a716676ca46bfa44`, 85 labelled cases, provider
`deterministic` (generation), provenance `model-backed-retrieval`. Embeddings are the real BGE-M3
model served locally (1024-d, keyless); the reranker is the real bge-reranker-v2-m3
cross-encoder. Reproduce with `scripts/setup_models.py` + the two server commands in the README,
then `python scripts/run_eval.py --all`.

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

With **real semantic embeddings** (BGE-M3) instead of the hashing baseline, `hybrid` already
saturates `recall@5` at **1.0**, so there is no recall headroom left for reranking to recover. The
cross-encoder reranker (bge-reranker-v2-m3) therefore does **not** improve ranking: `mrr`
0.9610 -> 0.9523, `ndcg` 0.9708 -> 0.9641 and `context_precision` 0.9212 -> 0.8673 all move
*down*. Its one genuine effect is safety: `refusal_appropriateness` rises 0.9176 -> 0.9294,
because cross-attention catches out-of-scope queries the bi-encoder scorer misses.

This is a measured result, reported as such - not a defect in the integration. The reranker is
verified to call the real `/v1/rerank` endpoint and return true cross-encoder scores (a relevant
passage scored +6.13 against -10.15 for an unrelated one in a direct probe), so the lack of
improvement is the model's behaviour on this corpus, not a wiring bug.

### The contrast between the two runs, and the recommendation

The two runs disagree about reranking, and the disagreement is the finding:

| | deterministic backend | model-backed backend |
|---|---|---|
| reranking changes recall@5 | 0.8987 -> 0.9620 (**helps**) | 1.0 -> 1.0 (no room) |
| reranking changes mrr | 0.8006 -> 0.8911 (**helps**) | 0.9610 -> 0.9523 (hurts) |

**Reranking helps exactly when retrieval leaves it room to.** Under hashing embeddings the
candidate set is poor, so a cross-encoder has plenty to fix; under real embeddings `hybrid` is
already at the ceiling and reordering can only shuffle a saturated top-5. Neither run is "the
system" - each is a measurement of one backend on one corpus.

**Recommendation:** keep `hybrid` as the shipped default for the model-backed path, and treat the
cross-encoder as an optional, corpus-dependent stage: enable it when a real measurement shows it
helps (as it does on the deterministic backend today) and leave it off when it does not (as on the
model-backed run). Re-measure after any corpus or embedding change rather than inheriting this
verdict - which is exactly the failure this document itself made and #92 fixed.
