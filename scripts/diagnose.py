#!/usr/bin/env python3
"""Reproduce a documented incident and measure the fix.

    python scripts/diagnose.py --case refusal-gate
    python scripts/diagnose.py --case cross-language
    python scripts/diagnose.py --all --assert     # exit 1 if any case improves by < 10%

Writes artifacts/diagnosis/<case>/{report.json, report.md}.

Enforces R13: attribution must survive reproduction. A fix is only credited when re-running the
incident reproduces the before state and the after state moves the metric by the claimed amount.
This script is that re-run, and `--assert` fails when the improvement is missing.
"""
from __future__ import annotations

import argparse
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

from ragserve.evaluation.diagnosis import (  # noqa: E402
    CASES,
    IMPROVEMENT_THRESHOLD,
    WITHDRAWN_CASES,
    render_case,
    run_case,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=sorted(CASES))
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--out", default=os.path.join(REPO_ROOT, "artifacts"))
    parser.add_argument("--assert", dest="do_assert", action="store_true")
    args = parser.parse_args()

    names = sorted(CASES) if args.all else ([args.case] if args.case else [])
    if not names:
        parser.error("use --all or --case <name>")

    if args.all and WITHDRAWN_CASES:
        print("# Withdrawn cases (measured effect no longer reproduces on the current corpus)")
        for name, reason in WITHDRAWN_CASES.items():
            print("  - %s: %s" % (name, reason))
        print()

    failures = []
    for name in names:
        report = run_case(name, REPO_ROOT, args.out)
        print(render_case(report))
        print("artifacts:", report["artifacts"])
        if not report["meets_threshold"]:
            failures.append(name)

    if args.do_assert and failures:
        print("FAIL: below the %.0f%% improvement threshold: %s"
              % (IMPROVEMENT_THRESHOLD * 100, ", ".join(failures)), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
