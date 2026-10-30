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
python scripts/start.py              # serves the API + UI on http://127.0.0.1:8174
```

One command: the corpus is generated deterministically, indexed in memory (~19 ms measured),
and the service starts. **No database, no embedding model, no API key, no `pip install`, no
network.**
Full guide: [`docs/deployment.md`](docs/deployment.md).

Then either click around the UI, or:

```bash
python scripts/run_tests.py          # hermetic test suite, zero third-party deps
python scripts/run_eval.py --all     # retrieval comparison + generative scoring + ops report
python scripts/run_bench.py --http --concurrency 5 --assert   # service-level load test
```

### Real models: bundled, open-source, and keyless

Everything above runs with **no credentials at all** on the offline deterministic backend, so a
cold clone always reproduces the published numbers. For a real semantic model, this repository
ships a one-command setup that installs **free, open-source, industrial-grade models locally** -
no API key, no account, no third-party Python package:

```bash
python scripts/setup_models.py          # ~1 GB, one time, into vendor/ and models/
python scripts/setup_models.py --check  # just report what is already present
```

It fetches a self-contained `llama.cpp` server into `vendor/llama.cpp/` plus two weights into
`models/`:

| what | model | why this one |
|---|---|---|
| embedding | **BGE-M3** (Q8_0, 1024-d) | multilingual (CN/EN) for the bilingual corpus; free for commercial use |
| reranking | **bge-reranker-v2-m3** (Q4_K_M) | a real **cross-encoder**, multilingual; not a hand-written feature scorer |

The runtime lives inside the repository (`vendor/`, `models/`, both gitignored) rather than in
`%LOCALAPPDATA%` or `~/.cache`, so the path is predictable: the config, the docs and the setup
script all point at the same place. Note that gitignored files do **not** travel with a `git
pull` - a reviewer re-creates them by running `setup_models.py` above, which is why that script
is committed.

Start the two servers (they are plain executables: no installer, no service, no admin rights):

```bash
vendor/llama.cpp/llama-server.exe -m models/bge-m3-q8_0.gguf \
    --embedding --host 127.0.0.1 --port 8011
vendor/llama.cpp/llama-server.exe -m models/bge-reranker-v2-m3-q4_k_m.gguf \
    --embedding --pooling rank --host 127.0.0.1 --port 8012
```

The first speaks an OpenAI-compatible `/v1/embeddings`; the second a `/v1/rerank`. Both are
reached with the standard library, so no dependency is added. Verified locally: the embedding
endpoint returns **1024-d** vectors, and the reranker scores a relevant passage at **6.13** vs
**-10.15** for an unrelated one, i.e. real cross-encoder scores rather than a degenerate
constant.

Then point the config at them - still **configuration, never a code change**:

| field | value for the bundled models |
|---|---|
| `embedding_provider` | `openai-compatible` |
| `embedding_endpoint` | `http://127.0.0.1:8011/v1` |
| `embedding_model` | `bge-m3` |
| `vector_dim` | `1024` (BGE-M3's width) |

Prefer a hosted API instead? Point `embedding_endpoint` at any OpenAI-compatible service
(SiliconFlow, DashScope/Qwen, your own deployment) and set `embedding_api_key_env` to the env var
holding its key. The key is never logged. If it is missing the server **fails loudly**
(`ProviderUnavailable`) rather than silently degrading, so a misconfigured production path is
never mistaken for a working one.

Requires **Python 3.11+** and nothing else.

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
