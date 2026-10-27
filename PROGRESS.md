# PROGRESS

Living status board. Updated when an EPIC or SUB issue changes state, not per commit.
Numbers below refer to GitHub issue numbers in this repository.

Legend: `todo` / `in-progress` / `needs-evidence` / `done`

---

## EPICs

| # | Title | Scope in one line | State |
|---|---|---|---|
| 1 | Repository bootstrap and harness foundation | layout, rules, roles, skills, CI, issue templates | done |
| 2 | Corpus and ingestion pipeline | synthetic bilingual corpus, chunking, OCR-noise subset | done |
| 3 | Retrieval layer | vector-only, hybrid (RRF), pluggable reranker, config switching | done |
| 4 | Generation, grounding, refusal, PII | prompt-injection defense, citations, refusal with guidance, redaction | done |
| 5 | Observability and caching | structured logs, trace/workflow ids, cache with TTL and invalidation | done |
| 6 | Evaluation suite and comparison report | one-click eval, metric rubrics, three-config comparison | done |
| 7 | Performance, concurrency and cost | p90 <= 10 s, >= 5 concurrent, token cost per 1,000 calls, model trade-offs | done |
| 8 | Diagnosis cases | >= 2 regressions with log evidence and >= 10% post-fix gain | done |
| 9 | Delivery documentation | log dictionary, sample logs, architecture decision records, final report | done |
| 10 | Harness retro and iteration | fold lessons learned back into RULES and skills | done |
| 11 (#36) | Model-backed evaluation lane | real generation via local CLI serve; 2 models x 3 configs x 30 cases | done |
| 12 (#41) | Real-generation quality fix | evidence attribution + Sources-line stripping; INC-003 | done |

---

## EPIC 2 children

- [x] #11 corpus generator + versioned manifest
- [x] #12 OCR-noise transform (scanned subset)
- [x] #13 chunking with metadata + artifact writer

## EPIC 3 children

- [x] #14 deterministic embeddings + vector index
- [x] #15 BM25 + RRF fusion + config-driven modes
- [x] #16 pluggable reranker with configuration-only toggle

## EPIC 5 children

- [x] #22 structured event log with workflow correlation
- [x] #23 two-layer cache with TTL and hit-rate accounting
- [x] #24 cache poisoning guards + request reconstruction

## EPIC 6 children

- [x] #25 metric definitions, scorers and calibration sets
- [x] #26 one-click evaluation script with reproducible artefacts
- [x] #27 three-config comparison with graded metrics
- [x] #28 operations report (text and CSV)

## EPIC 7 children

- [x] #29 concurrency benchmark with percentile reporting
- [x] #30 token cost model and provider ADR

## EPIC 8 children

- [x] #31 INC-001 refusal gate
- [x] #32 INC-002 OCR penalty + evaluation gap

## EPIC 9 children

- [x] #33 delivery index, final README, sample logs
- [x] #34 architecture decision records

## EPIC 10 children

- [x] #35 harness retro

## EPIC 11 (#36) children

- [x] #37 CodeBuddy serve provider adapter with loopback-only safety
- [x] #38 model-backed evaluation run (2 models x 3 configs x 30 cases)
- [x] #39 latency and cost under real generation
- [x] #40 ADR 0004 - measured model-version trade-off

## EPIC 12 (#41) children

- [x] #42 evidence attribution + Sources-line stripping (INC-003)
- [x] #43 re-measure the cross and record the delta

## EPIC 4 children

- [x] #17 grounded generation with resolvable citations
- [x] #18 refusal with reason codes and guidance
- [x] #19 prompt-injection defence
- [x] #20 PII redaction in answers and logs
- [x] #21 multi-turn follow-up resolution

## Change log (reverse chronological)

Entries follow: issue, then change, then evidence status.

* **#42 #43 / EPIC 12 (#41)** CLOSED (2026-10-28). INC-003: 32 wrong refusals (attribution
  fallback) + a Sources line being scored as an unsupported claim (stripped before scoring).
  hy3+hybrid now meets every advanced target under real generation: faithfulness 0.8913,
  refusal appropriateness 0.9000, style 0.8957, compliance 0.965. flash+hybrid+rerank
  faithfulness regressed (0.7174 -> 0.6159) and is recorded as an unexplained negative result.
  ADR 0004 recommendation reversed from flash to hy3, with the reversal documented.

* **#37-#40 / EPIC 11 (#36)** CLOSED (2026-10-28). Real-generation lane: loopback-only provider
  adapter (no credentials in the repo, non-loopback endpoints refused), hermetic tests against a
  fake local server, 180 real calls over hy3 and deepseek-v4.1-flash across three retrieval
  configurations. Retrieval metrics proved generator-independent; faithfulness dropped from 1.0
  to 0.64-0.72 and compliance to 0.73-0.90 under real generation - both recorded as unmet
  targets, not smoothed over. ADR 0004 picks the flash-tier model on measured evidence.

* **#33 #34 / EPIC 9** CLOSED (2026-10-28). `docs/deliverables.md` maps every required
  deliverable to a file and command; sample logs are generated (`scripts/sample_logs.py`)
  rather than hand-written; ADRs for retrieval strategy and the synthetic corpus added; README
  targets table now carries measured values with the deterministic-provider caveat.
  118 tests, CI green (run 40541966467).
* **#31 #32 / EPIC 8** CLOSED (2026-10-28). Two reproducible incidents: INC-001 refusal gate
  (+575% refusal appropriateness) and INC-002 OCR penalty (+100% scanned-document MRR). The
  suite gap (no case pointed at a scanned document) was closed with 3 `ocr_target` cases. An
  earlier attribution to rank damping was withdrawn because replay showed no difference.
  CI green (run 40541310113).
* **#29 #30 / EPIC 7** CLOSED (2026-10-28). Concurrency benchmark (5 concurrent, p90 10.5 ms,
  0 errors) and a cost model that refuses to invent prices. Provider ADR states plainly that no
  hosted model was measured. CI green (run 40540260063).
* **#22 #23 #24 / EPIC 5** CLOSED (2026-10-28). Structured stage logging with workflow
  correlation, emit-time redaction, dictionary enforced by test; two-layer cache with
  config-scoped keys and no refusal caching. CI green (run 40538855567).

* **#17-#21 / EPIC 4** CLOSED (2026-10-28). Generation layer: deterministic provider emitting
  verbatim grounded sentences, five refusal reason codes with guidance, injection
  detection/neutralisation (EN+ZH), PII masking in answers and log records, multi-turn
  resolution. 64/64 tests pass, CI green (run 40537829847). Two measured limitations recorded
  rather than tuned away: hashing-embedding collisions (~0.11 noise vs ~0.14 true match) and
  OCR-degraded documents lowering confidence. See `docs/generation.md`.

* **#14 #15 #16 / EPIC 3** CLOSED (2026-10-27). Retrieval layer: bilingual tokeniser, hashing
  embeddings, BM25, RRF fusion, deterministic reranker behind a provider interface, all
  switches in `configs/retrieval.json`. 37/37 tests pass, CI green (run 40501465970).
  Measured: all three configurations tie at 9/10 recall on 10 labelled cases - recorded as a
  limitation, not a win. See `docs/retrieval.md`. Evidence in issues #14, #15, #16, #3.

* **#11 #12 #13 / EPIC 2** CLOSED (2026-10-27). Corpus pipeline: 32 bilingual documents,
  53 chunks, 3 OCR-degraded documents; `corpus_version = bea626ce863a0e44`.
  25/25 tests pass, CI green (run 40500680128). One design defect caught by a test-first
  failure: per-section chunking never produced overlap, so chunking moved to document level.
  Evidence in issues #11, #12, #13, #2.
* **#1** CLOSED (2026-10-27). Bootstrap + contract tests; CI green on 3.11/3.12/3.13
  (run 40482559462), 6/6 hermetic contract tests pass. Evidence in issue #1.
* **#1** Initial repository bootstrap: layout, `PROJECT.md`, `CONTRIBUTING.md`, `AGENTS.md`,
  `harness/RULES.md`, `harness/ROLES.md`, three skills, issue and PR templates, CI workflow,
  requirements traceability matrix.
  Evidence: CI green; `scripts/run_tests.py` runs clean from a cold clone. See issue #1.
