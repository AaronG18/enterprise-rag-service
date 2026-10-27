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
                body = _strip_heading(sentence)
                tokens = set(tokenize(body))
                if not tokens:
                    continue
                overlap = len(query_tokens & tokens) / max(1, len(query_tokens))
                # Retrieval rank must dominate: scoring on overlap alone let a lower-ranked
                # chunk with incidental term overlap outrank the right answer (measured bug).
                damped = overlap / (1.0 + 0.5 * rank)
                scored.append((damped, -rank, chunk.chunk_id, body))

        scored.sort(key=lambda item: (-item[0], item[1], item[3]))
        chosen = scored[:max_sentences]
        # Restore document order so the answer reads coherently rather than by score.
        chosen.sort(key=lambda item: item[1])

        # Join with a space, not ". ": Chinese sentences already end with their own
        # punctuation, and joining on ". " produced stray "." fragments that the faithfulness
        # scorer then counted as unsupported claims.
        text = " ".join(sentence.strip() for _o, _r, _cid, sentence in chosen)
        if text and not text.endswith((".", "。", "!", "?", "！", "？")):
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


def is_loopback(url: str) -> bool:
    """Only loopback endpoints are allowed: this provider may see user queries and retrieved
    content, so a remote endpoint would be a data-exfiltration path, not a config choice."""
    from urllib.parse import urlparse

    host = (urlparse(url or "").hostname or "").strip("[]").lower()
    return host in ("127.0.0.1", "localhost", "::1", "")


class CodeBuddyServeProvider:
    """Real generation through the local CodeBuddy CLI `--serve` endpoint.

    Contract (verified against the running server, not assumed):

    * `POST /api/v1/runs` with `{"id", "type": "message", "payload": {"text": ...}}`
      returns `{"data": {"runId": ...}}`
    * `GET /api/v1/runs/{runId}/stream` is SSE; `event: message` carries
      `content.markdown` (fallback `content.text`), `event: done` ends the run.
    * **No token usage is returned** - measured: message events carry only
      agent/content/replyTo/status/version. Token counts here are therefore estimates and
      must be reported with provenance `estimate`.

    The model version is fixed when the CLI is started (`--model`), because passing a model in
    the request body is not echoed back and cannot be verified.
    """

    name = "codebuddy-serve"

    def __init__(self, base_url: str, model: str, timeout: float = 120.0):
        if not is_loopback(base_url):
            raise ProviderUnavailable(
                "refusing non-loopback endpoint %r: this provider would send user queries and "
                "retrieved content off-host" % base_url)
        self.base_url = (base_url or "").rstrip("/")
        self.model = model
        self.version = model
        self.timeout = timeout

    # -- generation -------------------------------------------------------
    def generate_from_prompt(self, prompt: str, retrieved: List | None = None,
                             max_chars: int | None = None):
        text = self._complete(prompt)
        if max_chars and len(text) > max_chars:
            text = text[:max_chars].rstrip() + "..."
        return text, self._usage(prompt, text)

    # -- transport ---------------------------------------------------------
    def _complete(self, prompt: str) -> str:
        import json as _json
        import urllib.error
        import urllib.request
        import uuid

        headers = {"Content-Type": "application/json", "X-CodeBuddy-Request": "1"}
        body = _json.dumps({"id": "cb-" + uuid.uuid4().hex, "type": "message",
                             "payload": {"text": prompt}}, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(self.base_url + "/api/v1/runs", data=body,
                                        headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                created = _json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ProviderUnavailable("run creation failed HTTP %s" % exc.code) from exc
        except Exception as exc:  # noqa: BLE001 - surfaced as a clear provider error
            raise ProviderUnavailable(
                "CodeBuddy serve unreachable at %s: %s: %s" % (self.base_url, type(exc).__name__,
                                                               exc)) from exc

        try:
            run_id = created["data"]["runId"]
        except (KeyError, TypeError) as exc:
            raise ProviderUnavailable("no runId in response: %s" % str(created)[:160]) from exc

        stream_req = urllib.request.Request(
            self.base_url + "/api/v1/runs/%s/stream" % run_id, headers=headers, method="GET")
        pieces = []
        try:
            with urllib.request.urlopen(stream_req, timeout=self.timeout) as response:
                event = None
                for raw in response:
                    line = raw.decode("utf-8", "replace").rstrip("\r\n")
                    if line.startswith("event:"):
                        event = line[len("event:"):].strip()
                    elif line.startswith("data:"):
                        data = line[len("data:"):].strip()
                        if not data:
                            continue
                        try:
                            obj = _json.loads(data)
                        except _json.JSONDecodeError:
                            continue
                        if event == "message":
                            content = obj.get("content") or {}
                            piece = content.get("markdown") or content.get("text")
                            if piece:
                                pieces.append(piece)
                        elif event == "done":
                            break
        except Exception as exc:  # noqa: BLE001
            raise ProviderUnavailable("stream failed: %s: %s" % (type(exc).__name__, exc)) from exc

        text = "".join(pieces).strip()
        if not text:
            raise ProviderUnavailable("empty completion (filtered or timed out)")
        return text

    def _usage(self, prompt: str, text: str) -> Dict[str, int]:
        """Estimated: the endpoint returns no usage. Provenance `estimate` wherever reported."""
        input_tokens = max(1, len(prompt) // 4)
        output_tokens = max(1, len(text) // 4)
        return {"input_tokens": input_tokens, "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens}


SOURCES_LINE = re.compile(r"(?im)^\s*(?:sources?|来源|参考)\s*[:：].*$")


def strip_sources_line(text: str) -> str:
    """Remove a trailing `Sources: [id] [id]` line from an answer.

    Measured reason this exists: asking the model for a Sources line (to make citations
    explicit) caused the scorer to count that line as an answer *claim*. It never appears in
    the cited chunk, so every answer lost one claim mechanically - faithfulness fell from
    ~0.67 to ~0.45 on identical cases - and the answer no longer ended in sentence
    punctuation, which also cost style consistency. Citations are parsed before stripping, so
    no information is lost.
    """
    if not text:
        return text
    cleaned = SOURCES_LINE.sub("", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def attribute_evidence(text: str, retrieved: List, sentences_fn=None) -> List[str]:
    """Attribute each answer sentence to its best-matching retrieved chunk.

    Why this exists: a generated answer often supports its claims without writing a chunk id in
    the exact marker format. Treating that as "no evidence" produced 32 wrong refusals out of 44
    (measured). Attributing to the best-matching chunk answers "where did this come from".

    What it deliberately does NOT do: it does not gate on a support threshold, so it cannot
    inflate faithfulness. Faithfulness is scored separately and unchanged - a paraphrased claim
    attributed to its best chunk still scores below 1.0 if the support is weak.
    """
    from ..retrieval.text import tokenize

    splitter = sentences_fn or _sentences
    chunk_tokens = [(chunk, set(tokenize(chunk.text))) for chunk in retrieved or []]
    attributions: List[str] = []
    for sentence in splitter(text or ""):
        tokens = set(tokenize(sentence))
        if not tokens or not chunk_tokens:
            continue
        best_id, best_score = None, -1.0
        for chunk, ctokens in chunk_tokens:
            score = len(tokens & ctokens) / max(1, len(tokens))
            if score > best_score:
                best_id, best_score = chunk.chunk_id, score
        if best_id and best_id not in attributions:
            attributions.append(best_id)
    return attributions


def extract_citations(text: str, valid_chunk_ids) -> List[str]:
    """Pull `[chunk-id]` markers out of a generated answer, keeping only ids we retrieved."""
    import re

    valid = set(valid_chunk_ids or ())
    found = []
    for match in re.findall(r"\[([A-Za-z0-9_.\-]+:\d{4})\]", text or ""):
        if match in valid and match not in found:
            found.append(match)
    return found


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
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ProviderUnavailable("HTTP %s: %s" % (exc.code, exc.read().decode("utf-8", "ignore")[:200])) from exc
        except Exception as exc:  # noqa: BLE001 - surfaced as a clear provider error
            raise ProviderUnavailable("%s: %s" % (type(exc).__name__, exc)) from exc
        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderUnavailable("unexpected response shape: %s" % str(body)[:200]) from exc

    def generate_from_prompt(self, prompt: str, retrieved: List | None = None,
                             max_chars: int | None = None):
        """Same interface as the CodeBuddy provider, so the service can dispatch uniformly.

        Returns the text and a usage estimate tagged as such - the caller decides how to
        present it.
        """
        text = self.generate(prompt)
        if max_chars and len(text) > max_chars:
            text = text[:max_chars].rstrip() + "..."
        input_tokens = max(1, len(prompt) // 4)
        output_tokens = max(1, len(text) // 4)
        return text, {"input_tokens": input_tokens, "output_tokens": output_tokens,
                      "total_tokens": input_tokens + output_tokens}


def _sentences(text: str) -> List[str]:
    return [s.strip() for s in SENTENCE_SPLIT.split(text or "") if s.strip()]


def _strip_heading(sentence: str) -> str:
    """Chunk text starts with heading lines; carrying them into an answer reads like noise."""
    if "\n" in sentence:
        sentence = sentence.rsplit("\n", 1)[-1].strip()
    return sentence
