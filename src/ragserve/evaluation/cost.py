"""Token cost estimation.

Deliberate design choice: **no prices are invented.** `configs/pricing.json` holds entries the
operator must fill; unset prices are `null`, and the report says "price not set" instead of
printing a confident 0.00. A cost table with fabricated prices is worse than no cost table.
"""
from __future__ import annotations

import json
import os
from typing import Dict, Optional


def load_pricing(path: str) -> Dict:
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def cost_per_1000_calls(input_tokens_per_call: float, output_tokens_per_call: float,
                        price_input_per_1k: Optional[float],
                        price_output_per_1k: Optional[float]) -> Optional[float]:
    """Return USD per 1,000 calls, or None when a price is unset.

    Arithmetic only - no rounding to a flattering figure.
    """
    if price_input_per_1k is None or price_output_per_1k is None:
        return None
    per_call = (input_tokens_per_call / 1000.0 * price_input_per_1k
                + output_tokens_per_call / 1000.0 * price_output_per_1k)
    return round(per_call * 1000.0, 4)


def estimate_from_usage(usage_totals: Dict[str, float], calls: int, pricing: Dict,
                         model_version: str) -> Dict:
    """`usage_totals` comes from a measured run - never from a guess."""
    entry = pricing.get(model_version, {})
    price_in = entry.get("input_per_1k_usd")
    price_out = entry.get("output_per_1k_usd")
    per_call_in = usage_totals.get("input_tokens", 0.0) / max(1, calls)
    per_call_out = usage_totals.get("output_tokens", 0.0) / max(1, calls)
    total = cost_per_1000_calls(per_call_in, per_call_out, price_in, price_out)
    return {
        "model_version": model_version,
        "calls_measured": calls,
        "input_tokens_per_call": round(per_call_in, 2),
        "output_tokens_per_call": round(per_call_out, 2),
        "price_input_per_1k_usd": price_in,
        "price_output_per_1k_usd": price_out,
        "cost_per_1000_calls_usd": total,
        "price_provided": total is not None,
        "provenance": "estimate",
    }


def render_cost_text(estimate: Dict) -> str:
    lines = ["Token cost estimate", "=" * 19, ""]
    for key, value in estimate.items():
        lines.append("  %-26s %s" % (key + ":", value))
    if not estimate.get("price_provided"):
        lines.append("")
        lines.append("  NOTE: no price is configured for this model, so no cost is reported.")
        lines.append("  Fill configs/pricing.json rather than accepting a placeholder number.")
    return "\n".join(lines) + "\n"
