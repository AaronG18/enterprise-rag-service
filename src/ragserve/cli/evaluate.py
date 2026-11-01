#!/usr/bin/env python3
"""One-click evaluation - the single entry point for every deliverable.

    python scripts/run.py --eval --all              # three-config comparison + generative scoring + ops report
    python scripts/run.py --eval --all --deliverables  # ...plus the committed deliverables, with paths
    python scripts/run.py --eval --out DIR          # write artefacts elsewhere

The retrieval mode and reranker are configuration, not code (FR-1). Override them at run time:

    python scripts/run.py --eval --mode vector_only          # score vector-only only
    python scripts/run.py --eval --mode hybrid --rerank off  # score hybrid, reranker off
    python scripts/run.py --eval --mode hybrid --rerank on   # score hybrid + reranker

`--deliverables` regenerates everything the brief asks to be handed over and prints every path
written: the deterministic snapshot, the comparison report, the sample logs and the QA dashboard.
`--refresh-model-backed` additionally re-measures the model-backed lane (needs the local model
servers); it refuses rather than filing a deterministic run under a model-backed label.

Deterministic: same code + same configs -> identical quality metrics. Latency is measured with
the cache disabled, and cache hit rate comes from a separate cached pass.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import REPO_ROOT

from ragserve.evaluation.runner import run_evaluation, run_model_backed  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="run everything (default behaviour)")
    parser.add_argument("--out", default=os.path.join(REPO_ROOT, "artifacts"))
    parser.add_argument("--cases", default=None)
    parser.add_argument("--provider", default="deterministic",
                        choices=("deterministic", "codebuddy-serve"),
                        help="codebuddy-serve needs the local CLI serve running; not used in CI")
    parser.add_argument("--cost", action="store_true",
                        help="print the token-cost estimate per 1,000 calls for this run")
    parser.add_argument("--models", default="",
                        help="comma-separated model versions for --provider codebuddy-serve")
    parser.add_argument("--max-cases", type=int, default=0, help="0 = all (smoke runs use 3)")
    parser.add_argument("--mode", default=None, choices=("vector_only", "hybrid"),
                        help="score only this mode (overrides configs/retrieval.json; FR-1)")
    parser.add_argument("--rerank", default=None, choices=("on", "off"),
                        help="enable/disable the reranker for the run (overrides the config; FR-1)")
    parser.add_argument("--corpus", metavar="DIR", default=None,
                        help="index the documents in this directory (.txt, .md, .pdf) instead of "
                             "the built-in synthetic corpus, and write a corpus report. The "
                             "labelled comparison is skipped: its cases name synthetic documents "
                             "and would score nothing meaningful here.")
    parser.add_argument("--deliverables", action="store_true",
                        help="after the run, also regenerate the committed deliverables - the "
                             "deterministic snapshot, the comparison report, the sample logs and "
                             "the QA dashboard - and print every path written")
    parser.add_argument("--refresh-model-backed", action="store_true",
                        help="with --deliverables: re-measure the model-backed retrieval lane "
                             "first (needs the local model servers from scripts/run.py)")
    parser.add_argument("--seed-model-backed", metavar="METRICS_JSON", default=None,
                        help="commit an existing model-backed run (an artifacts/eval/<id>/"
                             "metrics.json) as the snapshot, without re-measuring")
    args = parser.parse_args()

    # A reviewer should never have to guess where they are or where the files land: say both
    # before printing a single number.
    print("Terminal folder   : %s" % os.getcwd())
    print("Repository root   : %s" % REPO_ROOT)
    print()

    if args.seed_model_backed:
        from ragserve.evaluation.deliverables import (  # noqa: E402
            SNAPSHOT_MODEL_BACKED,
            write_snapshot,
        )
        with open(args.seed_model_backed, "r", encoding="utf-8") as fh:
            seed = json.load(fh)
        seed_id = os.path.basename(os.path.dirname(os.path.abspath(args.seed_model_backed)))
        write_snapshot(seed, os.path.join(REPO_ROOT, *SNAPSHOT_MODEL_BACKED.split("/")), seed_id)
        print("seeded docs/eval/model-backed-retrieval-metrics.json from run %s" % seed_id)

    if args.corpus and args.deliverables:
        # Silently ignoring the flag would leave a reviewer believing the committed deliverables
        # describe their documents. They describe the synthetic corpus, so refuse instead.
        print("REFUSED: --corpus and --deliverables cannot be combined.")
        print("The committed deliverables (snapshot, comparison report, sample logs, dashboard) "
              "describe the synthetic corpus; a --corpus run produces a corpus report instead.")
        print("Run --corpus alone to measure your documents, or drop --corpus to regenerate the "
              "committed deliverables.")
        return 1

    if args.corpus:
        # Deliberately does not touch docs/eval/*. The labelled comparison belongs to the
        # synthetic corpus; measuring it against someone else's files would publish a number
        # nobody could reproduce.
        from ragserve.evaluation.corpus_report import run_corpus_report  # noqa: E402

        outcome = run_corpus_report(args.corpus, REPO_ROOT, args.out)
        report = outcome["report"]
        print("Corpus report (user-supplied documents)")
        print("  source        :", report["source_dir"])
        print("  documents     :", report["doc_count"], "chunks:", report["chunk_count"],
              "languages:", report["per_language"])
        for item in report.get("skipped_files") or []:
            print("  skipped       : %s (%s)" % (item["file"], item["reason"]))
        print("  index build   : %.3f ms" % report["index_build_ms"])
        print("  recall@5      :", report["recall@5"])
        print("  mrr           :", report["mrr"])
        print("  ndcg          :", report["ndcg"])
        print("  context_precision:", report["context_precision"])
        print("  p50 / p95 ms  :", report["p50_latency_ms"], "/", report["p95_latency_ms"])
        print("  refusal_rate  :", report["refusal_rate"])
        print("  provenance    :", report["provenance"])
        print("  note          :", report["provenance_note"])
        print("  artifact      :", outcome["paths"]["markdown"])
        print()
        print("Outputs")
        print("  corpus report  : %s" % outcome["paths"]["markdown"])
        return 0

    if args.provider == "codebuddy-serve":
        models = [m.strip() for m in args.models.split(",") if m.strip()]
        if not models:
            parser.error("--models is required for --provider codebuddy-serve")
        result = run_model_backed(REPO_ROOT, args.out, models,
                                 os.path.join(REPO_ROOT, "configs", "providers.json"),
                                 args.cases, args.max_cases)
        print("provenance     :", result["run_metadata"]["provenance"])
        print("token usage    :", result["run_metadata"]["token_usage_provenance"])
        print("models         :", result["run_metadata"]["models"])
        print()
        for key, metrics in result["comparison"].items():
            print("  %-34s %s" % (key, metrics))
        print()
        print("artifacts      :", result["artifacts"]["metrics"])
        return 0

    # The model-backed lane is measured first, on purpose: if it is refused we must not have
    # already replaced the deterministic snapshot, or the repository is left half-updated.
    model_payload = None
    model_run_id = None
    if args.refresh_model_backed:
        os.environ.pop("RAGSERVE_EMBEDDING_PROVIDER", None)
        os.environ.pop("RAGSERVE_RERANKER_PROVIDER", None)
        model_result = run_evaluation(REPO_ROOT, args.out, args.cases,
                                      mode=args.mode,
                                      rerank_enabled=(args.rerank == "on") if args.rerank else None)
        model_run_id = os.path.basename(os.path.dirname(model_result["artifacts"]["metrics"]))
        provenance = str(model_result["run_metadata"].get("provenance", ""))
        if "model-backed" not in provenance:
            print("REFUSED: this run is '%s', not model-backed (no model server reachable)."
                  % provenance)
            print("Start the two servers from scripts/run.py and re-run. Nothing was "
                  "written: the existing snapshots and report are untouched.")
            return 1
        model_payload = model_result

    if args.deliverables:
        # The deterministic snapshot is the CI baseline, so the run that produces it is pinned:
        # published numbers must be reproducible offline, with no model server and no credential.
        os.environ["RAGSERVE_EMBEDDING_PROVIDER"] = "deterministic"
        os.environ["RAGSERVE_RERANKER_PROVIDER"] = "deterministic"

    result = run_evaluation(REPO_ROOT, args.out, args.cases,
                            mode=args.mode,
                            rerank_enabled=(args.rerank == "on") if args.rerank else None)
    meta = result["run_metadata"]
    print("corpus_version :", meta["corpus_version"])
    print("case_count     :", meta["case_count"])
    print("provenance     :", meta["provenance"])
    print()
    print("Operations")
    for key in ("p50_latency_ms", "p95_latency_ms", "token_usage_total",
                "cache_hit_rate", "refusal_rate", "answer_compliance_rate"):
        print("  %-24s %s" % (key, result["operations"][key]))
    print()
    print("Configuration comparison")
    for name, metrics in result["comparison"].items():
        print("  %-16s %s" % (name, metrics))
    print()
    print("artifacts       :", result["artifacts"]["metrics"])

    if args.cost:
        # The brief asks for a token-cost estimate per 1,000 calls. It is computed from the
        # tokens this run actually consumed - never from an assumed number - and it says
        # "no cost" rather than inventing a price.
        from ragserve.evaluation.cost import (  # noqa: E402
            estimate_from_usage,
            load_pricing,
            render_cost_text,
        )

        # The number of calls comes from the measurement itself, not from arithmetic here.
        calls = result["operations"].get("calls_measured", meta["case_count"])
        total = result["operations"]["token_usage_total"]
        estimate = estimate_from_usage(
            {"input_tokens": result["operations"].get("token_usage_input_total", 0),
             "output_tokens": result["operations"].get("token_usage_output_total", 0)},
            calls,
            load_pricing(os.path.join(REPO_ROOT, "configs", "pricing.json")),
            meta.get("model_version") or meta.get("provider", "deterministic"))
        estimate["token_usage_total"] = total
        print()
        print(render_cost_text(estimate))

    written = []
    if args.deliverables:
        from ragserve.evaluation import deliverables as D  # noqa: E402

        run_id = os.path.basename(os.path.dirname(result["artifacts"]["metrics"]))
        snapshot = os.path.join(REPO_ROOT, *D.SNAPSHOT_DETERMINISTIC.split("/"))
        D.write_snapshot(result, snapshot, run_id)
        written.append(("deterministic snapshot", snapshot))
        if model_payload is not None:
            model_snapshot = os.path.join(REPO_ROOT, *D.SNAPSHOT_MODEL_BACKED.split("/"))
            D.write_snapshot(model_payload, model_snapshot, model_run_id)
            written.append(("model-backed snapshot", model_snapshot))
        written.append(("comparison report", D.regenerate_comparison_report(REPO_ROOT)))
        written.append(("sample logs", D.regenerate_sample_logs(REPO_ROOT)))
        written.append(("QA dashboard", D.regenerate_dashboard(REPO_ROOT)))

    print()
    print("Outputs")
    print("  evaluation artefacts : %s" % result["artifacts"]["metrics"])
    for label, path in written:
        print("  %-21s: %s" % (label, path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
