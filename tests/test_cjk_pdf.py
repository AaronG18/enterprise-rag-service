"""Bilingual PDF ingestion.

The brief's corpus is CN/EN and includes scanned PDFs, so "a few dozen mixed CN/EN PDFs" is the
realistic input. These tests use tiny generated PDFs (tests/data/cjk-pdf), so they are hermetic:
no download, no model server, no network.

The regression they exist for: a CJK PDF that subsets its font carries small CIDs (1, 2, 3...) and
a ToUnicode CMap that maps them back to characters. Decoding those CIDs as UTF-16BE produced
control characters instead of Chinese - and worse, scanned the CMap itself and indexed its own
literals ("Adobe", "UCS") as document text.
"""
from __future__ import annotations

import os
import unittest

from ragserve.corpus.loader import extract_pdf_text, load_documents

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "cjk-pdf")
CN = "员工手册"


def pdf(name: str) -> str:
    return os.path.join(FIXTURES, name)


def doc_text(doc) -> str:
    return "\n".join(s.body for s in doc.sections)


class CjkPdfExtractionTest(unittest.TestCase):
    def test_subset_font_with_tounicode_yields_chinese(self):
        """The realistic CJK case: subset CIDs plus a ToUnicode CMap."""
        text = extract_pdf_text(pdf("subset-cn.pdf"))
        self.assertIn(CN, text, "subset CIDs must be mapped through the ToUnicode CMap: %r" % text)

    def test_identity_font_yields_chinese(self):
        """Identity-H where the CID is itself the code point needs no CMap."""
        text = extract_pdf_text(pdf("identity-cn.pdf"))
        self.assertIn(CN, text, "identity-encoded CIDs must decode as UTF-16BE: %r" % text)

    def test_uncompressed_stream_is_read_not_dropped(self):
        """A stream stored without a filter is still a text layer, not a scanned page."""
        text = extract_pdf_text(pdf("uncompressed-cn.pdf"))
        self.assertIn(CN, text, "an uncompressed content stream must not be skipped: %r" % text)

    def test_image_only_pdf_yields_no_text(self):
        self.assertEqual(extract_pdf_text(pdf("scanned.pdf")), "",
                         "a page with no text layer must yield nothing, never noise")

    def test_font_metadata_is_never_indexed(self):
        """The CMap is parsed, not read: indexing it claimed the document says 'Adobe UCS'."""
        for name in ("subset-cn.pdf", "identity-cn.pdf", "uncompressed-cn.pdf"):
            text = extract_pdf_text(pdf(name))
            for noise in ("Adobe", "UCS", "GB1", "begincmap", "CIDSystemInfo"):
                self.assertNotIn(noise, text, "%s leaked font metadata: %r" % (name, text))

    def test_english_pdf_is_untouched(self):
        self.assertIn("Employee Handbook", extract_pdf_text(pdf("en.pdf")))


class MixedDirectoryTest(unittest.TestCase):
    def test_chinese_documents_are_indexed_and_only_the_scan_is_skipped(self):
        documents, skipped = load_documents(FIXTURES)
        names = {d.doc_id for d in documents}
        self.assertTrue(any(CN in doc_text(d) for d in documents),
                        "at least one document must carry the Chinese text")
        self.assertIn("zh", {d.language for d in documents},
                      "a Chinese document must be detected as zh, got %s"
                      % sorted({d.language for d in documents}))
        skipped_names = {s["file"] for s in skipped}
        self.assertEqual(skipped_names, {"scanned.pdf"},
                         "only the image-only PDF may be skipped, got %s" % sorted(skipped_names))
        self.assertTrue(names)

    def test_a_short_chinese_document_is_not_mistaken_for_a_scan(self):
        """A complete Chinese clause is ~34 characters where English is ~150. A single floor sized
        for English silently dropped those documents as 'scanned'."""
        documents, skipped = load_documents(FIXTURES)
        skipped_names = {s["file"] for s in skipped}
        for name in ("subset-cn.pdf", "identity-cn.pdf", "uncompressed-cn.pdf"):
            self.assertNotIn(name, skipped_names,
                             "%s is a real document and must not be reported as scanned" % name)


if __name__ == "__main__":
    unittest.main()
