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

Two details carry a bilingual corpus. `ToUnicode` CMaps are parsed and applied, so a CJK PDF that
subsets its font yields Chinese instead of control characters - and the CMap itself is never
indexed, which is what used to put the string "Adobe UCS" into documents. Streams stored without a
filter are read as-is, so an uncompressed PDF is not misreported as scanned. And the "is this
scanned?" floor is language-aware: a complete Chinese clause is ~34 characters where the English
equivalent is ~150, so one floor sized for English silently dropped short Chinese documents.

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

# A CJK character carries roughly a word, not a letter, so a complete Chinese clause is ~20-40
# characters where the English equivalent is ~120-290. One floor sized for English silently drops
# perfectly good short Chinese documents as "scanned".
_SCANNED_TEXT_FLOOR_CJK = 12
_CJK = re.compile(r"[㐀-鿿぀-ヿ]")


def _scanned_floor(text: str) -> int:
    if not text:
        return _SCANNED_TEXT_FLOOR
    cjk = len(_CJK.findall(text))
    if cjk and cjk / len(text) > 0.3:
        return _SCANNED_TEXT_FLOOR_CJK
    return _SCANNED_TEXT_FLOOR


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


def _iter_pdf_streams(data: bytes):
    """Every stream body: decompressed when it is FlateDecode, raw when it is not.

    Skipping anything that is not FlateDecode would silently discard uncompressed content
    streams - a PDF with a perfectly good text layer would come back empty and be misreported as
    scanned. Image streams fall out here too and simply contain no text operators.
    """
    # The naive r"stream" also matches the "stream" inside "endstream", which produced bogus
    # regions that swallowed the surrounding object dictionaries - that is how font metadata such
    # as (Adobe) / (GB1) ended up in extracted text. Match only a real keyword and resume after
    # the matching endstream.
    opener = re.compile(rb"(?<!end)stream\r?\n")
    pos = 0
    while True:
        match = opener.search(data, pos)
        if not match:
            return
        start = match.end()
        end = data.find(b"endstream", start)
        if end < 0:
            return
        raw = data[start:end]
        if raw.endswith(b"\r\n"):
            raw = raw[:-2]
        elif raw.endswith(b"\n"):
            raw = raw[:-1]
        try:
            yield zlib.decompress(raw)
        except zlib.error:
            yield raw
        pos = end + len(b"endstream")


def _hex_to_text(hexpart: bytes) -> str:
    raw = bytes.fromhex(hexpart.decode("ascii"))
    if len(raw) % 2:
        raw = raw[:-1]
    for encoding in ("utf-16-be", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return ""


def _parse_tounicode(cmap: bytes) -> Dict[int, str]:
    """CID -> Unicode, from a ToUnicode CMap.

    A CJK PDF almost always subsets its font: the content stream then carries small CIDs (1, 2, 3
    ...) that mean nothing on their own, and this CMap is the only thing that maps them back to
    characters. Decoding those CIDs as UTF-16BE yields control characters - which looks like a
    successful extraction and is worse than an honest failure.
    """
    text = cmap.decode("latin-1", "replace")
    mapping: Dict[int, str] = {}

    def as_text(hexstr: str) -> str:
        try:
            raw = bytes.fromhex(hexstr)
        except ValueError:
            return ""
        if len(raw) % 2:
            raw = raw[:-1]
        try:
            return raw.decode("utf-16-be")
        except UnicodeDecodeError:
            return ""

    for block in re.finditer(r"beginbfchar(.*?)endbfchar", text, re.S):
        for m in re.finditer(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block.group(1)):
            chars = as_text(m.group(2))
            if chars:
                mapping[int(m.group(1), 16)] = chars

    for block in re.finditer(r"beginbfrange(.*?)endbfrange", text, re.S):
        for m in re.finditer(
                r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block.group(1)):
            lo, hi = int(m.group(1), 16), int(m.group(2), 16)
            dst = as_text(m.group(3))
            if not dst:
                continue
            base = ord(dst[0])
            for offset in range(min(hi - lo, 65535) + 1):
                mapping[lo + offset] = chr(base + offset)
    return mapping


def _decode_hex_operand(hexpart: bytes, cmap: Dict[int, str]) -> str:
    """Hex text operand -> characters, through the font's ToUnicode map when there is one."""
    clean = re.sub(rb"\s+", b"", hexpart)
    if len(clean) % 4:  # not two-byte CIDs: fall back to the whole string
        return _hex_to_text(clean)
    codes = [int(clean[i:i + 4], 16) for i in range(0, len(clean), 4)]
    if cmap and any(code in cmap for code in codes):
        return "".join(cmap.get(code, chr(code)) for code in codes)
    # No CMap: an Identity-H font whose CID *is* the code point.
    return _hex_to_text(clean)


def extract_pdf_text(path: str) -> str:
    """Best-effort text from a PDF, using only the standard library.

    Decompresses every stream and collects the operands of the text-showing operators (`Tj`, `TJ`,
    `'`, `"`). Two details matter for a bilingual corpus:

    * `ToUnicode` CMaps are **parsed, not indexed**. They are how subset CJK fonts map CID ->
      Unicode; treating them as page text is what puts `Adobe` and `UCS` into the index.
    * Streams stored without a filter are read as-is, so an uncompressed PDF is not misreported as
      scanned.

    Layout, hyphenation and non-Identity encodings are not reconstructed - the goal is retrieval,
    not typesetting.
    """
    with open(path, "rb") as fh:
        data = fh.read()
    cmap: Dict[int, str] = {}
    pieces: List[str] = []
    for content in _iter_pdf_streams(data):
        if b"begincmap" in content or b"beginbfchar" in content or b"beginbfrange" in content:
            # A CMap is font metadata. Indexing it would claim the document says "Adobe UCS".
            cmap.update(_parse_tounicode(content))
            continue
        for operator in re.finditer(
                rb"\((?:\\.|[^\\()])*\)|<[0-9A-Fa-f\s]+>\s*(?:Tj|TJ|'|\")", content):
            operand = re.match(rb"\((?:\\.|[^\\()])*\)|<[0-9A-Fa-f\s]+>", operator.group(0))
            if not operand:
                continue
            token = operand.group(0)
            if token.startswith(b"<"):
                text = _decode_hex_operand(token[1:-1], cmap)
            else:
                text = _decode_pdf_string(token)
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
                if len(text) < _scanned_floor(text):
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
