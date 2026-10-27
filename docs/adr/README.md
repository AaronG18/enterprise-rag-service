# Architecture decision records

| ADR | Decision |
|---|---|
| [0001](0001-generation-provider-selection.md) | Deterministic provider is the CI-enforced baseline; hosted model is opt-in. States explicitly that no hosted model was measured. |
| [0002](0002-retrieval-strategy.md) | Hybrid retrieval with Reciprocal Rank Fusion; reranking is separately toggleable. |
| [0003](0003-synthetic-corpus.md) | Corpus is synthetic and seeded, with a version hash stamped into every artefact. |
| [0004](0004-model-version-tradeoff.md) | Flash-tier model is the default for real generation; measured over 180 calls, monetary cost recorded as N/A. |

Conventions for these records: state the decision, the alternatives rejected with reasons, the
measured consequences, and the cost accepted. An ADR that only records what was chosen is a
commit message with extra steps.
