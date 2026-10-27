# Model-backed evaluation (real generation)

Run: `artifacts/eval-model/20261028-014423` - corpus `bea626ce863a0e44`, 30 labelled cases,
2 model versions x 3 retrieval configurations = 180 real model calls.

Reproduce (requires the local CodeBuddy CLI serve running on the configured ports):

```bash
python scripts/run_eval.py --provider codebuddy-serve --models hy3,deepseek-v4.1-flash
```

**Provenance: `model-backed`.** Token counts are `estimate` (the endpoint returns no usage).
Model output varies between runs; differences of a few points should be read as noise.

This table sits **next to** the deterministic baseline in
[`retrieval-comparison.md`](retrieval-comparison.md). It does not replace it.

## Quality

| Configuration | recall@5 | mrr | ndcg | context_precision | faithfulness | refusal_appropriateness | style | compliance |
|---|---|---|---|---|---|---|---|---|
| hy3, vector-only | 0.9231 | 0.8526 | 0.8704 | 0.9491 | 0.6842 | 0.7667 | 0.8211 | 0.737 |
| hy3, hybrid | 0.9615 | 0.9167 | 0.9281 | 0.9484 | 0.6627 | 0.8333 | 0.8190 | 0.743 |
| hy3, hybrid+rerank | 0.9231 | 0.9231 | 0.9231 | 0.9815 | 0.6389 | 0.7333 | 0.8222 | 0.733 |
| flash, vector-only | 0.9231 | 0.8526 | 0.8704 | 0.9485 | 0.6667 | 0.8667 | 0.9636 | 0.882 |
| flash, hybrid | 0.9615 | 0.9167 | 0.9281 | 0.9484 | 0.6723 | 0.8333 | 0.9714 | 0.886 |
| flash, hybrid+rerank | 0.9231 | 0.9231 | 0.9231 | 0.9420 | 0.7174 | 0.9000 | 0.9652 | 0.904 |

## Latency and token usage (sequential, cache disabled)

| Configuration | p50 | p95 | refused | tokens/call (est.) |
|---|---|---|---|---|
| hy3, vector-only | 3307 ms | 5217 ms | 11/30 | 322 |
| hy3, hybrid | 2519 ms | 6147 ms | 9/30 | 328 |
| hy3, hybrid+rerank | 1988 ms | 4938 ms | 12/30 | 328 |
| flash, vector-only | 1911 ms | 2421 ms | 8/30 | 321 |
| flash, hybrid | 1749 ms | 2466 ms | 9/30 | 328 |
| flash, hybrid+rerank | 1778 ms | 2698 ms | 7/30 | 329 |

Worst observed p95 is 6.15 s, inside the 10 s bound, but the margin is now measured in seconds
rather than the milliseconds of the deterministic path. Concurrency behaviour under real
generation is a separate measurement (see `docs/performance.md`).

## What this run proves that the deterministic run could not

1. **Retrieval metrics are generator-independent.** recall / MRR / nDCG / context precision are
   identical to the deterministic run to four decimals - as they should be, since they measure
   retrieval, not generation. This is now measured rather than assumed.
2. **The deterministic quality numbers were vacuous, and this run shows it.** Faithfulness was
   1.0 with the deterministic provider because answers are copied from context. Under real
   generation it is **0.64-0.72 - below the 0.85 target**. Compliance is 0.73-0.90 instead of
   0.90.
3. **Style consistency separates the models.** hy3 0.82 vs flash 0.96: the flash-tier model
   follows the style rubric far better on this task (it writes shorter, cleaner answers), while
   hy3 adds preamble that trips the rubric.

## Two gaps this run exposes (not yet fixed)

| Gap | Measured | Target |
|---|---|---|
| Faithfulness under real generation | 0.64-0.72 | >= 0.85 |
| Over-refusal under real generation | 7-12 of 30 cases refused (expected 4) -> refusal appropriateness 0.73-0.90 | >= 0.90 advanced |

Both have the same likely root cause: generated answers often do not contain a chunk id in the
exact `[doc:nnnn]` form, so citation extraction returns nothing, which (a) leaves claims
unattributed - scoring as unsupported - and (b) triggers the `citations_required` refusal. That
is a concrete, testable hypothesis and it is the next piece of work, not a footnote.

## Honest limits

* 30 cases is small; per-configuration differences of a few points are noise.
* Token counts are estimated (chars/4) because the endpoint reports no usage.
* No monetary cost is reported: no price list was available for these model versions, so
  `configs/pricing.json` stays null and the cost axis is expressed in tokens per 1,000 calls.
