"""Docs must not drift from the code: the single entry point, its flags, and the
parameter matrix have to be described consistently.

These are cheap static checks - they fail when someone edits the CLI or the README and forgets
the matrix, or fleshes out the matrix but never links it. The numbers in the matrix are asserted by
the evaluation suite, not here; this only guards that the *documentation* stays connected to the
*entry point*. The "no second entry script" assertion lives in test_harness_selfcheck.py.
"""
from __future__ import annotations

import json
import os
import unittest


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel: str) -> str:
    with open(os.path.join(_repo_root(), rel), "r", encoding="utf-8") as fh:
        return fh.read()


class ParameterMatrixDocumentedTest(unittest.TestCase):
    def test_matrix_doc_lists_every_entry_flag(self):
        matrix = _read("docs/eval/parameter-matrix.md")
        for flag in ("--all", "--mode", "--rerank", "--corpus", "--deliverables",
                     "--refresh-model-backed", "--cost", "--max-cases", "--cases"):
            self.assertIn(flag, matrix, "parameter-matrix.md must document %s" % flag)
        self.assertIn("scripts/run.py", matrix, "matrix must name the single entry point")

    def test_readme_links_matrix_and_single_entry_point(self):
        readme = _read("README.md")
        self.assertIn("parameter-matrix.md", readme,
                      "README must link to docs/eval/parameter-matrix.md")
        # The entry point is scripts/run.py alone; no second script may appear.
        self.assertIn("scripts/run.py", readme)
        self.assertNotIn("build_deliverables.py", readme,
                         "README must not reference the deleted second entry point")
        self.assertNotIn("build_deliverables.py",
                         _read("docs/eval/parameter-matrix.md"),
                         "matrix must not reference the deleted second entry point")

    def test_readme_documents_reviewer_supplied_corpus(self):
        """The reviewer-supplied corpus is a required capability (issue #96)."""
        readme = _read("README.md")
        self.assertIn("--corpus", readme, "README must document the --corpus flag")
        self.assertIn("Bring your own documents", readme,
                      "README needs the 'Bring your own documents' section")

    def test_readme_quotes_the_current_corpus_and_case_count(self):
        """The README once quoted a corpus version and case count from an older run, which made
        every number in its table look current when it was not. Pin it to the committed snapshot."""
        with open(os.path.join(_repo_root(), "docs", "eval", "deterministic-metrics.json"),
                  "r", encoding="utf-8") as fh:
            snapshot = json.load(fh)
        meta = snapshot.get("run_metadata", {})
        corpus = str(meta.get("corpus_version", ""))
        cases = str(meta.get("case_count", ""))
        self.assertTrue(corpus and cases, "the snapshot must record corpus_version and case_count")
        readme = _read("README.md")
        self.assertIn(corpus, readme,
                      "README must quote the current corpus version %s, not one from an older run"
                      % corpus)
        self.assertIn("%s labelled cases" % cases, readme,
                      "README must quote the current case count (%s)" % cases)
        matrix = _read("docs/eval/parameter-matrix.md")
        self.assertIn(corpus, matrix, "parameter-matrix.md must quote the current corpus version")
        self.assertIn("%s labelled cases" % cases, matrix,
                      "parameter-matrix.md must quote the current case count")


if __name__ == "__main__":
    unittest.main()
