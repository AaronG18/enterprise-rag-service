"""Every suffix advertised as supported is actually parsed (R18).

`.markdown` is the easy one to forget: `.md` and `.markdown` are the same format, so a bug that
only accepts one of them passes every test written against the other. The fixture is
`tests/data/formats/notes.markdown`.
"""
from __future__ import annotations

import os
import unittest

from ragserve.corpus.loader import load_documents

FORMATS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "formats")


class MarkdownSuffixTest(unittest.TestCase):
    def test_dot_markdown_is_parsed_into_sections(self):
        documents, skipped = load_documents(FORMATS)
        self.assertEqual([s["file"] for s in skipped], [], "nothing here should be unreadable")
        self.assertTrue(documents, "the .markdown fixture must be indexed")
        headings = [s.heading for d in documents for s in d.sections]
        bodies = "\n".join(s.body for d in documents for s in d.sections)
        self.assertTrue(any("Expense notes" in h for h in headings),
                        "the markdown heading must become a section: %s" % headings)
        self.assertIn("Receipts are required for any single item above 25 USD.", bodies,
                      "the markdown body must be indexed verbatim")


if __name__ == "__main__":
    unittest.main()
