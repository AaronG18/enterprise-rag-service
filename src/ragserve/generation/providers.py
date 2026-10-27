"""Generation providers.

`DeterministicProvider` is the default: it composes answers from verbatim sentences of the
retrieved chunks. That is not a toy - it is what makes grounding *testable*: a test can assert
that every answer sentence appears in a cited passage. A model-based provider cannot offer that
guarantee, which is why the deterministic one is the baseline that CI enforces.

`OpenAICompatibleProvider` exists so the interface is real, but it is never used by default
and never in CI (INV-1). It is documented as untested against a live endpoint.
"""
from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Tuple

from ..retrieval.text import tokenize

SENTENCE_SPLIT = re.compile(r"(?<=[。！？!?.])\s*")


class ProviderUnavailable(RuntimeError):
    """Raised when a network provider is selected but not configured."""


class DeterministicProvider:
    name = "deterministic"
    version = "stub-deterministic-1"

    def generate(self, query: str, retrieved: List, max_sentences: int,
                 max_chars: int) -> Tuple[str, List[str], Dict[str, int], float]:
        query_tokens = set(tokenize(query))
        scored = []
        for rank, chunk in enumerate(retrieved[:3]):
            for sentence in _sentences(chunk.text):
                tokens = set(tokenize(sentence))
                if not tokens:
                    continue
                overlap = len(query_tokens & tokens) / max(1, len(query_tokens))
                scored.append((overlap, -rank, chunk.chunk_id, sentence))

        scored.sort(key=lambda item: (-item[0], item[1], item[3]))
        chosen = scored[:max_sentences]
        # Restore document order so the answer reads coherently rather than by score.
        chosen.sort(key=lambda item: item[1])

        text = ". ".join(sentence.strip().rstrip(".") for _o, _r, _cid, sentence in chosen)
        if text and not text.endswith("."):
            text += "."
        if len(text) > max_chars:
            text = text[:max_chars].rstrip() + "..."

        citations = []
        for _o, _r, chunk_id, _sentence in chosen:
            if chunk_id not in citations:
                citations.append(chunk_id)

        coverage = chosen[0][0] if chosen else 0.0
        return text, citations, self._usage(query, text), coverage

    def _usage(self, query: str, text: str) -> Dict[str, int]:
        # Deterministic proxy: 4 characters per token. Tagged as `estimate` wherever reported;
        # it exists so cost arithmetic has a stable input, not because it is a measurement.
        input_tokens = max(1, len(query) // 4)
        output_tokens = max(1, len(text) // 4)
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        }


class OpenAICompatibleProvider:
    """Thin client for a chat-completions endpoint. Opt-in only (never the CI path)."""

    name = "openai-compatible"

    def __init__(self, endpoint: str, api_key_env: str = "OPENAI_API_KEY", model: str = ""):
        self.endpoint = endpoint
        self.api_key_env = api_key_env
        self.model = model
        self.version = model or "unspecified"

    def _api_key(self) -> str:
        key = os.environ.get(self.api_key_env, "")
        if not key:
            raise ProviderUnavailable(
                "%s is not set; the deterministic provider is the only hermetic path" % self.api_key_env)
        return key

    def generate(self, prompt: str, **kwargs):
        import urllib.request

        payload = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        }).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=payload,
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer " + self._api_key()},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"]


def _sentences(text: str) -> List[str]:
    return [s.strip() for s in SENTENCE_SPLIT.split(text or "") if s.strip()]
