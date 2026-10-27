#!/usr/bin/env python3
"""Build the corpus and write artifacts.

    python scripts/build_corpus.py                 # configs/corpus.json -> artifacts/
    python scripts/build_corpus.py --out DIR      # explicit output root

Deterministic: same config and same code -> same corpus_version, byte-identical files.
"""
from __future__ import annotations

import argparse
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

from ragserve.corpus.builder import CorpusConfig, build_corpus, write_artifacts  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=os.path.join(REPO_ROOT, "configs", "corpus.json"))
    parser.add_argument("--out", default=os.path.join(REPO_ROOT, "artifacts"))
    args = parser.parse_args()

    config = CorpusConfig.from_json(args.config) if os.path.isfile(args.config) else CorpusConfig()
    corpus = build_corpus(config)
    paths = write_artifacts(corpus, args.out)

    manifest = corpus.manifest
    print("corpus_version :", manifest["corpus_version"])
    print("documents      :", manifest["doc_count"], manifest["per_family"])
    print("languages      :", manifest["per_language"])
    print("chunks         :", manifest["chunk_count"])
    print("ocr documents  :", manifest["ocr_doc_count"], "(ratio %s)" % manifest["ocr_ratio"])
    print("artifacts      :", paths["dir"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
