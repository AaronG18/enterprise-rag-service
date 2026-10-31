#!/usr/bin/env python3
"""One-click evaluation.

    python scripts/run_eval.py --all        # three-config comparison + generative scoring + ops report
    python scripts/run_eval.py --out DIR   # write artefacts elsewhere

The retrieval mode and reranker are configuration, not code (FR-1). Override them at run time:

    python scripts/run_eval.py --mode vector_only          # score vector-only only
    python scripts/run_eval.py --mode hybrid --rerank off  # score hybrid, reranker off
    python scripts/run_eval.py --mode hybrid --rerank on   # score hybrid + reranker

Deterministic: same code + same configs -> identical quality metrics. Latency is measured with
the cache disabled, and cache hit rate comes from a separate cached pass.
"""
from __future__ import annotations

import argparse
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

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
    args = parser.parse_args()

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
            meta.get("provider", "deterministic"))
        estimate["token_usage_total"] = total
        print()
        print(render_cost_text(estimate))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
