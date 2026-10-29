#!/usr/bin/env python3
"""Hermetic test runner.

Deliberately uses only the standard library: this command must work on a cold clone and
in CI without any package index access. See PROJECT.md INV-1.

Usage:
    python scripts/run_tests.py                # everything
    python scripts/run_tests.py -v             # verbose
    python scripts/run_tests.py -k routing     # substring filter on test name
    python scripts/run_tests.py --json         # machine-readable summary on stdout
    python scripts/run_tests.py --json --classes TestRefusal,TestMultiTurn
    python scripts/run_tests.py --jobs 4       # run the test classes in parallel

Why --jobs exists: the suite is dominated by a handful of slow classes (each one starts a
server or runs the whole evaluation). Running the classes in parallel worker processes turns
a 24-second suite into an 8-second run, which is what the CI gate spends its time on. The
workers claim classes off a shared list, so the wall-clock time approaches the slowest single
class; the merged report keeps every failure, and the report order does not depend on which
worker finished first. In parallel mode the per-test progress stream is not reproduced - the
summary line and the list of failures are what CI reads.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR = os.path.join(REPO_ROOT, "tests")
SRC_DIR = os.path.join(REPO_ROOT, "src")

MIN_PYTHON = (3, 11)


def default_jobs() -> int:
    """How many worker processes to use.

    The suite's cost is concentrated in four classes, so the wall-clock time approaches the
    slowest single class once there are enough workers to spread them. Measured on this
    machine (8 cores): 1 worker 24.4 s, 4 workers 9.0 s, 6 workers 6.5 s, 8 workers 6.5 s.
    Beyond six the discovery overhead cancels the gain.
    """
    return max(1, min(6, (os.cpu_count() or 2)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-v", "--verbose", action="count", default=1)
    parser.add_argument("-k", "--keyword", default=None, help="filter tests by substring")
    parser.add_argument("--json", dest="as_json", action="store_true",
                        help="print a machine-readable summary on stdout")
    parser.add_argument("--classes", default="",
                        help="comma-separated test class names to run (exact names)")
    parser.add_argument("--jobs", type=int, default=default_jobs(),
                        help="run the test classes in N parallel workers (default: %(default)s)")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--classes-file", default="", help=argparse.SUPPRESS)
    parser.add_argument("--report-dir", default="", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if sys.version_info < MIN_PYTHON:
        print("requires Python >= %d.%d, found %d.%d" % (MIN_PYTHON + sys.version_info[:2]))
        return 2

    # Make `src/` importable without installing anything.
    if SRC_DIR not in sys.path:
        sys.path.insert(0, SRC_DIR)

    # Keep the test runner hermetic: the delivered retrieval config defaults to a real
    # (network-backed) embedding provider, but CI / cold clone must need no key. Pin the
    # embedding backend to the offline deterministic one here; the production service leaves this
    # unset and uses the real provider from configs/retrieval.json.
    os.environ.setdefault("RAGSERVE_EMBEDDING_PROVIDER", "deterministic")

    if args.worker:
        return _run_worker(args)

    wanted = [name.strip() for name in args.classes.split(",") if name.strip()]
    missing = []
    suite = None
    if wanted:
        suite, missing = _select_classes(_discover(), wanted)
        if missing:
            # Report the missing classes but still run the ones that exist: one wrong name in
            # a list must not void the verdicts for every other class in the list.
            print("no test class named %s" % ", ".join(missing), file=sys.stderr)

    if args.jobs > 1 and not args.keyword:
        return _run_parallel(args, wanted, missing)

    if suite is None:
        suite = _discover()
        if args.keyword:
            suite = _filter(suite, args.keyword)
    return _run_inline(args, suite, missing)


def _discover() -> unittest.TestSuite:
    loader = unittest.TestLoader()
    return loader.discover(start_dir=TESTS_DIR, top_level_dir=REPO_ROOT) \
        if os.path.isdir(TESTS_DIR) else unittest.TestSuite()


def _run_inline(args, suite: unittest.TestSuite, missing) -> int:
    stream = io.StringIO() if args.as_json else sys.stderr
    counts = _class_counts(suite)
    started = time.perf_counter()
    result = unittest.TextTestRunner(stream=stream, verbosity=args.verbose).run(suite)
    seconds = round(time.perf_counter() - started, 3)

    if args.as_json:
        payload = _summarise(result, counts, seconds)
        payload["missing_classes"] = missing
        if missing:
            payload["ok"] = False
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    if missing:
        return 2
    return 0 if result.wasSuccessful() else 1


def _run_parallel(args, wanted, missing) -> int:
    """Run the selected classes in parallel worker processes, with work stealing.

    Static partitioning is easy but wrong: the suite's cost is concentrated in four classes
    (each starts a server or runs the whole evaluation), so a fixed split leaves one worker
    holding all the slow classes while the others idle. Instead the workers pull classes off a
    shared list and claim them atomically, so the wall-clock time approaches the slowest single
    class rather than the sum of one worker's share.

    Each worker is this same script, so there is exactly one implementation of "run these
    tests". Failures are never swallowed: the merged report lists every failing test and the
    exit code is non-zero if any worker failed.
    """
    classes = wanted if wanted else sorted(_class_names(_discover()))
    if not classes:
        return _run_inline(args, _discover(), missing)

    workers = min(args.jobs, len(classes))
    script = os.path.join(REPO_ROOT, "scripts", "run_tests.py")

    with tempfile.TemporaryDirectory(prefix="harness-tests-") as tmp:
        classes_file = os.path.join(tmp, "classes.txt")
        with open(classes_file, "w", encoding="utf-8") as fh:
            fh.write("\n".join(classes) + "\n")
        report_dir = os.path.join(tmp, "reports")
        os.makedirs(report_dir)

        started = time.perf_counter()
        processes = []
        for _ in range(workers):
            processes.append(subprocess.Popen(
                [sys.executable, script, "--worker", "--classes-file", classes_file,
                 "--report-dir", report_dir],
                cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE))
        errors = []
        for process in processes:
            _out, err = process.communicate()
            if process.returncode not in (0, None):
                errors.append((err or b"").decode("utf-8", "ignore")[-200:])
        seconds = round(time.perf_counter() - started, 3)

        merged = {"ok": not errors, "total": 0, "seconds": seconds, "failures": [], "errors": [],
                  "classes": {}, "missing_classes": list(missing), "workers": workers}
        for name in sorted(os.listdir(report_dir)):
            if not name.startswith("report-"):
                continue
            with open(os.path.join(report_dir, name), "r", encoding="utf-8") as fh:
                payload = json.load(fh)
            merged["total"] += payload.get("total", 0)
            merged["failures"].extend(payload.get("failures", []))
            merged["errors"].extend(payload.get("errors", []))
            for class_name, entry in (payload.get("classes") or {}).items():
                merged["classes"][class_name] = entry
            if not payload.get("ok", False):
                merged["ok"] = False
        merged["failures"].sort(key=lambda item: item.get("test", ""))
        merged["errors"].sort(key=lambda item: item.get("test", ""))
        for message in errors:
            merged["errors"].append({"test": "worker", "message": message})
            merged["ok"] = False
        if missing:
            merged["ok"] = False

    if args.as_json:
        print(json.dumps(merged, ensure_ascii=False, sort_keys=True))
    else:
        for failure in merged["failures"] + merged["errors"]:
            print("%s: %s" % (failure.get("test"), failure.get("message")), file=sys.stderr)
        print("Ran %d tests in %.3fs (%d workers)" % (merged["total"], seconds, workers),
              file=sys.stderr)
        if merged["ok"]:
            print("OK", file=sys.stderr)
        else:
            print("FAILED (failures=%d, errors=%d)"
                  % (len(merged["failures"]), len(merged["errors"])), file=sys.stderr)

    if missing:
        return 2
    return 0 if merged["ok"] else 1


def _run_worker(args) -> int:
    """Worker mode: claim classes off the shared list and report each one.

    The claim is an exclusive file creation, which is atomic on both Windows and POSIX, so two
    workers never run the same class and no class is left unrun.
    """
    with open(args.classes_file, "r", encoding="utf-8") as fh:
        names = [line.strip() for line in fh if line.strip()]

    by_class: dict = {}
    for item in _flatten(_discover()):
        by_class.setdefault(type(item).__name__, []).append(item)

    for index, name in enumerate(names):
        claim = os.path.join(args.report_dir, "claim-%04d" % index)
        try:
            handle = os.open(claim, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except (FileExistsError, OSError):
            continue
        os.close(handle)

        items = by_class.get(name)
        if not items:
            continue
        suite = unittest.TestSuite(items)
        counts = _class_counts(suite)
        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
        payload = _summarise(result, counts, 0.0)
        payload["missing_classes"] = []
        with open(os.path.join(args.report_dir, "report-%04d.json" % index), "w",
                  encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, sort_keys=True)
    return 0


def _flatten(suite: unittest.TestSuite) -> list:
    flat: list = []

    def walk(s):
        for item in s:
            if isinstance(item, unittest.TestSuite):
                walk(item)
            else:
                flat.append(item)

    walk(suite)
    return flat


def _class_names(suite: unittest.TestSuite) -> set:
    names = set()

    def walk(s):
        for item in s:
            if isinstance(item, unittest.TestSuite):
                walk(item)
            else:
                names.add(type(item).__name__)

    walk(suite)
    return names


def _class_counts(suite: unittest.TestSuite) -> dict:
    """How many tests each class contributes. A TestResult is not iterable, so the counts come
    from the suite that was selected."""
    counts: dict = {}

    def walk(s):
        for item in s:
            if isinstance(item, unittest.TestSuite):
                walk(item)
            else:
                name = type(item).__name__
                counts[name] = counts.get(name, 0) + 1

    walk(suite)
    return counts


def _summarise(result, counts: dict, seconds: float) -> dict:
    """Per-class verdicts, so a requirement row can ask about one class, not a whole run."""
    failure_text = {test.id(): text for test, text in result.failures}
    error_text = {test.id(): text for test, text in result.errors}

    classes: dict = {}
    for name, count in counts.items():
        classes[name] = {"total": count, "failures": [], "errors": []}
    for test, _text in result.failures:
        classes.setdefault(type(test).__name__,
                           {"total": 0, "failures": [], "errors": []})["failures"].append(test.id())
    for test, _text in result.errors:
        classes.setdefault(type(test).__name__,
                           {"total": 0, "failures": [], "errors": []})["errors"].append(test.id())

    return {
        "ok": result.wasSuccessful(),
        "total": result.testsRun,
        "seconds": seconds,
        "failures": [{"test": test_id, "message": _last_line(text)}
                     for test_id, text in sorted(failure_text.items())],
        "errors": [{"test": test_id, "message": _last_line(text)}
                   for test_id, text in sorted(error_text.items())],
        "classes": classes,
    }


def _last_line(text: str) -> str:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    return lines[-1][:200] if lines else ""


def _filter(suite: unittest.TestSuite, keyword: str) -> unittest.TestSuite:
    """Keep only tests whose id() contains the keyword. Flattens nested suites."""
    flat: list[unittest.TestCase] = []

    def walk(s):
        for item in s:
            if isinstance(item, unittest.TestSuite):
                walk(item)
            elif keyword in item.id():
                flat.append(item)

    walk(suite)
    out = unittest.TestSuite()
    out.addTests(flat)
    return out


def _select_classes(suite: unittest.TestSuite, wanted):
    """Keep only the named test classes. Returns (suite, missing class names).

    A requested class that does not exist is an error, not an empty selection: an empty
    selection exits 0, which would let a requirement row pass without running anything.
    """
    wanted_set = set(wanted)
    flat: list[unittest.TestCase] = []

    def walk(s):
        for item in s:
            if isinstance(item, unittest.TestSuite):
                walk(item)
            else:
                flat.append(item)

    walk(suite)
    # The class name is the type name, not a fragment of the test id: ids look like
    # `tests.test_generation.TestRefusal.test_x`, so id-splitting finds the module.
    found = {type(item).__name__ for item in flat}
    missing = sorted(wanted_set - found)
    out = unittest.TestSuite()
    out.addTests([item for item in flat if type(item).__name__ in wanted_set])
    return out, missing


if __name__ == "__main__":
    raise SystemExit(main())
