# Performance, concurrency and cost (EPIC #7)

## Benchmark: 5 concurrent requests, one instance

`python scripts/run_bench.py --concurrency 5 --requests 30 --assert`, cache disabled so the
number describes the service rather than the cache.

| Field | Value |
|---|---|
| concurrency | 5 |
| requests | 30 |
| p50 latency | 5.127 ms |
| **p90 latency** | **10.476 ms** (bound: 10,000 ms) |
| p95 latency | 22.972 ms |
| max latency | 57.247 ms |
| throughput | 182.3 req/s |
| errors | 0 |
| within bound | true |

The constraint "90% of requests complete end-to-end within 10 s at >= 5 concurrent" is met with
roughly three orders of magnitude of headroom.

**Read that headroom honestly.** It comes from a 53-chunk in-memory index on one developer
machine with a deterministic provider that does no network I/O. It is a real measurement of this
code path and it is not a production figure: a hosted embedding call or an LLM generation round
trip would dominate. The benchmark exists so the claim is checkable, not so that 10 ms can be
quoted as a service-level number.

## Measurement rules

* Cache disabled during latency measurement; hit rate comes from a separate cached pass.
* One service instance shared by all worker threads - the requirement is about a single instance.
* `--assert` exits non-zero when p90 exceeds the bound or any request errors, so the claim is
  enforceable rather than decorative.

## Cost model

`src/ragserve/evaluation/cost.py` + `configs/pricing.json`.

* Token counts come from a **measured run**, never from an assumption.
* Prices are configuration, and unset prices are `null`. The report then says "no price is
  configured" instead of printing a made-up `0.00`. Inventing prices is the easiest way to make
  a cost table look authoritative and mean nothing.
* Every cost figure is tagged `estimate`: it is arithmetic over a stated price list, not a bill.

Measured per-call tokens come from `run_eval.py` (`token_usage_total` over 27 cases). To turn
that into a cost, fill `configs/pricing.json` for the model you actually use.
