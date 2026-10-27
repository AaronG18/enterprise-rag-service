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

See [`docs/deliverables.md`](docs/deliverables.md) for the full map with reproduction commands.

| Deliverable asked for | Where it lives |
|---|---|
| Complete code and configs | `src/`, `configs/` |
| One-click evaluation script | `scripts/run_eval.py` |
| Evaluation report with before/after | `docs/eval/retrieval-comparison.md` (+ generated `artifacts/eval/<run>/`) |
| Log field dictionary and sample logs | `docs/logging/log_fields.md`, `docs/logging/sample_logs.md` |
| Retrieval quality comparison | `docs/eval/retrieval-comparison.md` |
| Issue diagnosis (>= 2 cases, >= 10% gain) | `docs/diagnosis/INC-001-refusal-gate.md`, `docs/diagnosis/INC-002-ocr-penalty.md` |

## 4. Targets and current measured values

Measured with the deterministic provider on corpus `bea626ce863a0e44`, 30 labelled cases;
full detail and caveats in [`docs/eval/retrieval-comparison.md`](docs/eval/retrieval-comparison.md).

See [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md) for the full traceability matrix that
maps each target to a verification command and an owning issue.

| Family | Target | Measured |
|---|---|---|
| End-to-end latency | p90 <= 10 s | 10.5-34.8 ms at 5 concurrent |
| Concurrency | >= 5 concurrent, single instance | 5 concurrent, 0 errors |
| Faithfulness | >= 0.85 | 1.0 |
| Context Precision | >= 0.70 | 0.9529 |
| Answer Compliance | >= 0.80 / 0.90 | 0.9000 |
| Refusal Appropriateness | >= 0.80 / 0.90 | 0.9000 |
| Style Consistency | >= 0.80 / 0.85 | 1.0 |
| Cost | estimate per 1,000 calls | arithmetic provided; `configs/pricing.json` must be filled |
| Observability | structured logs, single-request reconstruction | 5 stages per request, documented dictionary |
| Issue diagnosis | >= 2 cases, >= 10% gain | 2 cases: +575%, +100% |

**Read these numbers with the caveat they carry:** they come from the deterministic provider,
which composes answers from verbatim retrieved sentences. They establish the pipeline floor
(never fabricates, always cites, refuses when it should), not the behaviour of a real model.

The repository also carries a **model-backed lane** (`model-backed` provenance): 180 real model
calls over 2 model versions x 3 retrieval configurations. Real generation initially missed the
targets (faithfulness 0.64-0.72, compliance 0.73-0.90) - two defects in our own pipeline were
found and fixed as a result (INC-003), and the best configuration now meets every advanced target:
**hy3 + hybrid, faithfulness 0.8913, refusal appropriateness 0.9000, style 0.8957, compliance
0.965**. See [`docs/eval/model-backed.md`](docs/eval/model-backed.md),
[`docs/diagnosis/INC-003-real-generation-quality.md`](docs/diagnosis/INC-003-real-generation-quality.md)
and [ADR 0004](docs/adr/0004-model-version-tradeoff.md) - which records a recommendation
reversal once the measurements were corrected.

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
