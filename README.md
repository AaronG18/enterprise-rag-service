# Enterprise RAG Service

A bilingual (CN/EN) **Retrieval-Augmented Generation QA service** over an internal-style
knowledge base: employee handbook, compliance guides, technical specifications and
architecture documents. Built and hardened as an engineering exercise; every technical
choice must survive a quantitative check, not a narrative argument.

The goal of this repository is deliberately narrow and checkable:

> Turn "our RAG service works" into a machine-verifiable claim, with evidence anyone can
> reproduce by running one command.

---

## 1. What the service does

```
               ┌──────────────────────────────────────────────────────┐
  question ──▶ │  guard (injection defense / scope / PII)             │
               │  retrieve  ─ vector-only | hybrid | hybrid + rerank  │
               │  cache ──────────────── exact + semantic, TTL bound  │
               │  generate ─ grounded answer + citations, or refusal  │
               │  redact ── PII scrubbing on answer AND log record    │
               │  emit ──── structured JSON log lines (trace/workflow)│
               └──────────────────────────────────────────────────────┘
```

Every one of those stages is **configuration-driven**. Switching retrieval modes or
toggling the reranker never touches Python code.

## 2. Scope of the knowledge base

The corpus is **synthetically generated** inside this repository. No real internal
documents are shipped. This is an intentional constraint:

* the repository stays publishable and carries no third-party confidential content;
* the corpus generator is deterministic (seeded), so every evaluation run uses an
  identical corpus and results stay comparable across commits;
* roughly 8% of documents are passed through an OCR-noise transform to emulate scanned
  PDFs, which is what makes the retrieval stage interesting rather than trivial.

## 3. Deliverables map

| Deliverable asked for | Where it lives | Status |
|---|---|---|
| Complete code and configs | `src/`, `configs/` | tracked per issue |
| One-click evaluation script | `scripts/run_eval.py` | tracked per issue |
| Evaluation report with before/after | `docs/eval/` | tracked per issue |
| Log field dictionary and sample logs | `docs/logging/`, `artifacts/logs/` | tracked per issue |
| Retrieval quality comparison | `docs/eval/retrieval-comparison.md` | tracked per issue |
| Issue diagnosis (>= 2 cases, >= 10% gain) | `docs/diagnosis/` | tracked per issue |

## 4. Targets (the numbers this repo must hit)

See [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md) for the full traceability matrix that
maps each target to a verification command and an owning issue.

| Family | Target |
|---|---|
| End-to-end latency | p90 <= 10 s |
| Concurrency | >= 5 concurrent requests, single instance, no degradation of p90 |
| Faithfulness | >= 0.85 (definition + rubric in `docs/metrics/`) |
| Context Precision | >= 0.70 |
| Answer Compliance | >= 0.80 baseline, >= 0.90 advanced target |
| Refusal Appropriateness | >= 0.80 baseline, >= 0.90 advanced target |
| Style Consistency | >= 0.80 baseline, >= 0.85 advanced target |
| Cost | token estimate per 1,000 calls, with model-version trade-off table |
| Observability | structured logs sufficient for monitoring and single-request diagnosis |
| Issue diagnosis | >= 2 documented regressions with log evidence and >= 10% post-fix gain |

## 5. Evidence policy (read this before trusting any number here)

Every metric in this repository carries a **provenance tag**. The distinction is enforced,
not stylistic:

| Tag | Meaning |
|---|---|
| `deterministic` | Produced by a fully reproducible local run (no network, seeded). Re-runnable by anyone with `python`. |
| `model-backed` | Produced with a real LLM provider. Requires credentials; numbers vary by model version and must state which. |
| `estimate` | Derived arithmetic from a stated price list. The price list is quoted inside the artifact; it is *not* a measurement. |

A metric with no provenance tag is a bug. See [`harness/RULES.md`](harness/RULES.md) R3.

## 6. Repository layout

```
src/                 service implementation (stdlib only by design)
configs/             retrieval modes, model versions, thresholds (no code change to switch)
corpus/              deterministic synthetic corpus generator
scripts/             run_tests.py (hermetic), run_eval.py (one-click eval), benchmarks
docs/                requirements, metrics rubrics, log dictionary, diagnosis cases
artifacts/           generated reports/logs (regenerated, not hand-edited)
harness/             the AI working harness: RULES.md, ROLES.md, skills/
.github/             issue templates, PR template, CI
```

## 7. Quickstart

```bash
python scripts/run_tests.py          # hermetic test suite, zero third-party deps
python scripts/run_eval.py --all     # retrieval comparison + generative scoring + ops report
```

Requires **Python 3.11+** and nothing else. No `pip install`, no network, no credentials:
the default provider is deterministic so that CI and a fresh clone produce identical numbers.

## 8. The harness

This repository is also a working agreement for AI agents operating on it:

* [`harness/RULES.md`](harness/RULES.md) - the hard rules (no issue, no code; no evidence, no close).
* [`harness/ROLES.md`](harness/ROLES.md) - planner / generator / evaluator / verifier split, and why the doer never grades itself.
* [`harness/skills/`](harness/skills/) - executable know-how: evaluation, issue lifecycle, evidence hygiene.
* [`CONTRIBUTING.md`](CONTRIBUTING.md) - the same workflow in human form.

Change policy in one line: **every change has an issue; every closing comment carries
reproducible output; large changes hang off an EPIC issue with child issues.**

## 9. License

MIT - see [`LICENSE`](LICENSE).
