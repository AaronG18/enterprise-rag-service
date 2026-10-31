---
name: harness-maintenance
description: Change the harness itself - adding or amending a rule, a skill, a requirement row or a CI job - without turning the gate into decoration. Use when editing harness/RULES.md, harness/ROLES.md, harness/skills/, harness/requirements.toml, docs/REQUIREMENTS.md or the GitHub Actions workflows, or when a check seems to have stopped catching anything.
---

# Skill: harness-maintenance

## When to use

Any time the change is *about* the harness rather than about the service: a new rule, a new
skill, a new requirement row, a changed CI job, or a check that has quietly stopped working.

This harness is only worth what its checks are worth. R16 says the gate is code and code needs
tests; this skill is the procedure for that.

## The four-file contract

A rule in this repository is not a paragraph. It is four things, and the change is incomplete
until all four exist:

| Artifact | What it is | What breaks without it |
|---|---|---|
| `harness/RULES.md` | the rule text and its row in the enforcement map | the rule is not discoverable |
| `harness/requirements.toml` | a `[[requirement]]` row with the verification | the rule is not enforced in CI |
| `docs/REQUIREMENTS.md` | the same id in the human-readable matrix | the two drift apart and the contract test fails |
| a test or workflow | the thing that can fail | the rule is decoration |

The id is the join key. `tests/test_requirements_gate.py` asserts that every id in the matrix has a
row in the manifest and vice versa, so a new id must be added in both places in the same change.

## Procedure

1. **Decide whether it is a rule at all.** A rule is a rule when violating it would quietly
   produce a wrong number, a broken promise or an unreviewable claim. Anything else is a
   convention and belongs in `CONTRIBUTING.md` or a skill.

2. **Write the rule text with the failure it prevents.** "No issue, no code" is enforceable.
   "Write good code" is not. If you cannot name the failure signal, it is not a rule yet.

3. **Give it an id that does not exist yet.** The ids are `R<n>`; the requirement ids are
   `R-<nn>`. They are different namespaces and the dangling-reference check knows it.

4. **Write the failing test first (R4).** The test must go red before the fix, and the red
   output goes in the PR body. A check that was never red is indistinguishable from a check that
   cannot fail.

5. **Give it an enforcement row.** Put a real path in the "where it is checked" cell
   (`tests/test_x.py`), or the literal word `manual` when a human reviewer is genuinely the
   enforcement - R4 and R5 cannot be automated, and pretending otherwise is worse than saying so.
   `tests/test_harness_selfcheck.py` enforces both halves of that contract.

6. **Make the rule id visible in the code that enforces it.** The traceability check looks for the
   id in `tests/`, `.github/`, `scripts/` or `src/`. A comment naming the rule next to the check
   is how the link is kept honest - the CI workflows do this at the top of the file.

7. **Add the requirement row and the matrix row** (same id), then run
   `python scripts/verify_requirements.py` and `python scripts/run_tests.py`.

8. **Fold the lesson in (R11).** If the rule was written *after* something broke, say in the rule
   what broke - that is what makes the next reader trust it.

## Adding a skill

A skill is a `SKILL.md` with YAML frontmatter (`name`, `description`) and a body that answers
"when do I use this?". The checks in `tests/test_harness_selfcheck.py` are strict on purpose:

* `name` must equal the directory name;
* `description` must say when to use it - a skill you cannot find at the moment you need it is
  not a skill;
* every relative link must resolve;
* something must point at it (the read order at the top of `harness/RULES.md` names them all).

New skills go in `harness/skills/<name>/SKILL.md` and get listed in that read order.

## Changing CI

CI is hermetic by contract (R7): no install step, no key, no network. Two rules follow from that,
and both are checked:

* every workflow that runs the service or the evaluation must pin
  `RAGSERVE_EMBEDDING_PROVIDER=deterministic` and `RAGSERVE_RERANKER_PROVIDER=deterministic`.
  Without the pins, the shipped config points at a local model server that CI does not have, and
  the run would silently fall back - or fail;
* no workflow may install anything. The repository ships stdlib-only code (INV-1), so an install
  step is a smell that the dependency crept in.

## Gotchas

* **A rule id is not a requirement id.** `R16` (rule) and `R-16` (requirement) are different
  things. The dangling-reference check only looks at the no-hyphen form.
* **The enforcement map is not prose any more.** Cells that point at a file are resolved against
  the repository; a cell that means "a human reads this" must say `manual`.
* **Adding a rule without a failing test breaks the traceability check**, which is the point:
  the failure is the evidence that the rule binds.
* **Do not weaken a floor to make a build green.** The golden-set floors in
  `tests/test_golden_retrieval.py` are measured values; lowering one is a deliberate, evidenced
  act (R2, R3), not a repair.
