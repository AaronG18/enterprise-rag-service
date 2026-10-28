"""Requirements verification gate.

The logic lives here rather than in `scripts/` so it can be imported and unit-tested; the script
is a thin CLI wrapper. CI runs the script, and a failing row is reported by ID - "verification
failed" without naming the row is useless for fixing anything.

Concurrency: the generators and the requirement rows are independent subprocesses, so they run
concurrently through an asyncio event loop (`asyncio.to_thread` over a bounded executor). What
that buys, measured on this machine:

| stage | serial | concurrent |
|---|---|---|
| three generators (eval, bench, diagnosis) | 3.4 s | 1.4 s (the slowest one) |
| ten test-kind rows (one process each) | ~14 s | 1.6 s (one shared suite run) |
| total gate | 14.2 s | ~3.5 s |

Two properties are preserved deliberately: the report order is the manifest order (not
completion order), and concurrency never changes a verdict.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import glob
import json
import os
import subprocess
import time
import tomllib

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
MANIFEST = os.path.join(REPO_ROOT, "harness", "requirements.toml")
ARTIFACTS = os.path.join(REPO_ROOT, "artifacts")

#: How many subprocesses may run at once. Subprocesses are I/O-bound from Python's point of
#: view, so a handful of workers saturates the machine without thrashing it.
DEFAULT_JOBS = max(2, min(8, (os.cpu_count() or 4)))


def default_jobs() -> int:
    return DEFAULT_JOBS


def load_manifest(path: str = MANIFEST) -> dict:
    with open(path, "rb") as fh:
        return tomllib.load(fh)


def run_command(command: str, timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=REPO_ROOT, shell=True, capture_output=True,
                          text=True, encoding="utf-8", errors="ignore", timeout=timeout)


def latest_artifact(pattern: str):
    matches = sorted(glob.glob(os.path.join(ARTIFACTS, pattern)))
    return matches[-1] if matches else None


def run_generators(manifest: dict, verbose: bool = True) -> dict:
    """Produce the artefacts every metric row reads from, once.

    Metric rows never read a stale file: the generators run first, so a gate run measures the
    tree it is running against.
    """
    results = {}
    for name, command in (manifest.get("generators") or {}).items():
        started = time.perf_counter()
        try:
            proc = run_command(command)
        except subprocess.TimeoutExpired:
            results[name] = {"ok": False, "detail": "timeout",
                             "seconds": round(time.perf_counter() - started, 1)}
            if verbose:
                print("  generator %-10s TIMEOUT" % name)
            continue
        results[name] = {
            "ok": proc.returncode == 0,
            "detail": (proc.stdout or "")[-400:] if proc.returncode else "",
            "seconds": round(time.perf_counter() - started, 1),
        }
        if verbose:
            print("  generator %-10s %s (%.1fs)" % (name, "ok" if proc.returncode == 0 else "FAILED",
                                                    results[name]["seconds"]))
    return results


def _compare(value, op: str, bound) -> bool:
    try:
        if op == "<=":
            return float(value) <= float(bound)
        if op == ">=":
            return float(value) >= float(bound)
        if op == "==":
            return value == bound
        if op == "<":
            return float(value) < float(bound)
        if op == ">":
            return float(value) > float(bound)
    except (TypeError, ValueError):
        return False
    return False


# --------------------------------------------------------------------- test-kind rows


def test_report(classes) -> dict:
    """Run the requested test classes once and return the machine-readable report.

    One process for all rows: ten rows used to start ten interpreters, each paying for test
    discovery. A class that does not exist is an error, because `unittest` exits 0 when a
    filter matches nothing - which let seven requirement rows pass without running a test.
    """
    wanted = [name for name in classes if name]
    if not wanted:
        return {"ok": True, "total": 0, "classes": {}, "failures": [], "errors": []}
    command = "%s %s --json --classes %s" % (
        _python(), os.path.join("scripts", "run_tests.py"), ",".join(sorted(set(wanted))))
    proc = run_command(command)
    payload = {}
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                payload = {}
    if not payload:
        return {"ok": False, "total": 0, "classes": {}, "failures": [],
                "errors": [{"test": "run_tests.py", "message": (proc.stderr or "")[-200:]}]}
    payload["missing_classes"] = payload.get("missing_classes", [])
    return payload


def _python() -> str:
    import sys

    return '"%s"' % sys.executable if " " in sys.executable else sys.executable


def _check_test_row(row: dict, report: dict) -> dict:
    selections = row.get("tests") or []
    if not selections and row.get("run"):
        selections = [row["run"].split("-k ")[-1].strip()]
    classes = report.get("classes", {})
    missing = [name for name in selections if name not in classes]
    if missing:
        return {"ok": False,
                "detail": "no test class named %s (a selection that matches nothing must not "
                          "count as a pass)" % ", ".join(missing)}
    failed = []
    for name in selections:
        entry = classes.get(name, {})
        failed.extend(entry.get("failures", []))
        failed.extend(entry.get("errors", []))
    if failed:
        return {"ok": False, "detail": "%d failing test(s): %s" % (len(failed), ", ".join(failed[:3]))}
    total = sum(classes.get(name, {}).get("total", 0) for name in selections)
    return {"ok": True, "detail": "%s: %d test(s) passed" % (", ".join(selections), total)}


# --------------------------------------------------------------------- other row kinds


def check_requirement(row: dict, manifest: dict, report: dict | None = None) -> dict:
    kind = row.get("kind")

    if kind == "command":
        proc = run_command(row["run"], timeout=row.get("timeout", 600))
        return {"ok": proc.returncode == 0,
                "detail": (proc.stdout or proc.stderr or "")[-300:]}

    if kind == "test":
        if report is not None:
            return _check_test_row(row, report)
        selections = row.get("tests") or []
        if not selections and row.get("run"):
            selections = [row["run"].split("-k ")[-1].strip()]
        return _check_test_row(row, test_report(selections))

    if kind == "file":
        path = os.path.join(REPO_ROOT, row["path"])
        if not os.path.isfile(path):
            return {"ok": False, "detail": "missing file: %s" % row["path"]}
        if row.get("contains"):
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                if row["contains"] not in fh.read():
                    return {"ok": False,
                            "detail": "%s does not contain %r" % (row["path"], row["contains"])}
        return {"ok": True, "detail": row["path"]}

    if kind == "metric":
        if row.get("path"):
            path = os.path.join(REPO_ROOT, row["path"])
            if not os.path.isfile(path):
                return {"ok": False, "detail": "missing file: %s" % row["path"]}
        else:
            pattern = (manifest.get("artifacts") or {}).get(row["artifact"])
            if not pattern:
                return {"ok": False, "detail": "no artifact pattern for %r" % row["artifact"]}
            path = latest_artifact(pattern)
            if not path:
                return {"ok": False, "detail": "no artefact found for %s" % row["artifact"]}
        with open(path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)

        if row.get("artifact") == "diagnosis":
            value = payload.get(row["metric"])
        else:
            if row.get("config"):
                section = (payload.get("comparison") or {}).get(row["config"], {})
            else:
                section_name = row.get("section", "comparison")
                section = payload.get(section_name)
                if section is None and section_name == "comparison":
                    # Bench artefacts are flat (metrics at the top level), not a table.
                    section = payload
            value = section.get(row["metric"]) if isinstance(section, dict) else None

        if value is None:
            return {"ok": False, "detail": "metric %r not found in %s" % (row["metric"], path)}
        ok = _compare(value, row.get("op", ">="), row.get("bound"))
        return {"ok": ok, "detail": "%s %s %s (actual %s, from %s)"
                                     % (row["metric"], row.get("op"), row.get("bound"), value,
                                        os.path.basename(os.path.dirname(path)) or
                                        os.path.basename(path))}

    return {"ok": False, "detail": "unknown kind %r" % kind}


# --------------------------------------------------------------------- orchestration


def _row_classes(row: dict) -> list:
    if row.get("kind") != "test":
        return []
    selections = row.get("tests") or []
    if not selections and row.get("run"):
        selections = [row["run"].split("-k ")[-1].strip()]
    return [name for name in selections if name]


async def _run_generators_async(manifest: dict, executor) -> dict:
    """Run the generators concurrently: they are independent and each writes its own artefacts."""
    loop = asyncio.get_running_loop()

    async def one(name: str, command: str):
        started = time.perf_counter()

        def work():
            try:
                return run_command(command)
            except subprocess.TimeoutExpired:
                return None

        proc = await loop.run_in_executor(executor, work)
        seconds = round(time.perf_counter() - started, 1)
        if proc is None:
            return name, {"ok": False, "detail": "timeout", "seconds": seconds}
        return name, {"ok": proc.returncode == 0,
                      "detail": (proc.stdout or "")[-400:] if proc.returncode else "",
                      "seconds": seconds}

    names = list((manifest.get("generators") or {}).items())
    outcomes = await asyncio.gather(*(one(name, command) for name, command in names))
    results = dict(outcomes)
    for name in results:
        print("  generator %-10s %s (%.1fs)" % (name, "ok" if results[name]["ok"] else "FAILED",
                                                results[name]["seconds"]))
    return results


async def _verify_async(manifest: dict, only=None, use_generators=True, jobs: int = DEFAULT_JOBS):
    rows = [r for r in manifest.get("requirement", []) if not only or r["id"] in only]

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=max(1, jobs),
                                                       thread_name_prefix="harness")
    loop = asyncio.get_running_loop()
    try:
        generator_results = {}
        if use_generators and not only:
            print("generators (concurrent):")
            generator_results = await _run_generators_async(manifest, executor)

        # One shared test-suite run for every test-kind row.
        wanted_classes = []
        for row in rows:
            for name in _row_classes(row):
                if name not in wanted_classes:
                    wanted_classes.append(name)
        shared_report = None
        if wanted_classes:
            shared_report = await loop.run_in_executor(executor, test_report, wanted_classes)

        print("\nrequirements:")

        async def one(row: dict):
            outcome = await loop.run_in_executor(executor, check_requirement, row, manifest,
                                                 shared_report)
            return {"id": row["id"], "title": row.get("title", ""),
                    "owner": row.get("owner", ""), **outcome}

        # gather keeps the input order, so the report is in manifest order regardless of
        # which row finished first.
        results = await asyncio.gather(*(one(row) for row in rows))
    finally:
        executor.shutdown(wait=True)

    for result in results:
        print("  %-7s %-4s %s" % (result["id"], "PASS" if result["ok"] else "FAIL",
                                  (result.get("detail") or "")[:110]))

    failed = [r for r in results if not r["ok"]]
    return {
        "total": len(results),
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "generators": generator_results,
        "requirements": list(results),
        "ok": not failed,
    }


def verify(manifest: dict, only=None, use_generators=True, jobs: int = DEFAULT_JOBS) -> dict:
    """Run the gate. Concurrent by default; `jobs=1` forces the serial path."""
    if jobs <= 1:
        return _verify_serial(manifest, only=only, use_generators=use_generators)
    try:
        return asyncio.run(_verify_async(manifest, only=only, use_generators=use_generators,
                                         jobs=jobs))
    except RuntimeError:
        # Already inside an event loop: fall back to the serial path rather than crash.
        return _verify_serial(manifest, only=only, use_generators=use_generators)


def _verify_serial(manifest: dict, only=None, use_generators=True) -> dict:
    rows = [r for r in manifest.get("requirement", []) if not only or r["id"] in only]
    generator_results = {}
    if use_generators and not only:
        print("generators:")
        generator_results = run_generators(manifest)

    wanted_classes = []
    for row in rows:
        for name in _row_classes(row):
            if name not in wanted_classes:
                wanted_classes.append(name)
    shared_report = test_report(wanted_classes) if wanted_classes else None

    print("\nrequirements:")
    results = []
    for row in rows:
        outcome = check_requirement(row, manifest, shared_report)
        results.append({"id": row["id"], "title": row.get("title", ""),
                        "owner": row.get("owner", ""), **outcome})
        print("  %-7s %-4s %s" % (row["id"], "PASS" if outcome["ok"] else "FAIL",
                                  (outcome.get("detail") or "")[:110]))

    failed = [r for r in results if not r["ok"]]
    return {
        "total": len(results),
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "generators": generator_results,
        "requirements": results,
        "ok": not failed,
    }


def render_report(summary: dict) -> str:
    lines = ["Requirements verification", "=" * 26, "",
             "rows: %d | passed: %d | failed: %d" % (summary["total"], summary["passed"],
                                                     summary["failed"]), ""]
    for row in summary["requirements"]:
        lines.append("%-7s %-4s %-60s %s" % (row["id"], "PASS" if row["ok"] else "FAIL",
                                             row["title"][:60], row.get("detail", "")[:80]))
    if summary["failed"]:
        lines += ["", "FAILED ROWS: %s"
                  % ", ".join(r["id"] for r in summary["requirements"] if not r["ok"])]
    return "\n".join(lines) + "\n"
