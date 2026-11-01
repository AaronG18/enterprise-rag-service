# ADR 0005: local, keyless model serving for retrieval (measured)

## Status

Accepted for the model-backed retrieval lane. The deterministic provider remains the CI baseline;
this decision governs how real embeddings and a real cross-encoder reranker are served in the
delivered default.

## Context

The brief (see `docs/jd.md`, "Candidates may choose any tech stack") names **no specific tool**;
the only requirement it implies is real semantic retrieval, reproducible by a reviewer who clones
the repo. Two stages need a real model:

1. **embedding** - a multilingual bi-encoder (the corpus is bilingual CN/EN);
2. **rerank** - a real **cross-encoder**, not a hand-written feature scorer.

The delivered path must be **keyless** (no API key, no account, no third-party Python package) so a
cold clone reproduces the published numbers with `python` alone, and the model binaries must live
in the project tree (so the path is predictable) rather than in `%LOCALAPPDATA%` / `~/.cache`.

## Candidates considered

| Option | Embedding | Rerank (cross-encoder) | Keyless | In project tree | Verdict |
|---|---|---|---|---|---|
| **llama.cpp** (bundled server) | `/v1/embeddings` | `/v1/rerank` with `--pooling rank` | yes (loopback) | yes (`vendor/`, `models/`) | **chosen** |
| **Ollama** | `/api/embed` (bi-encoder only) | **none** - no rerank endpoint | yes | no (system service, `~/.ollama`) | rejected |
| **TEI** (HuggingFace) | yes | yes | yes | server container | rejected: needs Docker, and `registry-1.docker.io` is blocked here |
| **Hosted API** (SiliconFlow / DashScope) | yes | yes | **no** (key + network) | n/a | opt-in config only, not the default |

Ollama was rejected even though it is simpler to start: it exposes reranking only as a bi-encoder
similarity (`/api/embed`), which is not a cross-encoder, so it cannot satisfy stage 2. It also
installs a system-level service and stores weights outside the project tree. llama.cpp covers both
stages from one executable and stores everything under `vendor/` + `models/`, both gitignored.

## Measured evidence (not "it works", but "it works and here are the numbers")

Setup: `python scripts/run.py --setup` (ghproxy for llama.cpp, hf-mirror for the GGUFs, because
`objects.githubusercontent.com`, `huggingface.co` and `registry-1.docker.io` are all unreachable
from this network). Result: `vendor/llama.cpp/` (64 MB) + `models/bge-m3-q8_0.gguf` (634 MB) +
`models/bge-reranker-v2-m3-q4_k_m.gguf` (438 MB) ≈ 1 GB, all gitignored.

Embedding (bge-m3, Q8_0, port 8011):

```
/v1/embeddings -> dim=1024   cosine(EN query, ZH query) = 0.4551
```

Rerank (bge-reranker-v2-m3, Q4_K_M, `--pooling rank`, port 8012) on a real case:

```
score=   6.13  relevant passage      (ranked 1)
score=  -9.52  partially relevant
score= -10.15  unrelated passage     (ranked last)
```

These are real cross-encoder scores, not a degenerate constant. The full three-configuration eval
(85 cases, corpus `a716676ca46bfa44`, provenance `model-backed-retrieval`):

| Config | recall@5 | mrr | ndcg | context_precision |
|---|---|---|---|---|
| vector_only | 0.9747 | 0.9034 | 0.9216 | 0.8648 |
| hybrid | **1.0** | **0.9610** | **0.9708** | **0.9212** |
| hybrid+rerank | 1.0 | 0.9523 | 0.9641 | 0.8673 |

**Honest finding:** on this corpus the cross-encoder reranker did **not** improve over hybrid - it
reordered within an already-saturated candidate set (hybrid already has recall@5 = 1.0) and MRR
dipped slightly. That is a measured result, reported as-is, not hidden. The point of the change was
to *use* a real cross-encoder behind a config switch; whether it wins on a given corpus is data,
not a foregone conclusion.

## Cost / trade-off

* **CPU-bound:** ~0.34 s/chunk on this machine (no usable GPU path - the bundled CUDA build
  silently fell back to CPU on a GTX 1050 Ti). A full eval builds the same 204-chunk index several
  times; mitigated by a **process-wide shared embedding cache** (re-embed each chunk once) and by
  raising timeouts to 120 s so a slow chunk never trips a spurious failure. Measured full run ≈
  10 min on CPU.
* **1 GB download**, gitignored, recreated by `setup_models.py` (the script is committed so the
  reviewer can reproduce without the binaries travelling in the repo).
* **No third-party Python dependency** - both endpoints are reached with the standard library, so
  R7 (stdlib-only shipped code, hermetic CI) is preserved. CI pins both stages to the
  deterministic backend via `RAGSERVE_EMBEDDING_PROVIDER` / `RAGSERVE_RERANKER_PROVIDER`, so the
  test gate stays offline and keyless.

## Consequences

* The delivered default is a real, keyless, offline model; swapping to a hosted API is a config
  change (three fields), never a code change (FR1 / NFR2).
* Provenance is **measured**, not declared: `retrieval_provenance()` reads the `degraded_*` flags
  the factories set on a fallback, so a run that silently dropped to deterministic can never be
  reported as `model-backed`.
* A reviewer who does nothing but `git clone` + `python scripts/run.py --test` still gets a green,
  keyless, offline suite (deterministic fallback, loudly flagged), and one who follows
  `setup_models.py` + the two server commands gets the real numbers above.
