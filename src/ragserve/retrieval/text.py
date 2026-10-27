"""Tokenisation for a bilingual (CN/EN) corpus.

The important constraint: Chinese has no whitespace word boundaries. Splitting on spaces
would give one giant token per Chinese sentence, which destroys both BM25 and hashing-based
vectors. So CJK runs are tokenised as single characters **plus** character bigrams, while
latin runs are split on non-alphanumerics.

Numbers are kept as tokens in both scripts - policy corpora are full of thresholds, status
codes and byte limits, and those are exactly the exact-term matches dense retrieval loses.
"""
from __future__ import annotations

import re
import unicodedata

CJK_RANGE = r"\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
CJK_RUN = re.compile("[%s]+" % CJK_RANGE)
LATIN_RUN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-\.]*")
CJK_CHAR = re.compile("[%s]" % CJK_RANGE)

# Punctuation that carries no retrieval signal in either language.
NOISE = re.compile(r"[，,。\.！!？\?；;：:\"'“”‘’（）\(\)\[\]【】/\\|<>\-–—~`\*#\n\r\t]+")


def has_cjk(text: str) -> bool:
    return bool(CJK_CHAR.search(text))


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = NOISE.sub(" ", text)
    return text.strip().lower()


def tokenize(text: str) -> list:
    text = normalize(text)
    tokens: list = []
    for match in CJK_RUN.finditer(text):
        run = match.group(0)
        tokens.extend(list(run))
        if len(run) > 1:
            tokens.extend(run[i:i + 2] for i in range(len(run) - 1))
    for match in LATIN_RUN.finditer(text):
        token = match.group(0)
        tokens.append(token)
    return tokens
