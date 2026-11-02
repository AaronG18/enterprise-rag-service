"""Identical concurrent questions share one computation (issue #133).

Measured before this: five identical requests arriving together all missed an empty cache and then
queued behind the single-slot model server - 14.1 s p50 on a question the service had just answered,
so the brief's ">= 5 concurrent" target failed while the deterministic gate reported 78 ms.

The assertion is exact rather than timing-based, so it cannot flake: of five simultaneous identical
questions exactly one computes and the other four are cache hits. Timing is not asserted - that
belongs to the benchmark, not to a unit test.
"""
from __future__ import annotations

import os
import threading
import unittest

from ragserve.cache import ResponseCache
from ragserve.corpus.builder import CorpusConfig, build_corpus
from ragserve.retrieval.pipeline import RetrievalConfig
from ragserve.service import GenerationConfig, RagService

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUESTION = "How many days of annual leave do full-time employees accrue?"


def make_service() -> RagService:
    corpus = build_corpus(CorpusConfig.from_json(os.path.join(ROOT, "configs", "corpus.json")))
    retrieval = RetrievalConfig.from_json(os.path.join(ROOT, "configs", "retrieval.json"))
    generation = GenerationConfig.from_json(os.path.join(ROOT, "configs", "generation.json"))
    return RagService(corpus, retrieval, generation, cache=ResponseCache())


class SingleFlightTest(unittest.TestCase):
    def test_five_identical_concurrent_questions_compute_once(self):
        service = make_service()
        results = []
        errors = []
        barrier = threading.Barrier(5)

        def ask():
            try:
                barrier.wait(timeout=30)  # release all five together, like a real burst
                results.append(service.answer(QUESTION))
            except Exception as exc:  # noqa: BLE001 - surfaced as a test failure below
                errors.append(exc)

        threads = [threading.Thread(target=ask) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=120)

        self.assertEqual(errors, [], "a concurrent request raised: %r" % errors)
        self.assertEqual(len(results), 5)
        computed = [r for r in results if not r.trace.get("cache_hit")]
        self.assertEqual(len(computed), 1,
                         "exactly one of five identical concurrent questions should compute, "
                         "got %d computations" % len(computed))
        for result in results:
            self.assertFalse(result.answer.refused)
            self.assertTrue(result.answer.citations)

    def test_a_second_call_hits_the_cache(self):
        """The guard must not break the ordinary repeat case."""
        service = make_service()
        first = service.answer(QUESTION)
        second = service.answer(QUESTION)
        self.assertFalse(first.trace.get("cache_hit"))
        self.assertTrue(second.trace.get("cache_hit"))

    def test_the_guard_does_not_serialise_different_questions(self):
        """A different question must compute, not wait for, the first one."""
        service = make_service()
        service.answer(QUESTION)
        other = service.answer("What is the p95 latency target?")
        self.assertFalse(other.trace.get("cache_hit"))


if __name__ == "__main__":
    unittest.main()
