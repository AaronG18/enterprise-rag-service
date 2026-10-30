import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from ragserve.retrieval.embeddings import (  # noqa: E402
    HashingEmbeddings,
    OpenAICompatibleEmbeddings,
    ProviderUnavailable,
    cosine,
)
from ragserve.retrieval.pipeline import (  # noqa: E402
    RetrievalConfig,
    RetrievalPipeline,
    build_embedder,
    build_reranker,
)
from ragserve.retrieval.rerank import DeterministicReranker  # noqa: E402
from ragserve.corpus.builder import CorpusConfig, build_corpus  # noqa: E402

RETRIEVAL_CONFIG = os.path.join(ROOT, "configs", "retrieval.json")
CORPUS_CONFIG = os.path.join(ROOT, "configs", "corpus.json")


class TestDeterministicEmbeddings(unittest.TestCase):
    def test_dim_and_determinism(self):
        emb = HashingEmbeddings(dim=512, seed=1)
        self.assertEqual(len(emb.embed_text("same text")), 512)
        self.assertEqual(emb.embed_text("same text"), emb.embed_text("same text"))
        self.assertNotEqual(emb.embed_text("same text"), emb.embed_text("different text"))

    def test_cosine_in_range(self):
        emb = HashingEmbeddings(dim=512, seed=1)
        s = cosine(emb.embed_text("alpha"), emb.embed_text("beta"))
        self.assertGreaterEqual(s, -1.0)
        self.assertLessEqual(s, 1.0)


class TestOpenAICompatibleEmbeddings(unittest.TestCase):
    def test_requires_endpoint(self):
        with self.assertRaises(ProviderUnavailable):
            OpenAICompatibleEmbeddings(endpoint="", api_key_env="OPENAI_API_KEY")

    def test_raises_without_key_hermetic(self):
        # Must refuse on the missing credential without making any network call.
        saved = os.environ.pop("OPENAI_API_KEY", None)
        try:
            emb = OpenAICompatibleEmbeddings(
                endpoint="https://api.openai.com/v1", api_key_env="OPENAI_API_KEY")
            with self.assertRaises(ProviderUnavailable):
                emb.embed_text("hello")
        finally:
            if saved is not None:
                os.environ["OPENAI_API_KEY"] = saved


class TestProviderSelection(unittest.TestCase):
    def _with_env(self, value):
        old = os.environ.get("RAGSERVE_EMBEDDING_PROVIDER")
        if value is None:
            os.environ.pop("RAGSERVE_EMBEDDING_PROVIDER", None)
        else:
            os.environ["RAGSERVE_EMBEDDING_PROVIDER"] = value
        return old

    def test_env_override_pins_deterministic(self):
        old = self._with_env("deterministic")
        try:
            cfg = RetrievalConfig.from_json(RETRIEVAL_CONFIG)
            self.assertEqual(cfg.embedding_provider, "deterministic")
            self.assertEqual(cfg.vector_dim, 512)
            self.assertIsInstance(build_embedder(cfg), HashingEmbeddings)
        finally:
            self._with_env(old)

    def test_pipeline_picks_embedder_from_config(self):
        old = self._with_env("deterministic")
        try:
            cfg = RetrievalConfig.from_json(RETRIEVAL_CONFIG)
            corpus = build_corpus(CorpusConfig.from_json(CORPUS_CONFIG))
            pipe = RetrievalPipeline(corpus, cfg)
            self.assertIsInstance(pipe.embeddings, HashingEmbeddings)
        finally:
            self._with_env(old)


class TestKeylessDeliveryDefault(unittest.TestCase):
    """The shipped configuration must run with no credentials at all.

    The delivered default is now a real semantic model served locally, which is still keyless:
    `embedding_api_key_env` is empty, so no Authorization header is sent and no key is required.
    The deterministic backend remains the hermetic safety net, used when the local model server is
    not running - loudly, and never silently.
    """

    def _clear_override(self):
        return os.environ.pop("RAGSERVE_EMBEDDING_PROVIDER", None)

    def _restore(self, saved):
        if saved is not None:
            os.environ["RAGSERVE_EMBEDDING_PROVIDER"] = saved

    def test_shipped_config_uses_a_real_keyless_model(self):
        saved = self._clear_override()
        try:
            cfg = RetrievalConfig.from_json(RETRIEVAL_CONFIG)
            self.assertEqual(cfg.embedding_provider, "openai-compatible")
            self.assertEqual(cfg.embedding_model, "bge-m3")
            self.assertEqual(cfg.vector_dim, 1024)  # BGE-M3's width
            # Keyless: an empty api_key_env means "send no Authorization header at all".
            self.assertEqual(cfg.embedding_api_key_env, "")
            self.assertIn("127.0.0.1", cfg.embedding_endpoint)
        finally:
            self._restore(saved)

    def test_shipped_config_uses_a_cross_encoder_reranker(self):
        saved = self._clear_override()
        try:
            cfg = RetrievalConfig.from_json(RETRIEVAL_CONFIG)
            self.assertEqual(cfg.reranker_provider, "cross-encoder")
            self.assertIn("127.0.0.1", cfg.reranker_endpoint)
        finally:
            self._restore(saved)

    def test_index_builds_without_any_credential(self):
        """With no model server running this must still build - via the loud fallback, not by
        raising ProviderUnavailable."""
        saved = self._clear_override()
        try:
            cfg = RetrievalConfig.from_json(RETRIEVAL_CONFIG)
            corpus = build_corpus(CorpusConfig.from_json(CORPUS_CONFIG))
            pipeline = RetrievalPipeline(corpus, cfg)  # must not raise
            self.assertEqual(len(pipeline.vectors), len(corpus.chunks))
        finally:
            self._restore(saved)

    def test_unreachable_model_falls_back_and_is_marked_degraded(self):
        """A fallback must be visible: the config is flagged so a report cannot claim
        model-backed numbers that a model did not produce."""
        saved = self._clear_override()
        try:
            cfg = RetrievalConfig.from_json(RETRIEVAL_CONFIG)
            # A port nothing listens on: connection refused, not a slow timeout.
            cfg.embedding_endpoint = "http://127.0.0.1:1/v1"
            cfg.reranker_endpoint = "http://127.0.0.1:1/v1"
            emb = build_embedder(cfg)
            self.assertIsInstance(emb, HashingEmbeddings)
            self.assertTrue(cfg.degraded_embedding)
            self.assertIsInstance(build_reranker(cfg), DeterministicReranker)
            self.assertTrue(cfg.degraded_reranker)
        finally:
            self._restore(saved)

    def test_keyless_endpoint_sends_no_authorization_header(self):
        """A local server needs no credential. This is distinct from 'declared a key but it is
        unset', which must still fail loudly."""
        emb = OpenAICompatibleEmbeddings(endpoint="http://127.0.0.1:8011/v1",
                                         api_key_env="", model="bge-m3")
        self.assertFalse(emb.requires_key)
        self.assertIsNone(emb._api_key())

        hosted = OpenAICompatibleEmbeddings(endpoint="https://api.example.com/v1",
                                            api_key_env="A_KEY_THAT_IS_NOT_SET", model="m")
        self.assertTrue(hosted.requires_key)
        with self.assertRaises(ProviderUnavailable):
            hosted._api_key()


if __name__ == "__main__":
    unittest.main()
