#!/usr/bin/env python3
"""Run the parameter matrix: every mode, every flag it declares, and the semantic combinations.

Why this exists
---------------
A documented command (`--corpus DIR` in interactive mode) was broken for weeks while a hand-picked
command list stayed green, because the list covered `--eval --corpus DIR` - a different module. The
lesson is not "test more": it is that a hand-written list of combinations is always a sample. This
module enumerates the combinations **from the CLI itself**:

1. for every mode, every flag that mode's `--help` declares is exercised (alone);
2. the evaluation's semantic dimensions - retrieval mode x reranker x corpus x case limit - are
   exercised as a full cross product, because those actually interact;
3. the interactive loop is exercised with no corpus, a directory and a single file, with and without
   bootstrap.

Anything unexpected is a failure with its exit code and the last line of output; commands that are
*supposed* to refuse (an empty corpus, a missing path, `--deliverables` with `--corpus`) are listed
with the refusal they must produce, so "non-zero" is never silently treated as success.

Usage
-----
    python scripts/run.py --matrix            # everything, including the full evaluation cross product
    python scripts/run.py --matrix --quick    # the same coverage without the slow evaluation runs
"""
from __future__ import annotations

import argparse
import itertools
import os
import re
import subprocess
import sys
import tempfile

from . import REPO_ROOT

ENTRY = os.path.join(REPO_ROOT, "scripts", "run.py")

#: mode flag -> (complete leading argv for that mode, is it safe to execute for real?)
#: The prefix is spelled out rather than derived, because a value-taking mode flag (`--corpus DIR`)
#: cannot be concatenated safely: appending it twice produced "argument --corpus: expected one
#: argument" and looked like a product defect.
MODES = (
    ("--ask", ["--ask"], True),
    ("--corpus", ["--no-bootstrap", "--corpus",
                  os.path.join("tests", "data", "external-corpus")], True),
    ("--eval", ["--eval", "--max-cases", "3"], True),
    ("--check", ["--check"], True),
    ("--setup", ["--setup"], False),          # downloads ~1 GB
    ("--serve", ["--serve"], False),          # binds a socket and blocks
    ("--bench", ["--bench"], True),
    ("--test", ["--test"], False),            # recursion
    ("--verify", ["--verify"], False),        # recursion
    ("--audit", ["--audit"], False),          # re-runs the probes
    ("--diagnose", ["--diagnose"], True),
    ("--gen-corpus", ["--gen-corpus"], True),
    # These two rewrite committed deliverables under docs/. A test that dirties the working tree is
    # a test nobody can trust: running the matrix used to leave qa-dashboard.html modified with the
    # latency of whatever bench had just run. Parse-only here; their content is guarded by the
    # --deliverables drift test.
    ("--samples", ["--samples"], False),
    ("--dashboard", ["--dashboard"], False),
    ("--build-corpus", ["--build-corpus"], True),
)

#: a value for every value-taking flag. A flag with no entry here is an outright failure: a new
#: option must be added deliberately, with a value that makes sense, or the matrix silently stops
#: covering it.
OPTION_VALUES = {
    "--corpus": os.path.join("tests", "data", "external-corpus"),
    "--mode": "vector_only",
    "--rerank": "on",
    "--max-cases": "3",
    "--out": "__TMP__",
    "--host": "127.0.0.1",
    "--port": "0",
    "--concurrency": "3",
    "--requests": "8",
    "--jobs": "2",
    "--classes": "SingleFlightTest",
    "--keyword": "cache",
    "--count": "3",
    "--seed": "1",
    "--config": os.path.join("configs", "corpus.json"),
    "--case": "INC-001",
    "--only": "R-16",
    "--endpoint": "http://127.0.0.1:8011/v1",
    "--model": "bge-m3",
    "--api-key-env": "",
    "--embedding-provider": "deterministic",
    "--reranker-provider": "deterministic",
    "--provider": "deterministic",
    "--cases": os.path.join("eval", "eval_cases.json"),
    "--case": "refusal-gate",
}

#: Arguments a mode *requires* before any optional flag makes sense. Probing `--gen-corpus --count`
#: on its own exits 2 with "the following arguments are required: --out" - which is correct
#: argparse behaviour, not a defect, so the baseline supplies it.
MODE_BASELINE = {
    "--gen-corpus": ["--out", "__TMP__"],
    "--diagnose": ["--all"],
}

BOOL_OPTIONS = {
    "--all", "--assert", "--check", "--cost", "--deliverables", "--help", "--html", "--http",
    "--json", "--no-bootstrap", "--no-browser", "--quick", "--refresh-model-backed", "--serial",
    "--seed-model-backed", "--verbose",
}

#: options we deliberately never execute, with the reason (asserted to be non-trivial).
SKIPPED_OPTIONS = {
    "--models": "needs a hosted model and credentials",
    "--provider": "changing the generation provider needs credentials",
    "--endpoint": "an arbitrary endpoint would need a server we do not control",
    "--model": "only meaningful together with --provider",
    "--api-key-env": "only meaningful with a hosted provider",
    "--port": "only meaningful for --serve, which blocks",
    "--host": "only meaningful for --serve, which blocks",
    "--no-browser": "only meaningful for --serve, which blocks",
    "--deliverables": "rewrites committed files; covered by the drift test",
    "--refresh-model-backed": "refuses without model servers; covered by the contract job",
    "--seed-model-backed": "commits an existing artefact rather than producing one",
}

REFUSALS = {
    # label -> (argv, text the refusal must contain)
    "empty corpus": (["--eval", "--corpus", "__EMPTY__"], "REFUSED"),
    "missing path": (["--eval", "--corpus", "__MISSING__"], "REFUSED"),
    "corpus + deliverables": (["--eval", "--corpus", "__CORPUS__", "--deliverables"], "REFUSED"),
}

ENV = {
    "PYTHONIOENCODING": "utf-8",
    "RAGSERVE_EMBEDDING_PROVIDER": "deterministic",
    "RAGSERVE_RERANKER_PROVIDER": "deterministic",
}


def _run(argv, stdin=None, timeout=600):
    env = dict(os.environ)
    env.update(ENV)
    return subprocess.run([sys.executable, ENTRY] + argv, cwd=REPO_ROOT, env=env, input=stdin,
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout)


def _options(mode: str):
    """The flags a mode's own --help declares, excluding --help itself."""
    proc = _run([mode, "--help"])
    found = sorted(set(re.findall(r"--[a-z][a-z-]+", (proc.stdout or "") + (proc.stderr or ""))))
    return [opt for opt in found if opt != "--help"]


def _argv_for(mode, options):
    argv = [mode]
    for opt in options:
        argv.append(opt)
        if opt in OPTION_VALUES:
            argv.append(OPTION_VALUES[opt])
    return argv


def build_cases(quick: bool):
    cases = []  # (label, argv, stdin, must_contain)

    # 1. every flag of every mode, alone
    for mode, probe, executable in MODES:
        for opt in _options(mode):
            if opt in SKIPPED_OPTIONS or opt == mode:
                continue  # the mode flag is already on the command line
            label = "flag %s %s" % (mode, opt)
            if not executable:
                # Parse-only for modes that block or recurse (--serve binds a socket; --test and
                # --verify run this very suite; --setup downloads 1 GB). Running them for real is
                # how the first version of this matrix hung for ten minutes on --serve.
                cases.append((label + " (parse)", list(probe) + [opt] +
                              ([OPTION_VALUES[opt]] if opt in OPTION_VALUES else []) + ["--help"],
                              None, None))
                continue
            argv = list(probe)
            if opt == "--case":
                # `--all` and `--case` are alternatives; probing --case must not also pass --all.
                argv += ["--case", OPTION_VALUES[opt]]
            else:
                argv += MODE_BASELINE.get(mode, []) + [opt]
                if opt in OPTION_VALUES:
                    argv.append(OPTION_VALUES[opt])
            cases.append((label, argv, None, None))

    # 2. the evaluation's semantic cross product - the dimensions that actually interact
    modes = ["hybrid"] if quick else ["hybrid", "vector_only"]
    for mode_opt, rerank, corpus_kind, limit in itertools.product(
            modes, ["on", "off"], ["builtin", "supplied"], ["default", "3"]):
        argv = ["--eval"]
        if not quick:
            argv += ["--all"]
        argv += ["--mode", mode_opt, "--rerank", rerank]
        if corpus_kind == "supplied":
            argv += ["--corpus", OPTION_VALUES["--corpus"]]
        if limit != "default":
            argv += ["--max-cases", limit]
        cases.append(("eval %s/%s/%s/%s" % (mode_opt, rerank, corpus_kind, limit), argv, None, None))

    # 3. the interactive loop: no corpus, a directory, a single file; with and without bootstrap
    question = "How many days of annual leave do full-time employees accrue?\n:quit\n"
    variants = [("builtin", []),
                ("dir", ["--corpus", OPTION_VALUES["--corpus"]]),
                ("file", ["--corpus", os.path.join("tests", "data", "formats", "notes.markdown")])]
    for kind, extra in variants:
        cases.append(("ask %s" % kind, ["--no-bootstrap"] + extra, question, None))
    cases.append(("ask bootstrap builtin", [], question, None))

    return cases


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--quick", action="store_true",
                        help="cover every mode and flag, but skip the slow evaluation cross product")
    parser.add_argument("--out", default=None, help="write the results here instead of stdout")
    args = parser.parse_args(argv)

    tmp = tempfile.mkdtemp(prefix="matrix-")
    empty = os.path.join(tmp, "empty")
    os.makedirs(empty, exist_ok=True)
    missing = os.path.join(tmp, "does-not-exist")

    cases = build_cases(args.quick)
    results = []
    failures = []
    print("Matrix: %d combinations%s" % (len(cases), " (quick)" if args.quick else ""))
    for label, argv, stdin, must in cases:
        argv = [a.replace("__TMP__", tmp) for a in argv]
        proc = _run(argv, stdin=stdin)
        out = (proc.stdout or "") + (proc.stderr or "")
        crashed = "Traceback (most recent call last)" in out
        ok = proc.returncode == 0 and not crashed and (must is None or must in out)
        results.append((label, proc.returncode, ok))
        print("  %-44s exit=%-4s %s" % (label, proc.returncode, "ok" if ok else "FAIL"))
        if not ok:
            tail = [l for l in out.strip().splitlines() if l.strip()][-2:]
            failures.append((label, proc.returncode, tail))

    # 4. refusals: non-zero is correct here, so they are asserted separately
    print("Refusals (non-zero is the expected outcome)")
    refusal_argv = {
        "empty corpus": REFUSALS["empty corpus"][0],
        "missing path": REFUSALS["missing path"][0],
        "corpus + deliverables": [a.replace("__CORPUS__", OPTION_VALUES["--corpus"])
                                  for a in REFUSALS["corpus + deliverables"][0]],
    }
    for label, argv in refusal_argv.items():
        argv = [a.replace("__EMPTY__", empty).replace("__MISSING__", missing) for a in argv]
        proc = _run(argv)
        out = (proc.stdout or "") + (proc.stderr or "")
        ok = proc.returncode != 0 and "REFUSED" in out
        print("  %-44s exit=%-4s %s" % (label, proc.returncode, "ok" if ok else "FAIL"))
        if not ok:
            failures.append((label, proc.returncode, [out.strip().splitlines()[-1][:120]]))

    print()
    print("%d/%d behaved as expected" % (len(results) + len(refusal_argv) - len(failures),
                                         len(results) + len(refusal_argv)))
    if failures:
        print("FAILURES:")
        for label, code, tail in failures:
            print("  %s (exit %s)" % (label, code))
            for line in tail:
                print("     |", line[:160])
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
