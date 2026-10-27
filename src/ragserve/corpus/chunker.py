"""Chunking.

Design constraints that drive the implementation:

* **Bilingual.** Chinese has no whitespace word boundaries, so splitting on spaces would
  produce one giant chunk or nothing useful. We split on *punctuation* instead, and the
  punctuation set covers both languages (。！？； and . ! ? ;).
* **Bounded size, with overlap.** Chunk ends are aligned forward to a sentence boundary
  (capped, so one long sentence cannot blow up the chunk), and each following chunk starts
  `overlap` characters before the previous end, so facts spanning a boundary stay retrievable.
* **Stable ids.** Identical input produces identical chunk ids; citation tests in later
  EPICs depend on that.
"""
from __future__ import annotations

import re
from typing import List, Tuple

SENTENCE_END = re.compile(r"[。！？；.!?;\n]")

# A sentence may stretch a chunk past the target, but only this much.
MAX_STRETCH = 1.6


def sentence_bounds(text: str) -> List[Tuple[int, int]]:
    """Return (start, end) spans for each sentence, in order, covering the whole text."""
    bounds: List[Tuple[int, int]] = []
    start = 0
    for match in SENTENCE_END.finditer(text):
        end = match.end()
        if end > start:
            bounds.append((start, end))
        start = end
    if start < len(text):
        bounds.append((start, len(text)))
    return [(s, e) for s, e in bounds if text[s:e].strip()]


def chunk_text(text: str, target: int, overlap: int) -> List[Tuple[int, int]]:
    """Split `text` into (start, end) spans of roughly `target` chars with `overlap`."""
    if not text or not text.strip():
        return []
    if overlap >= target:
        raise ValueError("overlap must be smaller than target: %r >= %r" % (overlap, target))

    sentences = sentence_bounds(text)
    n = len(text)
    spans: List[Tuple[int, int]] = []
    start = 0
    limit = int(target * MAX_STRETCH)

    while start < n:
        end = min(start + target, n)
        if end < n:
            for s, e in sentences:
                if e > end:
                    if e <= start + limit:
                        end = e
                    break
        end = min(end, n)
        if end <= start:
            end = min(start + target, n)
        spans.append((start, end))
        if end >= n:
            break
        start = max(start + 1, end - overlap)
    return spans
