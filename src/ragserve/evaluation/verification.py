"""Requirements verification gate.

The logic lives here rather than in `scripts/` so it can be imported and unit-tested; the script
is a thin CLI wrapper. CI runs the script, and a failing row is reported by ID - "verification
failed" without naming the row is useless for fixing anything.
"""
from __future__ import annotations

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


def check_requirement(row: dict, manifest: dict) -> dict:
    kind = row.get("kind")

    if kind == "command":
        proc = run_command(row["run"], timeout=row.get("timeout", 600))
        return {"ok": proc.returncode == 0,
                "detail": (proc.stdout or proc.stderr or "")[-300:]}

    if kind == "test":
        # run_tests.py matches a single -k substring against the test id, so a multi-class row
        # is expressed as a list and every entry must pass.
        selections = row.get("tests") or [row["run"]]
        details = []
        for selection in selections:
            command = selection if selection.startswith("python ") else \
                "python scripts/run_tests.py -k %s" % selection
            proc = run_command(command, timeout=row.get("timeout", 900))
            tail = [line for line in (proc.stdout or "").splitlines()
                    if line.startswith(("Ran ", "OK", "FAILED"))]
            details.append("%s: %s" % (selection, " | ".join(tail[-2:]) or (proc.stderr or "")[-120:]))
            if proc.returncode != 0:
                return {"ok": False, "detail": " ; ".join(details)[:300]}
        return {"ok": True, "detail": " ; ".join(details)[:300]}

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


def verify(manifest: dict, only=None, use_generators=True) -> dict:
    rows = [r for r in manifest.get("requirement", []) if not only or r["id"] in only]

    generator_results = {}
    if use_generators and not only:
        print("generators:")
        generator_results = run_generators(manifest)

    print("\nrequirements:")
    results = []
    for row in rows:
        outcome = check_requirement(row, manifest)
        results.append({"id": row["id"], "title": row.get("title", ""),
                        "owner": row.get("owner", ""), **outcome})
        print("  %-7s %-4s %s" % (row["id"], "PASS" if outcome["ok"] else "FAIL",
                                  (outcome.get("detail") or "")[:110]))
        if row.get("note") and not outcome["ok"]:
            print("         note: %s" % row["note"])

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
