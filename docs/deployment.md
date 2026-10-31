# Running the service

## The harness gate

The same repository carries its own gate, and it runs the same commands a reviewer would:

```bash
python scripts/verify_requirements.py     # every requirement row, ~8 s
python scripts/run_tests.py               # the hermetic suite, ~8 s
```

Both are concurrent: the requirement rows and the generators run in parallel, and the test
classes run in worker processes. `--serial` and `--jobs 1` force the one-at-a-time path.

## One command

```bash
python scripts/start.py
```

That single command:

1. generates the corpus if it is not already built (deterministic, seeded - no download);
2. indexes it **in memory** - measured at ~19 ms for 32 documents / 53 chunks;
3. serves the API on `http://127.0.0.1:8174`.

There is no database, no embedding model, no ETL step and no `pip install`. The reviewer needs
Python 3.11+ and nothing else. Regenerating the corpus is possible
(`python scripts/build_corpus.py`) but never required.

### If the port is already taken

The default port is 8174, and if any requested port is occupied by another local service the
server **moves to the first free port above it and prints the real URL** rather than dying or
silently sharing the address:

```
port 8174 is already in use by another service on this machine; using 8175 instead
Enterprise RAG Service listening on http://127.0.0.1:8175
```

The scan is deterministic (`find_free_port` in `src/ragserve/api.py`): 8174 -> 8175 -> 8176 ...,
so the fallback is a port a reviewer can retype rather than a random ephemeral one. `--port 0`
asks the OS for any free port, and if the whole 20-port span is taken the OS is asked as a last
resort. A bind-race (port taken between the check and the bind) also falls back rather than
raising.

This matters because a bind to an occupied port can *appear* to succeed on Windows when both
sockets carry `SO_REUSEADDR`, which would leave the reviewer looking at somebody else's
application. The port is therefore probed before it is trusted, not after a failed bind.

## What you get

| URL | What it is |
|---|---|
| `/` | a self-contained landing page: the endpoints and a copy-pasteable request |
| `/api/health` | provider, corpus version, chunk count, index build time, uptime |
| `/api/providers` | the generation providers this service can talk to |
| `/api/ask` | `POST {question, session_id?, provider?, endpoint?, api_key?, model?}` |

Example:

```bash
curl -s http://127.0.0.1:8174/api/health
curl -s -X POST http://127.0.0.1:8174/api/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"How many days of annual leave do full-time employees accrue?"}'
```

## Providers

The service is headless: a provider is chosen per request, or pinned at start-up with
`--provider`.

| Provider | Needs | Notes |
|---|---|---|
| `deterministic` (default) | nothing | Offline, reproducible, what CI verifies. Answers are composed from retrieved passages, so grounding is testable. |
| `codebuddy-serve` | a local CLI serve on loopback | `--provider codebuddy-serve --endpoint http://127.0.0.1:8788 --model hy3`. Non-loopback endpoints are refused by the adapter. |
| `openai-compatible` | your endpoint + key | Any chat-completions endpoint. The key is used for that request only: never logged, never written to disk. |

Bring-your-own-key from the command line:

```bash
export OPENAI_API_KEY=sk-...
python scripts/start.py --provider openai-compatible \
  --endpoint https://api.example.com/v1 --model your-model
```

The same key can be sent per request in the `api_key` field; it is used for that request only and is
never stored.

### Embeddings (opt-in, independent of the generation provider)

Embeddings ship with a **keyless** default: a local **bge-m3** served by `llama.cpp`
(`python scripts/setup_models.py` installs it), reached with no credential and no third-party
Python package. With no model server running, the service falls back **loudly** to the offline
deterministic hashing backend, so a cold clone still starts with no credential at all. To point at
a hosted model instead, set the three fields in `configs/retrieval.json` -
`embedding_endpoint`, `embedding_model`, `embedding_api_key_env` - and start with:

```bash
python scripts/start.py --embedding-provider openai-compatible
```

Any OpenAI-compatible `/v1/embeddings` service works (SiliconFlow, DashScope, a local Ollama).
Point the three fields at it to change models; this is a configuration change, never a code
change. If the key is missing the server fails loudly (`ProviderUnavailable`) instead of silently
degrading to the deterministic backend.

## Multi-turn

Send the same `session_id` on follow-up questions. The service keeps the last turns in memory
(bounded), and anaphoric follow-ups ("How many of them can be carried over?") are resolved
against the previous question - the rewrite is visible in the trace (`query_rewritten`).

## Load testing the service

```bash
python scripts/run_bench.py --http --concurrency 5 --requests 30 --assert
```

Starts the API in-process with the cache **disabled** and drives real HTTP requests, so the
numbers cannot be a cache hit. Exits non-zero if p90 exceeds the 10 s bound or any request
errors. Latest result: p50 36.7 ms, p90 148.3 ms, 0 errors.

## Explicit non-goals

This is a reviewable reference service, not a production deployment:

* no TLS, no authentication, no rate limiting - bind it to loopback and keep it local;
* single process, in-memory state (sessions and cache do not survive a restart);
* in-memory index, which is correct at this corpus size and would be replaced by an ANN index
  plus a vector store at millions of chunks (ADR 0002 records the reasoning).
