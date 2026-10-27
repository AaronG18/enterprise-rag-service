"""EPIC #2 / SUB 13: chunking behaviour, metadata integrity, bilingual correctness."""
from __future__ import annotations

import unittest

from ragserve.corpus.builder import CorpusConfig, build_corpus


class TestChunkMetadata(unittest.TestCase):
    def setUp(self):
        self.corpus = build_corpus(CorpusConfig())

    def test_chunk_ids_unique(self):
        ids = [c.chunk_id for c in self.corpus.chunks]
        self.assertEqual(len(ids), len(set(ids)))

    def test_ordinals_consecutive_per_document(self):
        by_doc: dict[str, list[int]] = {}
        for chunk in self.corpus.chunks:
            by_doc.setdefault(chunk.doc_id, []).append(chunk.ordinal)
        for doc_id, ordinals in by_doc.items():
            self.assertEqual(ordinals, list(range(len(ordinals))), "bad ordinals for %s" % doc_id)

    def test_spans_inside_source_text_and_monotonic(self):
        docs = {d.doc_id: d for d in self.corpus.documents}
        for chunk in self.corpus.chunks:
            text = chunk.source_text
            self.assertGreaterEqual(chunk.start, 0)
            self.assertLess(chunk.start, chunk.end)
            self.assertLessEqual(chunk.end, len(text))
            self.assertEqual(chunk.text, text[chunk.start:chunk.end])
        per_doc: dict[str, list] = {}
        for chunk in self.corpus.chunks:
            per_doc.setdefault(chunk.doc_id, []).append(chunk)
        for doc_id, chunks in per_doc.items():
            # Emission order is document order: ordinals and starts both ascend.
            self.assertEqual(chunks, sorted(chunks, key=lambda c: c.ordinal))
            starts = [c.start for c in chunks]
            self.assertEqual(starts, sorted(starts), "spans not monotonic in %s" % doc_id)

    def test_no_empty_chunks_and_size_bound(self):
        cfg = CorpusConfig()
        for chunk in self.corpus.chunks:
            self.assertTrue(chunk.text.strip(), "empty chunk %s" % chunk.chunk_id)
            self.assertLessEqual(len(chunk.text), cfg.chunk_target_chars * 3)

    def test_metadata_propagates_from_document(self):
        docs = {d.doc_id: d for d in self.corpus.documents}
        for chunk in self.corpus.chunks:
            doc = docs[chunk.doc_id]
            self.assertEqual(chunk.family, doc.family)
            self.assertEqual(chunk.language, doc.language)
            self.assertEqual(chunk.ocr, doc.ocr)

    def test_ocr_flag_consistency_within_document(self):
        per_doc: dict[str, set] = {}
        for chunk in self.corpus.chunks:
            per_doc.setdefault(chunk.doc_id, set()).add(chunk.ocr)
        for doc_id, flags in per_doc.items():
            self.assertEqual(len(flags), 1, "mixed ocr flag in %s" % doc_id)


class TestBilingualChunking(unittest.TestCase):
    def setUp(self):
        self.corpus = build_corpus(CorpusConfig())

    def test_both_languages_produce_chunks(self):
        counts = {}
        for chunk in self.corpus.chunks:
            counts[chunk.language] = counts.get(chunk.language, 0) + 1
        self.assertGreater(counts.get("en", 0), 0)
        self.assertGreater(counts.get("zh", 0), 0)

    def test_chinese_text_is_not_dropped(self):
        """A whitespace-based splitter would produce one giant chunk or none for ZH."""
        zh = [c for c in self.corpus.chunks if c.language == "zh"]
        self.assertTrue(zh)
        for chunk in zh:
            self.assertTrue(any("\u4e00" <= ch <= "\u9fff" for ch in chunk.text),
                            "no CJK content in %s" % chunk.chunk_id)

    def test_overlap_between_consecutive_chunks(self):
        """Overlap is what keeps answers complete across chunk boundaries."""
        per_doc: dict[str, list] = {}
        for chunk in self.corpus.chunks:
            per_doc.setdefault(chunk.doc_id, []).append(chunk)
        checked = 0
        docs_with_multiple = 0
        for doc_id, chunks in per_doc.items():
            if len(chunks) > 1:
                docs_with_multiple += 1
            for prev, nxt in zip(chunks, chunks[1:]):
                self.assertGreater(prev.end, nxt.start,
                                   "no overlap between %s and %s" % (prev.chunk_id, nxt.chunk_id))
                checked += 1
        self.assertGreater(checked, 0, "no consecutive chunks found")
        self.assertGreater(docs_with_multiple, 0,
                           "no document produced more than one chunk; chunking did not happen")


if __name__ == "__main__":
    unittest.main()
