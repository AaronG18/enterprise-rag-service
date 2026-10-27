#!/usr/bin/env python3
"""One-click evaluation.

    python scripts/run_eval.py --all        # three-config comparison + generative scoring + ops report
    python scripts/run_eval.py --out DIR   # write artefacts elsewhere

Deterministic: same code + same configs -> identical quality metrics. Latency is measured with
the cache disabled, and cache hit rate comes from a separate cached pass.
"""
from __future__ import annotations

import argparse
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

from ragserve.evaluation.runner import run_evaluation  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="run everything (default behaviour)")
    parser.add_argument("--out", default=os.path.join(REPO_ROOT, "artifacts"))
    parser.add_argument("--cases", default=None)
    args = parser.parse_args()

    result = run_evaluation(REPO_ROOT, args.out, args.cases)
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
