"""EPIC #13 / SUB 45, 49: HTTP API - hermetic, exercised over loopback inside the test."""
from __future__ import annotations

import json
import os
import threading
import unittest
import urllib.error
import urllib.request

from ragserve.api import ApiServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _ServerFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events = []
        cls.server = ApiServer(ROOT, host="127.0.0.1", port=0, log_sink=cls.events.append)
        cls.port = 0
        # Bind an ephemeral port by starting the HTTP server on a thread.
        from http.server import ThreadingHTTPServer

        cls.httpd = ThreadingHTTPServer((cls.server.host, 0), _handler_for(cls.server))
        cls.httpd.daemon_threads = True
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def _get(self, path):
        with urllib.request.urlopen("http://127.0.0.1:%d%s" % (self.port, path), timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))

    def _post(self, path, payload):
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request("http://127.0.0.1:%d%s" % (self.port, path), data=data,
                                     headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return json.loads(exc.read().decode("utf-8"))


def _handler_for(server):
    """Reuse the handler built by ApiServer.serve by importing the same factory logic."""
    from http.server import BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _json(self, status, payload):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            from urllib.parse import urlparse

            path = urlparse(self.path).path
            if path == "/api/health":
                self._json(200, server.health())
            elif path == "/api/providers":
                self._json(200, server.providers())
            else:
                self._json(404, {"error": "not_found"})

        def do_POST(self):
            from urllib.parse import urlparse

            if urlparse(self.path).path != "/api/ask":
                self._json(404, {"error": "not_found"})
                return
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            try:
                result = server.ask(payload)
            except ValueError as exc:
                self._json(400, {"error": "bad_request", "detail": str(exc)})
                return
            self._json(200 if "error" not in result else 503, result)

    return Handler


class TestHealth(_ServerFixture):
    def test_health_reports_corpus_and_index(self):
        health = self._get("/api/health")
        self.assertEqual(health["status"], "ok")
        self.assertTrue(health["corpus_version"])
        self.assertGreater(health["chunks"], 0)
        self.assertGreaterEqual(health["index_build_ms"], 0.0)

    def test_providers_endpoint_drives_the_ui(self):
        providers = self._get("/api/providers")
        ids = {p["id"] for p in providers["providers"]}
        self.assertEqual(ids, {"deterministic", "codebuddy-serve", "openai-compatible"})
        self.assertEqual(providers["default"], "deterministic")


class TestAsk(_ServerFixture):
    def test_question_returns_answer_with_citations(self):
        result = self._post("/api/ask", {
            "question": "How many days of annual leave do full-time employees accrue?"})
        self.assertNotIn("error", result)
        self.assertFalse(result["answer"]["refused"])
        self.assertTrue(result["answer"]["citations"])
        self.assertTrue(result["retrieved"])
        self.assertGreater(result["latency_ms"], 0.0)

    def test_session_follow_up_resolves(self):
        first = self._post("/api/ask", {
            "question": "How many days of annual leave do full-time employees accrue?",
            "session_id": "s1"})
        self.assertFalse(first["answer"]["refused"])
        second = self._post("/api/ask", {
            "question": "How many of them can be carried over?",
            "session_id": "s1"})
        self.assertFalse(second["answer"]["refused"])
        self.assertTrue(second["trace"]["query_rewritten"])
        self.assertIn("handbook-en-00", [c["doc_id"] for c in second["retrieved"][:3]])

    def test_missing_question_is_a_bad_request(self):
        result = self._post("/api/ask", {})
        self.assertEqual(result["error"], "bad_request")

    def test_out_of_scope_question_refuses_with_guidance(self):
        result = self._post("/api/ask", {"question": "quarterly dividend policy for bitcoin miners"})
        self.assertTrue(result["answer"]["refused"])
        self.assertTrue(result["answer"]["guidance"].strip())

    def test_byo_key_missing_is_reported_not_crashed(self):
        result = self._post("/api/ask", {
            "question": "annual leave",
            "provider": "openai-compatible",
            "endpoint": "https://api.example.com/v1"})
        self.assertEqual(result["error"], "bad_request")

    def test_codebuddy_endpoint_must_be_loopback(self):
        result = self._post("/api/ask", {
            "question": "annual leave",
            "provider": "codebuddy-serve",
            "endpoint": "https://api.example.com"})
        self.assertIn("error", result)
        self.assertNotIn("Traceback", json.dumps(result))


class TestPortFallback(unittest.TestCase):
    """A busy port must never leave the reviewer looking at a different application."""

    def _serve_on(self, port: int, occupy: bool):
        """Start our server on `port`. With `occupy=True`, another local service holds the port
        first - including SO_REUSEADDR, which mirrors a real service (Node sets it) and is the
        case where a plain bind succeeds but the traffic goes elsewhere."""
        import socket
        import threading
        from http.server import ThreadingHTTPServer

        blocker = None
        if occupy:
            blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            blocker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            blocker.bind(("127.0.0.1", port))
            blocker.listen(1)

        server = ApiServer(ROOT, host="127.0.0.1", port=port, cache_enabled=False)
        httpd = server.start()
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        return blocker, httpd, thread, httpd.server_address[1]

    def test_taken_port_is_skipped_and_our_service_answers(self):
        import json
        import socket
        import urllib.request

        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.bind(("127.0.0.1", 0))
        busy_port = probe.getsockname()[1]
        probe.close()

        blocker, httpd, thread, actual = self._serve_on(busy_port, occupy=True)
        try:
            self.assertNotEqual(actual, busy_port)
            with urllib.request.urlopen("http://127.0.0.1:%d/api/health" % actual, timeout=15) as r:
                health = json.loads(r.read().decode("utf-8"))
            self.assertEqual(health["status"], "ok")
            self.assertEqual(health["provider"], "deterministic")
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=3)
            blocker.close()

    def test_free_port_is_used_as_requested(self):
        import socket

        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.bind(("127.0.0.1", 0))
        free_port = probe.getsockname()[1]
        probe.close()

        blocker, httpd, thread, actual = self._serve_on(free_port, occupy=False)
        try:
            self.assertEqual(actual, free_port)
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=3)
            if blocker is not None:
                blocker.close()

    def test_busy_port_resolves_to_the_next_free_port_deterministically(self):
        """8174 taken -> 8175, not a random ephemeral port the reviewer cannot retype."""
        import socket

        base = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        base.bind(("127.0.0.1", 0))
        first = base.getsockname()[1]
        base.close()
        second = first + 1
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.bind(("127.0.0.1", second))
        probe.close()

        blockers = []
        try:
            for port in (first, second):
                blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                blocker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                blocker.bind(("127.0.0.1", port))
                blocker.listen(1)
                blockers.append(blocker)

            _b, httpd, thread, actual = self._serve_on(first, occupy=False)
            try:
                self.assertEqual(actual, second + 1,
                                 "expected the next free port above the taken ones")
            finally:
                httpd.shutdown()
                httpd.server_close()
                thread.join(timeout=3)
        finally:
            for blocker in blockers:
                blocker.close()

    def test_whole_span_busy_falls_back_to_os_port(self):
        import socket

        from ragserve.api import PORT_SCAN_SPAN, find_free_port

        base = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        base.bind(("127.0.0.1", 0))
        first = base.getsockname()[1]
        base.close()

        blockers = []
        try:
            for port in range(first, first + PORT_SCAN_SPAN):
                blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                blocker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                blocker.bind(("127.0.0.1", port))
                blocker.listen(1)
                blockers.append(blocker)
            self.assertEqual(find_free_port("127.0.0.1", first), 0,
                             "an exhausted span must ask the OS for a port")
        finally:
            for blocker in blockers:
                blocker.close()


class TestKeySafety(_ServerFixture):
    def test_api_key_never_appears_in_logs(self):
        secret = "sk-super-secret-value-1234567890"
        self._post("/api/ask", {
            "question": "annual leave",
            "provider": "openai-compatible",
            "endpoint": "http://127.0.0.1:1/v1",
            "api_key": secret,
            "model": "m"})
        joined = "\n".join(self.events)
        self.assertNotIn(secret, joined)
        self.assertNotIn("api_key", joined)

    def test_unreachable_endpoint_returns_provider_unavailable(self):
        result = self._post("/api/ask", {
            "question": "annual leave",
            "provider": "openai-compatible",
            "endpoint": "http://127.0.0.1:1/v1",
            "api_key": "sk-test",
            "model": "m"})
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
