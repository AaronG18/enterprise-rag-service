"""Corpus builder: documents -> OCR degradation -> chunks -> manifest + artifacts."""
from __future__ import annotations

import hashlib
import json
import os
import random
import zlib
from dataclasses import dataclass, field
from typing import Dict, List

from .content import iter_documents
from .chunker import chunk_text
from .model import Chunk, Document, Section, chunk_to_dict, document_to_dict
from .ocr import degrade_text, pick_ocr_documents

GENERATOR_VERSION = "1"


@dataclass(frozen=True)
class CorpusConfig:
    seed: int = 20261027
    ocr_ratio: float = 0.08
    chunk_target_chars: int = 320
    chunk_overlap_chars: int = 48
    # Chinese carries roughly twice the content per character, so a fixed character budget
    # produced one chunk per Chinese document and three per English one - an asymmetric corpus
    # that flattered Chinese retrieval (the whole document was the retrieved passage).
    cjk_chunk_scale: float = 0.55

    @classmethod
    def from_json(cls, path: str) -> "CorpusConfig":
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        known = {f: raw[f] for f in cls().__dict__ if f in raw}
        return cls(**known)

    def fingerprint(self) -> str:
        blob = json.dumps(self.__dict__, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


@dataclass
class BuiltCorpus:
    config: CorpusConfig
    documents: List[Document] = field(default_factory=list)
    chunks: List[Chunk] = field(default_factory=list)
    manifest: Dict[str, object] = field(default_factory=dict)


def _make_documents() -> List[Document]:
    """Instantiate documents from the literal content table."""
    docs: List[Document] = []
    for family, language, index, title, sections in iter_documents():
        doc_id = "%s-%s-%02d" % (family, language, index)
        docs.append(Document(
            doc_id=doc_id,
            family=family,
            language=language,
            title=title,
            ocr=False,
            sections=[Section(heading=h, body=b, clean_body=b) for h, b in sections],
        ))
    return docs


def _apply_ocr(documents: List[Document], config: CorpusConfig) -> List[Document]:
    """Degrade a deterministic subset of documents, keeping the clean original alongside."""
    flagged = pick_ocr_documents([d.doc_id for d in documents], config.ocr_ratio, config.seed)
    out: List[Document] = []
    for doc in documents:
        if doc.doc_id not in flagged:
            out.append(doc)
            continue
        rng = random.Random(config.seed + _crc(doc.doc_id))
        degraded = []
        for section in doc.sections:
            dirty_heading = degrade_text(section.heading, rng)
            dirty_body = degrade_text(section.body, rng)
            degraded.append(Section(heading=dirty_heading, body=dirty_body,
                                    clean_body=section.clean_body))
        out.append(Document(doc_id=doc.doc_id, family=doc.family, language=doc.language,
                            title=degrade_text(doc.title, rng), ocr=True, sections=degraded))
    return out


def _crc(value: str) -> int:
    return zlib.crc32(value.encode("utf-8"))


def _flatten(doc: Document):
    """Flatten a document into one text plus (heading, start, end) spans.

    Chunking runs over the whole document, not per section: section bodies are short
    (roughly 120-200 chars), so per-section chunking would produce exactly one chunk per
    section and never exercise overlap at all.
    """
    text_parts: List[str] = []
    spans: List[tuple] = []
    pos = 0

    def push(segment: str, heading: str) -> None:
        nonlocal pos
        text_parts.append(segment)
        start = pos
        pos += len(segment)
        spans.append((heading, start, pos))

    push(doc.title + "\n", doc.title)
    for section in doc.sections:
        push(section.heading + "\n", section.heading)
        push(section.body + "\n\n", section.heading)
    return "".join(text_parts), spans


def _heading_at(spans, position: int) -> str:
    heading = spans[0][0]
    for name, start, end in spans:
        if start <= position < end:
            return name
        if start > position:
            break
        heading = name
    return heading


def _make_chunks(documents: List[Document], config: CorpusConfig) -> List[Chunk]:
    chunks: List[Chunk] = []
    for doc in documents:
        text, spans = _flatten(doc)
        scale = config.cjk_chunk_scale if doc.language == "zh" else 1.0
        target = max(80, int(config.chunk_target_chars * scale))
        overlap = max(16, int(config.chunk_overlap_chars * scale))
        ordinal = 0
        for start, end in chunk_text(text, target, overlap):
            chunks.append(Chunk(
                chunk_id="%s:%04d" % (doc.doc_id, ordinal),
                doc_id=doc.doc_id,
                family=doc.family,
                language=doc.language,
                section=_heading_at(spans, start),
                ordinal=ordinal,
                text=text[start:end],
                start=start,
                end=end,
                ocr=doc.ocr,
                source_text=text,
            ))
            ordinal += 1
    return chunks


def _manifest(documents: List[Document], chunks: List[Chunk], config: CorpusConfig) -> Dict[str, object]:
    dump = json.dumps([document_to_dict(d) for d in documents], sort_keys=True, ensure_ascii=False)
    version = hashlib.sha256(
        ("%s|%s|%s|%s" % (GENERATOR_VERSION, config.seed, config.fingerprint(), dump))
        .encode("utf-8")
    ).hexdigest()[:16]
    per_family: Dict[str, int] = {}
    per_language: Dict[str, int] = {}
    for doc in documents:
        per_family[doc.family] = per_family.get(doc.family, 0) + 1
        per_language[doc.language] = per_language.get(doc.language, 0) + 1
    return {
        "corpus_version": version,
        "generator_version": GENERATOR_VERSION,
        "seed": config.seed,
        "config": dict(config.__dict__),
        "config_fingerprint": config.fingerprint(),
        "doc_count": len(documents),
        "chunk_count": len(chunks),
        "ocr_doc_count": len([d for d in documents if d.ocr]),
        "ocr_ratio": round(len([d for d in documents if d.ocr]) / max(1, len(documents)), 4),
        "per_family": per_family,
        "per_language": per_language,
    }


def build_corpus(config: CorpusConfig | None = None) -> BuiltCorpus:
    cfg = config or CorpusConfig()
    documents = _make_documents()
    documents = _apply_ocr(documents, cfg)
    chunks = _make_chunks(documents, cfg)
    return BuiltCorpus(config=cfg, documents=documents, chunks=chunks,
                       manifest=_manifest(documents, chunks, cfg))


def write_artifacts(corpus: BuiltCorpus, root: str) -> Dict[str, str]:
    """Write documents.jsonl / chunks.jsonl / manifest.json under `root/corpus/<version>`.

    Writes are atomic (temp file + os.replace): the CI gate runs the evaluation, benchmark and
    diagnosis generators concurrently, and all three rebuild the same corpus. A plain
    `open(path, "w")` truncates before it writes, so two writers can interleave and leave a torn
    artifact - and a torn artifact is silently wrong evidence.
    """
    target = os.path.join(root, "corpus", str(corpus.manifest["corpus_version"]))
    os.makedirs(target, exist_ok=True)
    paths = {
        "documents": os.path.join(target, "documents.jsonl"),
        "chunks": os.path.join(target, "chunks.jsonl"),
        "manifest": os.path.join(target, "manifest.json"),
    }
    _atomic_write_lines(paths["documents"],
                         [json.dumps(document_to_dict(doc), ensure_ascii=False, sort_keys=True)
                          for doc in sorted(corpus.documents, key=lambda d: d.doc_id)])
    _atomic_write_lines(paths["chunks"],
                         [json.dumps(chunk_to_dict(chunk), ensure_ascii=False, sort_keys=True)
                          for chunk in sorted(corpus.chunks, key=lambda c: c.chunk_id)])
    _atomic_write_json(paths["manifest"], corpus.manifest)
    paths["dir"] = target
    return paths


def _atomic_write_lines(path: str, lines) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        for line in lines:
            fh.write(line + "\n")
    os.replace(tmp, path)


def _atomic_write_json(path: str, payload) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, sort_keys=True, indent=2)
        fh.write("\n")
    os.replace(tmp, path)
