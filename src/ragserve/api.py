"""HTTP API - stdlib only, zero third-party dependencies.

The service is a *service*: this module exposes it over HTTP so a reviewer can ask it
questions, drive multi-turn sessions, and load-test it, without installing anything beyond
Python.

Routes:
    GET  /api/health       provider, corpus version, index size, index build time, uptime
    GET  /api/providers    what the UI needs to render the provider selector
    POST /api/ask          {question, session_id?, provider?, endpoint?, api_key?, model?}
    GET  /                 built UI (web/dist) or a built-in fallback page

Security posture, stated because it is a design decision and not an oversight:
  * The server binds 127.0.0.1 by default; it has no TLS and no authentication, and it is not
    a production deployment.
  * A reviewer-supplied API key is used for that request only: it is never logged, never
    written to disk, and never stored in a session. Asserted by test.
  * The `codebuddy-serve` provider refuses any non-loopback endpoint, because that endpoint
    carries no key of its own and would otherwise be a data-exfiltration path.
"""
from __future__ import annotations

import json
import os
import errno
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, List, Optional

from .cache import ResponseCache
from .corpus.builder import CorpusConfig, build_corpus
from .generation.providers import (
    CodeBuddyServeProvider,
    DeterministicProvider,
    OpenAICompatibleProvider,
    ProviderUnavailable,
)
from .observability.events import EventLog, StructuredLogger
from .retrieval.pipeline import RetrievalConfig
from .service import GenerationConfig, RagService

MAX_SESSIONS = 200
MAX_TURNS_PER_SESSION = 20
# How many ports to try above the requested one before letting the OS choose.
PORT_SCAN_SPAN = 20
FALLBACK_PAGE = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>Enterprise RAG Service</title>
<style>body{font-family:system-ui,sans-serif;max-width:640px;margin:64px auto;padding:0 16px;color:#1a1a1a}
code{background:#f3f4f6;padding:2px 6px;border-radius:4px}</style></head><body>
<h1>Enterprise RAG Service</h1>
<p>The API is running. The React UI has not been built in this checkout; start it with
<code>cd web && npm install && npm run build</code>, or call the API directly:</p>
<pre>curl -s http://127.0.0.1:8174/api/health
curl -s -X POST http://127.0.0.1:8174/api/ask \\
  -H 'Content-Type: application/json' \\
  -d '{"question":"How many days of annual leave do full-time employees accrue?"}'</pre>
</body></html>"""


def port_available(host: str, port: int) -> bool:
    """Is anything listening on this port?

    Probing is not optional. On Windows, when both sockets carry SO_REUSEADDR (which
    `http.server` sets), a bind to a port another service is actively listening on can
    *succeed* - and then the requests are delivered to the other service while this one
    believes it owns the address. That is how a reviewer ends up looking at a different
    application, so the port is probed before it is trusted.
    """
    import socket

    if port <= 0:
        return True
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.5)
        return probe.connect_ex((host, port)) != 0


def find_free_port(host: str, preferred: int, span: int = PORT_SCAN_SPAN) -> int:
    """First free port at or above `preferred`, scanning deterministically.

    Predictable beats random: 8174 -> 8175 -> 8176 is something a reviewer can retype, while an
    OS-assigned ephemeral port (49510) is not. Returns 0, meaning "let the OS choose", when the
    whole span is taken.
    """
    if preferred <= 0:
        return 0
    for candidate in range(preferred, preferred + span):
        if port_available(host, candidate):
            return candidate
    return 0


class ApiServer:
    """Owns the service instance, sessions and the log; the HTTP layer is a thin shell."""

    def __init__(self, root: str, host: str = "127.0.0.1", port: int = 8124,
                 log_sink=None, provider: str = "deterministic", model_version: str = "",
                 endpoint: str = "", embedding_provider: str = None,
                 cache_enabled: bool = True):
        self.root = root
        self.host = host
        self.port = port
        self.started_at = time.time()

        self.events = EventLog()
        self.logger = StructuredLogger(sink=log_sink or self.events.append)
        self.cache = ResponseCache() if cache_enabled else None
        self.cache_enabled = cache_enabled

        build_started = time.perf_counter()
        self.corpus = build_corpus(CorpusConfig.from_json(os.path.join(root, "configs", "corpus.json")))
        self.retrieval_config = RetrievalConfig.from_json(os.path.join(root, "configs", "retrieval.json"))
        if embedding_provider:
            self.retrieval_config.embedding_provider = embedding_provider
            if embedding_provider == "deterministic":
                self.retrieval_config.vector_dim = 512
        self.generation_config = GenerationConfig.from_json(os.path.join(root, "configs", "generation.json"))
        self.service = RagService(self.corpus, self.retrieval_config, self.generation_config,
                                  logger=self.logger, cache=self.cache)
        self.index_build_ms = round((time.perf_counter() - build_started) * 1000.0, 3)

        self.default_provider = provider
        self.default_model_version = model_version or self.generation_config.model_version
        self.default_endpoint = endpoint
        self.sessions: Dict[str, List] = {}
        self._lock = threading.Lock()

    # -- sessions ----------------------------------------------------------
    def _history(self, session_id: Optional[str]):
        if not session_id:
            return []
        with self._lock:
            turns = self.sessions.get(session_id, [])
            return [(q, a) for q, a in turns]

    def _remember(self, session_id: Optional[str], question: str, answer_text: str) -> None:
        if not session_id:
            return
        with self._lock:
            turns = self.sessions.setdefault(session_id, [])
            turns.append((question, answer_text))
            if len(turns) > MAX_TURNS_PER_SESSION:
                del turns[:len(turns) - MAX_TURNS_PER_SESSION]
            while len(self.sessions) > MAX_SESSIONS:
                self.sessions.pop(next(iter(self.sessions)))

    # -- request handling ---------------------------------------------------
    def health(self) -> Dict:
        return {
            "status": "ok",
            "provider": self.default_provider,
            "model_version": self.default_model_version,
            "embedding_provider": self.retrieval_config.embedding_provider,
            "corpus_version": self.service.corpus_version,
            "chunks": len(self.service.pipeline.chunks),
            "documents": len(self.corpus.documents),
            "index_build_ms": self.index_build_ms,
            "retrieval_mode": self.retrieval_config.mode,
            "rerank_enabled": self.retrieval_config.rerank_enabled,
            "sessions": len(self.sessions),
            "uptime_s": round(time.time() - self.started_at, 3),
        }

    def providers(self) -> Dict:
        return {
            "providers": [
                {"id": "deterministic", "label": "Deterministic (offline, no key)",
                 "needs_key": False,
                 "description": "Composes answers from retrieved passages. Hermetic and "
                                "reproducible; the CI baseline."},
                {"id": "codebuddy-serve", "label": "CodeBuddy local serve",
                 "needs_key": False, "needs_endpoint": True,
                 "description": "Local CodeBuddy CLI serve on 127.0.0.1. Loopback only."},
                {"id": "openai-compatible", "label": "Bring your own key (OpenAI-compatible)",
                 "needs_key": True, "needs_endpoint": True, "needs_model": True,
                 "description": "Any chat-completions endpoint. The key is used for this request "
                                "only and never logged or stored."},
            ],
            "default": self.default_provider,
        }

    def ask(self, payload: Dict) -> Dict:
        question = (payload.get("question") or "").strip()
        if not question:
            raise ValueError("question is required")
        session_id = payload.get("session_id") or None
        provider_name = payload.get("provider") or self.default_provider
        endpoint = (payload.get("endpoint") or self.default_endpoint or "").strip()
        api_key = (payload.get("api_key") or "").strip()
        model = (payload.get("model") or "").strip()

        workflow = self.logger.new_workflow_id()
        started = time.perf_counter()

        service = self.service
        if provider_name == "openai-compatible":
            if not endpoint:
                raise ValueError("endpoint is required for the openai-compatible provider")
            if not api_key:
                raise ValueError("api_key is required for the openai-compatible provider "
                                 "(it is used for this request only and never stored)")
            model_version = model or "unspecified"
            provider = OpenAICompatibleProvider(endpoint=endpoint, api_key_env="", model=model_version)
            provider._api_key = lambda: api_key  # supplied per request; never logged
            generation = GenerationConfig(**dict(self.generation_config.__dict__,
                                                 provider="openai-compatible",
                                                 model_version=model_version))
            service = RagService(self.corpus, self.retrieval_config, generation, provider=provider)
        elif provider_name == "codebuddy-serve":
            if not endpoint:
                raise ValueError("endpoint is required for the codebuddy-serve provider "
                                 "(e.g. http://127.0.0.1:8788)")
            model_version = model or "hy3"
            generation = GenerationConfig(**dict(self.generation_config.__dict__,
                                                 provider="codebuddy-serve",
                                                 model_version=model_version))
            try:
                provider = CodeBuddyServeProvider(endpoint, model_version)
            except ProviderUnavailable as exc:
                return {
                    "error": "provider_unavailable",
                    "detail": str(exc),
                    "hint": "The CodeBuddy provider only accepts loopback endpoints; use the "
                            "deterministic provider or bring your own OpenAI-compatible endpoint.",
                }
            service = RagService(self.corpus, self.retrieval_config, generation, provider=provider)

        history = self._history(session_id)
        try:
            result = service.answer(question, history=history, workflow_id=workflow)
        except ProviderUnavailable as exc:
            self.logger.emit("response", "provider_unavailable", workflow, query=question,
                             provider=provider_name, error=str(exc))
            return {
                "error": "provider_unavailable",
                "detail": str(exc),
                "hint": "Switch to the deterministic provider (no key required) or start the "
                        "local serve / supply your own endpoint.",
            }

        latency_ms = round((time.perf_counter() - started) * 1000.0, 3)
        self._remember(session_id, question, result.answer.text)

        trace = dict(result.trace)
        trace["latency_ms"] = latency_ms
        trace["provider"] = provider_name
        trace["session_id"] = session_id
        self.logger.emit("response", "api_response", workflow, query=question,
                         refused=result.answer.refused, reason_code=result.answer.reason_code,
                         citations=list(result.answer.citations), latency_ms=latency_ms,
                         provider=provider_name, cache_hit=bool(trace.get("cache_hit")))

        return {
            "session_id": session_id,
            "workflow_id": workflow,
            "latency_ms": latency_ms,
            "answer": result.answer.to_dict(),
            "retrieved": [
                {
                    "chunk_id": c.chunk_id,
                    "doc_id": c.doc_id,
                    "section": c.section,
                    "language": c.language,
                    "ocr": c.ocr,
                    "text": c.text,
                    "fused_score": round(c.fused_score, 5),
                }
                for c in result.retrieved
            ],
            "trace": trace,
        }

    # -- server -------------------------------------------------------------
    def start(self):
        """Bind the HTTP server without blocking. Returns the httpd so callers can stop it."""
        return self._build_httpd()

    def _port_available(self, port: int) -> bool:
        return port_available(self.host, port)

    def _build_httpd(self):
        server = self
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # silence default stderr logging
                pass

            def _json(self, status: int, payload: Dict) -> None:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _static(self, path: str) -> bool:
                dist = os.path.join(server.root, "web", "dist")
                target = os.path.normpath(os.path.join(dist, path.lstrip("/")))
                if not target.startswith(os.path.abspath(dist)):
                    return False
                if os.path.isdir(target):
                    target = os.path.join(target, "index.html")
                if not os.path.isfile(target):
                    return False
                with open(target, "rb") as fh:
                    body = fh.read()
                content_type = "text/html" if target.endswith(".html") else (
                    "application/javascript" if target.endswith(".js") else (
                        "text/css" if target.endswith(".css") else "application/octet-stream"))
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return True

            def do_GET(self):
                parsed = urllib.parse.urlparse(self.path)
                if parsed.path == "/api/health":
                    self._json(200, server.health())
                elif parsed.path == "/api/providers":
                    self._json(200, server.providers())
                elif parsed.path in ("/", "/index.html"):
                    if not self._static("/index.html"):
                        body = FALLBACK_PAGE.encode("utf-8")
                        self.send_response(200)
                        self.send_header("Content-Type", "text/html; charset=utf-8")
                        self.send_header("Content-Length", str(len(body)))
                        self.end_headers()
                        self.wfile.write(body)
                else:
                    if not self._static(parsed.path):
                        self._json(404, {"error": "not_found"})

            def do_POST(self):
                parsed = urllib.parse.urlparse(self.path)
                if parsed.path != "/api/ask":
                    self._json(404, {"error": "not_found"})
                    return
                length = int(self.headers.get("Content-Length", 0))
                try:
                    payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                except json.JSONDecodeError:
                    self._json(400, {"error": "invalid_json"})
                    return
                try:
                    result = server.ask(payload)
                except ValueError as exc:
                    self._json(400, {"error": "bad_request", "detail": str(exc)})
                    return
                except Exception as exc:  # noqa: BLE001 - the API must not leak stack traces
                    server.logger.emit("response", "api_error", "-",
                                       error="%s: %s" % (type(exc).__name__, exc))
                    self._json(500, {"error": "internal_error",
                                     "detail": "%s: %s" % (type(exc).__name__, exc)})
                    return
                status = 200 if "error" not in result else 503
                self._json(status, result)

        requested_port = self.port
        chosen_port = find_free_port(self.host, requested_port)
        if chosen_port != requested_port:
            if chosen_port == 0:
                print("ports %d-%d are all in use; letting the OS choose a free port"
                      % (requested_port, requested_port + PORT_SCAN_SPAN - 1))
            else:
                print("port %d is already in use by another service on this machine; "
                      "using %d instead" % (requested_port, chosen_port))
            self.port = chosen_port

        try:
            httpd = ThreadingHTTPServer((self.host, self.port), Handler)
        except OSError as exc:
            # Last resort: the port can be taken between the probe and the bind (a race), and a
            # reviewer must still get a working service rather than a stack trace.
            if exc.errno not in (errno.EADDRINUSE, getattr(errno, "WSAEADDRINUSE", 10048)):
                raise
            print("port %d was taken between the check and the bind; using a free port"
                  % self.port)
            self.port = 0
            httpd = ThreadingHTTPServer((self.host, 0), Handler)
        httpd.daemon_threads = True
        self.httpd = httpd
        return httpd

    def start(self):
        """Bind the HTTP server without blocking. Returns the httpd so callers can stop it."""
        return self._build_httpd()

    def serve(self, open_browser: bool = False) -> None:
        httpd = self._build_httpd()
        url = "http://%s:%d" % (self.host, httpd.server_address[1])
        print("Enterprise RAG Service listening on %s" % url)
        print("  UI      %s/" % url)
        print("  health  %s/api/health" % url)
        print("  corpus  %s (%d documents, %d chunks, index built in %.1f ms, cache %s)"
              % (self.service.corpus_version, len(self.corpus.documents),
                 len(self.service.pipeline.chunks), self.index_build_ms,
                 "on" if self.cache_enabled else "off"))
        if open_browser:
            try:
                webbrowser.open(url)
            except Exception:  # noqa: BLE001 - a missing browser must not stop the server
                pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nshutting down")
        finally:
            httpd.server_close()


def create_server(root: str, host: str = "127.0.0.1", port: int = 8124, **kwargs) -> ApiServer:
    return ApiServer(root=root, host=host, port=port, **kwargs)
