"""Regenerate the deliverable documents from a run.

One entry point owns this: `scripts/run.py --deliverables`. It was previously a second
script, and two entry points for one job is how an interviewer ends up asking which one to run.

Everything here writes to the repository's `docs/` tree, so it is only invoked when the caller
asked for deliverables - the CI evaluation writes to `artifacts/` alone and must never rewrite a
committed document.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Dict

SNAPSHOT_DETERMINISTIC = os.path.join("docs", "eval", "deterministic-metrics.json")
SNAPSHOT_MODEL_BACKED = os.path.join("docs", "eval", "model-backed-retrieval-metrics.json")
COMPARISON_DOC = os.path.join("docs", "eval", "retrieval-comparison.md")
SAMPLE_LOGS = os.path.join("docs", "logging", "sample_logs.md")
QA_DASHBOARD = os.path.join("docs", "qa", "qa-dashboard.html")

SNAPSHOT_NOTE = ("Snapshot of a real run, committed so the comparison report and the requirements "
                 "gate can read it without re-measuring. Regenerate with "
                 "python scripts/run.py --eval --all --deliverables.")


def write_snapshot(payload: Dict, path: str, run_id: str) -> None:
    """Commit a run's numbers so the report - and CI - can read them without re-measuring."""
    from .comparison_doc import render_comparison_doc  # noqa: PLC0415 - avoids an import cycle

    metadata = dict(payload["run_metadata"])
    metadata["run_id"] = run_id  # also inside the metadata: the report header reads it from there
    snapshot = {
        "run_id": run_id,
        "run_metadata": metadata,
        "operations": payload["operations"],
        "comparison": payload["comparison"],
        "note": SNAPSHOT_NOTE,
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(snapshot, fh, ensure_ascii=False, sort_keys=True, indent=2)
        fh.write("\n")


def load_snapshot(root: str, relative: str):
    path = os.path.join(root, *relative.split("/"))
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def regenerate_comparison_report(root: str) -> str:
    """Render `retrieval-comparison.md` from the committed snapshots and write it back."""
    from .comparison_doc import render_comparison_doc  # noqa: PLC0415

    deterministic = load_snapshot(root, SNAPSHOT_DETERMINISTIC) or {}
    model_backed = load_snapshot(root, SNAPSHOT_MODEL_BACKED)
    document = render_comparison_doc(deterministic, model_backed)
    target = os.path.join(root, *COMPARISON_DOC.split("/"))
    with open(target, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(document)
    return target


def _run_mode(root: str, *mode_args) -> None:
    """Run one mode of the single entry point, in a fresh interpreter."""
    entry = os.path.join(root, "scripts", "run.py")
    subprocess.run([sys.executable, entry] + list(mode_args), cwd=root, check=True)


def regenerate_sample_logs(root: str) -> str:
    _run_mode(root, "--samples")
    return os.path.join(root, "docs", "logging", "sample_logs.md")


def regenerate_dashboard(root: str) -> str:
    target = os.path.join(root, *QA_DASHBOARD.split("/"))
    _run_mode(root, "--dashboard")
    return target
