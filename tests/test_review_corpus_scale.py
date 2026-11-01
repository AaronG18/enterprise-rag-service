"""The scale of a claimed measurement must be reproducible from the repository (R19).

"28 mixed CN/EN PDFs were ingested end to end" was once true of one run against files built by
scratch scripts into %TEMP%. The repository itself carried six PDF fixtures of 1-3 KB, so a reviewer
asking "where are the dozens?" was right, and deleting the temp directory would have destroyed the
only copy of the evidence. This test runs the committed generator and asserts the claimed scale and
behaviour, which turns the claim into a CI-checked fact instead of an anecdote.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

from ragserve.corpus.loader import extract_pdf_pages, load_documents

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GENERATOR = os.path.join(REPO, "scripts", "gen_review_corpus.py")
SCALE = 36
FONT_METADATA = ("Adobe", "UCS", "GB1", "begincmap")


class ReviewCorpusScaleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out_dir = tempfile.mkdtemp(prefix="review-corpus-")
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        cls.proc = subprocess.run(
            [sys.executable, GENERATOR, "--out", cls.out_dir, "--count", str(SCALE)],
            cwd=REPO, env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=300)
        with open(os.path.join(cls.out_dir, "manifest.json"), "r", encoding="utf-8") as fh:
            cls.manifest = json.load(fh)
        cls.documents, cls.skipped = load_documents(cls.out_dir)

    def test_the_committed_generator_produces_the_claimed_scale(self):
        self.assertEqual(self.proc.returncode, 0,
                         "the committed generator must run: %s" % self.proc.stderr[-300:])
        pdfs = [n for n in os.listdir(self.out_dir) if n.endswith(".pdf")]
        self.assertGreaterEqual(len(pdfs), 30,
                                "the 'dozens of PDFs' claim must be backed by the repository")
        self.assertEqual(self.manifest["total"], len(pdfs))

    def test_every_document_is_multi_page(self):
        """A 1 KB single-page stub is an edge-case fixture, not a corpus document."""
        for name in os.listdir(self.out_dir):
            if not name.endswith(".pdf"):
                continue
            pages = extract_pdf_pages(os.path.join(self.out_dir, name))
            if name in {s["file"] for s in self.skipped}:
                continue  # a pure-image document has no text layer by design
            self.assertGreaterEqual(len(pages), 3, "%s must be multi-page" % name)

    def test_ingestion_matches_the_generator_manifest_exactly(self):
        indexed = {d.doc_id for d in self.documents}
        # manifest.json is not a supported suffix, so the loader reports it as unsupported - that
        # is correct behaviour, and the assertion below is about the PDFs only.
        skipped = {s["file"] for s in self.skipped if s["file"].endswith(".pdf")}
        self.assertEqual(len(self.documents), self.manifest["total"] - self.manifest["pure_image"])
        self.assertEqual(self.manifest["pure_image"], len(skipped))
        self.assertEqual(skipped, set(self.manifest["pure_image_files"]))
        for doc in self.documents:
            self.assertNotIn(doc.doc_id, skipped)
        languages = {}
        for doc in self.documents:
            languages[doc.language] = languages.get(doc.language, 0) + 1
        self.assertEqual(languages.get("en", 0), self.manifest["en"])
        self.assertEqual(languages.get("zh", 0), self.manifest["zh"])
        self.assertGreaterEqual(languages.get("zh", 0), 8, "the corpus must actually be bilingual")

    def test_mixed_documents_are_indexed_and_report_their_unreadable_pages(self):
        partial = [d for d in self.documents if d.scanned_pages > 0]
        self.assertEqual(len(partial), self.manifest["mixed"],
                         "every text+image document must be indexed, none dropped")
        for doc in partial:
            self.assertGreaterEqual(doc.scanned_pages, 1)

    def test_chinese_is_extracted_as_chinese_and_metadata_never_leaks(self):
        zh_texts = [ "\n".join(s.body for s in d.sections) for d in self.documents
                     if d.language == "zh"]
        self.assertTrue(zh_texts, "Chinese documents must be indexed")
        self.assertTrue(any("年假" in t for t in zh_texts),
                        "the Chinese text must survive extraction, not decode to noise")
        for doc in self.documents:
            text = "\n".join(s.body for s in doc.sections)
            for noise in FONT_METADATA:
                self.assertNotIn(noise, text,
                                 "font metadata must never be indexed: %s" % doc.doc_id)

    def test_the_corpus_is_not_a_few_kb_of_stubs(self):
        """Real scanned PDFs are large because a scan *is* an image; the corpus reflects that.

        A previous corpus averaged 3 KB per document, which is what made the 'dozens of PDFs'
        claim look hollow. The committed generator embeds real bitmap data in its scanned pages,
        and this pins the scale so it cannot quietly shrink back to stubs.
        """
        total = sum(os.path.getsize(os.path.join(self.out_dir, n))
                    for n in os.listdir(self.out_dir) if n.endswith(".pdf"))
        self.assertGreaterEqual(total, 300_000,
                                "the review corpus must be a real corpus, not a folder of stubs")

    def test_documents_are_substantive_not_stubs(self):
        """Addresses 'each is only a few KB': the corpus is multi-section prose, not one line."""
        for doc in self.documents:
            text = "\n".join(s.body for s in doc.sections)
            self.assertGreaterEqual(len(text), 400,
                                    "%s is a stub, not a document" % doc.doc_id)


if __name__ == "__main__":
    unittest.main()
