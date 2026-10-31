"""Golden-set regression: retrieval must not quietly get worse.

The requirement gate reads metrics out of a full evaluation artefact, which is expensive and only
runs in CI. This file is the fast, in-process version: a small labelled retrieval set, scored with
the *same* metric functions the evaluation uses (`ragserve.evaluation.metrics`), against the
*same* offline deterministic backend, so a regression shows up in the hermetic suite in seconds.

The floors below were measured, not guessed (harness/RULES.md R3): with the deterministic backend
on `tests/data/retrieval_cases.json` the measurements were

    vector_only    recall@5 0.6000  mrr 0.6000  ndcg 0.6000  context_precision 0.6000
    hybrid         recall@5 0.9000  mrr 0.6533  ndcg 0.7149  context_precision 0.5933
    hybrid+rerank  recall@5 0.8000  mrr 0.7333  ndcg 0.7500  context_precision 0.7083

and the floors sit a little below those numbers so that a deliberate, evidenced change can lower
them - but a silent regression cannot. Lowering a floor is an act that needs evidence, like any
other change to a number in this repository.
"""
from __future__ import annotations

import json
import os
import unittest

from ragserve.corpus.builder import CorpusConfig, build_corpus
from ragserve.evaluation import metrics as M
from ragserve.retrieval.pipeline import RetrievalConfig, RetrievalPipeline

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES_PATH = os.path.join(os.path.dirname(__file__), "data", "retrieval_cases.json")
CORPUS_CONFIG = os.path.join(REPO_ROOT, "configs", "corpus.json")
RETRIEVAL_CONFIG = os.path.join(REPO_ROOT, "configs", "retrieval.json")

# Measured floors. See the module docstring for the measurement they came from.
FLOORS = {
    "vector_only": {"recall@5": 0.55, "mrr": 0.55, "ndcg": 0.55, "context_precision": 0.55},
    "hybrid": {"recall@5": 0.85, "mrr": 0.60, "ndcg": 0.66, "context_precision": 0.55},
    "hybrid+rerank": {"recall@5": 0.75, "mrr": 0.68, "ndcg": 0.70, "context_precision": 0.65},
}

CONFIGS = {
    "vector_only": {"mode": "vector_only", "rerank_enabled": False},
    "hybrid": {"mode": "hybrid", "rerank_enabled": False},
    "hybrid+rerank": {"mode": "hybrid", "rerank_enabled": True},
}


def load_cases():
    with open(CASES_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def build_pipeline(**overrides) -> RetrievalPipeline:
    """A pipeline on the offline backend.

    The pins matter: the shipped config now points at a local model server, and a suite that
    silently fell back would score a different system than the one it claims to measure.
    """
    config = RetrievalConfig.from_json(RETRIEVAL_CONFIG)
    config.embedding_provider = "deterministic"
    config.reranker_provider = "deterministic"
    for key, value in overrides.items():
        setattr(config, key, value)
    corpus = build_corpus(CorpusConfig.from_json(CORPUS_CONFIG))
    return RetrievalPipeline(corpus, config)


def score(pipeline: RetrievalPipeline, cases) -> dict:
    """Score the golden set with the evaluation's own metric functions."""
    hits = 0
    reciprocal = 0.0
    ndcg = 0.0
    precision = 0.0
    for case in cases:
        results = pipeline.retrieve(case["query"])
        doc_ids = [r.doc_id for r in results]
        chunk_ids = [r.chunk_id for r in results]
        expected = case["expected_doc_id"]
        if expected in doc_ids:
            hits += 1
        reciprocal += M.reciprocal_rank(doc_ids, expected)
        ndcg += M.ndcg(doc_ids, expected)
        relevant = [r.chunk_id for r in results if r.doc_id == expected]
        precision += M.context_precision(chunk_ids, relevant)
    total = len(cases)
    return {"recall@5": hits / total, "mrr": reciprocal / total,
            "ndcg": ndcg / total, "context_precision": precision / total}


class TestGoldenSetIsSane(unittest.TestCase):
    """A golden set with a typo in it measures nothing, so it is checked first."""

    @classmethod
    def setUpClass(cls):
        cls.cases = load_cases()
        cls.corpus = build_corpus(CorpusConfig.from_json(CORPUS_CONFIG))
        cls.doc_ids = {doc.doc_id for doc in cls.corpus.documents}

    def test_set_is_not_empty(self):
        self.assertGreaterEqual(len(self.cases), 8,
                                "the golden set must stay big enough to notice a regression")

    def test_every_case_names_a_document_that_exists(self):
        unknown = sorted({case["expected_doc_id"] for case in self.cases
                          if case["expected_doc_id"] not in self.doc_ids})
        self.assertEqual(unknown, [], "golden set points at documents that do not exist: %s" % unknown)

    def test_set_covers_both_languages(self):
        languages = {case.get("language") for case in self.cases}
        self.assertIn("en", languages, "the golden set lost its English cases")
        self.assertIn("zh", languages, "the golden set lost its Chinese cases")

    def test_every_case_has_a_query_and_an_expected_document(self):
        broken = [case for case in self.cases
                  if not case.get("query") or not case.get("expected_doc_id")]
        self.assertEqual(broken, [], "golden cases missing a query or an expected document")


class TestGoldenRetrieval(unittest.TestCase):
    """Each configuration must stay at or above its measured floor."""

    @classmethod
    def setUpClass(cls):
        cls.cases = load_cases()

    def _check(self, name: str):
        pipeline = build_pipeline(**CONFIGS[name])
        measured = score(pipeline, self.cases)
        floors = FLOORS[name]
        below = ["%s %.4f < %.4f" % (metric, measured[metric], floor)
                 for metric, floor in floors.items() if measured[metric] < floor]
        self.assertEqual(below, [], "golden-set regression in %s: %s" % (name, below))

    def test_vector_only_meets_its_floor(self):
        self._check("vector_only")

    def test_hybrid_meets_its_floor(self):
        self._check("hybrid")

    def test_hybrid_with_rerank_meets_its_floor(self):
        self._check("hybrid+rerank")


class TestRetrievalIsDeterministic(unittest.TestCase):
    """Retrieval must be reproducible, or no metric in this repository means anything.

    The evaluation reports numbers to four decimals and compares runs across commits. That is only
    meaningful if the same corpus and the same question always produce the same ranking.
    """

    @classmethod
    def setUpClass(cls):
        cls.cases = load_cases()

    def test_two_builds_produce_identical_vectors(self):
        first = build_pipeline(**CONFIGS["hybrid"])
        second = build_pipeline(**CONFIGS["hybrid"])
        self.assertEqual(len(first.vectors), len(second.vectors))
        for index, (left, right) in enumerate(zip(first.vectors, second.vectors)):
            self.assertEqual(left, right, "vector %d differs between two builds" % index)

    def test_the_same_query_ranks_the_same_after_a_rebuild(self):
        first = build_pipeline(**CONFIGS["hybrid"])
        second = build_pipeline(**CONFIGS["hybrid"])
        for case in self.cases:
            left = first.retrieve(case["query"])
            right = second.retrieve(case["query"])
            self.assertEqual([r.chunk_id for r in left], [r.chunk_id for r in right],
                             "ranking changed between builds for: %s" % case["query"])
            self.assertEqual([r.fused_score for r in left], [r.fused_score for r in right],
                             "scores changed between builds for: %s" % case["query"])

    def test_scoring_the_same_set_twice_gives_the_same_numbers(self):
        pipeline = build_pipeline(**CONFIGS["hybrid"])
        self.assertEqual(score(pipeline, self.cases), score(pipeline, self.cases))


if __name__ == "__main__":
    unittest.main()
