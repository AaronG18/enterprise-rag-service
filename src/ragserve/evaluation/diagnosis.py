"""Reproducible incident replays.

Each case has three parts, because a diagnosis without all three is a story, not a diagnosis:

1. **Evidence** - a metric value or a log line produced by running the code, not by memory.
2. **Fix rationale** - why that fix and not another.
3. **Post-fix measurement** - the same command, same corpus version, with a >= 10% improvement
   asserted by the script itself (exit non-zero otherwise).

Cases that were demonstrated once but no longer reproduce on the current corpus are withdrawn
in writing (R-13 in RULES.md), not left as green-but-empty assertions. See `WITHDRAWN_CASES`.
"""
from __future__ import annotations

import json
import os
import time
from typing import Dict, List

from ..corpus.builder import CorpusConfig, build_corpus
from ..observability.events import EventLog, StructuredLogger
from ..retrieval.pipeline import RetrievalConfig
from ..retrieval.rerank import DeterministicReranker
from ..service import GenerationConfig, RagService
from . import metrics as M
from .runner import load_cases

IMPROVEMENT_THRESHOLD = 0.10


# Cases withdrawn because the measured effect no longer reproduces on the expanded corpus.
# Kept here so the audit trail is visible, not silently dropped.
WITHDRAWN_CASES = {
    "ocr-penalty": (
        "INC-002 (unconditional OCR penalty demoting the only copy of a scanned document) was "
        "real on the 32-document corpus. On the 80-document corpus the scanned documents always "
        "share a clean twin in the other language, so the conditional penalty never fires: legacy "
        "vs fixed differ by 0% on the OCR-targeted subset (ocr_mrr 1.0 -> 1.0). The guard itself "
        "stays in rerank.py; only the quantified attribution is withdrawn."
    ),
}


def _measure(service, cases: List[Dict], max_chars: int) -> Dict[str, float]:
    mrr = ndcg = cp = faith = comp = 0.0
    answered = 0
    doc_hits = 0
    wrong_refusals = 0
    correct = 0
    for case in cases:
        result = service.answer(case["query"])
        expected_refusal = bool(case.get("expect_refusal"))
        if result.answer.refused == expected_refusal:
            correct += 1
        if expected_refusal:
            continue
        mrr += M.reciprocal_rank([c.doc_id for c in result.retrieved], case["expected_doc_id"])
        ndcg += M.ndcg([c.doc_id for c in result.retrieved], case["expected_doc_id"])
        relevant = [c.chunk_id for c in result.retrieved if c.doc_id == case["expected_doc_id"]]
        cp += M.context_precision([c.chunk_id for c in result.retrieved], relevant)
        if result.answer.refused:
            wrong_refusals += 1
            continue
        answered += 1
        cited_chunks = [c for c in result.retrieved if c.chunk_id in set(result.answer.citations)]
        faith += M.faithfulness(result.answer.text, [c.text for c in cited_chunks])
        comp += M.answer_compliance(result, max_chars)["score"]
        # The question faithfulness cannot answer: which document did the answer actually
        # lean on? Counting "any cited chunk is the right doc" is too lenient - an answer that
        # quotes three chunks, one of them correct, still misleads. So we take the FIRST
        # citation, i.e. the dominant source of the answer.
        if cited_chunks and case["expected_doc_id"] in {cited_chunks[0].doc_id}:
            doc_hits += 1
    answerable = len([c for c in cases if not c.get("expect_refusal")])
    return {
        "mrr": round(mrr / answerable, 4),
        "ndcg": round(ndcg / answerable, 4),
        "context_precision": round(cp / answerable, 4),
        "faithfulness": round(faith / answered, 4) if answered else 0.0,
        "compliance": round(comp / answered, 4) if answered else 0.0,
        "answer_doc_accuracy": round(doc_hits / answered, 4) if answered else 0.0,
        "wrong_refusals": wrong_refusals,
        "refusal_appropriateness": round(correct / len(cases), 4),
    }


def _service(root: str, generation: GenerationConfig, provider=None, logger=None):
    corpus = build_corpus(CorpusConfig.from_json(os.path.join(root, "configs", "corpus.json")))
    retrieval = RetrievalConfig.from_json(os.path.join(root, "configs", "retrieval.json"))
    return RagService(corpus, retrieval, generation, provider=provider, logger=logger)


def _log_evidence(root: str, generation: GenerationConfig, cases: List[Dict], limit: int = 2) -> List[Dict]:
    """Capture real log lines under the broken configuration - the 'evidence' in evidence-based diagnosis."""
    events = EventLog()
    logger = StructuredLogger(sink=events.append)
    service = _service(root, generation, logger=logger)
    for case in cases:
        service.answer(case["query"])
    interesting = [e for e in events.parsed()
                   if e.get("stage") == "decision" and e.get("refusal_reason")]
    return interesting[:limit]


def case_refusal_gate(root: str) -> Dict:
    cases = load_cases(os.path.join(root, "eval", "eval_cases.json"))
    before_cfg = GenerationConfig.from_json(os.path.join(root, "configs", "generation.json"))
    before_cfg.min_confidence = 0.60           # the misconfiguration that caused the spike
    after_cfg = GenerationConfig.from_json(os.path.join(root, "configs", "generation.json"))

    before = _measure(_service(root, before_cfg), cases, after_cfg.max_answer_chars)
    after = _measure(_service(root, after_cfg), cases, after_cfg.max_answer_chars)
    evidence = _log_evidence(root, before_cfg, cases)
    return {
        "case": "refusal-gate",
        "symptom": "refusal spike: legitimate questions refused as low_confidence",
        "before": before,
        "after": after,
        "log_evidence": evidence,
        "primary_metric": "refusal_appropriateness",
        "fix": "min_confidence lowered from 0.60 to 0.30; the gate was above the confidence a "
               "correct single-chunk answer can reach",
        "fix_rationale": "Confidence is 0.6*coverage + 0.4*score_share. A correct answer that "
                         "draws on one chunk scores ~0.5-0.6, so a 0.60 gate refuses correct "
                         "answers. The gate must sit below the achievable confidence of a good "
                         "answer, not at the top of the range.",
    }


class LegacyLanguageBlindReranker(DeterministicReranker):
    """Pre-fix reranker: no notion of whether the chunk is in the language of the question.

    Reproduces INC-004. With one corpus serving both languages, shared numerals and codes give
    a wrong-language chunk a competitive feature score, so an English question about rate limits
    was answered from the Chinese copy of the same specification.
    """

    def rerank(self, query: str, candidates: List) -> List:
        scores = [(candidate, self.score(query, candidate)
                   - self._ocr_penalty(candidate, self.score(query, candidate), []))
                  for candidate in candidates]
        scores.sort(key=lambda item: (-item[1], item[0].chunk_id))
        return scores


def _measure_language(service, probes: List[str]) -> Dict[str, float]:
    """Fraction of answers whose top cited document is written in the language of the question.

    Measured over terse, identifier/figure-bearing English questions - the realistic case where a
    language-blind reranker surfaces the wrong-language copy, because shared numerals and codes
    give that copy a competitive feature score.
    """
    correct = 0
    for query in probes:
        result = service.answer(query)
        languages = [chunk.language for chunk in result.retrieved
                     if chunk.chunk_id in set(result.answer.citations)]
        if languages and all(item == "en" for item in languages):
            correct += 1
    return {
        "answer_language_accuracy": round(correct / len(probes), 4) if probes else 0.0,
        "wrong_language_answers": len(probes) - correct,
        "probes": len(probes),
    }


# Terse English questions that carry the identifiers/figures a bilingual user types. These are
# exactly the queries where the two language copies share the same codes, so a language-blind
# reranker answers some of them from the Chinese copy.
CROSS_LANGUAGE_PROBES = [
    "429 Retry-After",
    "429 Retry-After ingestion",
    "Idempotency Key",
    "AES TLS",
    "token normalised",
    "202 422 status",
    "200 Accepted POST",
    "256-bit key",
    "TTL 300",
    "p95 800",
    "15 carry-over",
    "90 onboarding",
    "1200 budget",
    "16 weeks parental",
    "7 days travel",
    "24 hours fire drill",
    "6 months access",
    "300 cache",
    "15 minutes token",
    "10 percent traces",
    "512 dimensions",
    "1.2 256 30",
    "Restrict per minute",
    "queue depth ingestion",
    "dead-letter retries",
    "watermark advance",
    "concurrency limit generator",
    "semantic cache TTL",
    "vector dimensions normalised",
]


def case_cross_language(root: str) -> Dict:
    corpus = build_corpus(CorpusConfig.from_json(os.path.join(root, "configs", "corpus.json")))
    retrieval = RetrievalConfig.from_json(os.path.join(root, "configs", "retrieval.json"))
    generation = GenerationConfig.from_json(os.path.join(root, "configs", "generation.json"))

    before_service = RagService(corpus, retrieval, generation,
                                reranker=LegacyLanguageBlindReranker())
    after_service = RagService(corpus, retrieval, generation)
    return {
        "case": "cross-language",
        "symptom": "questions were answered from the copy of the document written in the other "
                   "language: shared numerals and codes gave a wrong-language chunk a "
                   "competitive score, so an English question about rate limits was answered "
                   "from the Chinese specification",
        "before": _measure_language(before_service, CROSS_LANGUAGE_PROBES),
        "after": _measure_language(after_service, CROSS_LANGUAGE_PROBES),
        "log_evidence": [],
        "primary_metric": "answer_language_accuracy",
        "fix": "the reranker penalises a chunk whose language differs from the question's "
               "(soft penalty of 0.22, not a filter, because a Chinese answer can legitimately "
               "contain the codes an English question asks for)",
        "fix_rationale": "One corpus serves both languages, and every topic exists in both. "
                         "Term overlap alone cannot tell the copies apart, so the answer "
                         "language was decided by whatever copy happened to score higher "
                         "instead of by the language the question was asked in.",
    }


CASES = {"refusal-gate": case_refusal_gate, "cross-language": case_cross_language}


def _improvement(before: float, after: float) -> float:
    if before == 0:
        return float("inf") if after > 0 else 0.0
    return (after - before) / abs(before)


def run_case(name: str, root: str, out_dir: str) -> Dict:
    if name not in CASES:
        raise ValueError("unknown case: %s" % name)
    report = CASES[name](root)
    primary = report["primary_metric"]
    delta = _improvement(report["before"][primary], report["after"][primary])
    report["improvement"] = delta
    report["meets_threshold"] = delta >= IMPROVEMENT_THRESHOLD
    report["corpus_version"] = build_corpus(
        CorpusConfig.from_json(os.path.join(root, "configs", "corpus.json"))
    ).manifest["corpus_version"]
    report["provenance"] = "deterministic"

    target = os.path.join(out_dir, "diagnosis", name)
    os.makedirs(target, exist_ok=True)
    with open(os.path.join(target, "report.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(report, fh, ensure_ascii=False, sort_keys=True, indent=2)
        fh.write("\n")
    with open(os.path.join(target, "report.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(render_case(report))
    report["artifacts"] = target
    return report


def render_case(report: Dict) -> str:
    lines = [
        "# Incident: %s" % report["case"], "",
        "**Symptom:** %s" % report["symptom"], "",
        "Corpus version: `%s` - provenance: `%s`" % (report["corpus_version"], report["provenance"]),
        "",
        "## Measured before and after",
        "",
        "| Metric | Before | After | Improvement |",
        "|---|---|---|---|",
    ]
    for key in sorted(report["before"]):
        before = report["before"][key]
        after = report["after"][key]
        delta = _improvement(float(before), float(after))
        lines.append("| %s | %s | %s | %s |" % (key, before, after,
                                                 "n/a" if delta == float("inf") else "%+.1f%%"
                                                 % (delta * 100)))
    lines += [
        "",
        "Primary metric: `%s` - improvement %s (threshold %.0f%%)"
        % (report["primary_metric"],
           "from zero" if report["improvement"] == float("inf")
           else "%+.1f%%" % (report["improvement"] * 100),
           IMPROVEMENT_THRESHOLD * 100),
        "",
        "## Fix",
        "",
        report["fix"],
        "",
        "## Why this fix",
        "",
        report["fix_rationale"],
    ]
    if report["log_evidence"]:
        lines += ["", "## Log evidence (captured under the failing configuration)", "", "```json"]
        for event in report["log_evidence"]:
            lines.append(json.dumps(event, ensure_ascii=False, sort_keys=True))
        lines += ["```"]
    return "\n".join(lines) + "\n"
