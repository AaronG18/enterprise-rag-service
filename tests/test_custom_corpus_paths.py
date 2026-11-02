"""Any path a reviewer may paste must work, or refuse readably (issue #128).

Measured before the fix: spaces, a Chinese directory name, nesting, mixed files, UPPERCASE
extensions, relative paths, a trailing separator and `..` segments all worked - while a single file
and a missing path raised a Python traceback, and an empty folder exited 0 with a report about
nothing.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from ragserve.corpus.loader import SUPPORTED_SUFFIXES, load_documents

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRY = os.path.join(REPO, "scripts", "run.py")
TEXT = "Annual leave is fifteen days per calendar year.\n"
ZH = "\u5458\u5de5\u6bcf\u5e74\u53ef\u4eab\u53d7\u5341\u4e94\u5929\u5e74\u5047\u3002\n"


def _write(path: str, body: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)


class CustomCorpusPathTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = tempfile.mkdtemp(prefix="path-cases-")
        cls.spaces = os.path.join(cls.base, "custom corpus with spaces")
        _write(os.path.join(cls.spaces, "leave.txt"), TEXT)
        _write(os.path.join(cls.spaces, "handbook-zh.md"), ZH)
        cls.chinese = os.path.join(cls.base, "\u81ea\u5b9a\u4e49\u8bed\u6599\u5e93")
        _write(os.path.join(cls.chinese, "\u5e74\u5047\u5236\u5ea6.txt"), ZH)
        cls.nested = os.path.join(cls.base, "nested", "deep", "docs")
        _write(os.path.join(cls.nested, "a.txt"), TEXT)
        cls.mixed = os.path.join(cls.base, "mixed")
        _write(os.path.join(cls.mixed, "doc.txt"), TEXT)
        _write(os.path.join(cls.mixed, "config.json"), "{}")
        _write(os.path.join(cls.mixed, "blob.bin"), "x")
        cls.upper = os.path.join(cls.base, "upper")
        _write(os.path.join(cls.upper, "NOTES.TXT"), TEXT)
        cls.empty = os.path.join(cls.base, "empty")
        os.makedirs(cls.empty, exist_ok=True)
        cls.single = os.path.join(cls.base, "single-file.txt")
        _write(cls.single, TEXT)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base, ignore_errors=True)

    def test_a_directory_with_spaces_and_a_chinese_sibling_indexes_everything(self):
        for path, expected in ((self.spaces, 2), (self.chinese, 1)):
            documents, _skipped = load_documents(path)
            self.assertEqual(len(documents), expected, "path %r" % path)

    def test_a_single_file_is_a_corpus_of_one(self):
        """A reviewer pasting a PDF path should not have to wrap it in a directory."""
        documents, skipped = load_documents(self.single)
        self.assertEqual(len(documents), 1)
        self.assertEqual(skipped, [])
        self.assertIn("single-file", documents[0].doc_id)

    def test_unsupported_files_are_reported_not_silently_dropped(self):
        documents, skipped = load_documents(self.mixed)
        self.assertEqual(len(documents), 1)
        self.assertEqual({item["file"] for item in skipped}, {"blob.bin", "config.json"})

    def test_uppercase_extensions_are_supported(self):
        documents, _skipped = load_documents(self.upper)
        self.assertEqual(len(documents), 1, "NOTES.TXT must be read; suffix matching is lowercase")

    def test_nested_directories_are_walked(self):
        documents, _skipped = load_documents(self.nested)
        self.assertEqual(len(documents), 1)

    def test_a_missing_path_raises_one_readable_error(self):
        with self.assertRaises(ValueError) as caught:
            load_documents(os.path.join(self.base, "does-not-exist"))
        self.assertIn("no such file or directory", str(caught.exception))

    def _run_cli(self, path: str):
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["RAGSERVE_EMBEDDING_PROVIDER"] = "deterministic"
        env["RAGSERVE_RERANKER_PROVIDER"] = "deterministic"
        return subprocess.run([sys.executable, ENTRY, "--eval", "--corpus", path], cwd=REPO,
                              env=env, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=300)

    def test_the_cli_refuses_an_empty_folder_without_a_traceback(self):
        proc = self._run_cli(self.empty)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("REFUSED", proc.stdout)
        self.assertNotIn("Traceback", proc.stdout + proc.stderr)
        self.assertIn(", ".join(SUPPORTED_SUFFIXES), proc.stdout)

    def test_the_cli_refuses_a_missing_path_without_a_traceback(self):
        proc = self._run_cli(os.path.join(self.base, "nope"))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("REFUSED", proc.stdout)
        self.assertNotIn("Traceback", proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
