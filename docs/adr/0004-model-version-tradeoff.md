# ADR 0004: model-version trade-off (measured)

## Status

Accepted for the model-backed lane. The deterministic provider remains the CI baseline; this
decision only governs which real model version to use when real generation runs.

## Context

The brief asks for a model-version selection rationale with explicit quality / cost / latency
trade-offs. Guessing is not acceptable, so both candidates were run over the same 30-case set
and the same three retrieval configurations (180 calls, `docs/eval/model-backed.md`).

Candidates: `hy3` and `deepseek-v4.1-flash`, both taken from the CLI's documented model list
(`codebuddy --help`), chosen as a main-tier vs a flash-tier option so the trade-off is real.

## Measured comparison

| Axis | hy3 | deepseek-v4.1-flash | Winner |
|---|---|---|---|
| Faithfulness | 0.639-0.684 | 0.667-0.717 | flash |
| Answer compliance | 0.733-0.743 | 0.882-0.904 | **flash (clearly)** |
| Refusal appropriateness | 0.733-0.833 | 0.833-0.900 | **flash** |
| Style consistency | 0.819-0.822 | 0.964-0.971 | **flash (clearly)** |
| Retrieval metrics | identical (generator-independent) | identical | tie |
| p50 latency | 1988-3307 ms | 1749-1911 ms | flash |
| p95 latency | 4938-6147 ms | 2421-2698 ms | **flash** |
| Tokens per call (est.) | 322-328 | 321-329 | tie |
| Monetary cost | **N/A** | **N/A** | unknown |

## Decision

Use the **flash-tier model** as the default for the model-backed lane: it wins on every axis we
could measure - compliance, refusal appropriateness, style, and it is roughly 2x faster at p95.

Keep `hy3` as the escalation option: it is the main-tier model and may win on harder, longer or
more reasoning-heavy questions, which this 30-case factual policy set does not exercise. That is
stated as a hypothesis, not a finding.

## What is measured and what is not

* **Measured:** every cell above except monetary cost, from 180 real calls on corpus
  `bea626ce863a0e44`, provenance `model-backed`.
* **Not measured:** monetary cost. No price list was available for these versions, so
  `configs/pricing.json` keeps null prices and the report refuses to print a number. Cost is
  therefore expressed as tokens per 1,000 calls (~322k tokens per 1,000 calls at ~322
  tokens/call); converting it to money requires the operator to fill the price list.
* **Not measured:** behaviour on long, multi-hop or reasoning-heavy questions.

## Consequences

* The model-backed lane now has a defensible default and a documented escalation path.
* The result contradicts the intuitive "bigger model is better": on this corpus the flash-tier
  model is better *and* faster. Recording that is the point of measuring instead of assuming.
* Both models miss the faithfulness (0.85) and refusal (0.90) targets. That is a pipeline
  problem (citation attribution), not a model choice - see the gaps section in
  `docs/eval/model-backed.md`.
