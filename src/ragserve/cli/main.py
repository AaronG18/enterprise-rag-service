"""One entry point for everything a reviewer runs.

The brief asks for **one** one-click evaluation script. Twelve scripts in a folder is not that, so
`scripts/run.py` is the only file in `scripts/` and everything else is a module here, dispatched by
this function. Each mode is a thin import: the logic did not move, only the surface did.

    python scripts/run.py                  # interactive QA (bootstraps the environment on first run)
    python scripts/run.py --eval           # evaluation + comparison report (+ --deliverables)
    python scripts/run.py --corpus DIR     # measure documents the reviewer supplies
    python scripts/run.py --serve          # serve the HTTP API
    python scripts/run.py --bench          # concurrency/latency benchmark
    python scripts/run.py --setup|--check  # install or inspect the local models
    python scripts/run.py --test           # hermetic test suite (harness)
    python scripts/run.py --verify         # requirement gate (harness)
"""
from __future__ import annotations

import importlib
import sys

# flag -> (module, keep the flag in argv)
MODES = (
    ("--ask", "ragserve.cli.ask", False),
    ("--eval", "ragserve.cli.evaluate", False),
    ("--corpus", "ragserve.cli.ask", False),   # a supplied corpus still runs through the service
    ("--serve", "ragserve.cli.serve", False),
    ("--setup", "ragserve.cli.setup", False),
    ("--check", "ragserve.cli.setup", True),
    ("--bench", "ragserve.cli.bench", False),
    ("--test", "ragserve.cli.tests", False),
    ("--verify", "ragserve.cli.verify", False),
    ("--audit", "ragserve.cli.audit", False),
    ("--diagnose", "ragserve.cli.diagnose", False),
    ("--gen-corpus", "ragserve.cli.corpus", False),
    ("--samples", "ragserve.cli.samples", False),
    ("--dashboard", "ragserve.cli.dashboard", False),
    ("--build-corpus", "ragserve.cli.build_corpus", False),
)


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    for flag, module, keep in MODES:
        if flag not in args:
            continue
        rest = list(args)
        rest.remove(flag)
        if keep:
            rest.insert(0, flag)
        sys.argv = ["run.py"] + rest
        return importlib.import_module(module).main()
    # No mode flag: the reviewer just typed the command and wants to ask questions.
    sys.argv = ["run.py"] + args
    return importlib.import_module("ragserve.cli.ask").main()
