"""The real models, exercised by CI with ordinal assertions (R21).

The gate pins the deterministic fixture so its published numbers are exactly reproducible. That is
correct for the numbers and useless for the integration: it never touches BGE-M3, so a broken
endpoint, a changed response shape or a dead reranker would leave every gate green forever.

This test is the counterweight. Its sharpest assertion is the cross-lingual one: the similarity
between a **Chinese** question and the **English** leave policy must beat the similarity to an
unrelated English document by a margin. That is not a float threshold tuned to a runner - it is the
difference between "the model understands both languages" and "the vectors are unrelated noise", and
hashing embeddings score ~0 on both sides, so the margin collapses to ~0 and the test fails. Measured
locally: BGE-M3 gives ~0.5 versus ~0.02; CRC32 hashing gives ~0.0 versus ~0.0.

Two details make the job honest:

* `conftest.py` pins the offline provider for every pytest run, which is what kept CI blind to the
  real lane in the first place - this module pops those pins explicitly, and only here;
* `RAGSERVE_REQUIRE_REAL_MODELS=1` turns "models missing" into a failure instead of a skip, so the
  dedicated job cannot go green by not testing anything.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import tempfile
import unittest
import urllib.request

from ragserve.api import ApiServer
from ragserve.cli import REPO_ROOT
from ragserve.cli import setup as setup_mod

REQUIRE = os.environ.get("RAGSERVE_REQUIRE_REAL_MODELS") == "1"
QUESTION_ZH = "\u5458\u5de5\u6bcf\u5e74\u6709\u591a\u5c11\u5929\u5e74\u5047\uff1f"
LEAVE = ("Employees receive fifteen days of paid time off each year. "
         "Unused days may be carried over once, up to five.")
DISTRACTORS = {
    "datacentre-policy.txt": "The datacentre procurement policy covers server racks and cooling.",
    "travel-policy.txt": "Travel expenses are reimbursed within thirty days of the trip.",
    "incident-runbook.txt": "Sev-1 incidents are acknowledged within five minutes.",
    "api-reference.txt": "The ingestion endpoint accepts documents up to twelve megabytes.",
    "storage-layout.txt": "Cold storage keeps immutable audit logs for three hundred days.",
    "onboarding.txt": "New joiners complete security training in their first two weeks.",
}
# Measured on the shipped models, and deliberately above what a hashing backend can reach.
# BGE-M3: relevant 0.674, unrelated 0.384, margin +0.290. CRC32 hashing: relevant 0.085,
# unrelated 0.000, margin +0.085 - so both bars below fail for the fixture and pass for the model
# with ~20% headroom. A model swap may need these revisited; that is what a contract is for.
MIN_RELEVANT_SIMILARITY = 0.55
MIN_CROSS_LINGUAL_MARGIN = 0.15


def _embed(endpoint: str, model: str, text: str):
    body = json.dumps({"model": model, "input": text}).encode("utf-8")
    request = urllib.request.Request(endpoint.rstrip("/") + "/embeddings", data=body,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload["data"][0]["embedding"]


def _cosine(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


class RealModelContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not REQUIRE and not (setup_mod._listening(8011) and setup_mod._listening(8012)):
            raise unittest.SkipTest(
                "real-model contract runs in its own job; set RAGSERVE_REQUIRE_REAL_MODELS=1")

        # conftest.py pins the offline provider for every pytest run. Undo it here, or this module
        # would test the fixture it is supposed to be the counterweight to.
        os.environ.pop("RAGSERVE_EMBEDDING_PROVIDER", None)
        os.environ.pop("RAGSERVE_RERANKER_PROVIDER", None)

        if REQUIRE:
            for _name, weight, _port, _extra in setup_mod.SERVERS:
                if not os.path.isfile(os.path.join(setup_mod.MODELS, weight)):
                    raise AssertionError(
                        "RAGSERVE_REQUIRE_REAL_MODELS=1 but %s is missing - the contract job must "
                        "install the models rather than pass by not testing" % weight)
        cls.started = setup_mod.start_servers()

        cls.tmp = tempfile.mkdtemp(prefix="real-contract-")
        with open(os.path.join(cls.tmp, "leave-policy.txt"), "w", encoding="utf-8") as fh:
            fh.write(LEAVE + "\n")
        for name, text in DISTRACTORS.items():
            with open(os.path.join(cls.tmp, name), "w", encoding="utf-8") as fh:
                fh.write(text + "\n")
        cls.server = ApiServer(REPO_ROOT, host="127.0.0.1", port=0, corpus_dir=cls.tmp)

    @classmethod
    def tearDownClass(cls):
        setup_mod.stop_servers(getattr(cls, "started", []))
        shutil.rmtree(getattr(cls, "tmp", ""), ignore_errors=True)

    def test_the_shipped_config_is_model_backed(self):
        """A silently degraded config is how the real lane rots without anyone noticing."""
        config = self.server.retrieval_config
        self.assertNotEqual(config.embedding_provider, "deterministic",
                            "the shipped config must ask for the real embedding model")
        self.assertFalse(config.degraded_embedding,
                         "the embedding server was unreachable: %s" % config.degraded_embedding)
        self.assertFalse(config.degraded_reranker,
                         "the reranker server was unreachable: %s" % config.degraded_reranker)

    def test_the_embedding_endpoint_answers_at_the_configured_dimension_and_is_stable(self):
        config = self.server.retrieval_config
        first = _embed(config.embedding_endpoint, config.embedding_model, LEAVE)
        second = _embed(config.embedding_endpoint, config.embedding_model, LEAVE)
        self.assertEqual(len(first), config.vector_dim,
                         "the endpoint answered %d dimensions, the config says %d"
                         % (len(first), config.vector_dim))
        self.assertGreaterEqual(_cosine(first, second), 0.999,
                                "the same text embedded twice must not drift")

    def test_the_embedding_is_cross_lingual(self):
        """Chinese question, English answer. Hashing cannot fake this; SIMD cannot flip it."""
        config = self.server.retrieval_config
        query = _embed(config.embedding_endpoint, config.embedding_model, QUESTION_ZH)
        relevant = _embed(config.embedding_endpoint, config.embedding_model, LEAVE)
        unrelated = _embed(config.embedding_endpoint, config.embedding_model,
                           DISTRACTORS["datacentre-policy.txt"])
        relevant_score = _cosine(query, relevant)
        unrelated_score = _cosine(query, unrelated)
        margin = relevant_score - unrelated_score
        self.assertGreater(
            relevant_score, MIN_RELEVANT_SIMILARITY,
            "a Chinese annual-leave question must sit close to the English leave policy (>= %.2f), "
            "got %.3f - hashing embeddings score ~0.09 here" % (MIN_RELEVANT_SIMILARITY,
                                                                relevant_score))
        self.assertGreater(
            margin, MIN_CROSS_LINGUAL_MARGIN,
            "and it must be closer to the leave policy than to an unrelated document by >= %.2f, "
            "got %.3f (relevant %.3f, unrelated %.3f)"
            % (MIN_CROSS_LINGUAL_MARGIN, margin, relevant_score, unrelated_score))

    def test_a_chinese_question_retrieves_the_english_policy_first(self):
        result = self.server.ask({"question": QUESTION_ZH})
        self.assertNotIn("error", result, "the service refused to answer: %r" % result)
        retrieved = [item["doc_id"] for item in result["retrieved"]]
        self.assertTrue(retrieved, "nothing was retrieved at all")
        self.assertIn("leave", retrieved[0],
                      "the Chinese question must rank the English leave policy first, got %r"
                      % retrieved[:3])


if __name__ == "__main__":
    unittest.main()
