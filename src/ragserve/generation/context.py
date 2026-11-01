"""Multi-turn query resolution.

Follow-ups like "Can they be carried over?" (anaphoric) or "What about part-time employees?"
(elliptical) carry no retrievable content on their own. The resolution is deliberately simple and
inspectable: when a follow-up is one of those two shapes, the previous user question is prepended.
Nothing clever (no co-reference model), because a wrong rewrite is worse than no rewrite - and this
way the rewrite is visible in the trace and can be diagnosed.
"""
from __future__ import annotations

import re
from typing import List, Optional, Sequence, Tuple

ANAPHORA = re.compile(
    r"\b(it|its|this|that|they|them|their|those)\b|它|它们|这个|那个|其|该",
    re.IGNORECASE,
)

# A follow-up opening with one of these is elliptical: it only means something next to the
# previous turn ("What about part-time employees?"). Kept deliberately narrow - "why" and "how
# many" are excluded because they also open self-contained questions, and a wrong rewrite is worse
# than no rewrite. A query with no history is never rewritten.
ELLIPSIS = re.compile(
    r"^\s*(what about|how about|what if|and|but)\b|^\s*(那|那么|如果)",
    re.IGNORECASE,
)


def resolve_query(query: str, history: Optional[Sequence[Tuple[str, str]]] = None):
    """Return (query_to_retrieve_with, was_rewritten)."""
    if not history:
        return query, False
    if ANAPHORA.search(query or "") or ELLIPSIS.search(query or ""):
        previous_question = history[-1][0]
        return "%s %s" % (previous_question, query), True
    return query, False
