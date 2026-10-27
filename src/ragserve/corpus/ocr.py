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

SUBSTITUTION_PROBABILITY = 0.30
SPACE_LOSS_PROBABILITY = 0.15
FORCED_MUTATIONS = 3


def degrade_text(text: str, rng: random.Random) -> str:
    """Apply OCR-like noise to `text`.

    The first `FORCED_MUTATIONS` confusable characters are always changed, so a degraded
    passage is guaranteed to differ from the original (tests assert this).
    """
    out: list[str] = []
    forced = FORCED_MUTATIONS
    index = 0
    while index < len(text):
        char = text[index]
        two = text[index:index + 2]
        if forced > 0 and (two in CONFUSIONS or char in CONFUSIONS):
            replacement = CONFUSIONS.get(two) if two in CONFUSIONS else CONFUSIONS[char]
            out.append(replacement)
            index += len(two) if two in CONFUSIONS else 1
            forced -= 1
            continue
        if two in CONFUSIONS and rng.random() < SUBSTITUTION_PROBABILITY:
            out.append(CONFUSIONS[two])
            index += 2
            continue
        if char in CONFUSIONS and rng.random() < SUBSTITUTION_PROBABILITY:
            out.append(CONFUSIONS[char])
            index += 1
            continue
        if char == " " and rng.random() < SPACE_LOSS_PROBABILITY:
            index += 1  # spacing collapse: the word boundary disappears
            continue
        out.append(char)
        index += 1
    return "".join(out)


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
