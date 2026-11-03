"""The one-click script must be usable from a bare terminal: it has to say where it is, and it
must refuse a combination it cannot honour instead of silently doing nothing.

Both checks run through the real script. They are cheap because the refusal happens before any
evaluation runs.
"""
from __future__ import annotations

import os
import subprocess
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(REPO, "tests", "data", "external-corpus")
#: The three committed deliverables. The QA dashboard is generated on demand and gitignored - it
#: reflects the latest run by design, so committing it dirtied the tree after every test run.
DELIVERABLES = [
    os.path.join(REPO, "docs", "eval", "deterministic-metrics.json"),
    os.path.join(REPO, "docs", "eval", "retrieval-comparison.md"),
    os.path.join(REPO, "docs", "logging", "sample_logs.md"),
]


def run_script(*args: str):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["RAGSERVE_EMBEDDING_PROVIDER"] = "deterministic"
    env["RAGSERVE_RERANKER_PROVIDER"] = "deterministic"
    return subprocess.run([sys.executable, os.path.join(REPO, "scripts", "run.py"), "--eval"] + list(args),
                          cwd=REPO, env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=300)


class EntryScriptClarityTest(unittest.TestCase):
    def test_the_terminal_says_which_folder_it_is_in_and_where_the_repo_is(self):
        """A reviewer opens a terminal and runs one command; they must not have to guess."""
        proc = run_script("--corpus", FIXTURE, "--deliverables")
        self.assertIn("Terminal folder", proc.stdout,
                      "the script must print the folder the terminal is in")
        self.assertIn("Repository root", proc.stdout,
                      "the script must print the repository root the deliverables belong to")
        self.assertIn(REPO, proc.stdout, "the printed root must be this repository")

    def test_corpus_plus_deliverables_refuses_instead_of_writing_nothing_silently(self):
        before = {p: os.path.getmtime(p) for p in DELIVERABLES}
        proc = run_script("--corpus", FIXTURE, "--deliverables")
        self.assertNotEqual(proc.returncode, 0,
                            "a flag that cannot be honoured must refuse, not exit 0")
        self.assertIn("REFUSED", proc.stdout)
        after = {p: os.path.getmtime(p) for p in DELIVERABLES}
        self.assertEqual(before, after, "a refused run must not touch the committed deliverables")

    def test_a_plain_corpus_run_still_reports_where_its_output_went(self):
        proc = run_script("--corpus", FIXTURE)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Outputs", proc.stdout,
                      "every combination must end with the paths it wrote")


def run_ask(*questions: str):
    """Drive the interactive loop with piped answers, hermetically."""
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["RAGSERVE_EMBEDDING_PROVIDER"] = "deterministic"
    env["RAGSERVE_RERANKER_PROVIDER"] = "deterministic"
    return subprocess.run(
        [sys.executable, os.path.join(REPO, "scripts", "run.py"), "--no-bootstrap"],
        cwd=REPO, env=env, input="\n".join(questions) + "\n", capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300)


class InteractiveMultiTurnTest(unittest.TestCase):
    """The loop must carry the previous turn, not just the service API (issue #132).

    Observed: `Session.ask` called `answer(question)` with no history, so "multi-turn" only worked if
    you drove the service directly - the one script the reviewer runs was single-turn.
    """

    def test_a_follow_up_is_rewritten_against_the_previous_turn(self):
        proc = run_ask("How many days of annual leave do full-time employees accrue?",
                       "What about part-time employees?", ":quit")
        self.assertEqual(proc.returncode, 0, proc.stderr[-400:])
        self.assertIn("resolved to:", proc.stdout,
                      "the loop must show the rewrite, or a bad one is invisible")
        rewritten = next(line for line in proc.stdout.splitlines() if "resolved to:" in line)
        self.assertIn("annual leave", rewritten)
        self.assertIn("part-time", rewritten)

    def test_a_first_question_is_never_rewritten(self):
        proc = run_ask("How many days of annual leave do full-time employees accrue?", ":quit")
        self.assertEqual(proc.returncode, 0, proc.stderr[-400:])
        self.assertNotIn("resolved to:", proc.stdout)


if __name__ == "__main__":
    unittest.main()
