"""Report writer: text and CSV, from one run (never a second, divergent run)."""
from __future__ import annotations

import csv
import io
from typing import Dict, List, Sequence

# The operational contract: a report missing any of these is not a report.
OPS_FIELDS = (
    "p50_latency_ms",
    "p95_latency_ms",
    "token_usage_total",
    "cache_hit_rate",
    "refusal_rate",
    "answer_compliance_rate",
)

QUALITY_FIELDS = (
    "recall@5",
    "mrr",
    "ndcg",
    "context_precision",
    "faithfulness",
    "refusal_appropriateness",
    "style_consistency",
)


def render_text(operations: Dict[str, float], comparison: Dict[str, Dict[str, float]],
                run_metadata: Dict[str, object]) -> str:
    out = io.StringIO()
    out.write("Enterprise RAG Service - evaluation report\n")
    out.write("=" * (38 + 0) + "\n\n")
    out.write("Run metadata\n")
    for key in sorted(run_metadata):
        out.write("  %-22s %s\n" % (key + ":", run_metadata[key]))
    out.write("\nOperations\n")
    for field in OPS_FIELDS:
        out.write("  %-24s %s\n" % (field + ":", operations.get(field)))
    out.write("\nConfiguration comparison\n")
    header = "%-22s" % "metric"
    names = list(comparison)
    for name in names:
        header += "%-18s" % name
    out.write(header + "\n")
    for field in QUALITY_FIELDS:
        row = "%-22s" % field
        for name in names:
            row += "%-18s" % round(comparison[name].get(field, 0.0), 4)
        out.write(row + "\n")
    return out.getvalue()


def render_csv(operations: Dict[str, float], comparison: Dict[str, Dict[str, float]]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["section", "metric", "configuration", "value"])
    for field in OPS_FIELDS:
        writer.writerow(["operations", field, "-", operations.get(field)])
    for name, metrics in comparison.items():
        for field in QUALITY_FIELDS:
            writer.writerow(["quality", field, name, round(metrics.get(field, 0.0), 4)])
    return out.getvalue()


def comparison_table(comparison: Dict[str, Dict[str, float]]) -> List[str]:
    """Markdown rows for docs, so docs and artifacts cannot silently disagree."""
    rows = ["| Metric | " + " | ".join(comparison) + " |",
            "|" + "---|" * (len(comparison) + 1)]
    for field in QUALITY_FIELDS:
        row = "| %s | " % field
        row += " | ".join("%.3f" % comparison[name].get(field, 0.0) for name in comparison)
        row += " |"
        rows.append(row)
    return rows
