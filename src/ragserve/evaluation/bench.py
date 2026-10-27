"""Concurrency benchmark.

One service instance, N worker threads, real requests. The point is the constraint in the
brief - 90% of requests under 10 s at >= 5 concurrent - which is a *loaded* property and cannot
be inferred from sequential latency.

The cache is disabled here: otherwise the benchmark measures the cache, not the service.
"""
from __future__ import annotations

import json
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List

from ..corpus.builder import CorpusConfig, build_corpus
from ..retrieval.pipeline import RetrievalConfig
from ..service import GenerationConfig, RagService
from .metrics import percentile

LATENCY_BOUND_MS = 10_000.0


def run_benchmark(root: str, concurrency: int = 5, requests: int = 30,
                  queries: List[str] | None = None) -> Dict:
    configs = os.path.join(root, "configs")
    corpus = build_corpus(CorpusConfig.from_json(os.path.join(configs, "corpus.json")))
    retrieval = RetrievalConfig.from_json(os.path.join(configs, "retrieval.json"))
    generation = GenerationConfig.from_json(os.path.join(configs, "generation.json"))

    if queries is None:
        cases_path = os.path.join(root, "eval", "eval_cases.json")
        with open(cases_path, "r", encoding="utf-8") as fh:
            queries = [c["query"] for c in json.load(fh)]
    if not queries:
        raise ValueError("no queries to benchmark")

    service = RagService(corpus, retrieval, generation)  # no cache: measure the service
    plan = [queries[i % len(queries)] for i in range(requests)]

    def one(query: str) -> Dict:
        started = time.perf_counter()
        try:
            result = service.answer(query)
            error = None
            refused = result.answer.refused
        except Exception as exc:  # noqa: BLE001 - a benchmark must record, not crash
            error = type(exc).__name__ + ": " + str(exc)
            refused = None
        return {"latency_ms": (time.perf_counter() - started) * 1000.0, "error": error,
                "refused": refused}

    wall_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        results = list(pool.map(one, plan))
    wall_seconds = time.perf_counter() - wall_start

    latencies = [r["latency_ms"] for r in results]
    errors = [r for r in results if r["error"]]
    ordered = sorted(latencies)
    return {
        "concurrency": concurrency,
        "requests": requests,
        "p50_latency_ms": round(percentile(latencies, 50), 3),
        "p90_latency_ms": round(percentile(latencies, 90), 3),
        "p95_latency_ms": round(percentile(latencies, 95), 3),
        "max_latency_ms": round(max(ordered), 3) if ordered else 0.0,
        "mean_latency_ms": round(statistics.fmean(latencies), 3) if latencies else 0.0,
        "throughput_rps": round(requests / wall_seconds, 3) if wall_seconds else 0.0,
        "errors": len(errors),
        "error_samples": [e["error"] for e in errors[:3]],
        "latency_bound_ms": LATENCY_BOUND_MS,
        "within_bound": (percentile(latencies, 90) <= LATENCY_BOUND_MS) if latencies else False,
        "provenance": "deterministic-logic, wall-clock-latency",
    }


def render_bench_text(summary: Dict) -> str:
    lines = ["Concurrency benchmark", "=" * 20, ""]
    for key in ("concurrency", "requests", "p50_latency_ms", "p90_latency_ms", "p95_latency_ms",
                "max_latency_ms", "mean_latency_ms", "throughput_rps", "errors",
                "latency_bound_ms", "within_bound", "provenance"):
        lines.append("  %-20s %s" % (key + ":", summary.get(key)))
    return "\n".join(lines) + "\n"
