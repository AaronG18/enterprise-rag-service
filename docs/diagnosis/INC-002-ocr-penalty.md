# INC-002: OCR penalty demoted the only copy of scanned documents

Reproduce: `python scripts/diagnose.py --case ocr-penalty`

## Symptom

Questions whose answer lives only in a scanned (OCR-degraded) document were refused, or answered
from a different document.

## Evidence

The evaluation set originally contained **no** case pointing at a scanned document - every
labelled case had been chosen to avoid the OCR-degraded documents. That is itself the finding:
the suite could not detect this class of failure, so it could not regress. Three `ocr_target`
cases were added (`compliance-en-00`, `compliance-en-01`, `architecture-en-03`) and the failure
appeared immediately.

Measurement with the pre-fix reranker, on those three cases: `ocr_mrr` 0.3333, 2 of 3 refused.
With reranking disabled entirely: `ocr_mrr` 0.7778 - i.e. the reranker was *causing* the problem.

## Root cause

The reranker subtracted a fixed 0.12 penalty from every OCR-flagged chunk. For a scanned document
that is the **only** copy of that content, the penalty does not compare evidence - it buries it.
The demoted chunk then fails the confidence gate and the question is refused, or a clean but
irrelevant document wins.

The design error is one of scope: "scanned text is weaker evidence" is true **between comparable
candidates**. It is false when there is no alternative candidate.

## Fix

The penalty now applies only when a clean chunk is comparably strong - within
`OCR_COMPARABLE_MARGIN = 0.08` of the scanned chunk's score. Otherwise it is suppressed.

**Why this fix and not another:**

* *Removing the penalty entirely* - gives up a real signal: when a clean and a scanned chunk say
  the same thing, the clean one should win. Measured, the penalty is worth keeping in that case.
* *Lowering the penalty* - arbitrary; the failure is not about magnitude but about applying a
  relative judgement absolutely.

## Measured before / after

Same command, same corpus (`bea626ce863a0e44`), OCR-targeted subset (3 cases):

| Metric | Before | After | Improvement |
|---|---|---|---|
| ocr_mrr | 0.3333 | 0.6667 | +100.0% |
| ocr_context_precision | 0.3333 | 0.6667 | +100.0% |
| ocr_refusals | 2 | 1 | -50% |

Primary metric `ocr_mrr`: **+100.0%** (threshold: 10%).

Note the after value (0.667) is still below reranking-off (0.778). The residual gap is reported
rather than closed: on one of the three cases the conditional penalty still demotes a scanned
chunk in favour of a comparable clean one. Fixing that would mean special-casing the case, which
is not justified by three data points.

## Correction of an earlier attribution

An earlier commit message credited "retrieval-rank damping of sentence scores" with fixing
wrong-document answers. Re-measuring with a reconstruction of the pre-fix provider showed **no
difference** on the current evaluation set (0.9524 before and after). The measurable gain at that
time came from the answer-joining and claim-splitting fix, not from rank damping. The damping is
kept (it is correct in principle) but it is not claimed as a measured improvement anywhere.
