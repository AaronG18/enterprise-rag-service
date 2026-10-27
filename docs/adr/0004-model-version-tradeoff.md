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

Best configuration per model, after the INC-003 fixes (180 calls, corpus `bea626ce863a0e44`):

| Axis | hy3 (hybrid) | flash (hybrid) | Winner |
|---|---|---|---|
| Faithfulness | **0.8913** | 0.7609 | **hy3 (clearly)** |
| Answer compliance | **0.965** | 0.887 | **hy3 (clearly)** |
| Refusal appropriateness | 0.9000 | 0.9000 | tie |
| Style consistency | 0.8957 | **0.9565** | flash |
| Retrieval metrics | identical | identical | tie |
| p50 latency | 2519 ms | 1749 ms | flash |
| p95 latency | 6147 ms | 2466 ms | **flash** |
| Tokens per call (est.) | 328 | 328 | tie |
| Monetary cost | **N/A** | **N/A** | unknown |

## Decision

Use **hy3 with hybrid retrieval** as the default for the model-backed lane: it is the only
configuration that meets all advanced targets (faithfulness >= 0.85, refusal appropriateness >=
0.90, style >= 0.85, compliance 0.965).

Use **flash** when latency dominates: it is roughly 2.5x faster at p95 and scores higher on style
consistency, at the cost of faithfulness (0.76 vs 0.89) and compliance (0.89 vs 0.97).

This reverses the earlier recommendation in this ADR, which favoured flash. That earlier call was
made on the first model-backed run, before two defects in our own pipeline (wrong refusals and a
Sources line counted as a claim, see INC-003) were fixed. Once those were fixed hy3's answers
scored substantially better, so the recommendation follows the corrected measurement - and the
reversal is recorded rather than the old text quietly edited.

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
