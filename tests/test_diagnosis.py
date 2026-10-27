"""EPIC #8: diagnosis cases must be reproducible and must clear the 10% bar."""
from __future__ import annotations

import os
import tempfile
import unittest

from ragserve.evaluation.diagnosis import CASES, IMPROVEMENT_THRESHOLD, run_case

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestDiagnosisCases(unittest.TestCase):
    def test_at_least_two_cases_exist(self):
        self.assertGreaterEqual(len(CASES), 2)

    def test_refusal_gate_case_clears_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = run_case("refusal-gate", ROOT, tmp)
            self.assertTrue(report["meets_threshold"],
                            "improvement %s below %s" % (report["improvement"],
                                                         IMPROVEMENT_THRESHOLD))
            self.assertLess(report["after"]["wrong_refusals"], report["before"]["wrong_refusals"])
            self.assertGreater(report["after"]["refusal_appropriateness"],
                               report["before"]["refusal_appropriateness"])

    def test_ocr_penalty_case_clears_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = run_case("ocr-penalty", ROOT, tmp)
            self.assertTrue(report["meets_threshold"],
                            "improvement %s below %s" % (report["improvement"],
                                                          IMPROVEMENT_THRESHOLD))
            self.assertGreater(report["after"]["ocr_mrr"], report["before"]["ocr_mrr"])
            self.assertLessEqual(report["after"]["ocr_refusals"], report["before"]["ocr_refusals"])

    def test_refusal_case_carries_log_evidence(self):
        """A diagnosis without log evidence is a story."""
        with tempfile.TemporaryDirectory() as tmp:
            report = run_case("refusal-gate", ROOT, tmp)
            self.assertTrue(report["log_evidence"])
            self.assertTrue(all(e.get("refusal_reason") for e in report["log_evidence"]))

    def test_artifacts_are_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = run_case("refusal-gate", ROOT, tmp)
            for name in ("report.json", "report.md"):
                self.assertTrue(os.path.isfile(os.path.join(report["artifacts"], name)), name)

    def test_the_legacy_behaviour_really_is_worse(self):
        """Guards against the reconstruction silently matching the fixed behaviour."""
        with tempfile.TemporaryDirectory() as tmp:
            report = run_case("ocr-penalty", ROOT, tmp)
            self.assertGreater(report["before"]["ocr_refusals"], 0)


if __name__ == "__main__":
    unittest.main()
