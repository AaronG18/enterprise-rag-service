"""Harness self-check: the rules, the skills and the CI must enforce something.

Enforces R16 (the gate is code, and code needs tests) and R17 (no front end).

The gap this file closes: `harness/RULES.md` carries an "Enforcement map" that used to be prose
a human was trusted to keep true. Nothing checked it. A rule could be added with no enforcement, a
map row could point at a file that no longer exists, a skill could be deleted while the docs kept
pointing at it, and CI could grow a workflow that quietly broke the hermetic promise - and the
harness would still have been green, which is the failure mode R16 exists to prevent.

Everything here is hermetic: it reads files and runs nothing that needs the network, a model
server or a credential.
"""
from __future__ import annotations

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HARNESS = os.path.join(REPO_ROOT, "harness")
SKILLS_DIR = os.path.join(HARNESS, "skills")
WORKFLOWS = os.path.join(REPO_ROOT, ".github", "workflows")

# Where a rule may be enforced by code. RULES.md itself is excluded: a rule always mentions
# itself there, which would make the traceability check vacuous.
CODE_SURFACES = ("tests", ".github", "scripts", "src")

PATH_SUFFIXES = (".md", ".py", ".yml", ".yaml", ".toml", ".json", ".txt")
RULE_HEADING = re.compile(r"^## (R\d+) - ", re.MULTILINE)
MAP_ROW = re.compile(r"^\| (R\d+) \| (.+?) \| (.+?) \|$", re.MULTILINE)
RULE_ID = re.compile(r"\bR(\d+)\b")
BACKTICKED = re.compile(r"`([^`]+)`")
MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def repo_file(*parts: str) -> str:
    return os.path.join(REPO_ROOT, *parts)


def read(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def rule_ids_in(text: str):
    """Every rule id mentioned in a piece of text, as 'R<n>' strings."""
    return {"R%s" % n for n in RULE_ID.findall(text)}


def is_path_like(token: str) -> bool:
    token = token.strip()
    if not token or token.startswith("#") or "://" in token:
        return False
    return "/" in token or token.endswith(PATH_SUFFIXES)


def resolve(token: str):
    """Resolve a path token the way the rules write them.

    The map writes `ROLES.md` for a file that lives in harness/, and `tests/x.py` for one that
    lives at the root, so several roots are tried before giving up.
    """
    token = token.strip().rstrip("/")
    roots = (REPO_ROOT, HARNESS, os.path.join(REPO_ROOT, "scripts"),
             os.path.join(REPO_ROOT, "docs"), os.path.join(REPO_ROOT, ".github"))
    for root in roots:
        candidate = os.path.join(root, *token.split("/"))
        if os.path.exists(candidate):
            return candidate
    return None


def all_code_files():
    for surface in CODE_SURFACES:
        base = repo_file(*surface.split("/"))
        if not os.path.isdir(base):
            continue
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules")]
            for name in files:
                if os.path.splitext(name)[1] in PATH_SUFFIXES:
                    yield os.path.join(root, name)


class TestRuleTraceability(unittest.TestCase):
    """R16: the gate is code, and code needs tests - including the rules' own map."""

    @classmethod
    def setUpClass(cls):
        cls.rules_text = read(os.path.join(HARNESS, "RULES.md"))
        cls.headings = RULE_HEADING.findall(cls.rules_text)
        cls.map_rows = {rid: (where, signal) for rid, where, signal in MAP_ROW.findall(cls.rules_text)}

    def test_every_rule_has_exactly_one_enforcement_row(self):
        missing = [rid for rid in self.headings if rid not in self.map_rows]
        self.assertEqual(missing, [],
                         "rules with no row in the enforcement map: %s" % missing)
        orphan = [rid for rid in self.map_rows if rid not in self.headings]
        self.assertEqual(orphan, [],
                         "enforcement-map rows for rules that do not exist: %s" % orphan)

    def test_rule_ids_are_unique(self):
        duplicates = [rid for rid in set(self.headings) if self.headings.count(rid) > 1]
        self.assertEqual(duplicates, [], "duplicate rule headings: %s" % duplicates)

    def test_enforcement_map_points_at_files_that_exist(self):
        dangling = []
        for rid, (where, _signal) in sorted(self.map_rows.items()):
            for token in BACKTICKED.findall(where):
                if not is_path_like(token):
                    continue
                if resolve(token) is None:
                    dangling.append("%s -> %s" % (rid, token))
        self.assertEqual(dangling, [], "enforcement map points at missing paths: %s" % dangling)

    def test_every_rule_is_enforced_by_code_or_marked_manual(self):
        """A rule that nothing checks is decoration.

        Either the rule id appears in something that can fail (a test, a workflow, a script or the
        implementation), or the map marks it `manual`, which is an honest statement that a human
        reviewer is the enforcement - R4 and R5 cannot be automated at all.
        """
        enforced_in_code = set()
        for path in all_code_files():
            enforced_in_code |= rule_ids_in(read(path))
        for name in sorted(os.listdir(WORKFLOWS)):
            if name.endswith((".yml", ".yaml")):
                enforced_in_code |= rule_ids_in(read(os.path.join(WORKFLOWS, name)))

        unenforced = []
        for rid in self.headings:
            where = self.map_rows.get(rid, ("", ""))[0]
            if "manual" in where.lower():
                continue
            if rid in enforced_in_code:
                continue
            unenforced.append(rid)
        self.assertEqual(unenforced, [],
                         "rules that nothing enforces and are not marked manual: %s" % unenforced)

    def test_no_dangling_rule_references(self):
        """Every R<n> mentioned in the harness and the docs must name a rule that exists."""
        known = set(self.headings)
        sources = [os.path.join(HARNESS, "RULES.md"), os.path.join(HARNESS, "ROLES.md"),
                   repo_file("README.md"), repo_file("AGENTS.md"), repo_file("CONTRIBUTING.md")]
        if os.path.isdir(SKILLS_DIR):
            for name in sorted(os.listdir(SKILLS_DIR)):
                source = os.path.join(SKILLS_DIR, name, "SKILL.md")
                if os.path.isfile(source):
                    sources.append(source)
        dangling = {}
        for source in sources:
            if not os.path.isfile(source):
                continue
            unknown = rule_ids_in(read(source)) - known
            if unknown:
                dangling[os.path.relpath(source, REPO_ROOT)] = sorted(unknown)
        self.assertEqual(dangling, {}, "references to rules that do not exist: %s" % dangling)


class TestSkillValidity(unittest.TestCase):
    """A skill nobody can find, or that points at a file that moved, is decoration."""

    @classmethod
    def setUpClass(cls):
        cls.skills = []
        if os.path.isdir(SKILLS_DIR):
            for name in sorted(os.listdir(SKILLS_DIR)):
                source = os.path.join(SKILLS_DIR, name, "SKILL.md")
                if os.path.isdir(os.path.join(SKILLS_DIR, name)) and os.path.isfile(source):
                    cls.skills.append((name, source))

    def test_at_least_one_skill_exists(self):
        self.assertTrue(self.skills, "harness/skills/ contains no skill")

    def test_every_skill_has_valid_frontmatter(self):
        for name, source in self.skills:
            text = read(source)
            self.assertTrue(text.startswith("---"), "%s lacks frontmatter" % name)
            head = text.split("---", 2)[1] if text.count("---") >= 2 else ""
            self.assertIn("name:", head, "%s frontmatter has no name" % name)
            self.assertIn("description:", head, "%s frontmatter has no description" % name)

    def test_skill_name_matches_its_directory(self):
        for name, source in self.skills:
            head = read(source).split("---", 2)[1]
            declared = re.search(r"^name:\s*(\S+)\s*$", head, re.MULTILINE)
            self.assertIsNotNone(declared, "%s frontmatter has no name field" % name)
            self.assertEqual(declared.group(1), name,
                             "%s declares a different name than its directory" % name)

    def test_skill_description_says_when_to_use_it(self):
        """A skill that does not say when to use it cannot be found at the moment it matters."""
        for name, source in self.skills:
            head = read(source).split("---", 2)[1]
            description = re.search(r"^description:\s*(.+)$", head, re.MULTILINE)
            self.assertIsNotNone(description, "%s has no description" % name)
            self.assertIn("Use when", description.group(1),
                          "%s description must say when to use the skill" % name)

    def test_skill_links_resolve(self):
        broken = []
        for name, source in self.skills:
            base = os.path.dirname(source)
            for target in MARKDOWN_LINK.findall(read(source)):
                if target.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                path = target.split("#", 1)[0]
                if not path:
                    continue
                if not os.path.exists(os.path.normpath(os.path.join(base, path))):
                    broken.append("%s -> %s" % (name, target))
        self.assertEqual(broken, [], "skills link to files that do not exist: %s" % broken)

    def test_every_skill_is_referenced_from_the_harness(self):
        """Otherwise the skill is unreachable: no document points a reader at it."""
        haystack = []
        for source in (os.path.join(HARNESS, "RULES.md"), os.path.join(HARNESS, "ROLES.md"),
                       repo_file("AGENTS.md"), repo_file("CONTRIBUTING.md"), repo_file("README.md")):
            if os.path.isfile(source):
                haystack.append(read(source))
        joined = "\n".join(haystack)
        orphans = [name for name, _source in self.skills if name not in joined]
        self.assertEqual(orphans, [],
                         "skills nothing points at: %s" % orphans)


class TestWorkflowHermeticity(unittest.TestCase):
    """R7: CI must run with no install step, no key and no network."""

    @classmethod
    def setUpClass(cls):
        cls.workflows = []
        if os.path.isdir(WORKFLOWS):
            for name in sorted(os.listdir(WORKFLOWS)):
                if name.endswith((".yml", ".yaml")):
                    cls.workflows.append((name, os.path.join(WORKFLOWS, name)))

    def test_workflows_never_install_anything(self):
        offenders = []
        for name, path in self.workflows:
            text = read(path)
            if "pip install" in text or "npm install" in text or "npm ci" in text:
                offenders.append(name)
        self.assertEqual(offenders, [],
                         "workflows must stay install-free (INV-1): %s" % offenders)

    def test_workflows_that_run_the_service_pin_the_offline_providers(self):
        """A workflow that runs the evaluation or the service must pin both stages.

        Without the pins, the shipped config points at a local model server that CI does not have,
        and the run silently falls back - or fails. The pin is what makes CI hermetic.
        """
        offenders = []
        for name, path in self.workflows:
            text = read(path)
            runs_service = ("run_eval.py" in text or "run_tests.py" in text
                            or "start.py" in text or "verify_requirements.py" in text)
            if not runs_service:
                continue
            for var in ("RAGSERVE_EMBEDDING_PROVIDER", "RAGSERVE_RERANKER_PROVIDER"):
                if var not in text or "deterministic" not in text:
                    offenders.append("%s (%s)" % (name, var))
        self.assertEqual(offenders, [],
                         "workflows that run the service must pin the offline providers: %s" % offenders)


class TestNoFrontEnd(unittest.TestCase):
    """R17: this repository ships a service, not an application."""

    FRONTEND_MARKERS = ("web/dist", "web/src", "npm install", "npm run build", "React + AntD")

    def test_shipped_code_does_not_reference_a_front_end(self):
        offenders = []
        this_file = os.path.abspath(__file__)
        for path in all_code_files():
            # This file names the markers it looks for, so it cannot be scanned for them.
            if os.path.abspath(path) == this_file:
                continue
            text = read(path)
            for marker in self.FRONTEND_MARKERS:
                if marker in text:
                    offenders.append("%s -> %s" % (os.path.relpath(path, REPO_ROOT), marker))
        self.assertEqual(offenders, [], "shipped code references a front end: %s" % offenders)

    def test_readme_and_deployment_doc_do_not_advertise_a_ui(self):
        for rel in ("README.md", os.path.join("docs", "deployment.md")):
            text = read(repo_file(*rel.split("/")))
            for marker in ("React + AntD", "npm install", "npm run build", "web/dist"):
                self.assertNotIn(marker, text, "%s still advertises the front end (%s)" % (rel, marker))

    def test_a_leftover_front_end_directory_cannot_be_committed(self):
        """node_modules is thousands of files; the ignore rule is what keeps it out of history."""
        with open(repo_file(".gitignore"), "r", encoding="utf-8") as fh:
            lines = [ln.strip() for ln in fh if ln.strip() and not ln.startswith("#")]
        self.assertIn("/web/", lines, "a stray web/ directory must stay gitignored")

    def test_one_entry_point_for_the_deliverables(self):
        """Two scripts that do the same job is how a reviewer ends up asking which one to run."""
        self.assertFalse(os.path.isfile(repo_file("scripts", "build_deliverables.py")),
                         "build_deliverables.py was folded into run_eval.py; do not resurrect it")


class TestDocsMatchConfig(unittest.TestCase):
    """The shipped configuration is the truth; the documentation must not contradict it.

    Observed failure this prevents: `docs/deployment.md` kept claiming "embeddings default to the
    offline deterministic backend" for months after the default had become the real keyless model.
    Nothing compared the two, so the docs quietly lied - and a reviewer reads the docs.
    """

    def _retrieval_config(self) -> dict:
        import json
        with open(repo_file("configs", "retrieval.json"), "r", encoding="utf-8") as fh:
            return json.load(fh)

    def test_shipped_embedding_default_is_documented(self):
        config = self._retrieval_config()
        readme = read(repo_file("README.md"))
        deployment = read(repo_file("docs", "deployment.md"))
        if config.get("embedding_provider") != "deterministic":
            model = str(config.get("embedding_model", ""))
            self.assertIn(model, readme,
                          "README must name the shipped embedding model (%s)" % model)
            self.assertIn(model, deployment,
                          "deployment.md must name the shipped embedding model (%s)" % model)

    def test_docs_do_not_claim_the_old_embedding_default(self):
        stale = "Embeddings default to the offline deterministic"
        for rel in ("README.md", os.path.join("docs", "deployment.md")):
            self.assertNotIn(stale, read(repo_file(*rel.split("/"))),
                             "%s states an embedding default that the config no longer has" % rel)

    def test_runtime_switches_are_documented(self):
        """FR-1: the modes and the reranker switch are configuration. If they are only in the
        config file, a reviewer cannot find them."""
        readme = read(repo_file("README.md"))
        for flag in ("--mode", "--rerank"):
            self.assertIn(flag, readme, "README must document the %s switch" % flag)

    def test_evaluation_report_names_the_corpus_and_case_count_it_measured(self):
        """The comparison report is a committed document, and nothing regenerates it.

        `run_eval.py --all` writes only to artifacts/, so the report can silently keep describing
        a corpus the repository no longer ships - which is exactly what happened: EPIC 15 grew the
        corpus from 30 to 85 cases and the report still quoted the old numbers, leaving a
        recommendation standing on a measurement nobody could reproduce (#92). Naming the corpus
        version and the case count makes that impossible: change the corpus and this goes red
        until the report is refreshed.
        """
        import json  # local import: this module is otherwise stdlib-only and import-light

        from ragserve.corpus.builder import CorpusConfig, build_corpus

        corpus = build_corpus(CorpusConfig.from_json(repo_file("configs", "corpus.json")))
        version = corpus.manifest["corpus_version"]
        with open(repo_file("eval", "eval_cases.json"), "r", encoding="utf-8") as fh:
            cases = json.load(fh)
        document = read(repo_file("docs", "eval", "retrieval-comparison.md"))
        self.assertIn(version, document,
                      "the comparison must name the corpus it measured (current %s)" % version)
        self.assertIn(str(len(cases)), document,
                      "the comparison must name the case count (current %d)" % len(cases))
        self.assertIn("provenance", document.lower(),
                      "the comparison must state the provenance of its numbers")


if __name__ == "__main__":
    unittest.main()
