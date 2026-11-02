"""Every command the README documents is executed here (R23).

The failure this closes, and it was fatal: `python scripts/run.py --corpus DIR` - printed in the
Quickstart - failed **100% of the time** with `unrecognized arguments`. The dispatcher treated
`--corpus` as a valueless mode switch, stripped it, and left the path behind. Nothing caught it
because the command matrix I had run only covered `--eval --corpus DIR`, which takes a different
code path, and because no test ever executed a command taken from the README itself.

So the rule is mechanical, not aspirational: if the README shows a command, a test runs it, and a
self-check fails when the README gains a command that no test covers.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRY = os.path.join(REPO, "scripts", "run.py")
QUESTION = "How many days of annual leave do full-time employees accrue?"

#: (label, argv, stdin) for every command that can be executed inside the suite.
CASES = (
    ("--check", ["--check"], None),
    ("interactive", [], QUESTION + "\n:quit\n"),
    ("interactive --corpus", ["--corpus", os.path.join("tests", "data", "external-corpus")],
     QUESTION + "\n:quit\n"),
    ("--eval", ["--eval", "--all"], None),
    ("--eval --cost", ["--eval", "--all", "--cost"], None),
    ("--bench", ["--bench", "--concurrency", "5", "--assert"], None),
    ("--gen-corpus", ["--gen-corpus", "--out", "__TMP__"], None),
    ("--diagnose", ["--diagnose", "--all"], None),
    # The matrix itself is a documented command: it derives the combinations from the CLI, so this
    # one case keeps 61 of them honest on every build.
    ("--matrix --quick", ["--matrix", "--quick"], None),
)

#: Documented commands deliberately not executed here, each with a reason. The self-check reads this
#: map, so a new README command fails the build until it is either executed or explained.
NOT_EXECUTED = {
    "--setup": "downloads ~1 GB; the real-model contract job installs the models instead",
    "--serve": "blocks on a socket; covered by the API tests",
    "--test": "this suite (would recurse)",
    "--verify": "runs this suite in eight subprocesses (would recurse)",
    "--audit": "re-runs every probe including --eval and --verify",
    "--deliverables": "regenerates committed files; drift-guarded by the comparison-doc test",
    "--refresh-model-backed": "refuses without model servers; covered by the real-model contract job",
    "--seed-model-backed": "commits an existing artefact; exercised when the snapshot was made",
    "--samples": "regenerates a committed file; guarded by the same drift test as --deliverables",
    "--dashboard": "regenerates a committed file; guarded by the same drift test as --deliverables",
}

#: Mode flags the README may use. Anything else that looks like a mode is a documentation bug.
MODE_FLAGS = ("--ask", "--eval", "--corpus", "--serve", "--setup", "--check", "--bench", "--test",
              "--verify", "--audit", "--diagnose", "--gen-corpus", "--samples", "--dashboard",
              "--build-corpus", "--matrix")


def _env() -> dict:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["RAGSERVE_EMBEDDING_PROVIDER"] = "deterministic"
    env["RAGSERVE_RERANKER_PROVIDER"] = "deterministic"
    return env


def read(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


class DocumentedCommandsTest(unittest.TestCase):
    def test_every_documented_command_runs(self):
        failures = []
        for label, argv, stdin in CASES:
            with tempfile.TemporaryDirectory(prefix="doc-cmd-") as tmp:
                argv = [a.replace("__TMP__", tmp) for a in argv]
                proc = subprocess.run([sys.executable, ENTRY] + argv, cwd=REPO, env=_env(),
                                      input=stdin, capture_output=True, text=True,
                                      encoding="utf-8", errors="replace", timeout=900)
            out = (proc.stdout or "") + (proc.stderr or "")
            for marker in ("unrecognized arguments", "Traceback (most recent call last)",
                           "expected one argument", "invalid choice"):
                if marker in out:
                    failures.append("%s: %s" % (label, marker))
                    break
            if proc.returncode != 0:
                failures.append("%s: exit %d" % (label, proc.returncode))
        self.assertEqual(failures, [],
                         "a command the README documents does not work: %s" % failures)

    def test_a_supplied_corpus_is_indexed_interactively(self):
        """The exact command that was broken: it must not merely parse, it must index."""
        proc = subprocess.run(
            [sys.executable, ENTRY, "--no-bootstrap", "--corpus",
             os.path.join("tests", "data", "external-corpus")],
            cwd=REPO, env=_env(), input=QUESTION + "\n:quit\n", capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=300)
        self.assertEqual(proc.returncode, 0, proc.stderr[-400:])
        self.assertIn("documents     : 2", proc.stdout,
                      "the supplied corpus must be reported in the banner")

    def test_interactive_edge_cases_do_not_crash(self):
        """Typed input a reviewer will produce by accident must be handled, not traceback."""
        inputs = [
            "   \n:quit\n",                     # blank
            ":stats\n:quit\n",                  # stats before any question
            ":bench 5\n:quit\n",                # bench before any question
            QUESTION + "\n:bench 0\n:quit\n",   # zero concurrency
            QUESTION + "\n:bench abc\n:quit\n",  # non-numeric
            ":nonsense\n:quit\n",               # unknown command
            "\n",                               # EOF straight away
        ]
        for stdin in inputs:
            proc = subprocess.run([sys.executable, ENTRY, "--no-bootstrap"], cwd=REPO, env=_env(),
                                  input=stdin, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=300)
            out = (proc.stdout or "") + (proc.stderr or "")
            self.assertNotIn("Traceback (most recent call last)", out,
                             "input %r crashed the loop" % stdin)
            self.assertEqual(proc.returncode, 0, "input %r exited %d" % (stdin, proc.returncode))


class DocumentedCommandsAreCoveredTest(unittest.TestCase):
    """R23: a command in the README that no test executes is an untested promise."""

    def _documented_modes(self):
        readme = read(os.path.join(REPO, "README.md"))
        modes = set()
        for match in re.finditer(r"python\s+scripts/run\.py([^\n`]*)", readme):
            tokens = match.group(1).split()
            flags = [t for t in tokens if t.startswith("--")]
            mode = next((t for t in flags if t in MODE_FLAGS), None)
            modes.add(mode or "(interactive)")
        return modes

    def test_every_readme_command_is_executed_or_explicitly_excluded(self):
        executed = {label for label, _argv, _stdin in CASES}
        executed_modes = set()
        for label, argv, _stdin in CASES:
            flag = next((a for a in argv if a in MODE_FLAGS), None)
            executed_modes.add(flag or "(interactive)")
            self.assertIn(label, executed)
        missing = []
        for mode in sorted(self._documented_modes()):
            if mode == "(interactive)":
                if "(interactive)" not in executed_modes:
                    missing.append(mode)
                continue
            if mode in executed_modes:
                continue
            if mode in NOT_EXECUTED:
                continue
            missing.append(mode)
        self.assertEqual(missing, [],
                         "README documents commands no test runs and no exclusion explains: %s"
                         % missing)

    def test_every_exclusion_states_a_reason(self):
        for mode, reason in NOT_EXECUTED.items():
            self.assertGreater(len(reason), 20, "%s needs a real reason" % mode)


if __name__ == "__main__":
    unittest.main()
