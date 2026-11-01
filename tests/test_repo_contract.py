"""Repository contract tests (EPIC #1).

These guard the *infrastructure* promises the repo makes: required documents exist,
skills are well-formed, CI does its job, and no internal classification marker shape
is tracked. They are hermetic by construction.
"""
from __future__ import annotations

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REQUIRED_FILES = [
    "README.md",
    "PROJECT.md",
    "CONTRIBUTING.md",
    "AGENTS.md",
    "PROGRESS.md",
    "LICENSE",
    "docs/REQUIREMENTS.md",
    "harness/RULES.md",
    "harness/ROLES.md",
    "harness/skills/rag-eval/SKILL.md",
    "harness/skills/github-issue-workflow/SKILL.md",
    "harness/skills/evidence-and-testing/SKILL.md",
    "scripts/run.py",
    ".github/workflows/ci.yml",
    ".github/ISSUE_TEMPLATE/epic.md",
    ".github/ISSUE_TEMPLATE/sub-issue.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
]

# Generic shapes only: this test must never contain a company name itself.
MARKER_SHAPES = re.compile(
    r"\[[A-Za-z0-9]+ - (INTERNAL|RESTRICTED|CONFIDENTIAL)\]|MSIP_Label_[0-9a-f-]{36}_",
    re.IGNORECASE,
)
TEXT_SUFFIXES = {".md", ".py", ".yml", ".yaml", ".txt", ".toml"}


def repo_file(rel: str) -> str:
    return os.path.join(REPO_ROOT, *rel.split("/"))


def tracked_text_files():
    for root, dirs, files in os.walk(REPO_ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "artifacts", ".venv")]
        for name in files:
            if os.path.splitext(name)[1] in TEXT_SUFFIXES:
                yield os.path.join(root, name)


class TestRepositoryContract(unittest.TestCase):
    def test_required_files_exist_and_are_non_empty(self):
        missing = [f for f in REQUIRED_FILES
                   if not os.path.isfile(repo_file(f)) or os.path.getsize(repo_file(f)) == 0]
        self.assertEqual(missing, [], "missing or empty: %s" % missing)

    def test_gitignore_has_no_bare_data_rule(self):
        """A bare `data/` ignore rule silently swallows legit directories deeper in the tree."""
        with open(repo_file(".gitignore"), "r", encoding="utf-8") as fh:
            lines = [ln.strip() for ln in fh if ln.strip() and not ln.startswith("#")]
        self.assertNotIn("data/", lines)
        self.assertNotIn("data", lines)

    def test_ci_declares_hermetic_job_without_install_step(self):
        with open(repo_file(".github/workflows/ci.yml"), "r", encoding="utf-8") as fh:
            ci = fh.read()
        self.assertIn("hermetic-tests", ci)
        self.assertIn("scripts/run.py", ci)
        self.assertIn("--test", ci)
        self.assertNotIn("pip install", ci, "CI must stay install-free (INV-1)")

    def test_skills_have_valid_frontmatter(self):
        for rel in REQUIRED_FILES:
            if rel.endswith("SKILL.md"):
                with open(repo_file(rel), "r", encoding="utf-8") as fh:
                    head = fh.read(400)
                self.assertTrue(head.startswith("---"), "%s lacks frontmatter" % rel)
                self.assertIn("name:", head)
                self.assertIn("description:", head)

    def test_no_internal_classification_markers_tracked(self):
        offenders = []
        for path in tracked_text_files():
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                if MARKER_SHAPES.search(fh.read()):
                    offenders.append(os.path.relpath(path, REPO_ROOT))
        self.assertEqual(offenders, [], "classification marker shapes in: %s" % offenders)

    def test_rules_define_the_issue_first_contract(self):
        with open(repo_file("harness/RULES.md"), "r", encoding="utf-8") as fh:
            rules = fh.read()
        self.assertIn("No issue, no code", rules)
        self.assertIn("No evidence, no close", rules)
        # Added by the EPIC 10 retro: these are the rules the project actually needed.
        self.assertIn("Metric definitions are part of the change surface", rules)
        self.assertIn("Attribution must survive reproduction", rules)


if __name__ == "__main__":
    unittest.main()
