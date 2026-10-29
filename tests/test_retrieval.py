"""EPIC #3 / SUB 14-16: retrieval modes, fusion, config-driven reranker toggle."""
from __future__ import annotations

import json
import os
import unittest

from ragserve.corpus.builder import CorpusConfig, build_corpus
from ragserve.retrieval.pipeline import RetrievalConfig, RetrievalPipeline

CASES_PATH = os.path.join(os.path.dirname(__file__), "data", "retrieval_cases.json")
RETRIEVAL_CONFIG = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                "configs", "retrieval.json")


def load_cases():
    with open(CASES_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def make_pipeline(**overrides) -> RetrievalPipeline:
    config = RetrievalConfig.from_json(RETRIEVAL_CONFIG)
    for key, value in overrides.items():
        setattr(config, key, value)
    return RetrievalPipeline(build_corpus(CorpusConfig.from_json(corpus_config_path())), config)


def corpus_config_path() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "configs", "corpus.json")


def top_doc_ids(pipeline: RetrievalPipeline, query: str):
    return [r.doc_id for r in pipeline.retrieve(query)]


def recall_at_k(pipeline: RetrievalPipeline, cases) -> float:
    hits = 0
    for case in cases:
        if case["expected_doc_id"] in top_doc_ids(pipeline, case["query"]):
            hits += 1
    return hits / len(cases)


class TestVectorRetrieval(unittest.TestCase):
    def setUp(self):
        self.pipeline = make_pipeline(mode="vector_only", rerank_enabled=False)

    def test_returns_results(self):
        results = self.pipeline.retrieve("annual leave entitlement")
        self.assertTrue(results)
        self.assertLessEqual(len(results), self.pipeline.config.top_k)

    def test_top_k_is_respected(self):
        for k in (1, 3, 5):
            pipeline = make_pipeline(mode="vector_only", rerank_enabled=False, top_k=k)
            self.assertLessEqual(len(pipeline.retrieve("annual leave")), k)

    def test_ranking_is_deterministic(self):
        first = [r.chunk_id for r in self.pipeline.retrieve("annual leave entitlement")]
        second = [r.chunk_id for r in make_pipeline(mode="vector_only",
                                                    rerank_enabled=False).retrieve("annual leave entitlement")]
        self.assertEqual(first, second)

    def test_language_isolation(self):
        for case in load_cases():
            results = self.pipeline.retrieve(case["query"])
            self.assertEqual(results[0].language, case["language"],
                             "query language %s, top hit %s" % (case["language"], results[0].language))


class TestHybridAndFusion(unittest.TestCase):
    def setUp(self):
        self.cases = load_cases()

    def test_hybrid_recall_at_least_vector_only(self):
        vector = recall_at_k(make_pipeline(mode="vector_only", rerank_enabled=False), self.cases)
        hybrid = recall_at_k(make_pipeline(mode="hybrid", rerank_enabled=False), self.cases)
        self.assertGreaterEqual(hybrid, vector)

    def test_lexical_path_finds_exact_terms(self):
        """Dense retrieval alone loses exact tokens like status codes; BM25 must not.

        Asserts on the *term*, not on a document id: the corpus grows and reorders, and a test
        that pins an id breaks on content changes rather than on retrieval failures.
        """
        pipeline = make_pipeline(mode="hybrid", rerank_enabled=False)
        results = pipeline.retrieve("429 Retry-After queue depth")
        self.assertTrue(results)
        self.assertIn("429", " ".join(r.text for r in results))

    def test_score_provenance_per_mode(self):
        vector = make_pipeline(mode="vector_only", rerank_enabled=False).retrieve("annual leave")
        self.assertIsNotNone(vector[0].vector_score)
        self.assertIsNone(vector[0].lexical_score)
        hybrid = make_pipeline(mode="hybrid", rerank_enabled=False).retrieve("annual leave")
        self.assertIsNotNone(hybrid[0].vector_score)
        self.assertIsNotNone(hybrid[0].lexical_score)

    def test_modes_are_selected_by_config_not_code(self):
        """The requirement is explicit: switching mode must not require a code change."""
        on_disk = RetrievalConfig.from_json(RETRIEVAL_CONFIG)
        self.assertIn(on_disk.mode, ("vector_only", "hybrid"))
        pipeline = RetrievalPipeline(build_corpus(CorpusConfig.from_json(corpus_config_path())),
                                     on_disk)
        self.assertTrue(pipeline.retrieve("annual leave"))


class TestRerankerToggle(unittest.TestCase):
    def setUp(self):
        self.cases = load_cases()

    def test_reranker_respects_top_k(self):
        """Reranking reorders candidates; it must not change how many come back."""
        for k in (1, 3, 5):
            on = make_pipeline(mode="hybrid", rerank_enabled=True, top_k=k)
            self.assertLessEqual(len(on.retrieve("annual leave")), k)

    def test_rerank_scores_present_only_when_enabled(self):
        off = make_pipeline(mode="hybrid", rerank_enabled=False)
        on = make_pipeline(mode="hybrid", rerank_enabled=True)
        self.assertTrue(all(r.rerank_score is None for r in off.retrieve("annual leave")))
        self.assertTrue(all(r.rerank_score is not None for r in on.retrieve("annual leave")))

    def test_toggling_changes_ranking_on_at_least_one_case(self):
        off = make_pipeline(mode="hybrid", rerank_enabled=False)
        on = make_pipeline(mode="hybrid", rerank_enabled=True)
        changed = 0
        for case in self.cases:
            if [r.chunk_id for r in off.retrieve(case["query"])] != \
               [r.chunk_id for r in on.retrieve(case["query"])]:
                changed += 1
        self.assertGreater(changed, 0, "reranker changed nothing on any labelled case")

    def test_reranker_does_not_reduce_recall(self):
        off = recall_at_k(make_pipeline(mode="hybrid", rerank_enabled=False), self.cases)
        on = recall_at_k(make_pipeline(mode="hybrid", rerank_enabled=True), self.cases)
        self.assertGreaterEqual(on, off)


if __name__ == "__main__":
    unittest.main()
