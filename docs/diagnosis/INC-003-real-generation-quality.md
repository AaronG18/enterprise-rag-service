# INC-003: real generation missed faithfulness and refusal targets

Reproduce the before/after with:

```bash
python scripts/run_eval.py --provider codebuddy-serve --models hy3,deepseek-v4.1-flash
```

Two defects, found because the model-backed lane existed at all - the deterministic lane could
not see either of them.

## Defect 1: grounded answers were refused for missing citation markers

**Symptom.** 32 of 180 real calls were refused with `low_confidence` even though the model had
answered from the retrieved content. Only 24 refusals were legitimate (the out-of-scope,
safety and injection cases).

**Evidence.** Refusal reason histogram over the first model-backed run:
`low_confidence: 44, safety_trigger: 6, injection_detected: 6` - against 24 expected refusals.
Inspecting the refused answers showed they were correct answers that simply did not contain a
chunk id in the exact `[doc:nnnn]` form, and `citations_required` treated that as "no evidence".

**Fix.** Decouple "citation format missing" from "evidence missing": explicit markers first, then
`attribute_evidence()` maps each answer sentence to its best-matching retrieved chunk. The trace
records `citation_source: explicit | attributed | none`.

**Deliberate constraint on the fix.** Attribution carries **no support threshold**. If it only
attributed chunks that already satisfied the support rule, faithfulness would have become 1.0 by
construction - the same vacuity this repository forbids. Attribution answers "where did this come
from"; scoring stays unchanged.

**Effect (hy3, hybrid config):** refusal appropriateness 0.8333 -> 0.9000, wrong refusals 9 -> 3.

## Defect 2: the Sources line was scored as an answer claim

**Symptom.** After defect 1 was fixed, faithfulness **fell** from ~0.67 to ~0.45 on cases that
had been answered in both runs - verified on the common subset, so it was a real regression and
not a denominator change.

**Evidence.** A direct call showed why:

```
TEXT: 'Full-time employees accrue 15 working days of paid annual leave per calendar year.\n\nSources: [handbook-en-00:0000]'
claims: ['Full-time employees accrue ...' supported=True,
         'Sources: [handbook-en-00:0000]' supported=False]
```

The `Sources:` line was introduced by this repository's own prompt change (asking for explicit
citations), and the scorer counted it as a claim. It never appears in the cited chunk, so every
answer lost exactly one claim - and the answer no longer ended in sentence punctuation, which
cost a style check too.

**Fix.** `strip_sources_line()` removes the metadata line *after* citations are parsed (so no
citation is lost) and before scoring or attribution.

**Effect:** faithfulness restored and then improved; style consistency recovered.

## Before / after (same corpus, same 30 cases, `model-backed`)

| Config | Metric | Baseline | After both fixes | Change |
|---|---|---|---|---|
| hy3, hybrid | faithfulness | 0.6627 | 0.8913 | +34.5% |
| hy3, hybrid | refusal_appropriateness | 0.8333 | 0.9000 | +8.0% |
| hy3, hybrid | style_consistency | 0.8190 | 0.8957 | +9.4% |
| hy3, vector_only | faithfulness | 0.6842 | 0.8182 | +19.6% |
| hy3, hybrid+rerank | faithfulness | 0.6389 | 0.8696 | +36.1% |
| flash, hybrid | faithfulness | 0.6723 | 0.7609 | +13.2% |
| flash, hybrid+rerank | faithfulness | 0.7174 | 0.6159 | **-14.2%** |
| flash, vector_only | faithfulness | 0.6667 | 0.7955 | +19.3% |

## What did not improve, reported as such

* **flash, hybrid+rerank got worse on faithfulness** (0.7174 -> 0.6159). One run of 30 cases is
  too small to distinguish a real effect from noise, and no causal story has been established,
  so it is recorded as an unexplained negative result rather than smoothed over.
* **hy3, vector_only refusal appropriateness** improved only to 0.8667 (still below the 0.90
  advanced target). That is the weakest configuration; the recommendation follows.

## Outcome

The best configuration is now **hy3 + hybrid**: faithfulness 0.8913 (>= 0.85), refusal
appropriateness 0.9000 (>= 0.90), style consistency 0.8957 (>= 0.85), compliance 0.965 - all
advanced targets met under real generation. ADR 0004 is updated to match.
