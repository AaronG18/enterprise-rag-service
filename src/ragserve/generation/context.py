"""Multi-turn query resolution.

Follow-ups like "Can they be carried over?" have no retrievable content on their own. The
resolution is deliberately simple and inspectable: when a follow-up contains an anaphoric
reference, the previous user question is prepended. Nothing clever (no co-reference model),
because a wrong rewrite is worse than no rewrite - and this way the rewrite is visible in the
trace and can be diagnosed.
"""
from __future__ import annotations

import re
from typing import List, Optional, Sequence, Tuple

ANAPHORA = re.compile(
    r"\b(it|its|this|that|they|them|their|those)\b|它|它们|这个|那个|其|该",
    re.IGNORECASE,
)


def resolve_query(query: str, history: Optional[Sequence[Tuple[str, str]]] = None):
    """Return (query_to_retrieve_with, was_rewritten)."""
    if not history:
        return query, False
    if not ANAPHORA.search(query or ""):
        return query, False
    previous_question = history[-1][0]
    return "%s %s" % (previous_question, query), True
