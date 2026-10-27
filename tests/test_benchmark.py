"""EPIC #7 / SUB 29, 30: concurrency benchmark and cost estimation."""
from __future__ import annotations

import os
import unittest

from ragserve.evaluation.bench import LATENCY_BOUND_MS, render_bench_text, run_benchmark
from ragserve.evaluation.cost import (
    cost_per_1000_calls,
    estimate_from_usage,
    load_pricing,
    render_cost_text,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestConcurrency(unittest.TestCase):
    def test_five_concurrent_within_bound(self):
        summary = run_benchmark(ROOT, concurrency=5, requests=20)
        self.assertEqual(summary["errors"], 0, "errors: %s" % summary["error_samples"])
        self.assertLessEqual(summary["p90_latency_ms"], LATENCY_BOUND_MS)
        self.assertTrue(summary["within_bound"])
        self.assertEqual(summary["concurrency"], 5)

    def test_summary_reports_percentiles_and_throughput(self):
        summary = run_benchmark(ROOT, concurrency=5, requests=10)
        for field in ("p50_latency_ms", "p90_latency_ms", "p95_latency_ms",
                      "throughput_rps", "max_latency_ms"):
            self.assertIn(field, summary)
        self.assertGreater(summary["throughput_rps"], 0.0)

    def test_bench_report_mentions_the_bound(self):
        summary = run_benchmark(ROOT, concurrency=5, requests=5)
        text = render_bench_text(summary)
        self.assertIn("p90_latency_ms", text)
        self.assertIn("within_bound", text)


class TestCost(unittest.TestCase):
    def test_arithmetic_is_explicit(self):
        """1,000 input + 500 output tokens per call at 1.00 / 2.00 per 1k -> 2,000 USD per 1,000 calls."""
        self.assertEqual(cost_per_1000_calls(1000, 500, 1.0, 2.0), 2000.0)

    def test_unset_price_yields_no_number(self):
        self.assertIsNone(cost_per_1000_calls(1000, 500, None, None))

    def test_estimate_marks_unset_price_rather_than_zero(self):
        estimate = estimate_from_usage({"input_tokens": 1000, "output_tokens": 500}, calls=10,
                                       pricing={"m": {"input_per_1k_usd": None,
                                                      "output_per_1k_usd": None}},
                                       model_version="m")
        self.assertFalse(estimate["price_provided"])
        self.assertIsNone(estimate["cost_per_1000_calls_usd"])
        self.assertIn("no price is configured", render_cost_text(estimate))

    def test_pricing_config_has_no_invented_prices(self):
        pricing = load_pricing(os.path.join(ROOT, "configs", "pricing.json"))
        for model, entry in pricing.items():
            if model.startswith("_"):
                continue
            for side in ("input_per_1k_usd", "output_per_1k_usd"):
                self.assertIn(side, entry)
        placeholder = pricing["hosted-model-placeholder"]
        self.assertIsNone(placeholder["input_per_1k_usd"])


if __name__ == "__main__":
    unittest.main()
