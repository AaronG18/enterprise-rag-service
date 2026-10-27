# Deliverables map

Every required deliverable, where it lives, and the command that reproduces it.

| Deliverable | Location | Reproduce |
|---|---|---|
| Complete code and configs | `src/ragserve/` (corpus, retrieval, generation, observability, evaluation, service), `configs/` (corpus, retrieval, generation, observability, pricing) | `git clone` then `python scripts/run_tests.py` |
| One-click evaluation script | `scripts/run_eval.py` | `python scripts/run_eval.py --all` |
| Evaluation report with before/after comparisons | `docs/eval/retrieval-comparison.md` (committed) + `artifacts/eval/<run>/report.txt` and `report.csv` (generated) | `python scripts/run_eval.py --all` |
| Log field dictionary | `docs/logging/log_fields.md` | enforced by `test_log_field_dictionary_covers_emitted_fields` |
| Sample logs | `docs/logging/sample_logs.md` | `python scripts/sample_logs.py` |
| Latency / concurrency evidence | `docs/performance.md` + `artifacts/bench/<run>/bench.json` | `python scripts/run_bench.py --concurrency 5 --requests 30 --assert` |
| Incident diagnosis (>= 2 cases, >= 10% gain) | `docs/diagnosis/INC-001-refusal-gate.md`, `docs/diagnosis/INC-002-ocr-penalty.md` | `python scripts/diagnose.py --all --assert` |
| Metric definitions and calibration | `docs/metrics/metrics.md` | scorers in `src/ragserve/evaluation/metrics.py` |
| Architecture decisions | `docs/adr/` | see `docs/adr/README.md` |
| Labelled evaluation set | `eval/eval_cases.json` (30 cases: 26 answerable, 4 refusal, 3 marked `ocr_target`) | used by `run_eval.py` |

## Commands a reviewer should run, in order

```bash
python scripts/run_tests.py                                   # hermetic suite, zero deps
python scripts/run_eval.py --all                                # quality + ops report
python scripts/run_bench.py --concurrency 5 --assert           # performance claim
python scripts/diagnose.py --all --assert                      # incidents + >10% fixes
python scripts/build_corpus.py                                 # regenerate the corpus
python scripts/sample_logs.py                                  # regenerate sample logs
```

## Status against the required metrics

| Target | Required | Measured | Where |
|---|---|---|---|
| Faithfulness | >= 0.85 | 1.0 | `docs/eval/retrieval-comparison.md` |
| Context Precision | >= 0.70 | 0.9529 (hybrid) | same |
| Answer Compliance | >= 0.80 / 0.90 | 0.9000 | same |
| Refusal Appropriateness | >= 0.80 / 0.90 | 0.9000 | same |
| Style Consistency | >= 0.80 / 0.85 | 1.0 | same |
| p90 latency at >= 5 concurrent | <= 10 s | 10.5-34.8 ms across runs | `docs/performance.md` |
| Cost per 1,000 calls | estimate with price list | arithmetic provided; prices must be filled in `configs/pricing.json` | `src/ragserve/evaluation/cost.py` |

All measured values come from the **deterministic** provider. See the caveat in
`docs/eval/retrieval-comparison.md`: they establish the pipeline floor, not model behaviour.
