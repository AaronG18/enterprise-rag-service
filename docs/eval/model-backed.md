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

## Quality (current run, after INC-003 fixes)

Run: `artifacts/eval-model/20261028-021149` - 180 real calls.

| Configuration | recall@5 | mrr | ndcg | context_precision | faithfulness | refusal_appropriateness | style | compliance |
|---|---|---|---|---|---|---|---|---|
| hy3, vector-only | 0.9231 | 0.8526 | 0.8704 | 0.9485 | 0.8182 | 0.8667 | 0.8818 | 0.955 |
| **hy3, hybrid** | 0.9615 | 0.9167 | 0.9281 | 0.9529 | **0.8913** | **0.9000** | **0.8957** | **0.965** |
| hy3, hybrid+rerank | 0.9231 | 0.9231 | 0.9231 | 0.9420 | 0.8696 | 0.9000 | 0.9043 | 0.965 |
| flash, vector-only | 0.9231 | 0.8526 | 0.8704 | 0.9485 | 0.7955 | 0.8667 | 0.9455 | 0.900 |
| flash, hybrid | 0.9615 | 0.9167 | 0.9281 | 0.9529 | 0.7609 | 0.9000 | 0.9565 | 0.887 |
| flash, hybrid+rerank | 0.9231 | 0.9231 | 0.9231 | 0.9420 | 0.6159 | 0.9000 | 0.9652 | 0.861 |

**All advanced targets are met by `hy3 + hybrid`**: faithfulness 0.8913 (>= 0.85), refusal
appropriateness 0.9000 (>= 0.90), style consistency 0.8957 (>= 0.85), compliance 0.965.

## History of this measurement

Three runs exist, and the middle one is the reason the third one is trustworthy:

| Run | What changed | hy3/hybrid faithfulness | Wrong refusals |
|---|---|---|---|
| `20261028-014423` | first real run | 0.6627 | 32 of 180 calls |
| `20261028-020000` | attribution fallback added | 0.4710 | 3 of 180 calls |
| `20261028-021149` | Sources line stripped before scoring | 0.8913 | 3 of 180 calls |

The middle run is a regression that this repository caused and then measured (see
[`../diagnosis/INC-003-real-generation-quality.md`](../diagnosis/INC-003-real-generation-quality.md)):
asking the model for a `Sources:` line made the scorer count that line as an unsupported claim.
Both the wrong refusals and the regression were only visible because a real model was in the
loop.

**Unexplained negative result, recorded rather than smoothed:** flash + hybrid+rerank faithfulness
fell from 0.7174 to 0.6159 across these runs. With 30 cases per run that cannot be separated from
noise, and no causal story has been established, so it stays in the table.

## Latency and token usage

See `20261028-021149` in `artifacts/eval-model/`. Sequential, cache disabled:

| Configuration | p50 | p95 | refused | tokens/call (est.) |
|---|---|---|---|---|
| hy3, vector-only | ~3.3 s | ~5.2 s | 4/30 | ~322 |
| hy3, hybrid | ~2.5 s | ~6.1 s | 3/30 | ~328 |
| hy3, hybrid+rerank | ~2.0 s | ~4.9 s | 3/30 | ~328 |
| flash, hybrid | ~1.7 s | ~2.5 s | 3/30 | ~328 |
| flash, hybrid+rerank | ~1.8 s | ~2.7 s | 3/30 | ~329 |

Worst p95 6.15 s - inside the 10 s bound with real generation, but the margin is seconds.

## Honest limits

* 30 cases per configuration; differences of a few points are noise.
* Token counts are `estimate` (the endpoint reports no usage).
* No monetary cost: no price list was available, `configs/pricing.json` stays null.
* Model output varies run to run, so single-run comparisons should not be over-read.

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
