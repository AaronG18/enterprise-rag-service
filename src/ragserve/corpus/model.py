"""Data model for documents and chunks.

Every field here is plain data on purpose: the corpus is generated deterministically and
serialised to JSONL, so the model must stay trivially serialisable and hashable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class Section:
    """One section of a document.

    `body` is the text as stored (possibly OCR-degraded); `clean_body` is the pristine
    original, kept so degradation can be measured instead of guessed at.
    """

    heading: str
    body: str
    clean_body: str


@dataclass(frozen=True)
class Document:
    doc_id: str
    family: str      # handbook | compliance | techspec | architecture
    language: str    # en | zh
    title: str
    ocr: bool
    sections: List[Section] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "\n".join([self.title] + [s.body for s in self.sections])


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    family: str
    language: str
    section: str
    ordinal: int
    text: str
    start: int
    end: int
    ocr: bool
    source_text: str = ""


def section_to_dict(section: Section) -> Dict[str, Any]:
    return {"heading": section.heading, "body": section.body, "clean_body": section.clean_body}


def document_to_dict(doc: Document) -> Dict[str, Any]:
    return {
        "doc_id": doc.doc_id,
        "family": doc.family,
        "language": doc.language,
        "title": doc.title,
        "ocr": doc.ocr,
        "sections": [section_to_dict(s) for s in doc.sections],
    }


def chunk_to_dict(chunk: Chunk) -> Dict[str, Any]:
    """Serialised form. `source_text` is deliberately excluded: it is redundant on disk."""
    return {
        "chunk_id": chunk.chunk_id,
        "doc_id": chunk.doc_id,
        "family": chunk.family,
        "language": chunk.language,
        "section": chunk.section,
        "ordinal": chunk.ordinal,
        "text": chunk.text,
        "start": chunk.start,
        "end": chunk.end,
        "ocr": chunk.ocr,
    }
