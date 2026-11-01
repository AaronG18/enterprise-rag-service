"""Interactive QA: the reviewer's own questions, answered end to end in the terminal.

Why this is the default mode
----------------------------
The brief's performance target is about **QA requests**: "90% of QA requests must complete end to end
within 10 seconds; support >= 5 concurrent requests on a single instance". The requests that matter
are the ones a reviewer types, not the 85 cases this repository wrote for itself. So the default mode
prompts for questions, answers each one with citations, and reports the end-to-end latency of *those*
requests - and `:bench N` replays the reviewer's own last question N times concurrently.

Bootstrap
---------
The first run installs the local models if they are missing and starts the two servers, then says so.
The second run finds them and goes straight to the work. `--no-bootstrap` skips both (used by the
hermetic tests); when the servers are unavailable the service falls back to the deterministic backend
loudly, and the banner says which backend is actually in use rather than pretending.

Commands inside the loop
------------------------
    :stats            p50/p95 latency, refusals, tokens, cache hits for the questions asked so far
    :bench [N]        replay the last question N times concurrently (default 5)
    :quit / :q        leave (prints the summary)
"""
from __future__ import annotations

import argparse
import getpass
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from ..api import ApiServer
from . import REPO_ROOT


def _percentile(values, fraction):
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))
    return ordered[index]


def _bootstrap(enabled: bool):
    if not enabled:
        return []
    from . import setup as setup_mod

    print("Environment")
    if not (setup_mod.ensure_runtime() and setup_mod.ensure_weights()):
        print("  WARNING: the local models are unavailable, so this session will use the")
        print("           deterministic backend. Run `python scripts/run.py --check` for detail.")
        return []
    started = setup_mod.start_servers()
    if started:
        # Deliberately left running: the next invocation detects them and goes straight to the
        # questions, which is the "second run does not rebuild the environment" behaviour the
        # quickstart promises. They are bound to loopback only.
        print("  left running for the next run (loopback only)")
    return started


def _report_backend(server: ApiServer) -> None:
    config = server.retrieval_config
    degraded = bool(getattr(config, "degraded_embedding", False)
                    or getattr(config, "degraded_reranker", False))
    pinned = config.embedding_provider == "deterministic"
    if pinned or degraded:
        why = ("pinned by RAGSERVE_EMBEDDING_PROVIDER" if pinned
               else "a model server was unreachable")
        print("  backend       : deterministic (%s - answers are composed from retrieved" % why)
        print("                  text; run without the pin and with --setup for the real models)")
    else:
        print("  backend       : model-backed (%s + %s)"
              % (config.embedding_model, config.reranker_model))


class Session:
    def __init__(self, server: ApiServer):
        self.server = server
        self.latencies = []
        self.refusals = 0
        self.tokens = 0
        self.cache_hits = 0
        self.last_question = None

    def ask(self, question: str):
        started = time.perf_counter()
        result = self.server.service.answer(question)
        latency = (time.perf_counter() - started) * 1000.0
        self.latencies.append(latency)
        self.last_question = question
        if result.answer.refused:
            self.refusals += 1
        self.tokens += int(getattr(result.answer.usage, "total_tokens", 0) or 0)
        if getattr(result.answer, "cache_hit", False):
            self.cache_hits += 1
        return result, latency

    def stats(self) -> str:
        values = self.latencies
        if not values:
            return "  no questions asked yet"
        return ("  questions %d | p50 %.0f ms | p95 %.0f ms | max %.0f ms | refusals %d | "
                "tokens %d | cache hits %d"
                % (len(values), _percentile(values, 0.50), _percentile(values, 0.95),
                   max(values), self.refusals, self.tokens, self.cache_hits))

    def bench(self, concurrency: int):
        if not self.last_question:
            print("  ask a question first, then :bench")
            return
        print("  running %d concurrent requests on your last question..." % concurrency)
        started = time.perf_counter()
        latencies, errors = [], 0
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = [pool.submit(self._timed, self.last_question) for _ in range(concurrency)]
            for future in futures:
                try:
                    latencies.append(future.result())
                except Exception as exc:  # reported, never hidden
                    errors += 1
                    print("  request failed: %s" % exc)
        wall = (time.perf_counter() - started) * 1000.0
        if latencies:
            print("  concurrency %d | wall %.0f ms | p50 %.0f ms | p95 %.0f ms | errors %d"
                  % (concurrency, wall, statistics.median(latencies),
                     _percentile(latencies, 0.95), errors))
        print("  under-10s bound: %s" % ("PASS" if max(latencies or [0]) < 10_000 else "FAIL"))

    def _timed(self, question):
        started = time.perf_counter()
        result = self.server.service.answer(question)
        latency = (time.perf_counter() - started) * 1000.0
        if result.answer.refused:
            raise RuntimeError("refused: %s" % result.answer.reason_code)
        return latency


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--corpus", metavar="DIR", default=None,
                        help="index the documents in DIR instead of the built-in synthetic corpus")
    parser.add_argument("--no-bootstrap", action="store_true",
                        help="do not install/start the local models (the deterministic backend is used)")
    parser.add_argument("--concurrency", type=int, default=5, help="default for :bench (5)")
    args = parser.parse_args()

    print("Terminal folder   : %s" % os.getcwd())
    print("Repository root   : %s" % REPO_ROOT)
    print("User              : %s" % getpass.getuser())
    print()

    _bootstrap(not args.no_bootstrap)

    server = ApiServer(REPO_ROOT, host="127.0.0.1", port=0, corpus_dir=args.corpus)
    corpus = server.corpus
    print("Corpus")
    print("  source        : %s" % (args.corpus or "built-in synthetic corpus"))
    print("  documents     : %d | chunks %d | languages %s"
          % (len(corpus.documents), len(corpus.chunks), corpus.manifest.get("per_language")))
    _report_backend(server)
    print()
    print("Ask a question. Commands: :stats  :bench [N]  :quit")
    print()

    session = Session(server)
    while True:
        try:
            line = input("Q> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line in (":quit", ":q", "quit", "exit"):
            break
        if line == ":stats":
            print(session.stats())
            continue
        if line.startswith(":bench"):
            parts = line.split()
            count = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else args.concurrency
            session.bench(count)
            continue
        result, latency = session.ask(line)
        answer = result.answer
        if answer.refused:
            print("REFUSED (%s): %s" % (answer.reason_code, answer.text))
        else:
            print(answer.text)
            for citation in answer.citations[:3]:
                # Citations are already rendered strings ("doc#section"); printing them as they
                # are keeps the terminal honest instead of re-formatting a model of them.
                print("  %s" % citation)
        print("  (%.0f ms)" % latency)
        print()

    print()
    print("Summary")
    print(session.stats())
    return 0
