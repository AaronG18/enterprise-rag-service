"""Mixed text+image PDFs.

The brief says the corpus "includes a small portion of scanned PDFs" without saying whether they are
pure images or text pages mixed with image pages - both occur. The mixed case is the dangerous one:
a whole-document decision discards the text pages along with the scanned ones, and then reports
"no extractable text", which is false.

`tests/data/cjk-pdf/mixed.pdf` is one short text page followed by three image-only pages.
"""
from __future__ import annotations

import os
import unittest

from ragserve.corpus.loader import load_documents

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "cjk-pdf")
CN = "年假规定"


def doc_text(doc) -> str:
    return "\n".join(s.body for s in doc.sections)


class MixedScanPdfTest(unittest.TestCase):
    def load(self):
        return load_documents(FIXTURES)

    def test_a_document_with_one_text_page_is_indexed_not_dropped(self):
        """Its only text layer is short, so a whole-document floor discards it."""
        documents, skipped = self.load()
        self.assertNotIn("mixed.pdf", {s["file"] for s in skipped},
                         "a PDF with a usable text page must not be reported as scanned")
        self.assertIn("mixed.pdf", {d.doc_id for d in documents})

    def test_the_text_page_survives(self):
        documents, _ = self.load()
        mixed = [d for d in documents if d.doc_id == "mixed.pdf"]
        self.assertTrue(mixed, "mixed.pdf must be indexed")
        self.assertIn(CN, doc_text(mixed[0]),
                      "the text page must be kept: %r" % doc_text(mixed[0]))

    def test_unreadable_pages_are_reported_not_silent(self):
        """A reviewer must be able to see the document is incomplete."""
        documents, _ = self.load()
        mixed = [d for d in documents if d.doc_id == "mixed.pdf"]
        self.assertTrue(mixed)
        self.assertEqual(mixed[0].scanned_pages, 3,
                         "3 of the 4 pages carry no text and must be reported")

    def test_a_pure_image_pdf_is_still_skipped(self):
        documents, skipped = self.load()
        self.assertIn("scanned.pdf", {s["file"] for s in skipped},
                      "a PDF with no text at all is still a scan")
        self.assertNotIn("scanned.pdf", {d.doc_id for d in documents})


if __name__ == "__main__":
    unittest.main()
