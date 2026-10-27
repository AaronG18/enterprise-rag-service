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
| 3 | Retrieval layer | vector-only, hybrid (RRF), pluggable reranker, config switching | todo |
| 4 | Generation, grounding, refusal, PII | prompt-injection defense, citations, refusal with guidance, redaction | todo |
| 5 | Observability and caching | structured logs, trace/workflow ids, cache with TTL and invalidation | todo |
| 6 | Evaluation suite and comparison report | one-click eval, metric rubrics, three-config comparison | todo |
| 7 | Performance, concurrency and cost | p90 <= 10 s, >= 5 concurrent, token cost per 1,000 calls, model trade-offs | todo |
| 8 | Diagnosis cases | >= 2 regressions with log evidence and >= 10% post-fix gain | todo |
| 9 | Delivery documentation | log dictionary, sample logs, architecture decision records, final report | todo |
| 10 | Harness retro and iteration | fold lessons learned back into RULES and skills | todo |

---

## EPIC 2 children

- [x] #11 corpus generator + versioned manifest
- [x] #12 OCR-noise transform (scanned subset)
- [x] #13 chunking with metadata + artifact writer

## Change log (reverse chronological)

Entries follow: issue, then change, then evidence status.

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
