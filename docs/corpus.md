# Corpus design (EPIC #2)

## Why the corpus is synthetic

Three reasons, all load-bearing:

1. **Publishable** - RULES R6 forbids internal or third-party document text. Nothing here is
   copied from anywhere.
2. **Deterministic** - the corpus is generated from a seed with no wall-clock input, so a
   quality number measured today is comparable with one measured after twenty commits.
3. **Controllable** - the "scanned PDF" portion, language balance and chunk geometry are
   parameters, not accidents. That is what makes EPIC 6 comparisons meaningful.

## Composition

| Axis | Values |
|---|---|
| Families | employee handbook, compliance guides, technical specifications, architecture documents |
| Languages | `en`, `zh` |
| Documents | 4 per family per language = 32 |
| Sections | 3 per document |
| Chunks | 53 at `chunk_target_chars` = 220 / `chunk_overlap_chars` = 44 |
| Scanned portion | `ocr_ratio` = 0.08 -> 3 documents flagged `ocr=true` (0.094) |

Content carries concrete figures (days, thresholds, byte limits, percentages) on purpose:
retrieval comparisons need facts that are unambiguous to match, and later evaluation needs
answers that are either right or wrong rather than "roughly right".

## Processing pipeline

```
content.py  ->  documents (clean_body = body)
           ->  OCR subset selection (seeded) + degrade_text()   # body becomes noisy, clean_body retained
           ->  chunk_text() per section, punctuation-based, target + overlap
           ->  manifest (corpus_version = sha256(generator|seed|config|documents))
```

## Design decisions and the trade-off accepted

| Decision | Alternative rejected | Why | Cost accepted |
|---|---|---|---|
| Punctuation-based sentence splitting | whitespace tokenisation | whitespace splitting silently breaks Chinese (no spaces), producing one oversized chunk or empty chunks | chunk starts are not always sentence-aligned; overlap compensates |
| Chunk over the whole document | per-section chunking | section bodies are ~120-200 chars, so per-section chunking produced exactly one chunk per section and overlap never happened at all (caught by `test_overlap_between_consecutive_chunks`) | a chunk can span two sections; `section` metadata is the heading the chunk *starts* in |
| Chunk size 220 chars / overlap 44 | larger, non-overlapping chunks | short policy facts need to survive boundaries to be retrievable | duplicated text across chunks, slightly higher index size |
| Keep `clean_body` alongside degraded `body` | overwrite in place | degradation must be measurable, and diagnosis (EPIC 8) needs to distinguish "retrieval is bad" from "the text is damaged" | extra field in artifacts |
| Deterministic OCR selection by `random.Random(seed)` | hashing/`uuid` | same seed -> same subset, no environment dependence | selection pattern changes if doc count changes (acceptable; corpus_version changes too) |
| Content is literal, not randomly generated | template/random word assembly | random assembly produces text that reads like noise, which makes retrieval results uninterpretable | writing and maintaining content costs more effort |

## Reproducing

```bash
python scripts/build_corpus.py
```

Output lands in `artifacts/corpus/<corpus_version>/`. Every evaluation artifact later
records the `corpus_version` it was produced against, which is what makes a before/after
comparison legitimate.
