"""EPIC 14 / SUB 54: the requirements gate itself must be trustworthy.

These tests are regression guards for an existing implementation rather than red-first proofs -
the red-first proof for the gate is the demo PR in SUB 58, where a deliberate violation fails
the workflow and names the rule.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import unittest

from ragserve.evaluation.verification import check_requirement, load_manifest, verify

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(REPO_ROOT, "harness", "requirements.toml")
MATRIX = os.path.join(REPO_ROOT, "docs", "REQUIREMENTS.md")


class TestManifestMatrixSync(unittest.TestCase):
    def test_every_matrix_row_has_a_manifest_row_and_back(self):
        """The human matrix and the machine manifest cannot drift: a requirement that exists in
        one and not the other is either unverified or unenforced."""
        with open(MATRIX, "r", encoding="utf-8") as fh:
            matrix_ids = set(re.findall(r"\|\s*(R-\d+m?)\s*\|", fh.read()))
        manifest = load_manifest()
        manifest_ids = {row["id"] for row in manifest.get("requirement", [])}

        self.assertTrue(matrix_ids, "no requirement IDs found in docs/REQUIREMENTS.md")
        missing_in_manifest = matrix_ids - manifest_ids
        self.assertEqual(missing_in_manifest, set(),
                         "rows in the matrix with no verification: %s" % sorted(missing_in_manifest))
        # Manifest-only rows are allowed (the model-backed lane), but must be declared.
        extra = manifest_ids - matrix_ids
        for row in manifest.get("requirement", []):
            if row["id"] in extra:
                self.assertIn("note", row, "manifest row %s is not in the matrix and carries no "
                                           "note explaining why" % row["id"])

    def test_every_row_has_an_owner_issue(self):
        manifest = load_manifest()
        for row in manifest.get("requirement", []):
            self.assertTrue(row.get("owner", "").startswith("#"),
                            "%s has no owner issue" % row["id"])


class TestFailureReporting(unittest.TestCase):
    def test_failing_row_is_named_and_the_run_fails(self):
        manifest = {
            "requirement": [
                {"id": "R-99", "title": "synthetic failing row", "kind": "file",
                 "path": "does/not/exist.md", "owner": "#1"},
            ]
        }
        summary = verify(manifest, use_generators=False)
        self.assertFalse(summary["ok"])
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["requirements"][0]["id"], "R-99")
        self.assertIn("missing file", summary["requirements"][0]["detail"])

    def test_passing_row_is_reported_as_passing(self):
        manifest = {"requirement": [
            {"id": "R-98", "title": "synthetic passing row", "kind": "file",
             "path": "harness/requirements.toml", "owner": "#1"},
        ]}
        summary = verify(manifest, use_generators=False)
        self.assertTrue(summary["ok"])
        self.assertEqual(summary["passed"], 1)


class TestMetricRows(unittest.TestCase):
    def test_metric_reads_a_named_section_and_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = {"operations": {"answer_compliance_rate": 0.91},
                       "comparison": {"hybrid": {"faithfulness": 1.0}}}
            path = os.path.join(tmp, "metrics.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh)

            row = {"id": "R-01", "kind": "metric", "path": path, "section": "operations",
                   "metric": "answer_compliance_rate", "op": ">=", "bound": 0.90}
            outcome = check_requirement(row, {})
            self.assertTrue(outcome["ok"], outcome["detail"])
            self.assertIn("0.91", outcome["detail"])

            row["section"] = "comparison"
            row["config"] = "hybrid"
            row["metric"] = "faithfulness"
            row["bound"] = 0.85
            self.assertTrue(check_requirement(row, {})["ok"])

    def test_metric_below_its_bound_fails_with_the_numbers(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "m.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"comparison": {"hybrid": {"faithfulness": 0.42}}}, fh)
            row = {"id": "R-02", "kind": "metric", "path": path, "config": "hybrid",
                   "metric": "faithfulness", "op": ">=", "bound": 0.85}
            outcome = check_requirement(row, {})
            self.assertFalse(outcome["ok"])
            self.assertIn("0.42", outcome["detail"])


if __name__ == "__main__":
    unittest.main()
