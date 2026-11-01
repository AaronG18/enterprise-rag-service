"""Docs must not drift from the code: the single entry point, its flags, and the
parameter matrix have to be described consistently.

These are cheap static checks - they fail when someone edits the CLI or the README and forgets
the matrix, or fleshes out the matrix but never links it. The numbers in the matrix are asserted by
the evaluation suite, not here; this only guards that the *documentation* stays connected to the
*entry point*. The "no second entry script" assertion lives in test_harness_selfcheck.py.
"""
from __future__ import annotations

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
        self.assertIn("run_eval.py", matrix, "matrix must name the single entry point")

    def test_readme_links_matrix_and_single_entry_point(self):
        readme = _read("README.md")
        self.assertIn("parameter-matrix.md", readme,
                      "README must link to docs/eval/parameter-matrix.md")
        # The entry point is run_eval.py alone; the deleted second script must not appear.
        self.assertIn("run_eval.py", readme)
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


if __name__ == "__main__":
    unittest.main()
