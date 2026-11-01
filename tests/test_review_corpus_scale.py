"""The review corpus is committed test data, verified against its generator (R19).

"28 mixed CN/EN PDFs were ingested end to end" was once backed by files a scratch script wrote into
%TEMP% - invisible in the tree, gone on cleanup, unreproducible by CI or a reviewer. The corpus now
lives where every other fixture lives: `tests/data/review-corpus/`, committed, inspectable.

Two things are asserted here:

* **Scale and behaviour**, against the committed corpus - the "dozens of bilingual PDFs" claim is a
  CI-checked fact about data anyone can see in the tree.
* **Byte identity** between the committed corpus and what the committed generator produces (the
  golden-file loop), compared on **canonical (decompressed) content**: re-running the generator and
  comparing proves both that the generator is deterministic and that the data cannot silently drift
  from it - a generator change without regenerating the data is a red build. Raw compressed bytes
  are not compared because zlib output legitimately differs between zlib builds; the first CI run
  of this test caught exactly that.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import zlib

from ragserve.corpus.loader import extract_pdf_pages, load_documents

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMMITTED = os.path.join(REPO, "tests", "data", "review-corpus")
GENERATOR = os.path.join(REPO, "scripts", "gen_review_corpus.py")
FONT_METADATA = ("Adobe", "UCS", "GB1", "begincmap")


def canonical_digest(path: str) -> str:
    """sha256 over the sequence of decompressed stream bodies - and nothing else.

    Two earlier attempts failed, and the failures are the lesson. Raw byte equality is not portable:
    zlib output legitimately differs between zlib builds and Python versions. And substituting each
    stream with the hash of its body is not enough either, because the surrounding `/Length N` and
    the xref offsets still shift whenever zlib's *output size* changes - the first CI runs failed on
    a file whose decompressed content was byte-identical. What the generator actually writes, and
    what has to be stable, is the decompressed content in order; /Length and xref offsets are
    transport detail.
    """
    with open(path, "rb") as fh:
        data = fh.read()
    hashes = []
    pos = 0
    opener = re.compile(rb"(?<!end)stream\r?\n")
    while True:
        match = opener.search(data, pos)
        if not match:
            break
        start = match.end()
        end = data.find(b"endstream", start)
        if end < 0:
            break
        body = data[start:end]
        if body.endswith(b"\r\n"):
            body = body[:-2]
        elif body.endswith(b"\n"):
            body = body[:-1]
        try:
            body = zlib.decompress(body)
        except zlib.error:
            pass  # a raw (unfiltered) stream: its bytes are already the content
        hashes.append(hashlib.sha256(body).hexdigest())
        pos = end + len(b"endstream")
    return hashlib.sha256("\n".join(hashes).encode("ascii")).hexdigest()


def _pdf_names(directory: str) -> list:
    return sorted(n for n in os.listdir(directory) if n.endswith(".pdf"))


class ReviewCorpusScaleTest(unittest.TestCase):
    """Scale and behaviour, asserted against the corpus committed under tests/data."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(COMMITTED, "manifest.json"), "r", encoding="utf-8") as fh:
            cls.manifest = json.load(fh)
        cls.out_dir = COMMITTED
        cls.documents, cls.skipped = load_documents(COMMITTED)

    def test_the_committed_corpus_is_the_claimed_scale(self):
        pdfs = _pdf_names(COMMITTED)
        self.assertGreaterEqual(len(pdfs), 30,
                                "the 'dozens of PDFs' claim must be visible in the tree")
        self.assertEqual(self.manifest["total"], len(pdfs))
        total = sum(os.path.getsize(os.path.join(COMMITTED, n)) for n in pdfs)
        self.assertGreaterEqual(total, 300_000,
                                "the review corpus must be a real corpus, not a folder of stubs")

    def test_every_document_is_multi_page(self):
        skipped = {s["file"] for s in self.skipped}
        for name in _pdf_names(COMMITTED):
            if name in skipped:
                continue  # a pure-image document has no text layer by design
            pages = extract_pdf_pages(os.path.join(COMMITTED, name))
            self.assertGreaterEqual(len(pages), 3, "%s must be multi-page" % name)

    def test_ingestion_matches_the_generator_manifest_exactly(self):
        skipped = {s["file"] for s in self.skipped if s["file"].endswith(".pdf")}
        self.assertEqual(len(self.documents), self.manifest["total"] - self.manifest["pure_image"])
        self.assertEqual(skipped, set(self.manifest["pure_image_files"]))
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
        zh_texts = ["\n".join(s.body for s in d.sections) for d in self.documents
                    if d.language == "zh"]
        self.assertTrue(zh_texts, "Chinese documents must be indexed")
        self.assertTrue(any("年假" in t for t in zh_texts),
                        "the Chinese text must survive extraction, not decode to noise")
        for doc in self.documents:
            text = "\n".join(s.body for s in doc.sections)
            for noise in FONT_METADATA:
                self.assertNotIn(noise, text,
                                 "font metadata must never be indexed: %s" % doc.doc_id)

    def test_documents_are_substantive_not_stubs(self):
        for doc in self.documents:
            text = "\n".join(s.body for s in doc.sections)
            self.assertGreaterEqual(len(text), 400,
                                    "%s is a stub, not a document" % doc.doc_id)


class GeneratorIdentityTest(unittest.TestCase):
    """The committed corpus and the committed generator must never drift apart."""

    def test_rerunning_the_generator_reproduces_the_committed_corpus_byte_for_byte(self):
        tmp = tempfile.mkdtemp(prefix="review-corpus-check-")
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run([sys.executable, GENERATOR, "--out", tmp], cwd=REPO, env=env,
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=300)
        self.assertEqual(proc.returncode, 0,
                         "the committed generator must run: %s" % proc.stderr[-300:])
        self.assertEqual(_pdf_names(tmp), _pdf_names(COMMITTED),
                         "the committed corpus and the generator disagree on the file list")
        for name in _pdf_names(COMMITTED):
            committed = canonical_digest(os.path.join(COMMITTED, name))
            regenerated = canonical_digest(os.path.join(tmp, name))
            self.assertEqual(committed, regenerated,
                             "%s differs from what the generator produces - regenerate the corpus "
                             "(python scripts/gen_review_corpus.py --out tests/data/review-corpus) "
                             "or the committed data is stale" % name)
        with open(os.path.join(tmp, "manifest.json"), "r", encoding="utf-8") as fh:
            regenerated = json.load(fh)
        with open(os.path.join(COMMITTED, "manifest.json"), "r", encoding="utf-8") as fh:
            committed = json.load(fh)
        self.assertEqual(regenerated, committed, "manifest.json drifted from the generator")


if __name__ == "__main__":
    unittest.main()
