"""EPIC #5 / SUB 23, 24: cache layers, TTL, invalidation, poisoning guards."""
from __future__ import annotations

import os
import unittest

from ragserve.cache import ResponseCache
from ragserve.corpus.builder import CorpusConfig, build_corpus
from ragserve.observability.events import EventLog, StructuredLogger
from ragserve.retrieval.pipeline import RetrievalConfig
from ragserve.service import GenerationConfig, RagService

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class FakeClock:
    def __init__(self, start: float = 1000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def make_service(cache=None, logger=None):
    corpus = build_corpus(CorpusConfig.from_json(os.path.join(ROOT, "configs", "corpus.json")))
    return RagService(corpus,
                      RetrievalConfig.from_json(os.path.join(ROOT, "configs", "retrieval.json")),
                      GenerationConfig.from_json(os.path.join(ROOT, "configs", "generation.json")),
                      logger=logger, cache=cache)


class TestCacheLayers(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.cache = ResponseCache(exact_ttl=300, semantic_ttl=60, clock=self.clock)

    def test_exact_hit_on_repeat(self):
        key = ("annual leave days", "hybrid", True, "cv1", "stub-1")
        self.cache.put(query="annual leave days", retrieval_mode="hybrid", rerank=True,
                        corpus_version="cv1", model_version="stub-1", payload={"answer": "15 days"})
        hit = self.cache.get(query="annual leave days", retrieval_mode="hybrid", rerank=True,
                             corpus_version="cv1", model_version="stub-1")
        self.assertIsNotNone(hit)
        self.assertEqual(hit["payload"]["answer"], "15 days")
        self.assertEqual(hit["layer"], "exact")

    def test_semantic_hit_for_paraphrase(self):
        self.cache.put(query="how many annual leave days", retrieval_mode="hybrid", rerank=True,
                        corpus_version="cv1", model_version="stub-1", payload={"answer": "15"})
        hit = self.cache.get(query="annual leave days how many", retrieval_mode="hybrid",
                             rerank=True, corpus_version="cv1", model_version="stub-1")
        self.assertIsNotNone(hit)
        self.assertEqual(hit["layer"], "semantic")

    def test_ttl_expiry(self):
        self.cache.put(query="annual leave", retrieval_mode="hybrid", rerank=True,
                        corpus_version="cv1", model_version="stub-1", payload={"answer": "15"})
        self.clock.advance(301)
        self.assertIsNone(self.cache.get(query="annual leave", retrieval_mode="hybrid",
                                         rerank=True, corpus_version="cv1", model_version="stub-1"))

    def test_semantic_ttl_is_shorter(self):
        self.cache.put(query="annual leave entitlement days", retrieval_mode="hybrid",
                        rerank=True, corpus_version="cv1", model_version="stub-1",
                        payload={"answer": "15"})
        self.clock.advance(61)
        self.assertIsNone(self.cache.get(query="annual leave days entitlement",
                                         retrieval_mode="hybrid", rerank=True,
                                         corpus_version="cv1", model_version="stub-1"))

    def test_hit_rate_accounting(self):
        for _ in range(3):
            self.cache.get(query="unknown query", retrieval_mode="hybrid", rerank=True,
                           corpus_version="cv1", model_version="stub-1")
        self.assertEqual(self.cache.stats["lookups"], 3)
        self.assertEqual(self.cache.stats["hits"], 0)
        self.assertEqual(self.cache.hit_rate, 0.0)
        self.cache.put(query="known", retrieval_mode="hybrid", rerank=True,
                       corpus_version="cv1", model_version="stub-1", payload={})
        self.cache.get(query="known", retrieval_mode="hybrid", rerank=True,
                       corpus_version="cv1", model_version="stub-1")
        self.assertEqual(self.cache.stats["hits"], 1)
        self.assertAlmostEqual(self.cache.hit_rate, 0.25, places=4)


class TestCachePoisoningGuards(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.cache = ResponseCache(exact_ttl=300, semantic_ttl=60, clock=self.clock)

    def test_corpus_version_change_invalidates(self):
        self.cache.put(query="annual leave", retrieval_mode="hybrid", rerank=True,
                        corpus_version="cv1", model_version="stub-1", payload={"answer": "old"})
        self.assertIsNone(self.cache.get(query="annual leave", retrieval_mode="hybrid",
                                         rerank=True, corpus_version="cv2",
                                         model_version="stub-1"))

    def test_config_change_invalidates(self):
        self.cache.put(query="annual leave", retrieval_mode="hybrid", rerank=True,
                        corpus_version="cv1", model_version="stub-1", payload={"answer": "old"})
        self.assertIsNone(self.cache.get(query="annual leave", retrieval_mode="vector_only",
                                         rerank=True, corpus_version="cv1",
                                         model_version="stub-1"))

    def test_refusals_are_not_cached(self):
        service = make_service(cache=self.cache)
        first = service.answer("zzqqx wvbn kkk")
        self.assertTrue(first.answer.refused)
        self.assertEqual(self.cache.stats["stores"], 0,
                         "a refusal must never be cached - it would poison later answers")

    def test_cache_hit_is_visible_in_trace_and_log(self):
        events = EventLog()
        logger = StructuredLogger(sink=events.append, clock=self.clock)
        service = make_service(cache=self.cache, logger=logger)
        service.answer("How many days of annual leave?", workflow_id="wf-a")
        service.answer("How many days of annual leave?", workflow_id="wf-b")
        second_lines = [line for line in events.lines() if '"wf-b"' in line]
        self.assertTrue(any("cache_hit" in line for line in second_lines))
        self.assertTrue(service.last_trace.get("cache_hit"))

    def test_cached_answer_keeps_citations(self):
        service = make_service(cache=self.cache)
        first = service.answer("How many days of annual leave?")
        second = service.answer("How many days of annual leave?")
        self.assertTrue(second.answer.citations)
        self.assertEqual(first.answer.citations, second.answer.citations)
        self.assertEqual(first.answer.text, second.answer.text)


if __name__ == "__main__":
    unittest.main()
