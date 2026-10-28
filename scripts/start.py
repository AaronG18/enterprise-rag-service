#!/usr/bin/env python3
"""One-command start: build the corpus if needed, index it, serve the API and the UI.

    python scripts/start.py                 # 127.0.0.1:8174, deterministic provider
    python scripts/start.py --port 9000
    python scripts/start.py --provider codebuddy-serve --endpoint http://127.0.0.1:8788 --model hy3
    python scripts/start.py --provider openai-compatible --endpoint https://api.example.com/v1 \\
        --model my-model --api-key-env OPENAI_API_KEY

The default path needs no key, no network and no database: the corpus is generated
deterministically and indexed in memory at startup.

If the requested port is already taken by another service, a free port is chosen instead and
the real URL is printed - a reviewer must never end up looking at somebody else's application.
"""
from __future__ import annotations

import argparse
import errno
import os
import socket
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

DEFAULT_PORT = 8174

from ragserve.api import create_server  # noqa: E402


def port_is_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.5)
        return probe.connect_ex((host, port)) != 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--provider", default="deterministic",
                        choices=("deterministic", "codebuddy-serve", "openai-compatible"))
    parser.add_argument("--endpoint", default="",
                        help="required for codebuddy-serve and openai-compatible")
    parser.add_argument("--model", default="", help="model version to report / use")
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY",
                        help="env var holding the key for openai-compatible (never logged)")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    if args.provider in ("codebuddy-serve", "openai-compatible") and not args.endpoint:
        parser.error("--endpoint is required for %s" % args.provider)

    requested_port = args.port
    if not port_is_free(args.host, requested_port):
        print("NOTE: port %d is already in use by another service on this machine; "
              "choosing a free port instead." % requested_port)

    api_key = os.environ.get(args.api_key_env, "") if args.provider == "openai-compatible" else ""
    if args.provider == "openai-compatible" and not api_key:
        print("NOTE: %s is not set; the server will start but model calls need a key "
              "(supply it per request from the UI, or export it)." % args.api_key_env)

    server = create_server(REPO_ROOT, host=args.host, port=args.port,
                           provider=args.provider, model_version=args.model,
                           endpoint=args.endpoint)
    server.serve(open_browser=not args.no_browser)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
