#!/usr/bin/env python3
"""The one script. Everything a reviewer needs is a flag on this command.

    python scripts/run.py                  # interactive QA - ask questions, see latency per question
    python scripts/run.py --eval           # evaluation + comparison report
    python scripts/run.py --eval --deliverables
    python scripts/run.py --corpus DIR     # measure documents you supply
    python scripts/run.py --serve          # serve the HTTP API
    python scripts/run.py --bench --concurrency 5 --assert
    python scripts/run.py --setup          # install the local models (first run does this itself)
    python scripts/run.py --check          # report what is installed
    python scripts/run.py --test           # hermetic test suite
    python scripts/run.py --verify         # requirement gate

The first run of the default mode installs the bundled models and starts the two servers; every run
after that finds them and goes straight to the work. All logic lives in `src/ragserve/cli/`, so this
file stays a single entry point rather than a folder of scripts.
"""
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

from ragserve.cli.main import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
