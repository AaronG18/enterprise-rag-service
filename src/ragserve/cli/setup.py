#!/usr/bin/env python
"""Download the local model runtime and weights the model-backed path needs.

Why this script exists
----------------------
The repository ships a keyless deterministic backend so a cold clone always runs. The real,
industrial-grade models - a multilingual embedding model and a cross-encoder reranker - are
**not** committed: they are about 1 GB of binaries, and committing them would bloat every clone.
So `vendor/` and `models/` are gitignored, and this script rebuilds them.

That means a reviewer does not get the models by `git pull`; they get them by running this one
command. It is deliberately placed at a fixed path inside the repository (`vendor/llama.cpp`,
`models/`) rather than in `%LOCALAPPDATA%` or `~/.cache`, so the service config, the docs and this
script can all point at the same predictable location instead of leaving the reviewer to guess
where the model ended up.

What it downloads
-----------------
1. `llama.cpp` (build b12015) Windows CPU build - a self-contained server speaking an
   OpenAI-compatible `/v1/embeddings` **and** a `/v1/rerank` endpoint for cross-encoder
   rerankers. No installer, no service, no admin rights: it is just an exe plus DLLs.
2. `bge-m3` (Q8_0, 1024-d) - multilingual (CN/EN) embedding model, free for commercial use.
3. `bge-reranker-v2-m3` (Q4_K_M) - multilingual cross-encoder reranker.

Both models are reached over plain HTTP with the standard library, so nothing here adds a
third-party Python dependency (INV-1).

Mirrors: the canonical hosts (`objects.githubusercontent.com`, `huggingface.co`) are unreachable
from some networks. Each file therefore has a mirror list and the first source that answers wins.

Usage
-----
    python scripts/run.py --setup            # download anything missing, verify what is present
    python scripts/run.py --setup --check    # report only, download nothing
"""
from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile

from . import REPO_ROOT
VENDOR = os.path.join(REPO_ROOT, "vendor", "llama.cpp")
MODELS = os.path.join(REPO_ROOT, "models")

LLAMA_BUILD = "b12015"
LLAMA_ASSET = "llama-%s-bin-win-cpu-x64.zip" % LLAMA_BUILD
LLAMA_SOURCES = [
    # ghproxy fronts GitHub release assets, which are otherwise served from a host that some
    # networks cannot reach.
    "https://ghproxy.net/https://github.com/ggml-org/llama.cpp/releases/download/"
    "%s/%s" % (LLAMA_BUILD, LLAMA_ASSET),
    "https://github.com/ggml-org/llama.cpp/releases/download/%s/%s" % (LLAMA_BUILD, LLAMA_ASSET),
]

WEIGHTS = [
    ("bge-m3-q8_0.gguf", [
        "https://hf-mirror.com/ggml-org/bge-m3-Q8_0-GGUF/resolve/main/bge-m3-q8_0.gguf",
        "https://huggingface.co/ggml-org/bge-m3-Q8_0-GGUF/resolve/main/bge-m3-q8_0.gguf",
    ]),
    ("bge-reranker-v2-m3-q4_k_m.gguf", [
        "https://hf-mirror.com/gpustack/bge-reranker-v2-m3-GGUF/resolve/main/"
        "bge-reranker-v2-m3-Q4_K_M.gguf",
        "https://huggingface.co/gpustack/bge-reranker-v2-m3-GGUF/resolve/main/"
        "bge-reranker-v2-m3-Q4_K_M.gguf",
    ]),
]

MIN_WEIGHT_BYTES = 10 * 1024 * 1024  # a real GGUF is hundreds of MB; anything tiny is an error page


def _fetch(url: str, dest: str, label: str) -> bool:
    """Stream url to dest. Returns True on success."""
    for attempt_url in (url,):
        try:
            req = urllib.request.Request(attempt_url, headers={"User-Agent": "curl"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                total = int(resp.headers.get("Content-Length") or 0)
                downloaded = 0
                chunk = 1 << 20
                with open(dest, "wb") as fh:
                    while True:
                        block = resp.read(chunk)
                        if not block:
                            break
                        fh.write(block)
                        downloaded += len(block)
                        if total:
                            pct = 100 * downloaded / total
                            sys.stdout.write("\r   %s %5.1f%%" % (label, pct))
                            sys.stdout.flush()
                sys.stdout.write("\r   %s done (%d bytes)%s\n"
                                 % (label, downloaded, " " * 12))
            return True
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
            sys.stdout.write("\n   %s failed: %s\n" % (label, exc))
            if os.path.exists(dest):
                os.remove(dest)
            return False
    return False


def _download_any(sources, dest: str, label: str) -> bool:
    for i, url in enumerate(sources, 1):
        print("  source %d/%d" % (i, len(sources)))
        if _fetch(url, dest, label):
            return True
    return False


def ensure_runtime() -> bool:
    exe = os.path.join(VENDOR, "llama-server.exe")
    if os.path.exists(exe):
        print("runtime: present (%s)" % exe)
        return True
    if sys.platform != "win32":
        print("runtime: SKIPPED - this bundled build is Windows x64 only.")
        print("         On Linux/macOS build llama.cpp from source, or run Ollama, then point")
        print("         embedding_endpoint / reranker_endpoint at it (see README).")
        return False
    print("runtime: downloading llama.cpp %s ..." % LLAMA_BUILD)
    os.makedirs(VENDOR, exist_ok=True)
    zip_path = os.path.join(VENDOR, "llama.zip")
    if not _download_any(LLAMA_SOURCES, zip_path, "llama.cpp"):
        return False
    try:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(VENDOR)
    except zipfile.BadZipFile:
        print("   downloaded file is not a valid zip (a proxy error page?)")
        return False
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)
    print("runtime: extracted to %s" % VENDOR)
    return os.path.exists(exe)


def ensure_weights() -> bool:
    os.makedirs(MODELS, exist_ok=True)
    ok = True
    for name, sources in WEIGHTS:
        dest = os.path.join(MODELS, name)
        if os.path.exists(dest) and os.path.getsize(dest) >= MIN_WEIGHT_BYTES:
            print("weights: %-34s present (%.0f MB)"
                  % (name, os.path.getsize(dest) / 1e6))
            continue
        print("weights: downloading %s ..." % name)
        if not _download_any(sources, dest, name):
            ok = False
            continue
        if os.path.getsize(dest) < MIN_WEIGHT_BYTES:
            print("   %s is suspiciously small - treating as a failed download" % name)
            os.remove(dest)
            ok = False
    return ok


SERVERS = (
    ("embedding", "bge-m3-q8_0.gguf", 8011, ["--embedding"]),
    ("reranker", "bge-reranker-v2-m3-q4_k_m.gguf", 8012, ["--embedding", "--pooling", "rank"]),
)


def _listening(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.3)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _ready(port: int) -> bool:
    """The port is bound *before* the model finishes loading, so a listening socket is not ready.

    Waiting only for the socket let the first request hit a 503 and fall back to the deterministic
    backend - the reviewer saw a warning instead of the thing the quickstart promises. `/health`
    answers 200 only once the weights are loaded.
    """
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/health" % port, timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def server_binary() -> str:
    name = "llama-server.exe" if os.name == "nt" else "llama-server"
    return os.path.join(VENDOR, name)


def start_servers(wait_seconds: float = 180.0):
    """Start whichever model server is not already listening.

    Returns the processes this call started, so the caller can stop them again on exit. A server
    that is already listening is left alone: that is what makes the second run of the entry point
    skip the setup entirely.
    """
    binary = server_binary()
    if not os.path.isfile(binary):
        print("  llama-server not found at %s" % binary)
        return []
    started = []
    started_ports = []
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    for name, weight, port, extra in SERVERS:
        if _listening(port):
            print("  %-9s already listening on %d" % (name, port))
            continue
        path = os.path.join(MODELS, weight)
        if not os.path.isfile(path):
            print("  %-9s weights missing (%s)" % (name, weight))
            continue
        proc = subprocess.Popen(
            [binary, "-m", path] + extra + ["--host", "127.0.0.1", "--port", str(port)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags)
        started.append(proc)
        started_ports.append(port)
        print("  %-9s starting on %d (pid %d)" % (name, port, proc.pid))
    if not started:
        return []
    pending = list(started_ports)  # only the ones this call started need waiting for
    print("  waiting for the models to load...")
    deadline = time.time() + wait_seconds
    for port in pending:
        while not _ready(port) and time.time() < deadline:
            time.sleep(1.0)
        if not _ready(port):
            print("  port %d did not become ready within %.0f s" % (port, wait_seconds))
    return started


def stop_servers(processes) -> None:
    for proc in processes:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except Exception:
                proc.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="report what is present; download nothing")
    args = parser.parse_args()

    if args.check:
        exe = os.path.join(VENDOR, "llama-server.exe")
        print("runtime:", "present" if os.path.exists(exe) else "MISSING")
        for name, _ in WEIGHTS:
            p = os.path.join(MODELS, name)
            if os.path.exists(p):
                print("weights: %-34s present (%.0f MB)" % (name, os.path.getsize(p) / 1e6))
            else:
                print("weights: %-34s MISSING" % name)
        return 0 if os.path.exists(exe) else 1

    runtime_ok = ensure_runtime()
    weights_ok = ensure_weights()
    print("\nsummary: runtime=%s weights=%s" % ("ok" if runtime_ok else "MISSING",
                                                "ok" if weights_ok else "MISSING"))
    if runtime_ok and weights_ok:
        print("\nStart the model servers with:")
        print("  %s -m %s --embedding --host 127.0.0.1 --port 8011"
              % (os.path.join(VENDOR, "llama-server.exe"),
                 os.path.join(MODELS, "bge-m3-q8_0.gguf")))
        print("  %s -m %s --embedding --pooling rank --host 127.0.0.1 --port 8012"
              % (os.path.join(VENDOR, "llama-server.exe"),
                 os.path.join(MODELS, "bge-reranker-v2-m3-q4_k_m.gguf")))
        return 0
    print("\nSome components could not be fetched. The service still runs on its keyless "
          "deterministic backend; see README for the model-backed setup.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
