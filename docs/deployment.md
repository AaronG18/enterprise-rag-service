# Running the service

## One command

```bash
python scripts/start.py
```

That single command:

1. generates the corpus if it is not already built (deterministic, seeded - no download);
2. indexes it **in memory** - measured at ~19 ms for 32 documents / 53 chunks;
3. serves the API and the built UI on `http://127.0.0.1:8174` and opens your browser.

There is no database, no embedding model, no ETL step and no `pip install`. The reviewer needs
Python 3.11+ and nothing else. Regenerating the corpus is possible
(`python scripts/build_corpus.py`) but never required.

### If the port is already taken

The default port is 8174, and if any requested port is occupied by another local service the
server **moves to a free port and prints the real URL** rather than dying or silently sharing the
address:

```
NOTE: port 8174 is already in use by another service on this machine; choosing a free port instead.
Enterprise RAG Service listening on http://127.0.0.1:49510
```

This matters because a bind to an occupied port can *appear* to succeed on Windows when both
sockets carry `SO_REUSEADDR`, which would leave the reviewer looking at somebody else's
application. The port is therefore probed before binding, and a taken port is skipped.

## What you get

| URL | What it is |
|---|---|
| `/` | React + AntD UI: provider selector, chat, citations, inspectable trace |
| `/api/health` | provider, corpus version, chunk count, index build time, uptime |
| `/api/providers` | what the UI needs to render the provider selector |
| `/api/ask` | `POST {question, session_id?, provider?, endpoint?, api_key?, model?}` |

Example:

```bash
curl -s http://127.0.0.1:8174/api/health
curl -s -X POST http://127.0.0.1:8174/api/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"How many days of annual leave do full-time employees accrue?"}'
```

## Providers (the UI selector)

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

The same key can be pasted into the UI per session; it lives in browser memory only and is sent
per request.

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
