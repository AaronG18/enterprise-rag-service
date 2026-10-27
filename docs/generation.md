# Generation, refusal, injection defence and PII (EPIC #4)

## Request flow

```
query
 -> injection check on the query          -> refuse `injection_detected`
 -> safety blocklist                        -> refuse `safety_trigger`
 -> multi-turn resolution (anaphora only)   -> resolved_query (recorded in trace)
 -> retrieve (EPIC #3)
 -> coverage + confidence computed          -> refuse `out_of_scope` / `low_confidence`
 -> prompt assembly: delimited + neutralised context
 -> generate (deterministic provider by default)
 -> citations required, else refuse
 -> PII redaction on the answer
 -> trace (also PII-redacted before it is emitted as a log record)
```

## Grounding, enforced mechanically

The deterministic provider builds answers **only from verbatim sentences of retrieved
chunks**. That is a constraint, not a limitation of ambition: it makes grounding testable.
`test_answer_is_grounded_in_cited_chunks` asserts that every answer sentence appears in a cited
chunk. A free-form LLM cannot offer that guarantee, which is exactly why the deterministic
provider is the baseline CI enforces and a model provider is an opt-in adapter.

## Confidence: a defined number, not a vibe

```
confidence = 0.6 * coverage + 0.4 * score_share
coverage    = |query tokens present in the top chunk| / |query tokens|
score_share = top fused score / sum of fused scores in the result set
```

Both components are logged, so a refusal caused by `min_confidence` can be explained after the
fact - which is what EPIC 8 (diagnosis) requires.

## Refusal reason codes

| Code | Trigger | Guidance tells the user |
|---|---|---|
| `no_context` | retrieval returned nothing | rephrase or narrow to a document family |
| `out_of_scope` | term coverage ~0 | which areas the knowledge base actually covers |
| `low_confidence` | coverage present but confidence below threshold | ask more specifically, quote the section |
| `safety_trigger` | request asks for personal/restricted data | ask for the governing policy instead |
| `injection_detected` | query tries to override instructions | restate without instructions to the assistant |

Every refusal carries guidance text. A refusal that only says "I cannot answer" is treated as a
defect, because a monitored refusal *rate* is useless if the user learns nothing from it.

## Injection defence

Retrieved content is untrusted input, so it is handled twice over:

1. **Delimited** - context sits between `<<<RETRIEVED_CONTENT>>>` markers and the prompt states
   that content inside them is data, never instructions.
2. **Neutralised** - instruction-like spans (English and Chinese patterns) are replaced with
   `[filtered: instruction-like text removed]` before the prompt is built.

Detection is recorded on the trace (`injection_detected`), so a spike is observable rather than
silent.

## PII

Detection covers email, CN mobile numbers, 18-digit national IDs and payment card numbers.
Masking preserves shape (domain kept for email, last four kept for cards) so support can
recognise which value was involved without seeing it. Redaction is applied to **both** the answer
payload and the log record - the second half is the leak people miss.

## Known, measured limitations

* **Hashing embeddings collide.** A gibberish query still scores ~0.11 against unrelated chunks,
  while true matches start around 0.14. The margin is too thin to threshold on, so those weak
  hits are allowed through retrieval and then rejected by the coverage gate, which classifies
  them as `out_of_scope`. Documented rather than hidden; `test_gibberish_refuses_as_out_of_scope`
  pins the behaviour.
* **OCR-degraded documents answer worse.** "How often is privileged access reviewed?" targets an
  OCR-degraded document, and its confidence measurably drops below that of an equivalent clean
  query. `test_ocr_degradation_lowers_confidence` pins this; it is the intended seed of an EPIC 8
  diagnosis case.
* **The OpenAI-compatible provider is untested against a live endpoint.** It exists to prove the
  provider interface is real; no test exercises it, and CI never calls it (INV-1). Any number
  produced with it must be tagged `model-backed`.
* Token usage from the deterministic provider is a **character/4 estimate**, tagged `estimate`
  wherever reported. It exists so cost arithmetic has a stable input.
