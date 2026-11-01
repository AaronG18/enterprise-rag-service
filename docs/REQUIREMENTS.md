# Requirements Traceability

Every requirement below is traced back to a clause it came from, restated as a
testable acceptance criterion, and mapped to a verification command and an owning issue.
Nothing ships without a row here.

**Provenance:** the source brief is generic engineering scope; no employer-specific or
role-specific content is reproduced anywhere in this repository.

Legend for verification: `AUTO` = asserted by automated test, `EVAL` = produced by
`scripts/run.py` artifact, `MANUAL` = documented in `docs/` and reviewed.

---

## A. Global constraints

| ID | Requirement (source clause) | Acceptance criterion | Verification | Owner issue |
|---|---|---|---|---|
| R-01 | 90% of QA requests complete end-to-end within 10 s | p90 latency <= 10 s under the standard load profile | `scripts/run.py` (AUTO + EVAL) | #7 |
| R-02 | Support >= 5 concurrent requests on a single instance | 5 in-flight requests, p90 stays within bound, no error rate increase | `scripts/run.py --concurrency 5` (EVAL) | #7 |
| R-03 | Token-cost estimate per 1,000 calls | cost table per configuration with stated price list | `scripts/run.py --cost` (EVAL, provenance: `estimate`) | #7 |
| R-04 | Model-version selection rationale with explicit trade-offs | ADR comparing >= 2 model versions on quality/cost/latency | `docs/adr/` (MANUAL + EVAL) | #7 |
| R-05 | Structured logs sufficient for monitoring and issue diagnosis | log dictionary covers every emitted field; single-request reconstruction works from logs alone | `docs/logging/` + test (AUTO) | #5, #9 |
| R-06 | Minimal prompt-injection defense | adversarial corpus subset with test asserting no policy-breaking answer | test + eval (AUTO) | #4 |
| R-07 | Basic PII handling | PII redacted in **answer payload** and in **log record**; both tested | test (AUTO) | #4 |
| R-08 | Answers strictly grounded to retrieved context | unfaithful claim rate bounded; unsupported answers must refuse | test + eval (AUTO) | #4, #6 |

## B. Functional requirements

| ID | Requirement | Acceptance criterion | Verification | Owner issue |
|---|---|---|---|---|
| R-09 | At least two retrieval modes: vector-only and hybrid | both modes selectable; behavioral difference demonstrated | eval comparison (EVAL) | #3, #6 |
| R-10 | Reranker toggled by configuration, not code change | toggling is a config diff only; test asserts both paths | test (AUTO) | #3 |
| R-11 | Refusal with guidance on low confidence / out-of-scope / safety trigger | refusal response carries reason code + guidance text; all three triggers covered | test (AUTO) | #4 |
| R-12 | Operational report: p50/p95 latency, token usage, cache hit rate, refusal rate, answer compliance rate | report emitted as text **and** CSV, all six fields populated | `scripts/run.py --report` (EVAL) | #6 |
| R-13 | Multi-turn interaction support | conversational follow-up resolves references from prior turns | test (AUTO) | #4 |

## C. Quantitative quality targets

| ID | Metric | Baseline target | Advanced target | Verification | Owner issue |
|---|---|---|---|---|---|
| R-14 | Faithfulness | >= 0.85 | - | eval (EVAL) | #6 |
| R-15 | Context Precision | >= 0.70 | - | eval (EVAL) | #6 |
| R-16 | Answer Compliance | >= 0.80 | >= 0.90 | eval (EVAL) | #6 |
| R-17 | Refusal Appropriateness | >= 0.80 | >= 0.90 | eval (EVAL) | #6 |
| R-18 | Style Consistency | >= 0.80 | >= 0.85 | eval (EVAL) | #6 |

Each metric needs three things before any number may be published:
**(1)** a written definition, **(2)** an implemented scorer, **(3)** a rubric calibration
set (hand-labelled examples). See `docs/metrics/`.

## D. Non-functional requirements

| ID | Requirement | Acceptance criterion | Verification | Owner issue |
|---|---|---|---|---|
| R-19 | Compare vector-only / hybrid / hybrid+rerank quantitatively | side-by-side table + written conclusion stating which wins on which axis | `docs/eval/retrieval-comparison.md` (EVAL + MANUAL) | #6 |
| R-20 | Evolvability: retrieval strategy swap, model version swap, metric/logging extension | each swap performed as a config change in CI-visible test; each extension does not require touching core modules | test (AUTO) | #3, #5, #7 |
| R-21 | Document >= 2 issues with log/metric evidence, fix rationale, >= 10% post-fix improvement | two cases, each with before metric, root cause from logs, fix diff reference, after metric, delta >= 10% | `docs/diagnosis/` (EVAL + MANUAL) | #8 |

## E. Deliverables

| ID | Deliverable | Location | Owner issue |
|---|---|---|---|
| R-22 | Complete code and configs | `src/`, `configs/` | #2, #3, #4, #5 |
| R-23 | One-click evaluation script | `scripts/run.py` | #6 |
| R-24 | Evaluation report with before/after comparisons | `docs/eval/` | #6, #9 |
| R-25 | Log field dictionary and sample logs | `docs/logging/`, `artifacts/logs/` | #5, #9 |

## F. Model-backed lane (verified outside CI)

The real-generation numbers cannot be produced in CI because they need credentials. Instead, a
snapshot of the model-backed run is committed (`docs/eval/model-backed-metrics.json`) and the CI
requirements gate asserts the same thresholds against it. This is a documented substitution, not
a skipped requirement: the snapshot carries the run id, corpus version and provenance, and the
raw run stays reproducible with the documented command.

| ID | Metric | Target | Snapshot value (hy3 + hybrid) | Verification |
|---|---|---|---|---|
| R-14m | Faithfulness | >= 0.85 | 0.9130 | snapshot + `docs/eval/model-backed.md` |
| R-16m | Answer Compliance | >= 0.90 | 0.9830 | snapshot |
| R-17m | Refusal Appropriateness | >= 0.90 | 0.9000 | snapshot |
| R-18m | Style Consistency | >= 0.85 | 0.9043 | snapshot |
| R-24m | before/after history | present | 3 runs recorded | snapshot `history` block |

## G. Harness integrity (the harness is code, and code needs tests)

The brief asks for a verifiable service, so the verifier gets the same treatment as the product:
every rule has an enforcement, every skill is valid and reachable, CI stays hermetic, the
documentation cannot contradict the shipped configuration, and retrieval cannot regress silently.
Without these, a green pipeline proves only that the pipeline is green.

| ID | Requirement | Acceptance criterion | Verification | Owner issue |
|---|---|---|---|---|
| R-26 | Every rule in `harness/RULES.md` is enforced | each rule has exactly one row in the enforcement map; every path the map names exists; each rule is enforced by code or its row says `manual` | test (AUTO) | #90 |
| R-27 | Every skill is valid and reachable | frontmatter `name` equals the directory name, the description says when to use it, relative links resolve, and something points at the skill | test (AUTO) | #90 |
| R-28 | CI stays hermetic | no workflow installs anything, and every workflow that runs the service or the evaluation pins the offline embedding and reranker providers | test (AUTO) | #90 |
| R-29 | No front end in the tree | shipped code references no front-end directory, the README and deployment guide advertise no UI, and a stray `web/` directory stays gitignored | test (AUTO) | #90 |
| R-30 | Documentation matches the shipped configuration | the README and the deployment guide name the shipped embedding model and the runtime switches, and state no default the configuration no longer has | test (AUTO) | #90 |
| R-31 | Retrieval does not regress silently | the labelled golden set meets the measured floors for vector-only, hybrid and hybrid+rerank | test (AUTO) | #90 |
| R-32 | Retrieval is reproducible | two builds produce identical vectors, identical rankings for the same question and identical scores | test (AUTO) | #90 |
| R-33 | The comparison report is generated, never hand-edited | the committed report equals what the renderer produces from the committed snapshots, and the deterministic snapshot still matches the shipped corpus and case count | test (AUTO) | #94 |
| R-34 | A user-supplied corpus can be indexed and measured | `--corpus <dir>` builds a corpus from `.txt`/`.md`/`.pdf`, detects language per document, reports files it could not index instead of dropping them, and measures retrieval with self-labelled queries | test (AUTO) | #96 |

## Notes on derivation

Three requirements in the source brief are under-specified in a way that changes the
verification design, so the interpretation is recorded explicitly rather than silently:

1. **"90% within 10 s" under which load?** Latency is load-dependent, so R-01 is defined
   under the same concurrency used for R-02 (>= 5 concurrent). Sequential p90 alone would
   be easy to pass and meaningless.
2. **"Faithfulness >= 0.85" - measured how?** Claim-level entailment. LLM-judged scores are
   not reproducible for CI, so the repository ships a deterministic claim-alignment scorer
   as the enforceable baseline, with the LLM judge as a separate, tagged comparison
   (`model-backed`). Both are reported, never mixed.
3. **"Style Consistency" - consistent with what?** A fixed style rubric (structure, citation
   format, tone, verbosity bound) written in `docs/metrics/`, scored on every answer of a
   run. Consistency is variance across answers, so it is computed on a distribution,
   not per answer.
| R-35 | Chinese PDFs are extracted as Chinese, and font metadata is never indexed | a subset CJK font with a ToUnicode CMap yields its characters; `Adobe`/`UCS`/`GB1` never appear in indexed text; an uncompressed stream is read, not skipped | test (AUTO) | #106 |
| R-36 | A PDF with some text pages and some image pages is indexed, never dropped | per-page handling keeps the readable pages, counts the pages with no text layer, and still reports a PDF with no text at all as scanned | test (AUTO) | #109 |
