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
)
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
    """The shipped configuration must run with no credentials at all: a reviewer clones the
    repository and starts the service or runs the evaluation without setting any key. A real
    embedding model is opt-in (config change only), never the keyless default."""

    def _clear_override(self):
        return os.environ.pop("RAGSERVE_EMBEDDING_PROVIDER", None)

    def _restore(self, saved):
        if saved is not None:
            os.environ["RAGSERVE_EMBEDDING_PROVIDER"] = saved

    def test_shipped_config_defaults_to_keyless_backend(self):
        saved = self._clear_override()
        try:
            cfg = RetrievalConfig.from_json(RETRIEVAL_CONFIG)
            self.assertEqual(cfg.embedding_provider, "deterministic")
            self.assertEqual(cfg.vector_dim, 512)
            self.assertIsInstance(build_embedder(cfg), HashingEmbeddings)
        finally:
            self._restore(saved)

    def test_index_builds_without_any_credential(self):
        saved = self._clear_override()
        try:
            cfg = RetrievalConfig.from_json(RETRIEVAL_CONFIG)
            corpus = build_corpus(CorpusConfig.from_json(CORPUS_CONFIG))
            pipeline = RetrievalPipeline(corpus, cfg)  # must not raise ProviderUnavailable
            self.assertEqual(len(pipeline.vectors), len(corpus.chunks))
            self.assertEqual(len(pipeline.vectors[0]), 512)
        finally:
            self._restore(saved)

    def test_real_model_preset_is_opt_in_and_wired(self):
        saved = self._clear_override()
        try:
            cfg = RetrievalConfig.from_json(RETRIEVAL_CONFIG)
            cfg.embedding_provider = "openai-compatible"
            emb = build_embedder(cfg)
            self.assertIsInstance(emb, OpenAICompatibleEmbeddings)
            self.assertEqual(emb.model, "BAAI/bge-m3")
            self.assertEqual(emb.api_key_env, "SILICONFLOW_API_KEY")
        finally:
            self._restore(saved)


if __name__ == "__main__":
    unittest.main()
