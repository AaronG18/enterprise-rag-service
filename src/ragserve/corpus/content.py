"""Synthetic corpus content: four families, bilingual, with concrete retrievable facts.

Fully synthetic, no third-party or internal material (RULES R6). Content is literal rather than
randomly assembled word soup: retrieval quality later depends on passages that read like real
policy, specification and design text and carry figures a question can ask for.

Shape: 4 families x 2 languages x 10 topics, each with 4 sections (three substantive sections
plus a closing "exceptions / escalation / related" section from `content_extras`), split across
four modules:

* `content_handbook`     - employee handbook (leave, remote work, expenses, conduct, ...)
* `content_compliance`   - compliance guides (retention, access review, incidents, ...)
* `content_techspec`     - technical specifications (API, cache, auth, pipeline, ...)
* `content_architecture` - architecture documents (tenancy, scaling, decisions, ...)

Every topic exists in EN and ZH with the *same* facts, so bilingual retrieval is a fair test
rather than two different corpora that happen to share a namespace.
"""
from __future__ import annotations

from typing import Dict, Iterator, List, Tuple

from .content_architecture import ARCHITECTURE
from .content_compliance import COMPLIANCE
from .content_extras import EXTRAS
from .content_handbook import HANDBOOK
from .content_techspec import TECHSPEC

FAMILIES = ("handbook", "compliance", "techspec", "architecture")

_TABLES: Dict[str, Dict] = {
    "handbook": HANDBOOK,
    "compliance": COMPLIANCE,
    "techspec": TECHSPEC,
    "architecture": ARCHITECTURE,
}


def iter_documents() -> Iterator[Tuple[str, str, int, str, List[Tuple[str, str]]]]:
    """Yield (family, language, index, title, sections) for every document.

    The index is per family and language, so document ids stay stable when content is added to
    a different family. The closing section from `content_extras` is appended when the topic has
    one, which is what makes documents long enough for chunk overlap to matter.
    """
    for family in FAMILIES:
        counters: Dict[str, int] = {"en": 0, "zh": 0}
        for topic, by_language in _TABLES[family].items():
            for language in ("en", "zh"):
                title, sections = by_language[language]
                closing = EXTRAS.get(topic, {}).get(language)
                all_sections = list(sections)
                if closing:
                    all_sections.append(closing)
                index = counters[language]
                counters[language] += 1
                yield family, language, index, title, all_sections
