"""EPIC #6 / SUB 25-28: scorers, comparison harness, reproducibility, operations report."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import dataclass
from typing import List

from ragserve.evaluation import metrics as M
from ragserve.evaluation.report import OPS_FIELDS, render_csv, render_text
from ragserve.evaluation.runner import CONFIGURATIONS, load_cases, run_evaluation

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL_CASES = os.path.join(ROOT, "eval", "eval_cases.json")


class _FakeAnswer:
    def __init__(self, text, citations, refused=False, usage=None):
        self.text = text
        self.citations = citations
        self.refused = refused
        self.usage = usage or {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}


class _FakeChunk:
    def __init__(self, chunk_id, doc_id, text):
        self.chunk_id = chunk_id
        self.doc_id = doc_id
        self.text = text


class _FakeResult:
    def __init__(self, answer, retrieved, resolved_query):
        self.answer = answer
        self.retrieved = retrieved
        self.resolved_query = resolved_query


class TestFaithfulness(unittest.TestCase):
    def test_verbatim_answer_scores_one(self):
        text = "Full-time employees accrue 15 working days of paid annual leave per year."
        self.assertEqual(M.faithfulness(text, [text]), 1.0)

    def test_invented_sentence_lowers_score(self):
        supported = "Full-time employees accrue 15 working days of paid annual leave per year."
        invented = "The board approved a dividend of 4 euros per share last March."
        score = M.faithfulness(supported + " " + invented, [supported])
        self.assertLess(score, 1.0)
        self.assertGreaterEqual(score, 0.0)

    def test_empty_answer_scores_zero(self):
        self.assertEqual(M.faithfulness("", ["anything"]), 0.0)


class TestContextPrecision(unittest.TestCase):
    def test_relevant_at_top_rank_scores_one(self):
        self.assertEqual(M.context_precision(["a:1", "b:1", "b:2"], {"a:1"}), 1.0)

    def test_relevant_buried_at_rank_three(self):
        """Rank-weighted: a relevant chunk at rank 3 scores 1/3, not "1 of 5"."""
        self.assertAlmostEqual(M.context_precision(["b:1", "b:2", "a:1"], {"a:1"}), 1 / 3, places=4)

    def test_relevance_beats_coverage_ratio(self):
        """The naive fraction-of-retrieved definition is capped at 0.4 here (2 chunks/doc,
        top_k=5) and could never reach the 0.70 target; rank weighting can."""
        self.assertGreater(M.context_precision(["a:1", "b:1", "b:2", "c:1", "c:2"], {"a:1"}), 0.7)

    def test_no_retrieval_scores_zero(self):
        self.assertEqual(M.context_precision([], {"a:1"}), 0.0)


class TestAnswerCompliance(unittest.TestCase):
    def _result(self, text, citations, query="annual leave days"):
        chunk = _FakeChunk("c:1", "handbook-en-00", text)
        answer = _FakeAnswer(text, citations)
        return _FakeResult(answer, [chunk], query)

    def test_cited_answer_complies_more_than_uncited(self):
        text = "Full-time employees accrue 15 working days of paid annual leave per year."
        cited = M.answer_compliance(self._result(text, ["c:1"]))["score"]
        uncited = M.answer_compliance(self._result(text, []))["score"]
        self.assertGreater(cited, uncited)

    def test_overlong_answer_is_penalised(self):
        text = "Full-time employees accrue 15 working days of paid annual leave per year."
        long_text = text + " " + ("extra wording " * 200)
        normal = M.answer_compliance(self._result(text, ["c:1"]), max_chars=600)["score"]
        overlong = M.answer_compliance(self._result(long_text, ["c:1"]), max_chars=600)["score"]
        self.assertGreater(normal, overlong)


class TestRefusalAppropriateness(unittest.TestCase):
    def test_perfect_match(self):
        self.assertEqual(M.refusal_appropriateness([True, False, True], [True, False, True]), 1.0)

    def test_over_refusing_is_penalised(self):
        """A service that refuses everything looks safe and scores badly here."""
        self.assertEqual(M.refusal_appropriateness([True, True], [True, False]), 0.5)

    def test_missing_refusal_is_penalised(self):
        self.assertEqual(M.refusal_appropriateness([False, False], [True, False]), 0.5)


class TestStyle(unittest.TestCase):
    def test_consistent_answers_score_high(self):
        good = "Full-time employees accrue 15 working days of paid annual leave per year."
        self.assertGreater(M.style_score(good, True), 0.8)

    def test_deviant_answer_scores_lower(self):
        good = "Full-time employees accrue 15 working days of paid annual leave per year."
        deviant = "* BULLET POINT\n- another bullet"
        self.assertGreater(M.style_score(good, True), M.style_score(deviant, False))


class TestReport(unittest.TestCase):
    def setUp(self):
        self.operations = {field: 1.0 for field in OPS_FIELDS}
        self.comparison = {name: {"recall@5": 0.5, "mrr": 0.4, "ndcg": 0.3,
                                  "context_precision": 0.2, "faithfulness": 0.9,
                                  "refusal_appropriateness": 1.0, "style_consistency": 0.8}
                           for name in CONFIGURATIONS}

    def test_text_report_has_all_six_operations_fields(self):
        text = render_text(self.operations, self.comparison, {"corpus_version": "abc"})
        for field in OPS_FIELDS:
            self.assertIn(field, text)

    def test_csv_report_has_all_six_operations_fields(self):
        csv_text = render_csv(self.operations, self.comparison)
        for field in OPS_FIELDS:
            self.assertIn(field, csv_text)

    def test_csv_is_parseable(self):
        import csv as csv_module
        import io

        rows = list(csv_module.reader(io.StringIO(render_csv(self.operations, self.comparison))))
        self.assertEqual(rows[0], ["section", "metric", "configuration", "value"])


class TestEvaluationRun(unittest.TestCase):
    def test_labelled_set_is_large_enough_to_discriminate(self):
        cases = load_cases(EVAL_CASES)
        self.assertGreaterEqual(len(cases), 20)
        languages = {c["language"] for c in cases}
        self.assertEqual(languages, {"en", "zh"})
        self.assertTrue(any(c["expect_refusal"] for c in cases))

    def test_all_three_configurations_are_measured(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_evaluation(ROOT, tmp)
            self.assertEqual(set(result["comparison"]), set(CONFIGURATIONS))

    def test_graded_metrics_are_present_and_in_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_evaluation(ROOT, tmp)
            for name, metrics in result["comparison"].items():
                for field in ("recall@5", "mrr", "ndcg", "context_precision", "faithfulness",
                              "refusal_appropriateness", "style_consistency"):
                    self.assertIn(field, metrics)
                    self.assertGreaterEqual(metrics[field], 0.0)
                    self.assertLessEqual(metrics[field], 1.0)

    def test_quality_metrics_are_reproducible(self):
        """SUB 26 criterion: same inputs -> same numbers. Latency is excluded (it is wall clock)."""
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            a = run_evaluation(ROOT, first)
            b = run_evaluation(ROOT, second)
            self.assertEqual(a["comparison"], b["comparison"])
            self.assertEqual(a["run_metadata"], b["run_metadata"])
            self.assertEqual(a["operations"]["token_usage_total"],
                             b["operations"]["token_usage_total"])

    def test_artifacts_are_stamped(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_evaluation(ROOT, tmp)
            meta = result["run_metadata"]
            self.assertTrue(meta["corpus_version"])
            self.assertEqual(meta["provenance"], "deterministic")
            for key in ("metrics", "report", "report_csv", "scored_cases"):
                self.assertTrue(os.path.isfile(result["artifacts"][key]), key)


if __name__ == "__main__":
    unittest.main()
