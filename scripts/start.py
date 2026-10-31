#!/usr/bin/env python3
"""One-command start: build the corpus if needed, index it, serve the API and the UI.

    python scripts/start.py                 # 127.0.0.1:8174; fully offline, no credentials needed
    python scripts/start.py --port 9000
    python scripts/start.py --port 0        # let the OS pick any free port
    python scripts/start.py --provider codebuddy-serve --endpoint http://127.0.0.1:8788 --model hy3
    python scripts/start.py --provider openai-compatible --endpoint https://api.example.com/v1 \\
        --model my-model --api-key-env OPENAI_API_KEY

The delivered service runs with NO credentials at all: generation and embeddings both default to
the offline deterministic backend, so a reviewer can clone this repository and start it straight
away. A real embedding model is opt-in and is a config/flag change, never a code change:

    python scripts/start.py --embedding-provider openai-compatible

That path uses embedding_endpoint / embedding_model / embedding_api_key_env from
configs/retrieval.json (a ready BGE-M3 preset) and needs that key; without it the server fails at
index build with a clear message rather than silently degrading. Point those three fields at any
OpenAI-compatible /v1/embeddings service - SiliconFlow, DashScope, a local Ollama - to swap
models. The corpus is generated deterministically and indexed in memory at startup either way.

The retrieval mode and reranker are configuration, not code (FR-1). They can be set in
configs/retrieval.json (mode / rerank_enabled / reranker_provider) OR overridden on the command
line, with no edit to any source file:

    python scripts/start.py --mode vector_only            # vector-only retrieval
    python scripts/start.py --mode hybrid --rerank off   # hybrid, reranker disabled
    python scripts/start.py --mode hybrid --rerank on    # hybrid + cross-encoder reranker

Examples:
    python scripts/start.py --embedding-provider deterministic      # default, fully offline
    python scripts/start.py --embedding-provider openai-compatible  # real model, needs a key
    python scripts/start.py --mode hybrid --rerank on --reranker-provider cross-encoder

Port selection is deterministic: if the requested port is taken by another service, the first
free port above it is used (8174 -> 8175 -> ...) and the real URL is printed. A reviewer must
never end up looking at somebody else's application.
"""
from __future__ import annotations

import argparse
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

DEFAULT_PORT = 8174

from ragserve.api import create_server
from ragserve.retrieval.embeddings import ProviderUnavailable  # noqa: E402
from ragserve.retrieval.pipeline import RetrievalConfig  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help="preferred port; if it is taken the next free port is used (0 = any)")
    parser.add_argument("--provider", default="deterministic",
                        choices=("deterministic", "codebuddy-serve", "openai-compatible"))
    parser.add_argument("--embedding-provider", default="deterministic",
                        choices=("deterministic", "openai-compatible"),
                        help="embedding backend (default: deterministic = offline, no key; "
                             "openai-compatible = real model, needs embedding_api_key_env)")
    parser.add_argument("--endpoint", default="",
                        help="required for codebuddy-serve and openai-compatible")
    parser.add_argument("--model", default="", help="model version to report / use")
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY",
                        help="env var holding the key for openai-compatible (never logged)")
    parser.add_argument("--mode", default=None, choices=("vector_only", "hybrid"),
                        help="retrieval mode; overrides configs/retrieval.json (FR-1)")
    parser.add_argument("--rerank", default=None, choices=("on", "off"),
                        help="enable/disable the reranker; overrides configs/retrieval.json (FR-1)")
    parser.add_argument("--reranker-provider", default=None, choices=("deterministic", "cross-encoder"),
                        help="which reranker to use when reranking is on; overrides the config")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    if args.provider in ("codebuddy-serve", "openai-compatible") and not args.endpoint:
        parser.error("--endpoint is required for %s" % args.provider)

    api_key = os.environ.get(args.api_key_env, "") if args.provider == "openai-compatible" else ""
    if args.provider == "openai-compatible" and not api_key:
        print("NOTE: %s is not set; the server will start but model calls need a key "
              "(supply it per request from the UI, or export it)." % args.api_key_env)
    emb_key_env = args.api_key_env
    if args.embedding_provider == "openai-compatible":
        emb_key_env = RetrievalConfig.from_json(
            os.path.join(REPO_ROOT, "configs", "retrieval.json")).embedding_api_key_env
        if not os.environ.get(emb_key_env, ""):
            print("NOTE: %s is not set; the server will start but the embedding index build needs "
                  "it. Run with --embedding-provider deterministic for a fully offline service, or "
                  "export %s." % (emb_key_env, emb_key_env))

    try:
        server = create_server(REPO_ROOT, host=args.host, port=args.port,
                               provider=args.provider, model_version=args.model,
                               endpoint=args.endpoint,
                               embedding_provider=args.embedding_provider,
                               mode=args.mode,
                               rerank_enabled=(args.rerank == "on") if args.rerank else None,
                               reranker_provider=args.reranker_provider)
    except ProviderUnavailable as exc:
        print("embedding provider unavailable: %s" % exc)
        print("set %s or re-run with: --embedding-provider deterministic" % emb_key_env)
        return 1
    server.serve(open_browser=not args.no_browser)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
