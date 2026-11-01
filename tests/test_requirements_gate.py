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


class TestTestRowSelections(unittest.TestCase):
    """A test row must fail when it names a test class that does not exist.

    Measured: seven selections in the manifest matched zero tests, and `scripts/run.py -k`
    exits 0 when nothing matches - so those rows were passing vacuously.
    """

    def test_a_row_naming_a_missing_class_fails(self):
        row = {"id": "R-98", "kind": "test", "tests": ["TestThisClassDoesNotExist"],
               "owner": "#1"}
        outcome = check_requirement(row, {})
        self.assertFalse(outcome["ok"], "a missing test class must not pass")
        self.assertIn("no test class", outcome["detail"].lower())

    def test_a_row_naming_an_existing_class_passes(self):
        row = {"id": "R-97", "kind": "test", "tests": ["TestRefusal"], "owner": "#1"}
        outcome = check_requirement(row, {})
        self.assertTrue(outcome["ok"], outcome["detail"])


class TestRunnerJsonOutput(unittest.TestCase):
    """The test runner must be able to report per-class results to the gate."""

    def _run(self, *args):
        import subprocess
        import sys

        return subprocess.run([sys.executable, os.path.join(REPO_ROOT, "scripts", "run.py"), "--test"] +
                              list(args), cwd=REPO_ROOT, capture_output=True, text=True,
                              encoding="utf-8", errors="ignore")

    def test_json_output_reports_per_class_results(self):
        proc = self._run("--json", "--classes", "TestRefusal")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["ok"])
        self.assertIn("TestRefusal", payload["classes"])
        self.assertGreater(payload["classes"]["TestRefusal"]["total"], 0)

    def test_missing_class_is_reported_and_exits_non_zero(self):
        proc = self._run("--json", "--classes", "TestNoSuchClass")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("no test class", (proc.stdout + proc.stderr).lower())

    def test_parallel_run_reports_the_same_tests_as_a_serial_run(self):
        """Parallelism must not lose or duplicate a test."""
        classes = "TestRefusal,TestMultiTurn,TestVectorRetrieval,TestHybridAndFusion"
        serial = json.loads(self._run("--json", "--jobs", "1", "--classes", classes).stdout)
        parallel = json.loads(self._run("--json", "--jobs", "4", "--classes", classes).stdout)
        self.assertEqual(serial["total"], parallel["total"])
        self.assertEqual(sorted(serial["classes"]), sorted(parallel["classes"]))
        for name, entry in serial["classes"].items():
            self.assertEqual(entry["total"], parallel["classes"][name]["total"], name)


class TestParallelEquivalence(unittest.TestCase):
    """Concurrency must not change a verdict."""

    def test_parallel_and_serial_agree(self):
        manifest = load_manifest()
        serial = verify(manifest, only=["R-14", "R-16", "R-19"], use_generators=False, jobs=1)
        parallel = verify(manifest, only=["R-14", "R-16", "R-19"], use_generators=False, jobs=4)
        self.assertEqual([(r["id"], r["ok"]) for r in serial["requirements"]],
                         [(r["id"], r["ok"]) for r in parallel["requirements"]])

    def test_results_keep_manifest_order(self):
        manifest = load_manifest()
        summary = verify(manifest, only=["R-19", "R-14", "R-16"], use_generators=False, jobs=4)
        self.assertEqual([r["id"] for r in summary["requirements"]], ["R-14", "R-16", "R-19"])


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
