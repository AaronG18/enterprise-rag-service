"""pr-hygiene must fail loudly, but it must not fail by surprise.

The workflow's evidence step greps the PR body for a few needles, and a separate step checks the
branch name and every commit subject against regexes. `.github/PULL_REQUEST_TEMPLATE.md` is the
body every new PR starts from, so if the template stops satisfying those needles, **every future PR
fails at the gate** with a message that points at something the author did write.

That nearly happened: the template's own commands block was labelled `Command(s):`, which does not
contain the string `Commands`, and the needle was satisfied only by the word "commands" sitting in
an unrelated checklist line. One edit to that line would have turned pr-hygiene red for every PR.

These tests read the needles and the regexes straight out of the workflow file, so the gate and the
template cannot drift apart unnoticed: if they do, `scripts/run.py` goes red locally instead of CI
going red on somebody's pull request.
"""
from __future__ import annotations

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOW = os.path.join(REPO_ROOT, ".github", "workflows", "harness.yml")
TEMPLATE = os.path.join(REPO_ROOT, ".github", "PULL_REQUEST_TEMPLATE.md")


def _workflow() -> str:
    with open(WORKFLOW, "r", encoding="utf-8") as fh:
        return fh.read()


def _template() -> str:
    with open(TEMPLATE, "r", encoding="utf-8") as fh:
        return fh.read()


def evidence_needles(workflow: str) -> list:
    """The strings pr-hygiene greps the PR body for (case-insensitive)."""
    match = re.search(r"for needle in ([^;]+);", workflow)
    assert match, "no needle list found in %s" % WORKFLOW
    return re.findall(r'"([^"]+)"', match.group(1))


def branch_regex(workflow: str) -> str:
    match = re.search(r"grep -Eq '(\^[^']+)'", workflow)
    assert match, "no branch-name regex found in %s" % WORKFLOW
    return match.group(1)


def commit_subject_regex(workflow: str) -> str:
    match = re.search(r"grep -Eq '(\^#[^']+)'", workflow)
    assert match, "no commit-subject regex found in %s" % WORKFLOW
    return match.group(1)


class TestPrTemplateSatisfiesEvidenceGate(unittest.TestCase):
    """A PR opened from the template must clear the evidence step with no edits."""

    def test_template_contains_every_needle(self):
        needles = evidence_needles(_workflow())
        self.assertTrue(needles, "the workflow declares no needles")
        body = _template().lower()
        for needle in needles:
            self.assertIn(needle.lower(), body,
                          "the PR template does not contain %r, so every PR opened from it "
                          "fails pr-hygiene" % needle)

    def test_commands_is_a_heading_not_an_incidental_word(self):
        """Regression: 'Commands' used to be satisfied only by the word 'commands' inside the
        checklist line '... behaviour or commands changed', while the commands block itself was
        labelled 'Command(s):'. Rewording that line would have failed every PR."""
        self.assertRegex(_template(), r"(?im)^\s*##\s+Commands\s*$",
                         "the template needs an explicit '## Commands' heading")

    def test_evidence_is_a_heading(self):
        self.assertRegex(_template(), r"(?im)^\s*##\s+Evidence\s*$",
                         "the template needs an explicit '## Evidence' heading")


class TestPrHygieneRegexes(unittest.TestCase):
    """The regexes the gate enforces must do what the repo says they do."""

    def test_branch_name_accepts_type_issue_slug(self):
        pattern = branch_regex(_workflow())
        for good in ["feat/84-keyless-delivery-default", "fix/57-cache-eviction",
                     "feat/8-corpus-diagnosis"]:
            self.assertRegex(good, pattern, "%s should be an acceptable branch name" % good)

    def test_branch_name_rejects_a_branch_without_an_issue_number(self):
        """Measured: 'corpus-expansion-diagnosis' failed pr-hygiene twice for exactly this."""
        pattern = branch_regex(_workflow())
        for bad in ["corpus-expansion-diagnosis", "main", "my-feature", "feat/no-number"]:
            self.assertNotRegex(bad, pattern, "%s should be rejected" % bad)

    def test_commit_subject_needs_an_issue_reference(self):
        pattern = commit_subject_regex(_workflow())
        self.assertRegex("#84 keyless delivery default: real embedding model becomes opt-in",
                         pattern)
        self.assertRegex("#84: tighten the gate", pattern)
        self.assertNotRegex("tighten the gate", pattern)


if __name__ == "__main__":
    unittest.main()
