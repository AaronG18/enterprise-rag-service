# ADR 0003: synthetic, seeded corpus

## Status

Accepted. The corpus is generated from literal content with a fixed seed; no real documents.

## Context

The service is a QA layer over an internal-style knowledge base: employee handbook, compliance
guides, technical specifications, architecture documents, bilingual, with a scanned-PDF subset.
Shipping real internal documents is not possible, and a corpus that changes between runs makes
every quality number incomparable.

## Decision

* Content is **literal** (written passages with concrete figures), not randomly assembled words.
* Generation is deterministic: seeded PRNG, no wall clock, no UUIDs.
* `corpus_version` = hash of generator version, seed, config and document content; every
  evaluation artefact records it.
* ~8% of documents pass through an OCR-noise transform and are flagged `ocr=true`.

## Alternatives rejected

| Alternative | Why rejected |
|---|---|
| Real internal documents | not publishable; RULES R6 |
| Scraped public documents | licensing unclear, and content would not match the four required families |
| Randomly assembled word soup | reads like noise, so retrieval results are uninterpretable and failures cannot be diagnosed |
| Corpus committed as static files | the OCR ratio, language mix and chunk geometry would no longer be parameters, so no experiment could vary them |

## Cost accepted

* 32 documents / 53 chunks is small: recall metrics saturate, and configuration differences are
  sometimes within noise. Expanding the corpus is the first remedy if metrics stop discriminating.
* Synthetic text is cleaner than real prose, so absolute quality numbers here are optimistic
  relative to a real corpus. The numbers are therefore reported as pipeline evidence, never as a
  claim about production data.
* Maintaining literal content costs more effort than generating it procedurally.
