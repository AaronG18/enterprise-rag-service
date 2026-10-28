# CONTRIBUTING

This repository is developed **issue-first**. There is no "quick tweak" path: if there is
no issue describing it, the change does not exist yet.

## 1. The loop

```
open/refine issue  ->  branch  ->  test first (red)  ->  implement (green)
      ->  commit with issue ref  ->  push  ->  PR  ->  harness gate green
      ->  paste evidence into the issue  ->  close
```

Every step is mandatory. Skipping the "paste evidence" step means the branch stays open.

## 1a. The harness gate

`main` is protected. A change reaches it only through a pull request whose checks are green:

| Check | What it proves |
|---|---|
| `requirements-gate` | every row in `harness/requirements.toml` verified; failures are reported by row ID |
| `contract-gate` | hermetic tests, no scratch files, no credential shapes, publishable content, standard-library-only shipped code |
| `pr-hygiene` | branch name shape, every commit references an issue, PR body carries the evidence block |

Reproduce the gate locally before pushing:

```bash
python scripts/verify_requirements.py     # the full gate, ~17 s
```

A red gate is the loop working. Fix on the branch and push again; do not weaken the gate to get
green - if a row is wrong, that is its own issue with its own evidence.

## 2. Issue tree structure

Large changes use a parent/child structure:

* **EPIC** (`epic` label) - scope, motivation, acceptance criteria written *before* work starts,
  plus its list of child issues.
* **SUB** (`sub` label) - one reviewable unit. Body states: what changes, how "done" is
  decided, what command proves it.

An EPIC is closed only when all of its children are closed **and** its own acceptance
criteria are verified by a command. Partial delivery does not close an EPIC.

## 3. Conventions

| Thing | Convention |
|---|---|
| Branch | `<type>/<issue-number>-<slug>`, e.g. `feat/12-hybrid-retrieval`, `fix/23-cache-poisoning` |
| Commit message | start with `#<issue-number> `, then imperative English summary |
| PR | body must contain `Fixes #<n>` (or `Closes #<n>`), and must link test output |
| New test | must fail before the change; if it passes without the fix, it is not a regression test |

## 4. What "done" means for a SUB issue

A closing comment must contain **all four**:

1. The exact commands run (copy-pasteable).
2. Their **unedited** output, including the test count.
3. A before/after comparison if the change touches any metric or latency path.
4. Provenance tag for every new number: `deterministic`, `model-backed`, or `estimate`.

Example closing comment:

```markdown
## Evidence

Command: `python scripts/run_tests.py`
Output (unedited):
    ----------------------------------------------------------------------
    Ran 148 tests in 4.31s
    OK

Before/after (deterministic):
| metric        | before | after | delta |
|---------------|--------|-------|-------|
| Context Precision@5 | 0.61 | 0.78 | +27.9% |

Closes #12.
```

## 5. Repository hygiene

* No third-party runtime dependency may enter the critical path without an EPIC that
  justifies it against INV-1.
* Scratch scripts created while debugging are removed before the commit. If a script has
  lasting value, it belongs in `scripts/` with a test.
* Generated files under `artifacts/` are never hand-edited and never committed as documents
  of record; the report lives in `docs/`, the machine output in `artifacts/`.
* **Nothing here may contain employer-specific or role-specific information.** The content
  is written to be publishable. If you are about to paste real internal text, stop.
