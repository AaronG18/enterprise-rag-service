---
name: rag-eval
description: Run, extend, or interpret evaluations for this RAG service - retrieval comparison across vector-only, hybrid and hybrid+rerank; faithfulness, context precision, answer compliance, refusal appropriateness, style consistency; latency and cost reports. Use when asked to evaluate quality, compare retrieval configurations, regenerate the evaluation report, or explain any metric number in this repo.
---

# Skill: rag-eval

## When to use

Use this skill for anything producing or questioning a **number** about service quality:
retrieval configuration comparison, generative scoring, latency percentiles, cost per
1,000 calls, or the operational report. Do not improvise commands; use the entrypoints
below so that results stay comparable across commits.

## Contract before you start

1. Decide the **provider mode** (`deterministic` or `model-backed`) and record it. Default
   is `deterministic`: seeded, offline, reproducible. Never compare a `model-backed` number
   against a `deterministic` one without saying both tags in the same sentence.
2. Decide the **corpus seed and version**. Comparisons are only valid inside one corpus
   version; changing the generator invalidates every historical comparison.
3. Write the pass/fail thresholds **before** running (they live in `configs/` and in
   `docs/REQUIREMENTS.md` rows R-14..R-18).

## Entrypoints

```
python scripts/run_tests.py                 # correctness, hermetic
python scripts/run_eval.py --all            # retrieval comparison + generative scoring + ops report
python scripts/run_eval.py --retrieval-only # vector-only / hybrid / hybrid+rerank comparison
python scripts/run_eval.py --cost           # token usage and cost per 1,000 calls (estimate)
python scripts/run_bench.py --concurrency 5 # latency percentiles under concurrency
```

Every run writes machine output to `artifacts/` under a timestamped run directory, and the
human-facing summary belongs in `docs/eval/`. `artifacts/` is regenerated, never edited.

## Interpreting the three retrieval configurations

Expected pattern, and what it means when you do **not** see it:

| Comparison | Usually true | If the opposite appears, suspect |
|---|---|---|
| hybrid > vector-only | yes, especially in bilingual queries where one language has sparse surface forms | tokenisation mismatch between CN and EN; inspect the analyzer, not the fusion weights |
| hybrid+rerank > hybrid | yes on Context Precision; often flat on Faithfulness | reranker rewarding lexical overlap over actual answer support |
| hybrid+rerank in latency budget | may break p90 | rerank cost scaling with candidate count; check top-k before blaming the model |

A reranker that raises Context Precision but lowers Faithfulness is a real and diagnostic
result, not a failure to hide.

## Gotchas

* **Bilingual asymmetry.** CN queries have no whitespace-delimited tokens; an analyzer tuned
  on EN silently destroys CN recall. Any recall claim must be reported per language.
* **OCR subset contamination.** Scanned-style documents with injected noise can enter Top-k
  and drag Context Precision down without any change in retrieval code. If numbers move with
  no code change, diff the corpus version first.
* **Cache poisoning.** With caching on, repeated identical queries during an eval produce
  latency numbers with no retrieval cost and inflated hit rates. Wash out or pin the seed.
* **Percentile vs. mean.** The target is p90 within 10 s. A mean that satisfies it means
  nothing. Report p50/p95 (and p90 explicitly) always.
* **Refusal rate gaming.** A system can trivially reach high Answer Compliance by refusing
  more. Compliance must always be reported **alongside** refusal rate; never alone.

## Fix/gain loop (used by diagnosis work, EPIC #8)

1. Capture the failing metric with its run directory.
2. Form one testable hypothesis about the cause, evidenced from logs (not intuition).
3. Change one thing. Re-run the same command. Same corpus version, same provider mode.
4. Report before/after and delta. A published improvement below 10% still gets written up,
   but it does not satisfy R-21.

## Related

`harness/skills/evidence-and-testing/` for how to present these numbers honestly;
`configs/` for every switch that must be changed without touching code.
