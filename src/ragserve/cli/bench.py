#!/usr/bin/env python3
"""Concurrency benchmark.

    python scripts/run.py --bench --concurrency 5 --requests 30
    python scripts/run.py --bench --concurrency 5 --assert   # exit 1 if p90 exceeds 10 s or any error

One service instance, cache disabled, real requests through worker threads.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

from . import REPO_ROOT

from ragserve.evaluation.bench import (  # noqa: E402
    LATENCY_BOUND_MS,
    render_bench_text,
    run_benchmark,
    run_benchmark_http,
)
from ragserve.evaluation.cost import estimate_from_usage, load_pricing, render_cost_text  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--requests", type=int, default=30)
    parser.add_argument("--out", default=os.path.join(REPO_ROOT, "artifacts"))
    parser.add_argument("--http", action="store_true",
                        help="drive real HTTP requests against the API server (cache disabled)")
    parser.add_argument("--assert", dest="do_assert", action="store_true",
                        help="exit non-zero when p90 exceeds the bound or any request errored")
    args = parser.parse_args()

    if args.http:
        summary = run_benchmark_http(REPO_ROOT, concurrency=args.concurrency,
                                     requests=args.requests)
    else:
        summary = run_benchmark(REPO_ROOT, concurrency=args.concurrency, requests=args.requests)

    run_id = time.strftime("%Y%m%d-%H%M%S")
    target = os.path.join(args.out, "bench", run_id)
    os.makedirs(target, exist_ok=True)
    with open(os.path.join(target, "bench.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(summary, fh, ensure_ascii=False, sort_keys=True, indent=2)
        fh.write("\n")
    with open(os.path.join(target, "bench.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(render_bench_text(summary))

    print(render_bench_text(summary))
    print("artifacts:", target)

    if args.do_assert and (not summary["within_bound"] or summary["errors"]):
        print("FAIL: p90 %s ms exceeds bound %s ms, or errors=%s"
              % (summary["p90_latency_ms"], LATENCY_BOUND_MS, summary["errors"]),
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
