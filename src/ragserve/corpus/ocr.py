"""OCR degradation: emulating what scanned-PDF text extraction does to a document.

Why it exists: a small portion of the corpus being "scanned" is part of the brief. Scanned
text degrades retrieval in a specific, recognisable way (character confusion, lost
spacing), and later EPICs need that effect present *and labelled* so contaminated chunks
can be identified instead of silently dragging metrics down.

Determinism (RULES R3): all randomness comes from a seeded PRNG derived from the corpus
seed and the document id, so the same document always degrades identically.
"""
from __future__ import annotations

import random

# Character confusions typical of OCR. ASCII digits and letters appear in both EN and ZH
# text, which is why this map degrades both languages.
CONFUSIONS = {
    "l": "1",
    "1": "l",
    "I": "1",
    "O": "0",
    "0": "O",
    "5": "S",
    "8": "B",
    "rn": "m",
    "cl": "d",
}

# CJK confusions. Without these an ASCII-only confusion map leaves a pure Chinese document
# byte-identical after "scanning" - measured: the corpus grew to mostly Chinese documents and
# one of them degraded to exactly the original, so the scanned subset did not exist for it.
# These pairs are the ones real recognisers mix up: visually near-identical glyphs.
CJK_CONFUSIONS = {
    "日": "曰",
    "曰": "日",
    "己": "已",
    "已": "己",
    "人": "入",
    "入": "人",
    "未": "末",
    "末": "未",
    "士": "土",
    "土": "士",
    "千": "干",
    "干": "千",
    "贝": "见",
    "见": "贝",
    "天": "夭",
    "大": "犬",
    "十": "卜",
    "王": "玉",
}

SUBSTITUTION_PROBABILITY = 0.30
SPACE_LOSS_PROBABILITY = 0.15
DROPOUT_PROBABILITY = 0.02
FORCED_MUTATIONS = 3


def degrade_text(text: str, rng: random.Random) -> str:
    """Apply OCR-like noise to `text`.

    The first `FORCED_MUTATIONS` confusable characters are always changed, so a degraded
    passage is guaranteed to differ from the original (tests assert this).
    """
    table = _table_for(text)
    out: list[str] = []
    forced = FORCED_MUTATIONS
    index = 0
    mutated = False
    while index < len(text):
        char = text[index]
        two = text[index:index + 2]
        if forced > 0 and (two in CONFUSIONS or char in table):
            replacement = CONFUSIONS.get(two) if two in CONFUSIONS else table[char]
            out.append(replacement)
            index += len(two) if two in CONFUSIONS else 1
            forced -= 1
            mutated = True
            continue
        if two in CONFUSIONS and rng.random() < SUBSTITUTION_PROBABILITY:
            out.append(CONFUSIONS[two])
            index += 2
            mutated = True
            continue
        if char in table and rng.random() < SUBSTITUTION_PROBABILITY:
            out.append(table[char])
            index += 1
            mutated = True
            continue
        if char == " " and rng.random() < SPACE_LOSS_PROBABILITY:
            index += 1  # spacing collapse: the word boundary disappears
            mutated = True
            continue
        # Dropped glyph: a recogniser that cannot read a character omits it. This is the only
        # mutation available for text with no confusable character at all, and without it a
        # "scanned" document could come out byte-identical to the original.
        if rng.random() < DROPOUT_PROBABILITY:
            index += 1
            mutated = True
            continue
        out.append(char)
        index += 1

    if not mutated:
        # Guarantee the passage differs: drop a character rather than return the original,
        # because "scanned" text that equals the clean text makes the whole subset a lie.
        drop = min(len(out) - 1, max(0, rng.randrange(max(1, len(out)))))
        out.pop(drop)
    return "".join(out)


def _table_for(text: str) -> dict:
    """Use the CJK confusion table for text that is predominantly Chinese, and the union for
    mixed text: an English document that quotes a Chinese term should degrade like either."""
    if not text:
        return CONFUSIONS
    cjk = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    if cjk == 0:
        return CONFUSIONS
    if cjk / len(text) > 0.2:
        merged = dict(CONFUSIONS)
        merged.update(CJK_CONFUSIONS)
        return merged
    return CONFUSIONS


def pick_ocr_documents(doc_ids: list[str], ratio: float, seed: int) -> set:
    """Choose which documents are 'scanned'.

    Count is `round(n * ratio)` with a floor of 1, so a small corpus still exercises the
    scanned path. Selection is deterministic and independent of dict ordering.
    """
    ordered = sorted(doc_ids)
    if not ordered:
        return set()
    count = max(1, int(round(len(ordered) * ratio)))
    count = min(count, len(ordered))
    rng = random.Random(seed)
    chosen = rng.sample(range(len(ordered)), count)
    return {ordered[i] for i in sorted(chosen)}
