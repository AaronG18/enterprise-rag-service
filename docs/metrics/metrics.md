# Metric definitions, scorers and calibration

Every metric below has three things: a **definition**, a **deterministic scorer** in
`src/ragserve/evaluation/metrics.py`, and a **calibration case** in
`tests/test_evaluation.py` that pins the scorer's behaviour. A metric without the third is a
number nobody can audit.

## 1. Faithfulness - claim-level

**Definition.** Fraction of answer claims (sentences) supported by the cited context. A claim is
supported if it appears verbatim in a cited chunk, or at least 60% of its tokens occur in one.

**Why claim-level, not answer-level.** An answer-level judgement ("is this answer faithful?") is a
smooth number that hides how much of the answer is unsupported. Claim-level tells you which
sentence to fix.

**Scorer.** `faithfulness(answer_text, cited_texts)`.

**Calibration.**

| Case | Expected |
|---|---|
| answer copied verbatim from a cited chunk | 1.0 |
| same answer plus one invented sentence | < 1.0 |
| empty answer | 0.0 |

**Known property.** With the deterministic provider this scores 1.0 by construction, because the
provider only emits sentences copied from retrieved chunks. That is the point: it proves the
*pipeline* never fabricates. It says nothing about whether a free-form model would, which is why
any model-backed run must be reported separately and tagged `model-backed`.

## 2. Context Precision - rank-weighted

**Definition (ragas form).**

```
CP = sum_k (precision@k * rel_k) / (number of relevant chunks retrieved)
```

**Why not "fraction of retrieved chunks that are relevant".** That simpler form is structurally
capped in this corpus: a document has ~2 chunks and `top_k` is 5, so even a perfect retrieval
cannot exceed ~0.4 - it could never reach the required 0.70 no matter how good the system is.
Adopting it would have manufactured a permanent failure. The rank-weighted form measures what
matters: whether relevant chunks sit at the top.

**Calibration.** relevant at rank 1 -> 1.0; relevant at rank 3 -> 1/3; nothing relevant -> 0.0.
The test `test_relevance_beats_coverage_ratio` pins that the chosen definition can exceed 0.7
where the naive one cannot.

## 3. Answer Compliance

**Definition.** Fraction of the output contract satisfied:
citations present, grounded (faithfulness >= 0.85), within the length bound, language matches the
question, answer terminates cleanly.

**Calibration.** A cited answer scores strictly higher than the same answer without citations; an
over-long answer scores lower.

## 4. Refusal Appropriateness

**Definition.** Refusal happens exactly when the labelled case says it should. Both false
refusals and missed refusals are errors - accuracy over all cases.

**Why accuracy and not "refusal rate".** A service that refuses everything has a perfect safety
story and zero usefulness. `test_over_refusing_is_penalised` pins that.

## 5. Style Consistency

**Definition.** Per-answer style rubric (no markdown bullets, no ALL-CAPS shouting, terminal
punctuation, length in range, cites sources), aggregated as the mean over a run.

## 6. Ranking quality - MRR and nDCG

`MRR` = mean of 1/rank of the first relevant document. `nDCG` (single relevant item) =
1/log2(rank+1).

**Why they exist.** Recall@5 saturates on a 53-chunk corpus: all three configurations score
0.9565, so recall cannot tell them apart. MRR and nDCG do (see `docs/eval/retrieval-comparison.md`).

## Aggregation rule that matters

Answer-quality metrics (faithfulness, context precision, style) are computed over cases the
service **actually answered**. Folding wrong refusals into faithfulness mixes two different
failures into one unactionable number; refusal errors are counted by refusal appropriateness.
