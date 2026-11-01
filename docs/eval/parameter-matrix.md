# Run-time parameter matrix

Provenance: `deterministic` (seeded, offline, no model server, no credential). Every row below
was produced by a real `python scripts/run.py --eval <flags>` invocation and the exit code / key
metric are quoted exactly. The point is to show that **every combination an interviewer will try
behaves**, and what each one prints.

The retrieval mode and the reranker are configuration, not code (FR-1). The entry script is
`scripts/run.py` alone - there is no second script (issue #98).

## Flags

| Flag | Values | What it does |
|---|---|---|
| `--mode` | `vector_only` \| `hybrid` | override the retrieval configuration (config default: `hybrid`) |
| `--rerank` | `on` \| `off` | override the reranker toggle (config default: `on`) |
| `--corpus <dir>` | path | index a reviewer-supplied directory instead of the synthetic corpus |
| `--all` | - | run the three-config comparison + generative scoring + ops report |
| `--deliverables` | - | after the run, regenerate the committed deliverables and print every path |
| `--refresh-model-backed` | - | re-measure the model-backed lane (needs the local model servers; refuses otherwise) |
| `--cost` | - | emit a per-1k-call cost estimate from `configs/pricing.json` |
| `--max-cases N` | int | limit labelled cases (smoke runs) |
| `--cases <path>` | path | use a different labelled-case file |

## Measured matrix (deterministic, corpus `a716676ca46bfa44`, 85 labelled cases)

Recall@5 is the headline number; the full set (mrr, ndcg@10, context_precision, faithfulness,
compliance, refusal appropriateness, style) is in `docs/eval/retrieval-comparison.md`.

| Command | Config actually run | recall@5 | exit |
|---|---|---|---|
| `scripts/run.py --all` | vector_only / hybrid / hybrid+rerank | `0.7722` / `0.8987` / `0.9620` | 0 |
| `scripts/run.py --mode vector_only` | vector_only **+rerank** (config default on) | `0.8861` | 0 |
| `scripts/run.py --mode hybrid` | hybrid **+rerank** | `0.9620` | 0 |
| `scripts/run.py --rerank on` | hybrid **+rerank** | `0.9620` | 0 |
| `scripts/run.py --rerank off` | hybrid (no rerank) | `0.8987` | 0 |
| `scripts/run.py --mode hybrid --rerank on` | hybrid **+rerank** | `0.9620` | 0 |
| `scripts/run.py --mode vector_only --rerank off` | vector_only (no rerank) | `0.7722` | 0 |
| `scripts/run.py --corpus tests/data/external-corpus` | external corpus, self-labelled queries | `1.0` (proxy) | 0 |
| `scripts/run.py --all --cost` | as `--all` + cost estimate | `0.9620` | 0 |
| `scripts/run.py --max-cases 3` | `--all` limited to 3 cases | exit 0 | 0 |
| `scripts/run.py --cases eval/eval_cases.json` | `--all` on an explicit case file | exit 0 | 0 |

Read the `--corpus` row as a **self-labelled proxy**: the queries are derived from the documents
themselves (one per document, from its title and first section), so the number is high by
construction. It answers "are these files indexed and retrievable", and is only meaningful
compared against the same corpus under another configuration - never against the synthetic
labelled benchmark.

## One command for every deliverable

`scripts/run.py --all --deliverables` regenerates the deterministic snapshot, the comparison report,
the sample logs and the QA dashboard, then prints every path written:

```
Outputs
  evaluation artefacts : D:\Projects\AIA\artifacts\eval\<run>\metrics.json
  deterministic snapshot: D:\Projects\AIA\docs\eval\deterministic-metrics.json
  comparison report    : D:\Projects\AIA\docs\eval\retrieval-comparison.md
  sample logs          : D:\Projects\AIA\docs\logging/sample_logs.md
  QA dashboard         : D:\Projects\AIA\docs/qa/qa-dashboard.html
```

`--refresh-model-backed` (no servers running) **refuses** before writing anything - it does not
file a deterministic run under a model-backed label. Verified by checking the snapshot's
`mtime` is unchanged after the refused run.

## Honesty notes a reviewer will probe

* `--mode vector_only` does **not** disable the reranker on its own; the reranker is a separate
  config toggle, on by default. That is why its row reads `vector_only+rerank`. The report names
  the run after what it actually measured, not the flag that was passed (issue #98).
* The deterministic backend composes answers from verbatim retrieved sentences, so its generative
  metrics (faithfulness, compliance, style) are a **pipeline floor**, not a real-model result.
  The real-model lane lives in the model-backed snapshot and in `docs/eval/model-backed.md`.
* Latency is measured with the cache disabled; cache hit rate comes from a separate cached pass,
  so reported latency is never a cache hit.
