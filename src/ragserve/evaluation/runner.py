"""Evaluation harness: three configurations, one pass each, everything recorded."""
from __future__ import annotations

import json
import os
import time
from typing import Dict, List, Optional

from ..cache import ResponseCache
from ..corpus.builder import CorpusConfig, build_corpus
from ..generation.providers import CodeBuddyServeProvider
from ..retrieval.pipeline import RetrievalConfig
from ..service import GenerationConfig, RagService
from . import metrics as M
from .report import OPS_FIELDS, render_csv, render_text

CONFIGURATIONS = {
    "vector_only": {"mode": "vector_only", "rerank_enabled": False},
    "hybrid": {"mode": "hybrid", "rerank_enabled": False},
    "hybrid+rerank": {"mode": "hybrid", "rerank_enabled": True},
}


def load_cases(path: str) -> List[Dict]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _relevant_chunk_ids(result, expected_doc_id: Optional[str]) -> List[str]:
    if not expected_doc_id:
        return []
    return [c.chunk_id for c in result.retrieved if c.doc_id == expected_doc_id]


def evaluate_configuration(corpus, cases: List[Dict], retrieval_overrides: Dict,
                           generation: GenerationConfig, retrieval_base: RetrievalConfig,
                           provider=None) -> Dict:
    """One configuration, one pass. No cache: measuring a warmed cache is not a measurement."""
    retrieval = RetrievalConfig(**dict(retrieval_base.__dict__, **retrieval_overrides))
    service = RagService(corpus, retrieval, generation, provider=provider)
    return evaluate_with_service(service, cases, generation.max_answer_chars)


def evaluate_with_service(service, cases: List[Dict], max_chars: int) -> Dict:
    rows = []
    for case in cases:
        started = time.perf_counter()
        result = service.answer(case["query"])
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        compliance = M.answer_compliance(result, max_chars)
        style = M.style_score(result.answer.text, bool(result.answer.citations), max_chars)
        relevant = _relevant_chunk_ids(result, case.get("expected_doc_id"))
        rows.append({
            "query": case["query"],
            "language": case.get("language"),
            "expected_doc_id": case.get("expected_doc_id"),
            "expect_refusal": bool(case.get("expect_refusal")),
            "expected_reason": case.get("expected_reason"),
            "refused": result.answer.refused,
            "reason_code": result.answer.reason_code,
            "retrieved_doc_ids": [c.doc_id for c in result.retrieved],
            "hit": case.get("expected_doc_id") in [c.doc_id for c in result.retrieved]
                   if case.get("expected_doc_id") else None,
            "reciprocal_rank": M.reciprocal_rank([c.doc_id for c in result.retrieved],
                                                 case.get("expected_doc_id") or ""),
            "ndcg": M.ndcg([c.doc_id for c in result.retrieved], case.get("expected_doc_id") or ""),
            "context_precision": M.context_precision([c.chunk_id for c in result.retrieved], relevant),
            "faithfulness": M.faithfulness(result.answer.text,
                                           [c.text for c in result.retrieved
                                            if c.chunk_id in set(result.answer.citations)]),
            "compliance": compliance["score"],
            "style": style,
            "tokens": result.answer.usage.get("total_tokens", 0),
            "latency_ms": round(elapsed_ms, 3),
            "citations": list(result.answer.citations),
        })
    return {"rows": rows, "metrics": _aggregate(rows)}


def _aggregate(rows: List[Dict]) -> Dict[str, float]:
    answerable = [r for r in rows if not r["expect_refusal"] and r["hit"] is not None]
    # Answer-quality metrics are computed over cases the service actually answered. Folding
    # wrong refusals into faithfulness would mix two different failures into one number and
    # make the metric unactionable - refusal errors are counted by refusal_appropriateness.
    answered = [r for r in answerable if not r["refused"]]
    counts = len(answerable)
    answered_counts = len(answered)
    recall = (sum(1 for r in answerable if r["hit"]) / counts) if counts else 0.0
    return {
        "recall@5": round(recall, 4),
        "mrr": round(sum(r["reciprocal_rank"] for r in answerable) / counts, 4) if counts else 0.0,
        "ndcg": round(sum(r["ndcg"] for r in answerable) / counts, 4) if counts else 0.0,
        "context_precision": round(sum(r["context_precision"] for r in answered)
                                   / answered_counts, 4) if answered_counts else 0.0,
        "faithfulness": round(sum(r["faithfulness"] for r in answered) / answered_counts, 4)
                        if answered_counts else 0.0,
        "refusal_appropriateness": round(
            M.refusal_appropriateness([r["refused"] for r in rows],
                                      [r["expect_refusal"] for r in rows]), 4),
        "style_consistency": round(M.style_consistency([r["style"] for r in answered]), 4)
                             if answered_counts else 0.0,
    }


def measure_operations(corpus, cases: List[Dict], generation: GenerationConfig,
                        retrieval: RetrievalConfig, exact_ttl: float, semantic_ttl: float) -> Dict:
    """Latency with the cache disabled, then hit rate from a separate cached pass.

    Two passes on purpose: mixing them would report warmed-cache latency as if it were cold.
    """
    cold = RagService(corpus, retrieval, generation)
    latencies = []
    tokens = 0
    refusal_flags = []
    compliance_scores = []
    for case in cases:
        started = time.perf_counter()
        result = cold.answer(case["query"])
        latencies.append((time.perf_counter() - started) * 1000.0)
        tokens += result.answer.usage.get("total_tokens", 0)
        refusal_flags.append(result.answer.refused)
        compliance_scores.append(M.answer_compliance(result, generation.max_answer_chars)["score"])

    cache = ResponseCache(exact_ttl=exact_ttl, semantic_ttl=semantic_ttl)
    warm = RagService(corpus, retrieval, generation, cache=cache)
    for case in cases:
        warm.answer(case["query"])
        warm.answer(case["query"])  # second call probes the cache

    return {
        "p50_latency_ms": round(M.percentile(latencies, 50), 3),
        "p95_latency_ms": round(M.percentile(latencies, 95), 3),
        "token_usage_total": tokens,
        "cache_hit_rate": round(cache.hit_rate, 4),
        "refusal_rate": round(sum(1 for f in refusal_flags if f) / len(refusal_flags), 4),
        "answer_compliance_rate": round(sum(compliance_scores) / len(compliance_scores), 4),
        "cache_stats": dict(cache.stats),
    }


def run_evaluation(root: str, out_dir: str, cases_path: Optional[str] = None) -> Dict:
    configs = os.path.join(root, "configs")
    corpus_cfg = CorpusConfig.from_json(os.path.join(configs, "corpus.json"))
    retrieval_base = RetrievalConfig.from_json(os.path.join(configs, "retrieval.json"))
    generation = GenerationConfig.from_json(os.path.join(configs, "generation.json"))
    observability = _load_observability(os.path.join(configs, "observability.json"))

    cases_path = cases_path or os.path.join(root, "eval", "eval_cases.json")
    cases = load_cases(cases_path)
    corpus = build_corpus(corpus_cfg)

    comparison: Dict[str, Dict[str, float]] = {}
    all_rows: Dict[str, List[Dict]] = {}
    for name, overrides in CONFIGURATIONS.items():
        outcome = evaluate_configuration(corpus, cases, overrides, generation, retrieval_base)
        comparison[name] = outcome["metrics"]
        all_rows[name] = outcome["rows"]

    operations = measure_operations(
        corpus, cases, generation, retrieval_base,
        observability.get("exact_ttl_s", 300), observability.get("semantic_ttl_s", 60))

    run_metadata = {
        "corpus_version": corpus.manifest["corpus_version"],
        "config_fingerprint": retrieval_base.__dict__ and json.dumps(
            {k: v for k, v in retrieval_base.__dict__.items()}, sort_keys=True)[:80],
        "provider": generation.provider,
        "model_version": generation.model_version,
        "case_count": len(cases),
        "provenance": "deterministic",
    }

    run_id = time.strftime("%Y%m%d-%H%M%S")
    target = os.path.join(out_dir, "eval", run_id)
    os.makedirs(target, exist_ok=True)
    artifacts = {
        "metrics": os.path.join(target, "metrics.json"),
        "report": os.path.join(target, "report.txt"),
        "report_csv": os.path.join(target, "report.csv"),
        "scored_cases": os.path.join(target, "scored_cases.jsonl"),
    }

    payload = {
        "run_metadata": run_metadata,
        "operations": operations,
        "comparison": comparison,
    }
    with open(artifacts["metrics"], "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, sort_keys=True, indent=2)
        fh.write("\n")
    with open(artifacts["report"], "w", encoding="utf-8", newline="\n") as fh:
        fh.write(render_text(operations, comparison, run_metadata))
    with open(artifacts["report_csv"], "w", encoding="utf-8", newline="") as fh:
        fh.write(render_csv(operations, comparison))
    with open(artifacts["scored_cases"], "w", encoding="utf-8", newline="\n") as fh:
        for name in CONFIGURATIONS:
            for row in all_rows[name]:
                fh.write(json.dumps(dict(row, configuration=name), ensure_ascii=False,
                                    sort_keys=True) + "\n")
    payload["artifacts"] = artifacts
    return payload


def run_model_backed(root: str, out_dir: str, models, provider_config_path: str,
                     cases_path: str | None = None, max_cases: int = 0) -> Dict:
    """Real-generation evaluation: models x retrieval configurations x cases.

    Written next to the deterministic baseline, never over it. Provenance is `model-backed`,
    and token counts are estimates because the endpoint reports no usage.
    """
    import time as _time

    configs = os.path.join(root, "configs")
    corpus_cfg = CorpusConfig.from_json(os.path.join(configs, "corpus.json"))
    retrieval_base = RetrievalConfig.from_json(os.path.join(configs, "retrieval.json"))
    generation = GenerationConfig.from_json(os.path.join(configs, "generation.json"))

    with open(provider_config_path, "r", encoding="utf-8") as fh:
        provider_cfg = json.load(fh).get("codebuddy-serve", {})

    cases_path = cases_path or os.path.join(root, "eval", "eval_cases.json")
    cases = load_cases(cases_path)
    if max_cases and max_cases < len(cases):
        cases = cases[:max_cases]
    corpus = build_corpus(corpus_cfg)

    comparison: Dict[str, Dict[str, float]] = {}
    all_rows: Dict[str, List[Dict]] = {}
    for model in models:
        entry = provider_cfg.get(model)
        if not entry:
            raise ValueError("no endpoint configured for model %r" % model)
        for config_name, overrides in CONFIGURATIONS.items():
            key = "%s | %s" % (model, config_name)
            retrieval = RetrievalConfig(**dict(retrieval_base.__dict__, **overrides))
            provider = CodeBuddyServeProvider(entry["base_url"], model)
            service = RagService(corpus, retrieval, generation, provider=provider)
            outcome = evaluate_with_service(service, cases, generation.max_answer_chars)
            comparison[key] = outcome["metrics"]
            all_rows[key] = outcome["rows"]

    run_id = _time.strftime("%Y%m%d-%H%M%S")
    target = os.path.join(out_dir, "eval-model", run_id)
    os.makedirs(target, exist_ok=True)
    payload = {
        "run_metadata": {
            "corpus_version": corpus.manifest["corpus_version"],
            "provider": "codebuddy-serve",
            "models": list(models),
            "configurations": list(CONFIGURATIONS),
            "case_count": len(cases),
            "provenance": "model-backed",
            "token_usage_provenance": "estimate (endpoint returns no usage)",
            "note": "model output varies between runs; treat differences below a few points as noise",
        },
        "comparison": comparison,
    }
    artifacts = {
        "metrics": os.path.join(target, "metrics.json"),
        "scored_cases": os.path.join(target, "scored_cases.jsonl"),
    }
    with open(artifacts["metrics"], "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, sort_keys=True, indent=2)
        fh.write("\n")
    with open(artifacts["scored_cases"], "w", encoding="utf-8", newline="\n") as fh:
        for key, rows in all_rows.items():
            for row in rows:
                fh.write(json.dumps(dict(row, configuration=key), ensure_ascii=False,
                                    sort_keys=True) + "\n")
    payload["artifacts"] = artifacts
    return payload


def _load_observability(path: str) -> Dict:
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)
