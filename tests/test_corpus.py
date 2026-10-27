"""EPIC #2 / SUB 11-12: corpus generation, determinism, versioning, OCR subset."""
from __future__ import annotations

import json
import os
import tempfile
import unittest

from ragserve.corpus.builder import CorpusConfig, build_corpus, write_artifacts
from ragserve.corpus.model import chunk_to_dict, document_to_dict

FAMILIES = {"handbook", "compliance", "techspec", "architecture"}
LANGUAGES = {"en", "zh"}


def _dump(documents) -> str:
    return json.dumps([document_to_dict(d) for d in documents], sort_keys=True, ensure_ascii=False)


class TestCorpusGeneration(unittest.TestCase):
    def test_build_is_deterministic(self):
        """Same config -> identical documents and identical corpus_version (RULES R3: deterministic)."""
        a = build_corpus(CorpusConfig())
        b = build_corpus(CorpusConfig())
        self.assertEqual(_dump(a.documents), _dump(b.documents))
        self.assertEqual(a.manifest["corpus_version"], b.manifest["corpus_version"])

    def test_seed_changes_corpus_version(self):
        base = build_corpus(CorpusConfig(seed=1))
        other = build_corpus(CorpusConfig(seed=2))
        self.assertNotEqual(base.manifest["corpus_version"], other.manifest["corpus_version"])

    def test_all_families_and_languages_present(self):
        corpus = build_corpus(CorpusConfig())
        self.assertEqual({d.family for d in corpus.documents}, FAMILIES)
        self.assertEqual({d.language for d in corpus.documents}, LANGUAGES)

    def test_manifest_counts_are_consistent(self):
        corpus = build_corpus(CorpusConfig())
        manifest = corpus.manifest
        self.assertEqual(manifest["doc_count"], len(corpus.documents))
        self.assertEqual(manifest["chunk_count"], len(corpus.chunks))
        self.assertEqual(sum(manifest["per_family"].values()), len(corpus.documents))
        self.assertEqual(manifest["ocr_doc_count"], len([d for d in corpus.documents if d.ocr]))

    def test_documents_have_content_in_both_languages(self):
        corpus = build_corpus(CorpusConfig())
        for doc in corpus.documents:
            self.assertTrue(doc.title.strip(), "empty title: %s" % doc.doc_id)
            self.assertTrue(doc.sections, "no sections: %s" % doc.doc_id)
            for section in doc.sections:
                self.assertTrue(section.body.strip(), "empty section in %s" % doc.doc_id)


class TestOcrSubset(unittest.TestCase):
    def test_ocr_ratio_matches_configuration(self):
        cfg = CorpusConfig()
        corpus = build_corpus(cfg)
        ratio = manifest_ocr_ratio(corpus)
        self.assertGreaterEqual(len([d for d in corpus.documents if d.ocr]), 1)
        self.assertLess(abs(ratio - cfg.ocr_ratio), 0.03,
                        "ocr ratio %s too far from %s" % (ratio, cfg.ocr_ratio))

    def test_ocr_text_differs_from_clean_original(self):
        corpus = build_corpus(CorpusConfig())
        flagged = [d for d in corpus.documents if d.ocr]
        self.assertTrue(flagged, "no OCR-flagged document")
        for doc in flagged:
            changed = [s for s in doc.sections if s.body != s.clean_body]
            self.assertTrue(changed, "OCR doc unchanged: %s" % doc.doc_id)

    def test_clean_documents_keep_original_text(self):
        corpus = build_corpus(CorpusConfig())
        for doc in corpus.documents:
            if not doc.ocr:
                for section in doc.sections:
                    self.assertEqual(section.body, section.clean_body)


class TestArtifactWriter(unittest.TestCase):
    def test_artifacts_are_written_and_reloadable(self):
        corpus = build_corpus(CorpusConfig())
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_artifacts(corpus, tmp)
            for key in ("documents", "chunks", "manifest"):
                self.assertTrue(os.path.isfile(paths[key]), "missing artifact: %s" % key)
            with open(paths["documents"], "r", encoding="utf-8") as fh:
                rows = [json.loads(line) for line in fh if line.strip()]
            self.assertEqual(len(rows), len(corpus.documents))
            with open(paths["chunks"], "r", encoding="utf-8") as fh:
                chunk_rows = [json.loads(line) for line in fh if line.strip()]
            self.assertEqual(len(chunk_rows), len(corpus.chunks))
            self.assertEqual([r["chunk_id"] for r in chunk_rows],
                             sorted(r["chunk_id"] for r in chunk_rows))

    def test_chunk_ids_are_stable_across_builds(self):
        a = build_corpus(CorpusConfig())
        b = build_corpus(CorpusConfig())
        self.assertEqual([c.chunk_id for c in a.chunks], [c.chunk_id for c in b.chunks])


def manifest_ocr_ratio(corpus) -> float:
    total = len(corpus.documents)
    return 0.0 if total == 0 else len([d for d in corpus.documents if d.ocr]) / total


if __name__ == "__main__":
    unittest.main()
