# ADR 0001: generation provider selection

## Status

Accepted: deterministic provider is the default and the CI-enforced baseline. A hosted model
provider is available behind the same interface and is opt-in.

## Context

The service must answer from retrieved context, be evaluable reproducibly, and support swapping
the model version without a rewrite. Quality, cost and latency pull in different directions, so
the choice needs an explicit trade-off record rather than a default nobody remembers making.

## Decision

Two providers behind one interface (`ragserve/generation/providers.py`):

1. `DeterministicProvider` - composes answers from verbatim sentences of retrieved chunks. Default.
2. `OpenAICompatibleProvider` - thin chat-completions client. Opt-in, never used in CI.

## Trade-offs

| Axis | Deterministic | Hosted model |
|---|---|---|
| Quality (measured) | Faithfulness 1.0, compliance 0.90, style 1.0 - but only because answers are copied from context; this is the **pipeline floor**, not a model score | Unknown in this repository: **no live model was measured** |
| Reproducibility | Byte-identical output per input; runs offline in CI | Varies by model version and sampling; unreproducible across time |
| Cost | Zero marginal cost | Requires a price list; see `configs/pricing.json` |
| Latency | ~5-10 ms end to end (this corpus) | Dominated by the network round trip |

## What is measured and what is not

Stated plainly so nobody reads the table as a benchmark comparison:

* **Measured:** every number attributed to the deterministic provider, on corpus
  `bea626ce863a0e44`, 27 labelled cases, provenance `deterministic`.
* **Not measured:** any hosted-model quality, cost or latency figure. No model endpoint was
  called while building this repository. The "Unknown" cell above is genuine.
* Anyone adding a hosted provider must run the same evaluation, tag the results `model-backed`,
  and place them **next to** the deterministic floor rather than replacing it.

## Consequences

* Claims in this repository are reproducible by anyone with `python` and no credentials.
* The deterministic floor cannot tell us how a real model behaves; it can only prove the pipeline
  around the model never fabricates, always cites, and refuses when it should.
* If a hosted model is introduced, `docs/eval/retrieval-comparison.md` must be updated with a
  second table rather than overwritten.
