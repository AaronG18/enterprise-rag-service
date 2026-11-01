"""Command-line surfaces, all reached through scripts/run.py.

The package exists so that `scripts/` can hold exactly one entry point: the brief asks for a single
one-click script, and twelve scripts in a folder is not that.
"""
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
