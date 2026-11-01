# INC-001: refusal spike from an over-tight confidence gate

Reproduce: `python scripts/run.py --diagnose --case refusal-gate`

## Symptom

Legitimate questions were refused with `low_confidence`. Refusal rate collapsed the answer
compliance rate to zero because almost nothing was answered at all.

## Evidence

Configuration as found: `min_confidence = 0.60`.

Log lines captured under the failing configuration (stage `decision`):

```json
{"confidence": 0.5237, "coverage": 0.7273, "event": "decision_done", "refusal_reason": "low_confidence", "stage": "decision", "workflow_id": "wf-000003"}
```

The number that matters is in that line: `coverage` 0.73 - the retriever had the right material -
while `confidence` 0.52 sat below the 0.60 gate. The question was answerable and still refused.

## Root cause

Confidence is defined as `0.6 * coverage + 0.4 * score_share`. A correct answer that draws on a
single chunk has a `score_share` near 1.0 but a `coverage` well below 1.0, because a question
contains words the source sentence never uses ("How many", "do", "employees"). So a correct
single-source answer lands around 0.5-0.6 - exactly where the gate was set. The gate was placed
at the top of the achievable range instead of below it.

## Fix

`min_confidence` 0.60 -> 0.30 (shipped value).

**Why this fix and not another.** Two alternatives were rejected:

* *Raise coverage weighting* - would have changed the meaning of confidence for every consumer
  (logs, refusal metrics) to fix a threshold problem. Wrong layer.
* *Add a fallback "answer anyway" path below the gate* - would have reintroduced ungrounded
  answering, which is the failure the gate exists to prevent.

Moving the gate keeps a single confidence definition and one knob, and leaves the refusal
contract intact: below the gate we still refuse, we just no longer refuse correct answers.

## Measured before / after

Same command, same corpus (`bea626ce863a0e44`), 30 labelled cases:

| Metric | Before | After | Improvement |
|---|---|---|---|
| refusal_appropriateness | 0.1333 | 0.9000 | +575.2% |
| wrong_refusals | 23 | 2 | -91.3% |
| answer_doc_accuracy | 0.0 | ~0.95 | from zero |
| compliance | 0.0 | 1.0 | from zero |
| faithfulness | 0.0 | 1.0 | from zero |

Primary metric `refusal_appropriateness`: **+575.2%** (threshold: 10%).

## Provenance

`deterministic`. The before state is reproduced by setting `min_confidence` to 0.60 at runtime -
no code revert needed, so anyone can re-run the incident.
