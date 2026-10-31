"""Load a corpus from a directory the user points at.

The built-in corpus is synthetic and generated in-repository, which is what makes the published
numbers reproducible. A reviewer, though, will very plausibly bring their own documents - the
brief describes an internal knowledge base of handbooks, compliance guides, technical
specifications and architecture documents - so the service has to be able to index *their* files
instead.

Everything here is standard library only (PROJECT.md INV-1). That constraint is visible in the one
place it hurts: PDF text extraction. There is no PDF parser in the standard library, so this module
decompresses content streams with `zlib` and reads the text-showing operators directly. It is
best-effort by design, and it says so: a PDF whose text cannot be extracted is reported as
**scanned** rather than silently indexed as empty, because "the document is in the index" is a
claim nobody could then verify.

Supported: `.txt`, `.md`, `.markdown`, `.pdf`. Anything else is skipped and listed.
"""
from __future__ import annotations

import os
import re
import zlib
from typing import Dict, List, Tuple

# Reused rather than reimplemented: the reranker penalises chunks in a language other than the
# question's, so a document labelled with a different rule than the query would be silently
# down-ranked.
from ..retrieval.rerank import detect_language  # noqa: E402
from .model import Document, Section

SUPPORTED_SUFFIXES = (".txt", ".md", ".markdown", ".pdf")

# Below this many extracted characters, a PDF is treated as scanned: real text extraction yields
# sentences, a scanned page yields operators and no glyphs.
_SCANNED_TEXT_FLOOR = 40


def _decode_pdf_string(token: bytes) -> str:
    """One PDF string operand -> text. Handles literal `(...)` and hexadecimal `<...>`."""
    if token.startswith(b"(") and token.endswith(b")"):
        raw = token[1:-1]
        raw = re.sub(rb"\\([()\\])", rb"\1", raw)
        raw = raw.replace(rb"\n", b" ").replace(rb"\r", b" ").replace(rb"\t", b" ")
        for encoding in ("utf-8", "latin-1"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return ""
    if token.startswith(b"<") and token.endswith(b">"):
        hexpart = re.sub(rb"\s+", b"", token[1:-1])
        try:
            raw = bytes.fromhex(hexpart.decode("ascii"))
        except (ValueError, UnicodeDecodeError):
            return ""
        # UTF-16BE is the common encoding for CID-keyed text; utf-8 gains nothing here.
        for encoding in ("utf-16-be", "latin-1"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return ""
    return ""


def extract_pdf_text(path: str) -> str:
    """Best-effort text from a PDF, using only the standard library.

    Decompresses every FlateDecode stream and collects the operands of the text-showing operators
    (`Tj`, `TJ`, `'`, `"`). Layout, hyphenation and font encodings are not reconstructed - the goal
    is retrieval, not typesetting.
    """
    with open(path, "rb") as fh:
        data = fh.read()
    pieces: List[str] = []
    for match in re.finditer(rb"stream\r?\n?", data):
        start = match.end()
        end = data.find(b"endstream", start)
        if end < 0:
            continue
        raw = data[start:end]
        try:
            content = zlib.decompress(raw)
        except zlib.error:
            continue  # not FlateDecode: an image stream, or an unsupported filter
        for operator in re.finditer(
                rb"\((?:\\.|[^\\()])*\)|<[0-9A-Fa-f\s]+>\s*(?:Tj|TJ|'|\")", content):
            token = operator.group(0)
            operand = re.match(rb"\((?:\\.|[^\\()])*\)|<[0-9A-Fa-f\s]+>", token)
            if not operand:
                continue
            text = _decode_pdf_string(operand.group(0))
            if text.strip():
                pieces.append(text)
    return "\n".join(pieces).strip()


def _read_plain_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _slug(relative: str) -> str:
    """A stable, filesystem-safe doc id derived from the path."""
    stem = relative.replace("\\", "/")
    stem = re.sub(r"[^0-9A-Za-z/._-]+", "-", stem)
    stem = stem.strip("-")
    return stem or "document"


def _sections_from_markdown(text: str) -> List[Section]:
    """Split markdown on headings so a chunk can be attributed to a section."""
    blocks: List[Tuple[str, str]] = []
    heading = ""
    body: List[str] = []
    for line in text.splitlines():
        if re.match(r"^#{1,6}\s+", line):
            if body:
                blocks.append((heading, "\n".join(body).strip()))
                body = []
            heading = re.sub(r"^#{1,6}\s+", "", line).strip()
        else:
            body.append(line)
    if body:
        blocks.append((heading, "\n".join(body).strip()))
    if not blocks:
        return []
    return [Section(heading=h or "(body)", body=b, clean_body=b) for h, b in blocks if b]


def _sections_from_plain_text(text: str) -> List[Section]:
    paragraph = "\n\n".join(line.strip() for line in text.splitlines() if line.strip())
    if not paragraph:
        return []
    return [Section(heading="(body)", body=paragraph, clean_body=paragraph)]


def load_documents(path: str) -> Tuple[List[Document], List[Dict[str, str]]]:
    """Read every supported file under `path`.

    Returns (documents, skipped) where `skipped` explains each file that could not be indexed, so
    the report can say what it did *not* cover instead of quietly omitting it.
    """
    root = os.path.abspath(path)
    if not os.path.isdir(root):
        raise ValueError("corpus path is not a directory: %s" % path)

    documents: List[Document] = []
    skipped: List[Dict[str, str]] = []
    for current, _dirs, files in os.walk(root):
        for name in sorted(files):
            full = os.path.join(current, name)
            relative = os.path.relpath(full, root)
            suffix = os.path.splitext(name)[1].lower()
            if suffix not in SUPPORTED_SUFFIXES:
                skipped.append({"file": relative, "reason": "unsupported file type"})
                continue
            scanned = False
            if suffix == ".pdf":
                text = extract_pdf_text(full)
                if len(text) < _SCANNED_TEXT_FLOOR:
                    scanned = True
                    text = ""
            else:
                text = _read_plain_text(full)
            if not text.strip():
                skipped.append({"file": relative,
                                "reason": "no extractable text (treated as scanned)"})
                continue
            sections = (_sections_from_markdown(text) if suffix in (".md", ".markdown")
                        else _sections_from_plain_text(text))
            if not sections:
                skipped.append({"file": relative, "reason": "empty after parsing"})
                continue
            documents.append(Document(
                doc_id=_slug(relative),
                family="external",
                language=detect_language(text),
                title=name,
                ocr=scanned,
                sections=sections,
            ))
    return documents, skipped
