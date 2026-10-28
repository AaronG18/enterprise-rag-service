#!/usr/bin/env python3
"""Verify every requirement row in `harness/requirements.toml` and report per-row results.

    python scripts/verify_requirements.py            # run the full gate
    python scripts/verify_requirements.py --quick    # skip generators, reuse existing artefacts
    python scripts/verify_requirements.py --only R-14 R-15

Exit code is non-zero if any row fails, so CI can gate on it. A failing row is reported by ID.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

from ragserve.evaluation.verification import (  # noqa: E402
    load_manifest,
    render_report,
    verify,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true", help="skip generators, reuse artefacts")
    parser.add_argument("--only", nargs="*", default=None, help="verify only these row IDs")
    parser.add_argument("--out", default=os.path.join(REPO_ROOT, "artifacts"))
    args = parser.parse_args()

    manifest = load_manifest()
    started = time.perf_counter()
    summary = verify(manifest, only=args.only, use_generators=not args.quick)
    summary["seconds"] = round(time.perf_counter() - started, 1)

    run_id = time.strftime("%Y%m%d-%H%M%S")
    target = os.path.join(args.out, "verify", run_id)
    os.makedirs(target, exist_ok=True)
    with open(os.path.join(target, "results.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(summary, fh, ensure_ascii=False, sort_keys=True, indent=2)
        fh.write("\n")
    with open(os.path.join(target, "report.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(render_report(summary))

    print("\n%d/%d rows passed in %.1fs -> %s" % (summary["passed"], summary["total"],
                                                  summary["seconds"], target))
    if not summary["ok"]:
        print("FAILED: %s" % ", ".join(r["id"] for r in summary["requirements"] if not r["ok"]),
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
