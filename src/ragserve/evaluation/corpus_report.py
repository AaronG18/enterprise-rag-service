"""Measure retrieval on a corpus the user supplied.

The labelled evaluation set (85 cases) names documents from the synthetic corpus
(`handbook-en-00`, ...), so it scores nothing useful against someone else's files - reporting its
numbers there would be a fabricated measurement. Instead this module builds its labels from the
corpus itself: for every document, a query is derived from that document's title and first
section, and the expected answer is that document. Retrieval is then scored with the same metric
functions the labelled run uses.

This is a **self-labelled proxy**, not a human-labelled benchmark, and it is reported as one: it
proves the pipeline indexes and retrieves the supplied files, and it gives a number that can be
compared across configurations on the *same* corpus. It does not claim to measure answer quality
the way a hand-written question set would.
"""
from __future__ import annotations

import statistics
import time
from typing import Dict, List, Sequence

from ..retrieval.pipeline import RetrievalConfig
from ..service import GenerationConfig, RagService
from .metrics import context_precision, ndcg, reciprocal_rank

PROVENANCE_NOTE = ("self-labelled: each query is derived from the document it is expected to "
                   "retrieve, so this measures index-and-retrieve on the supplied files, not "
                   "human-judged answer quality. Expect these numbers to run high - a query built "
                   "from a document's own title and first section is an easy one - so read them "
                   "as 'the files are indexed and retrievable', and compare them only against "
                   "the same corpus under a different configuration")


def self_label_cases(corpus) -> List[Dict]:
    """One query per document, built from that document's own title and first heading."""
    cases = []
    for doc in corpus.documents:
        heading = doc.sections[0].heading if doc.sections else ""
        body = doc.sections[0].clean_body if doc.sections and doc.sections[0].clean_body else (
            doc.sections[0].body if doc.sections else "")
        # A short question-shaped query: the title plus the first sentence of the body.
        first_sentence = body.split("。")[0].split(". ")[0][:120].strip()
        query = " ".join(part for part in (doc.title, heading, first_sentence) if part).strip()
        if not query:
            continue
        cases.append({"query": query, "expected_doc_id": doc.doc_id, "language": doc.language})
    return cases


def measure_corpus(corpus, retrieval: RetrievalConfig,
                   generation: GenerationConfig) -> Dict:
    """Retrieve and answer the self-labelled queries, and report what happened."""
    cases = self_label_cases(corpus)
    started = time.perf_counter()
    service = RagService(corpus, retrieval, generation)
    build_ms = round((time.perf_counter() - started) * 1000, 3)

    hits = 0
    reciprocal = 0.0
    ndcg_sum = 0.0
    precision = 0.0
    latencies: List[float] = []
    refusals = 0
    tokens = 0
    rows: List[Dict] = []

    for case in cases:
        began = time.perf_counter()
        result = service.answer(case["query"])
        latencies.append((time.perf_counter() - began) * 1000)
        doc_ids = [chunk.doc_id for chunk in result.retrieved]
        chunk_ids = [chunk.chunk_id for chunk in result.retrieved]
        expected = case["expected_doc_id"]
        hit = expected in doc_ids
        hits += 1 if hit else 0
        reciprocal += reciprocal_rank(doc_ids, expected)
        ndcg_sum += ndcg(doc_ids, expected)
        relevant = [chunk.chunk_id for chunk in result.retrieved if chunk.doc_id == expected]
        precision += context_precision(chunk_ids, relevant)
        if getattr(result, "refused", False):
            refusals += 1
        usage = getattr(result, "usage", None) or {}
        tokens += int(usage.get("total_tokens", 0) or 0)
        rows.append({"query": case["query"], "expected_doc_id": expected, "hit": hit,
                     "top_doc_ids": doc_ids[:3]})

    total = max(1, len(cases))
    ordered = sorted(latencies)
    return {
        "provenance_note": PROVENANCE_NOTE,
        "corpus_version": corpus.manifest.get("corpus_version"),
        "source_dir": corpus.manifest.get("source_dir"),
        "doc_count": corpus.manifest.get("doc_count"),
        "chunk_count": corpus.manifest.get("chunk_count"),
        "per_language": corpus.manifest.get("per_language"),
        "skipped_files": corpus.manifest.get("skipped_files"),
        "partial_scan_docs": corpus.manifest.get("partial_scan_docs"),
        "case_count": len(cases),
        "index_build_ms": build_ms,
        "recall@5": round(hits / total, 4),
        "mrr": round(reciprocal / total, 4),
        "ndcg": round(ndcg_sum / total, 4),
        "context_precision": round(precision / total, 4),
        "p50_latency_ms": round(statistics.median(ordered), 3) if ordered else 0.0,
        "p95_latency_ms": round(_percentile(ordered, 0.95), 3) if ordered else 0.0,
        "token_usage_total": tokens,
        "refusal_rate": round(refusals / total, 4),
        "rows": rows,
    }


def run_corpus_report(directory: str, root: str, artifacts_dir: str) -> Dict:
    """Index `directory`, measure it, and write the report. Returns (paths, report)."""
    import json
    import os
    import time

    from ..corpus.builder import CorpusConfig, build_corpus_from_directory
    from ..retrieval.pipeline import RetrievalConfig
    from ..service import GenerationConfig

    configs = os.path.join(root, "configs")
    corpus = build_corpus_from_directory(directory, CorpusConfig.from_json(
        os.path.join(configs, "corpus.json")))
    retrieval = RetrievalConfig.from_json(os.path.join(configs, "retrieval.json"))
    generation = GenerationConfig.from_json(os.path.join(configs, "generation.json"))
    report = measure_corpus(corpus, retrieval, generation)
    # Provenance describes what actually ran, not what the config asked for: a pinned
    # `deterministic` provider is a deterministic run even though nothing degraded.
    if retrieval.embedding_provider == "deterministic":
        report["provenance"] = "deterministic"
    elif retrieval.degraded_embedding or retrieval.degraded_reranker:
        report["provenance"] = "deterministic (no model server reachable; fell back loudly)"
    else:
        report["provenance"] = "model-backed-retrieval"

    run_id = time.strftime("%Y%m%d-%H%M%S")
    target = os.path.join(artifacts_dir, "eval", run_id)
    os.makedirs(target, exist_ok=True)
    paths = {"json": os.path.join(target, "corpus_report.json"),
             "markdown": os.path.join(target, "corpus_report.md")}
    with open(paths["json"], "w", encoding="utf-8", newline="\n") as fh:
        json.dump(report, fh, ensure_ascii=False, sort_keys=True, indent=2)
        fh.write("\n")
    with open(paths["markdown"], "w", encoding="utf-8", newline="\n") as fh:
        fh.write(render_corpus_report(report))
    return {"paths": paths, "report": report}


def _percentile(ordered: Sequence[float], fraction: float) -> float:
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, max(0, int(round(fraction * (len(ordered) - 1)))))
    return ordered[index]


def render_corpus_report(report: Dict) -> str:
    lines = ["# Corpus report (user-supplied documents)", ""]
    lines.append("Generated by `python scripts/run.py --eval --corpus <path>`. "
                 "Provenance: `deterministic`.")
    lines.append("")
    lines.append("**%s.**" % report["provenance_note"])
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    for key in ("source_dir", "corpus_version", "doc_count", "chunk_count", "case_count",
                "index_build_ms", "recall@5", "mrr", "ndcg", "context_precision",
                "p50_latency_ms", "p95_latency_ms", "token_usage_total", "refusal_rate"):
        lines.append("| %s | %s |" % (key, report.get(key)))
    lines.append("")
    languages = report.get("per_language") or {}
    if languages:
        lines.append("Languages indexed: %s."
                     % ", ".join("%s=%d" % (k, v) for k, v in sorted(languages.items())))
        lines.append("")
    skipped = report.get("skipped_files") or []
    if skipped:
        lines.append("## Files indexed with gaps")
        lines.append("")
        lines.append("These were found but could not be turned into text. They are **reported, not "
                     "silently dropped** - an image-only PDF has nothing to index without OCR, "
                     "and OCR needs a third-party dependency this repository does not take "
                     "(PROJECT.md INV-1).")
        lines.append("")
        for item in skipped:
            lines.append("- `%s` - %s" % (item.get("file"), item.get("reason")))
        lines.append("")
    partial = report.get("partial_scan_docs") or []
    if partial:
        lines.append("## Documents indexed but incomplete")
        lines.append("")
        lines.append("Each of these has at least one page with a text layer and was indexed. The "
                     "pages counted below carried no text and are **not** searchable, so answers "
                     "about this document may be incomplete rather than wrong.")
        lines.append("")
        for item in partial:
            lines.append("- `%s` - %d page(s) with no text layer"
                         % (item.get("doc_id"), item.get("scanned_pages")))
        lines.append("")
    lines.append("## Per-document retrieval")
    lines.append("")
    lines.append("| Query (derived from the document) | Expected document | Retrieved top-1 | Hit |")
    lines.append("|---|---|---|---|")
    for row in report.get("rows", []):
        top = (row.get("top_doc_ids") or ["-"])[0]
        lines.append("| %s | `%s` | `%s` | %s |"
                     % (row["query"][:70].replace("|", "\\|"), row["expected_doc_id"], top,
                        "yes" if row["hit"] else "no"))
    lines.append("")
    return "\n".join(lines)
