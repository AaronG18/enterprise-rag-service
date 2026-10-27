"""PII detection and redaction.

Applied in two places, because applying it in only one is the classic leak: a clean answer
with a raw query sitting in the log line is still a leak.

Masking rather than deletion is deliberate: support staff need to recognise *which* value was
involved without seeing it, so shape is preserved (domain kept for email, last four for cards).
"""
from __future__ import annotations

import re
from typing import List

EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE_CN = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
NATIONAL_ID = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
CARD = re.compile(r"(?<!\d)(?:\d[ \-]?){12,18}\d(?!\d)")


def _mask_email(match: re.Match) -> str:
    local, _, domain = match.group(0).partition("@")
    return "%s***@%s" % (local[0] if local else "*", domain)


def _mask_phone_cn(match: re.Match) -> str:
    value = match.group(0)
    return "%s****%s" % (value[:3], value[-4:])


def _mask_national_id(match: re.Match) -> str:
    value = match.group(0)
    return "%s%s%s" % (value[:6], "*" * 8, value[-4:])


def _mask_card(match: re.Match) -> str:
    """Keep the last four digits, mask the rest, keep separators (walk backwards)."""
    value = match.group(0)
    keep = 4
    out = []
    for char in reversed(value):
        if char.isdigit():
            if keep > 0:
                out.append(char)
                keep -= 1
            else:
                out.append("*")
        else:
            out.append(char)
    return "".join(reversed(out))


# Order matters: the card pattern is broad enough to swallow the others if run first.
PATTERNS = [
    ("email", EMAIL, _mask_email),
    ("phone_cn", PHONE_CN, _mask_phone_cn),
    ("national_id", NATIONAL_ID, _mask_national_id),
    ("card", CARD, _mask_card),
]


def detect_pii(text: str) -> List[str]:
    """Return the kinds of PII present, in pattern order."""
    found = []
    for kind, pattern, _ in PATTERNS:
        if pattern.search(text or ""):
            found.append(kind)
    return found


def redact_text(text: str) -> str:
    if not text:
        return text
    out = text
    for _kind, pattern, mask in PATTERNS:
        out = pattern.sub(mask, out)
    return out


def redact_record(record):
    """Redact every string in a nested dict/list structure (log records)."""
    if isinstance(record, str):
        return redact_text(record)
    if isinstance(record, dict):
        return {key: redact_record(value) for key, value in record.items()}
    if isinstance(record, (list, tuple)):
        redacted = [redact_record(value) for value in record]
        return type(record)(redacted) if isinstance(record, tuple) else redacted
    return record
