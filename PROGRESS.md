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
| 13 (#45) | Submission hardening | HTTP API, React+AntD UI, one-command start, BYO key, service bench | done |
| 14 (#54) | Harness in CI | machine-readable requirements manifest, verifier, harness workflow, branch protection | done |
| 15 (#75) | Expand synthetic knowledge base | four families balanced, 80 docs / 204 chunks, meaningful scanned subset, grown eval set, re-measure | done |

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

## EPIC 13 (#45) children

- [x] #46 HTTP API with health, ask, session-based multi-turn
- [x] #47 React + AntD frontend with provider selector
- [x] #48 one-command start and reviewer quickstart
- [x] #49 service-level benchmark against the HTTP API
- [x] #50 bring-your-own-key model channel
- [x] #51 QA re-run and submission evidence

## EPIC 4 children

- [x] #17 grounded generation with resolvable citations
- [x] #18 refusal with reason codes and guidance
- [x] #19 prompt-injection defence
- [x] #20 PII redaction in answers and logs
- [x] #21 multi-turn follow-up resolution

## EPIC 14 (#54) children

- [x] #55 machine-readable requirements manifest and verifier
- [x] #56 harness workflow on every branch and pull request
- [x] #57 branch protection requiring the harness checks
- [x] #58 rules, skills and CONTRIBUTING describing the gate
- [x] #59 the gate demonstrated red to green
- [x] #67 concurrent gate: parallel requirement rows and test classes
- [x] #70 port tests made robust under the parallel runner

## EPIC 15 (#75) children

- [x] #76 expand corpus content across all four families (handbook, compliance, techspec, architecture), seed-deterministic
- [x] #77 keep scanned-PDF subset meaningful at larger size (6 scanned docs, ratio 0.075, clean originals retained)
- [x] #78 grow the labelled evaluation set with the corpus (realigned `eval_cases.json` + `retrieval_cases.json`, scanned targets + refusal cases)
- [x] #79 re-measure everything on the new corpus (recall@5 0.77/0.90/0.96 across configs, bench p90 79 ms, audit 24/24, diagnose green)

## Change log (reverse chronological)

Entries follow: issue, then change, then evidence status.

* **#67 / EPIC 14 (#54)** CLOSED (2026-10-28). The gate is now concurrent: the generators
  and the requirement rows run in parallel, and the hermetic suite runs its test classes in
  worker processes with work stealing. Measured: suite 24.4 s -> 7.8 s, gate 14.2 s ->
  8.1 s locally; in CI the slowest job went from 13 s to 11 s. The work also found that
  seven requirement rows were passing while asserting nothing (`unittest -k` exits 0 when
  the filter matches no test): the runner now fails on an empty selection, and each row
  reports how many tests it really ran.
* **#55-#59 / EPIC 14 (#54)** CLOSED (2026-10-28). The harness moved into GitHub Actions.
  `harness/requirements.toml` is a machine-readable manifest of every requirement; CI runs
  `scripts/verify_requirements.py` (30 rows, ~8 s) and fails by row ID; the workflow adds
  `requirements-gate`, `contract-gate` and `pr-hygiene` on every branch push and every pull
  request. `main` is protected and requires all three. Demonstrated end to end: a red PR is
  refused with `405 Required status check "contract-gate" is failing`, a green PR merges.
  Running the gate found three defects in the gate itself (a pattern that matched
  `__init__.py`, merge commits required to reference an issue, and `enforce_admins: false`
  letting the owner merge a red change) - all fixed and documented in
  `docs/qa/harness-gate.md`.

* **#46-#51 / EPIC 13 (#45)** CLOSED (2026-10-28). Submission hardening: the repository is now a
  runnable service. `python scripts/start.py` builds the corpus, indexes it in ~19 ms and serves
  a React + AntD UI plus a stdlib HTTP API on 127.0.0.1:8124. Default path needs no key and no
  network; a reviewer can bring their own OpenAI-compatible endpoint (key used per request,
  never stored or logged). Service-level benchmark: 5 concurrent HTTP requests, p90 148 ms,
  0 errors. Five UI screenshots committed. 144 tests, CI green.
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
