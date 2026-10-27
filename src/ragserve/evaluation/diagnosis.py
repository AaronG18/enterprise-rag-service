"""Reproducible incident replays.

Each case has three parts, because a diagnosis without all three is a story, not a diagnosis:

1. **Evidence** - a metric value or a log line produced by running the code, not by memory.
2. **Fix rationale** - why that fix and not another.
3. **Post-fix measurement** - the same command, same corpus version, with a >= 10% improvement
   asserted by the script itself (exit non-zero otherwise).

The pre-fix behaviour of INC-002 is reconstructed here (`LegacySelectionProvider`) rather than
left in the shipped code path, so reproduction does not require shipping a broken branch.
"""
from __future__ import annotations

import json
import os
import time
from typing import Dict, List

from ..corpus.builder import CorpusConfig, build_corpus
from ..observability.events import EventLog, StructuredLogger
from ..retrieval.pipeline import RetrievalConfig
from ..retrieval.rerank import OCR_PENALTY, DeterministicReranker
from ..service import GenerationConfig, RagService
from . import metrics as M
from .runner import load_cases

IMPROVEMENT_THRESHOLD = 0.10


class LegacyOcrPenaltyReranker(DeterministicReranker):
    """Pre-fix reranker: an unconditional penalty on every scanned chunk.

    Reproduces INC-002. The penalty is correct in spirit (scanned text is weaker evidence) but
    wrong in application: when the scanned document is the only copy of that content, demoting
    it buries the answer and the confidence gate then refuses the question.
    """

    def rerank(self, query: str, candidates: List) -> List:
        scored = [(candidate, self.score(query, candidate)
                   - (OCR_PENALTY if candidate.ocr else 0.0))
                  for candidate in candidates]
        scored.sort(key=lambda item: (-item[1], item[0].chunk_id))
        return scored


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


def _measure_subset(service, cases: List[Dict]) -> Dict[str, float]:
    """Metrics on the scanned-document subset: the population the incident affected."""
    mrr = cp = 0.0
    refusals = 0
    for case in cases:
        result = service.answer(case["query"])
        if result.answer.refused:
            refusals += 1
        mrr += M.reciprocal_rank([c.doc_id for c in result.retrieved], case["expected_doc_id"])
        relevant = [c.chunk_id for c in result.retrieved if c.doc_id == case["expected_doc_id"]]
        cp += M.context_precision([c.chunk_id for c in result.retrieved], relevant)
    n = len(cases)
    return {
        "ocr_mrr": round(mrr / n, 4),
        "ocr_context_precision": round(cp / n, 4),
        "ocr_refusals": refusals,
        "ocr_cases": n,
    }


def case_ocr_penalty(root: str) -> Dict:
    cases = load_cases(os.path.join(root, "eval", "eval_cases.json"))
    ocr_cases = [c for c in cases if c.get("ocr_target")]
    corpus = build_corpus(CorpusConfig.from_json(os.path.join(root, "configs", "corpus.json")))
    retrieval = RetrievalConfig.from_json(os.path.join(root, "configs", "retrieval.json"))
    generation = GenerationConfig.from_json(os.path.join(root, "configs", "generation.json"))

    before_service = RagService(corpus, retrieval, generation,
                                reranker=LegacyOcrPenaltyReranker())
    after_service = RagService(corpus, retrieval, generation)
    return {
        "case": "ocr-penalty",
        "symptom": "queries about scanned documents were refused or answered from the wrong "
                   "document: the OCR penalty demoted the only copy of the scanned text",
        "before": _measure_subset(before_service, ocr_cases),
        "after": _measure_subset(after_service, ocr_cases),
        "log_evidence": [],
        "primary_metric": "ocr_mrr",
        "fix": "the OCR penalty now applies only when a clean chunk is comparably strong "
               "(within 0.08 of the scanned chunk's score); otherwise it is suppressed",
        "fix_rationale": "Scanned text is weaker evidence, but when the scanned document is the "
                         "only copy of that content, penalising it buries the answer and the "
                         "confidence gate then refuses the question. Noise must break ties "
                         "between comparable candidates, never override sole evidence.",
    }


CASES = {"refusal-gate": case_refusal_gate, "ocr-penalty": case_ocr_penalty}


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
