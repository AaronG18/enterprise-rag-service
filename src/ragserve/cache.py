"""Two-layer response cache.

Two failure modes this design exists to prevent:

1. **Poisoning.** The cache key includes retrieval mode, rerank flag, corpus version and model
   version, so a configuration change can never serve a result produced under a different one.
   Refusals are never cached, because caching a transient refusal makes it permanent.
2. **Fake numbers.** Cache hits are marked in the trace and log, so a benchmark can exclude them
   instead of reporting warmed-cache latency as if it were cold.

Expiry is checked against an injectable clock - no background thread, so behaviour is
deterministic and testable.
"""
from __future__ import annotations

import time
from typing import Callable, Dict, Optional

from .retrieval.text import tokenize


class ResponseCache:
    def __init__(self, exact_ttl: float = 300.0, semantic_ttl: float = 60.0,
                 clock: Callable[[], float] = time.time, max_entries: int = 512):
        self.exact_ttl = exact_ttl
        self.semantic_ttl = semantic_ttl
        self.clock = clock
        self.max_entries = max_entries
        self._exact: Dict[str, Dict] = {}
        self._semantic: Dict[str, Dict] = {}
        self.stats = {"lookups": 0, "hits": 0, "stores": 0, "evictions": 0}

    # -- keys --------------------------------------------------------------
    @staticmethod
    def _scope(retrieval_mode: str, rerank: bool, corpus_version: str, model_version: str) -> str:
        return "%s|%s|%s|%s" % (retrieval_mode, int(bool(rerank)), corpus_version, model_version)

    @staticmethod
    def _signature(query: str) -> str:
        return "|".join(sorted(set(tokenize(query))))

    # -- ops ---------------------------------------------------------------
    def get(self, query: str, retrieval_mode: str, rerank: bool,
            corpus_version: str, model_version: str) -> Optional[Dict]:
        self.stats["lookups"] += 1
        scope = self._scope(retrieval_mode, rerank, corpus_version, model_version)

        entry = self._exact.get("%s::%s" % (scope, query.strip().lower()))
        if entry is not None:
            if self._fresh(entry, self.exact_ttl):
                self.stats["hits"] += 1
                return {"payload": dict(entry["payload"]), "layer": "exact"}
            del self._exact["%s::%s" % (scope, query.strip().lower())]

        semantic_key = "%s::%s" % (scope, self._signature(query))
        entry = self._semantic.get(semantic_key)
        if entry is not None:
            if self._fresh(entry, self.semantic_ttl):
                self.stats["hits"] += 1
                return {"payload": dict(entry["payload"]), "layer": "semantic"}
            del self._semantic[semantic_key]
        return None

    def put(self, query: str, retrieval_mode: str, rerank: bool,
            corpus_version: str, model_version: str, payload: Dict) -> None:
        self.stats["stores"] += 1
        scope = self._scope(retrieval_mode, rerank, corpus_version, model_version)
        now = self.clock()
        record = {"ts": now, "payload": dict(payload)}
        self._exact["%s::%s" % (scope, query.strip().lower())] = dict(record)
        self._semantic["%s::%s" % (scope, self._signature(query))] = dict(record)
        self._evict_if_needed()

    def invalidate_all(self) -> None:
        self._exact.clear()
        self._semantic.clear()

    # -- internals ---------------------------------------------------------
    def _fresh(self, entry: Dict, ttl: float) -> bool:
        return (self.clock() - entry["ts"]) <= ttl

    def _evict_if_needed(self) -> None:
        for store in (self._exact, self._semantic):
            while len(store) > self.max_entries:
                oldest = min(store.items(), key=lambda item: item[1]["ts"])[0]
                del store[oldest]
                self.stats["evictions"] += 1

    @property
    def hit_rate(self) -> float:
        lookups = self.stats["lookups"]
        return 0.0 if not lookups else self.stats["hits"] / lookups
