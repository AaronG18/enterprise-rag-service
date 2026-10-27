"""EPIC #11 / SUB 36: CodeBuddy serve adapter - hermetic, verified against a local fake server.

CI must never touch the network, so the real endpoint is replaced here by a throwaway HTTP
server on loopback that speaks the same protocol (run creation + SSE).
"""
from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

from ragserve.generation.providers import (
    CodeBuddyServeProvider,
    ProviderUnavailable,
    attribute_evidence,
    extract_citations,
    is_loopback,
    strip_sources_line,
)

SSE_BODY = (
    b'event: message\n'
    b'data: {"agent": {"sessionId": "s1", "toolCalls": []}, "content": {"markdown": '
    b'"Full-time employees accrue 15 working days [handbook-en-00:0000]."}, '
    b'"replyTo": null, "status": "done", "version": 1}\n\n'
    b'event: done\n'
    b'data: {}\n\n'
)


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep test output clean
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        payload = json.dumps({"data": {"runId": "run-1", "status": "queued"}}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(SSE_BODY)))
        self.end_headers()
        self.wfile.write(SSE_BODY)


class _FakeServer:
    def __init__(self):
        self.httpd = HTTPServer(("127.0.0.1", 0), _Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base_url(self) -> str:
        return "http://127.0.0.1:%d" % self.httpd.server_address[1]

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)


class TestLoopbackSafety(unittest.TestCase):
    def test_loopback_accepted(self):
        self.assertTrue(is_loopback("http://127.0.0.1:8788"))
        self.assertTrue(is_loopback("http://localhost:8788"))

    def test_remote_hosts_rejected(self):
        self.assertFalse(is_loopback("https://api.example.com"))
        self.assertFalse(is_loopback("http://10.0.0.5:8787"))

    def test_non_loopback_endpoint_raises(self):
        """The adapter may see user queries and retrieved content: a remote endpoint is a leak."""
        with self.assertRaises(ProviderUnavailable):
            CodeBuddyServeProvider("https://api.example.com", "hy3")


class TestProtocolHandling(unittest.TestCase):
    def setUp(self):
        self.server = _FakeServer()
        self.provider = CodeBuddyServeProvider(self.server.base_url, "fake-model")

    def tearDown(self):
        self.server.stop()

    def test_generate_parses_sse_markdown(self):
        text, usage = self.provider.generate_from_prompt("question?")
        self.assertIn("15 working days", text)
        self.assertEqual(self.provider.version, "fake-model")
        self.assertGreater(usage["total_tokens"], 0)

    def test_unreachable_serve_raises_provider_unavailable(self):
        """A clear error is what lets the deterministic lane remain the fallback."""
        provider = CodeBuddyServeProvider("http://127.0.0.1:1", "fake-model")
        with self.assertRaises(ProviderUnavailable):
            provider.generate_from_prompt("question?")


class TestSourcesLineStripping(unittest.TestCase):
    """The Sources line is metadata; scoring it as a claim was a measured regression."""

    def test_trailing_sources_line_is_removed(self):
        text = "Employees accrue 15 days.\n\nSources: [handbook-en-00:0000]"
        self.assertEqual(strip_sources_line(text), "Employees accrue 15 days.")

    def test_answer_without_sources_line_is_untouched(self):
        text = "Employees accrue 15 days."
        self.assertEqual(strip_sources_line(text), text)

    def test_chinese_label_variant_is_removed(self):
        text = "员工每年享有 15 天年假。\n\n来源：[handbook-zh-00:0000]"
        self.assertNotIn("来源", strip_sources_line(text))

    def test_stripped_answer_ends_in_sentence_punctuation(self):
        """Without this, style consistency lost a check on every model answer."""
        text = "Employees accrue 15 days.\n\nSources: [handbook-en-00:0000]"
        self.assertTrue(strip_sources_line(text).endswith("."))


class TestEvidenceAttribution(unittest.TestCase):
    """Attribution answers 'where did this come from'; it must not double as a support test."""

    def _chunks(self):
        return [
            _Chunk("handbook-en-00:0000", "Full-time employees accrue 15 working days of paid annual leave."),
            _Chunk("techspec-en-00:0000", "The read path targets a p95 of 800 milliseconds."),
        ]

    def test_sentences_are_attributed_to_best_matching_chunk(self):
        chunks = self._chunks()
        ids = attribute_evidence("Employees accrue 15 working days of leave.", chunks)
        self.assertEqual(ids, ["handbook-en-00:0000"])

    def test_mixed_answer_attributes_both_sources(self):
        ids = attribute_evidence(
            "Employees accrue 15 working days. The read path targets a p95 of 800 ms.",
            self._chunks())
        self.assertEqual(set(ids), {"handbook-en-00:0000", "techspec-en-00:0000"})

    def test_attribution_never_invents_ids(self):
        ids = attribute_evidence("Something about quarterly dividends.", self._chunks())
        self.assertTrue(set(ids).issubset({c.chunk_id for c in self._chunks()}))

    def test_empty_answer_attributed_to_nothing(self):
        self.assertEqual(attribute_evidence("", self._chunks()), [])


class _Chunk:
    def __init__(self, chunk_id, text):
        self.chunk_id = chunk_id
        self.text = text


class TestCitationExtraction(unittest.TestCase):
    def test_known_chunk_ids_are_extracted(self):
        text = "Answer [handbook-en-00:0000] and [handbook-en-00:0001]."
        found = extract_citations(text, {"handbook-en-00:0000", "handbook-en-00:0001"})
        self.assertEqual(found, ["handbook-en-00:0000", "handbook-en-00:0001"])

    def test_unknown_or_hallucinated_ids_are_dropped(self):
        """A cited chunk that was never retrieved must not count as support."""
        found = extract_citations("Answer [invented-doc:0009].", {"handbook-en-00:0000"})
        self.assertEqual(found, [])

    def test_duplicates_collapse(self):
        found = extract_citations("[a:0001] and [a:0001]", {"a:0001"})
        self.assertEqual(found, ["a:0001"])


if __name__ == "__main__":
    unittest.main()
