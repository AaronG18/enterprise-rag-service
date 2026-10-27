"""Injection defence, safety blocklist and refusal decisions.

Two different problems that are easy to conflate:

* **Injection** - untrusted *content* (retrieved chunks, or the user's own query) trying to
  override instructions. Handled by detection + neutralisation, and by refusing when the
  attempt arrives in the query itself.
* **Refusal** - the service legitimately cannot answer: no context, out of scope, or too
  little confidence. Handled by an explicit reason code, because "refusal rate" is a
  monitored metric (EPIC 6) and an unclassified refusal is unmeasurable.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

INJECTION_PATTERNS = [
    r"ignore\s+(?:all\s+|any\s+)?(?:previous|prior|above)\s+(?:instructions|prompts|rules)",
    r"disregard\s+(?:all\s+)?(?:previous|prior|above)",
    r"\bsystem\s*:",
    r"you\s+are\s+now\b",
    r"reveal\s+(?:all|the)\s+(?:secrets|data|prompt)",
    r"忽略(?:之前|上述|上面)的?(?:指令|提示|规则)",
    r"你现在是",
]
INJECTION_RE = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)
NEUTRALISED = "[filtered: instruction-like text removed]"

SAFETY_PATTERNS = [
    r"national\s+id\s+numbers?",
    r"social\s+security\s+numbers?",
    r"list\s+all\s+employees",
    r"dump\s+the\s+(?:knowledge\s+base|database)",
    r"身份证号",
    r"所有员工的",
]
SAFETY_RE = re.compile("|".join(SAFETY_PATTERNS), re.IGNORECASE)

REASON_GUIDANCE = {
    "no_context": "Nothing in the knowledge base matched this question. Try different wording, "
                  "or narrow it to a policy, specification or architecture document.",
    "out_of_scope": "This question does not match the knowledge base scope (handbook, compliance, "
                    "technical specifications, architecture). Ask about one of those areas.",
    "low_confidence": "Some material matched, but not strongly enough to answer safely. "
                      "Ask a more specific question, or quote the document section you mean.",
    "safety_trigger": "This request asks for personal or restricted data, which the service does "
                      "not return. Ask for the policy that governs the data instead.",
    "injection_detected": "This request tried to override the service instructions. "
                          "Re-state your question without instructions to the assistant.",
}


def detect_injection(text: str) -> bool:
    return bool(text) and bool(INJECTION_RE.search(text))


def neutralise(text: str) -> str:
    """Replace instruction-like spans so retrieved content cannot steer the model."""
    if not text:
        return text
    return INJECTION_RE.sub(NEUTRALISED, text)


def detect_safety(text: str) -> bool:
    return bool(text) and bool(SAFETY_RE.search(text))


def decide_refusal(query: str, retrieved: List, coverage: float,
                   confidence: float, min_confidence: float,
                   out_of_scope_coverage: float) -> Optional[str]:
    """Return a reason code, or None when the request may be answered."""
    if detect_injection(query):
        return "injection_detected"
    if detect_safety(query):
        return "safety_trigger"
    if not retrieved:
        return "no_context"
    if coverage <= out_of_scope_coverage:
        return "out_of_scope"
    if confidence < min_confidence:
        return "low_confidence"
    return None


def refusal_message(reason_code: str) -> str:
    return REASON_GUIDANCE.get(reason_code, "This request cannot be answered.")


def build_refusal(reason_code: str, confidence: float = 0.0) -> Tuple[str, str]:
    """Return (answer text, guidance). A refusal must always carry guidance."""
    guidance = refusal_message(reason_code)
    text = "I cannot answer this from the knowledge base. %s" % guidance
    return text, guidance
