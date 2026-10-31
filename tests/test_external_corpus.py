"""A reviewer may bring their own documents.

The built-in corpus is synthetic, which is what makes the published numbers reproducible - but the
brief describes an internal knowledge base a reviewer plausibly owns, so `--corpus <dir>` must work
and must be measured, not assumed.

Two honesty properties are enforced here:

* files that cannot be turned into text are **reported** as skipped, never silently dropped;
* the labelled evaluation is **not** run against a user corpus, because its cases name synthetic
  documents and would produce numbers that look measured but are not.
"""
from __future__ import annotations

import os
import tempfile
import unittest
import zlib

from ragserve.api import ApiServer
from ragserve.corpus.builder import CorpusConfig, build_corpus, build_corpus_from_directory
from ragserve.corpus.loader import extract_pdf_text, load_documents
from ragserve.evaluation.corpus_report import measure_corpus, self_label_cases
from ragserve.retrieval.pipeline import RetrievalConfig
from ragserve.service import GenerationConfig

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE_CORPUS = os.path.join(os.path.dirname(__file__), "data", "external-corpus")


def make_pdf(text: bytes) -> bytes:
    """A minimal PDF whose content stream is Flate-compressed - the normal real-world shape."""
    stream = zlib.compress(b"BT /F1 24 Tf 72 700 Td (" + text + b") Tj ET")
    return (b"%PDF-1.4\n"
            b"4 0 obj\n<< /Length " + str(len(stream)).encode() + b" /Filter /FlateDecode >>\n"
            b"stream\n" + stream + b"\nendstream\nendobj\n")


class TestDirectoryLoader(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = build_corpus_from_directory(
            FIXTURE_CORPUS, CorpusConfig.from_json(
                os.path.join(REPO_ROOT, "configs", "corpus.json")))

    def test_documents_are_indexed_from_the_directory(self):
        ids = {doc.doc_id for doc in self.corpus.documents}
        self.assertIn("handbook-en.txt", ids)
        self.assertIn("handbook-zh.md", ids)

    def test_language_is_detected_per_document(self):
        by_id = {doc.doc_id: doc.language for doc in self.corpus.documents}
        self.assertEqual(by_id["handbook-en.txt"], "en")
        self.assertEqual(by_id["handbook-zh.md"], "zh",
                         "a Chinese document labelled 'en' would be penalised at query time")

    def test_chunks_carry_everything_the_pipeline_reads(self):
        for chunk in self.corpus.chunks:
            for field in ("chunk_id", "doc_id", "family", "language", "section", "text", "ocr"):
                self.assertTrue(hasattr(chunk, field), "chunk missing %s" % field)

    def test_unsupported_files_are_reported_not_dropped(self):
        skipped = {item["file"]: item["reason"] for item in self.corpus.manifest["skipped_files"]}
        self.assertIn("diagram.png.bin", skipped)

    def test_the_corpus_version_differs_from_the_synthetic_one(self):
        synthetic = build_corpus(CorpusConfig.from_json(
            os.path.join(REPO_ROOT, "configs", "corpus.json")))
        self.assertNotEqual(self.corpus.manifest["corpus_version"],
                            synthetic.manifest["corpus_version"])

    def test_pdf_text_is_extracted_with_the_standard_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "spec.pdf")
            with open(path, "wb") as fh:
                fh.write(make_pdf(b"Max payload 32 MB, retry three times"))
            self.assertIn("Max payload", extract_pdf_text(path))

    def test_a_pdf_without_text_is_reported_as_scanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "scanned.pdf")
            with open(path, "wb") as fh:
                fh.write(make_pdf(b"   "))  # whitespace: no glyphs to extract
            documents, skipped = load_documents(tmp)
            self.assertEqual(documents, [], "a textless PDF must not be indexed as empty")
            self.assertTrue(any("scanned" in item["reason"] for item in skipped))


class TestExternalCorpusService(unittest.TestCase):
    def test_the_service_can_serve_a_supplied_directory(self):
        external = ApiServer(REPO_ROOT, host="127.0.0.1", port=0, corpus_dir=FIXTURE_CORPUS)
        default = ApiServer(REPO_ROOT, host="127.0.0.1", port=0)
        self.assertNotEqual(external.health()["corpus_version"],
                            default.health()["corpus_version"])
        result = external.service.answer(
            "How many days of annual leave do full-time employees accrue?")
        retrieved = {chunk.doc_id for chunk in result.retrieved}
        self.assertTrue(retrieved & {"handbook-en.txt"},
                        "the supplied document was not retrieved: %s" % sorted(retrieved))


class TestCorpusReport(unittest.TestCase):
    """A corpus without labels still gets a measured report - but an honest one."""

    @classmethod
    def setUpClass(cls):
        cls.corpus = build_corpus_from_directory(
            FIXTURE_CORPUS, CorpusConfig.from_json(
                os.path.join(REPO_ROOT, "configs", "corpus.json")))
        retrieval = RetrievalConfig.from_json(
            os.path.join(REPO_ROOT, "configs", "retrieval.json"))
        retrieval.embedding_provider = "deterministic"
        retrieval.reranker_provider = "deterministic"
        cls.report = measure_corpus(
            cls.corpus, retrieval,
            GenerationConfig.from_json(os.path.join(REPO_ROOT, "configs", "generation.json")))

    def test_cases_are_derived_from_the_corpus_itself(self):
        cases = self_label_cases(self.corpus)
        self.assertTrue(cases)
        for case in cases:
            self.assertTrue(case["query"])
            self.assertIn(case["expected_doc_id"],
                          {doc.doc_id for doc in self.corpus.documents})

    def test_retrieval_is_measured_not_assumed(self):
        self.assertEqual(self.report["recall@5"], 1.0,
                         "self-labelled queries should retrieve their own document")
        self.assertGreaterEqual(self.report["mrr"], 0.9)

    def test_the_report_states_its_own_limitation(self):
        self.assertIn("self-labelled", self.report["provenance_note"])
        self.assertIn("human-judged", self.report["provenance_note"])

    def test_skipped_files_appear_in_the_report(self):
        self.assertTrue(self.report["skipped_files"])


if __name__ == "__main__":
    unittest.main()
