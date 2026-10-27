#!/usr/bin/env python3
"""Hermetic test runner.

Deliberately uses only the standard library: this command must work on a cold clone and
in CI without any package index access. See PROJECT.md INV-1.

Usage:
    python scripts/run_tests.py                # everything
    python scripts/run_tests.py -v             # verbose
    python scripts/run_tests.py -k routing     # substring filter on test name
"""
from __future__ import annotations

import argparse
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR = os.path.join(REPO_ROOT, "tests")
SRC_DIR = os.path.join(REPO_ROOT, "src")

MIN_PYTHON = (3, 11)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-v", "--verbose", action="count", default=1)
    parser.add_argument("-k", "--keyword", default=None, help="filter tests by substring")
    args = parser.parse_args()

    if sys.version_info < MIN_PYTHON:
        print("requires Python >= %d.%d, found %d.%d" % (MIN_PYTHON + sys.version_info[:2]))
        return 2

    # Make `src/` importable without installing anything.
    if SRC_DIR not in sys.path:
        sys.path.insert(0, SRC_DIR)

    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=TESTS_DIR, top_level_dir=REPO_ROOT) if os.path.isdir(TESTS_DIR) \
        else unittest.TestSuite()

    if args.keyword:
        suite = _filter(suite, args.keyword)

    result = unittest.TextTestRunner(verbosity=args.verbose).run(suite)
    return 0 if result.wasSuccessful() else 1


def _filter(suite: unittest.TestSuite, keyword: str) -> unittest.TestSuite:
    """Keep only tests whose id() contains the keyword. Flattens nested suites."""
    flat: list[unittest.TestCase] = []

    def walk(s):
        for item in s:
            if isinstance(item, unittest.TestSuite):
                walk(item)
            elif keyword in item.id():
                flat.append(item)

    walk(suite)
    out = unittest.TestSuite()
    out.addTests(flat)
    return out


if __name__ == "__main__":
    raise SystemExit(main())
