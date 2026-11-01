# Log field dictionary

One JSON object per line, one line per stage. A request is reconstructed by filtering on
`workflow_id` and ordering by `ts`.

`tests/test_logging.py::test_log_field_dictionary_covers_emitted_fields` fails if the code emits
a field that is not documented here, so this file cannot drift silently.

## Common fields (every line)

| Field | Type | Meaning |
|---|---|---|
| `ts` | float | Emit time from the injected clock. Deterministic in tests. |
| `workflow_id` | string | Correlation id for one request; identical on every stage of that request. |
| `stage` | string | One of `request`, `retrieval`, `decision`, `generation`, `response`. |
| `event` | string | Stage-specific event name, e.g. `request_start`, `retrieval_done`. |

## Stage: request

| Field | Meaning |
|---|---|
| `query` | User query **after PII redaction**. |
| `resolved_query` | Query actually used for retrieval (may include the previous turn after multi-turn resolution). |
| `query_rewritten` | Whether multi-turn resolution changed the query. |
| `corpus_version` | Corpus the request ran against; also part of the cache key. |

## Stage: retrieval

| Field | Meaning |
|---|---|
| `retrieval_mode` | `vector_only` or `hybrid`. |
| `rerank_enabled` | Whether the reranker ran. |
| `retrieved_count` | Number of chunks returned. |
| `retrieved_chunk_ids` | Chunk ids in ranked order. |

## Stage: decision

| Field | Meaning |
|---|---|
| `coverage` | Fraction of query tokens present in the top chunk. |
| `confidence` | `0.6 * coverage + 0.4 * score_share`. |
| `refusal_reason` | Reason code, or `null` when the request proceeds. |

## Stage: generation

| Field | Meaning |
|---|---|
| `citations` | Chunk ids the answer was composed from. |
| `usage` | Token usage object (`input_tokens`, `output_tokens`, `total_tokens`). |
| `provider` | Provider name, e.g. `deterministic`. |
| `model_version` | Provider/model version string. |

## Stage: response

| Field | Meaning |
|---|---|
| `refused` | Whether the request was refused. |
| `reason_code` | Refusal reason code when refused. |
| `citations` | Citations of the returned answer (empty on refusal). |
| `text` | Answer text after redaction. |
| `cache_hit` | Whether this response came from the cache. Benchmarks must exclude these. |
| `cache_layer` | `exact` or `semantic` on a hit, absent otherwise. |
| `latency_ms` | End-to-end latency of the API response in milliseconds, measured around the whole call - this is the number the performance target is about, so it belongs in the dictionary too. |
| `usage` | Token usage of this response. |

## Redaction

Every string field is passed through `redact_record` at emit time, so raw PII never reaches the
sink even if a caller forgets to redact. See `docs/generation.md` for the detected shapes.
