# The harness gate, demonstrated

`harness/RULES.md` states the rules; `.github/workflows/harness.yml` enforces the enforceable
ones. This file records a real demonstration of that gate - red, blocked, fixed, green - with
the run identifiers, so the claim "the gate works" is backed by runs rather than by intention.

## What the gate checks

| Check | What it proves | Failure message |
|---|---|---|
| `requirements-gate` | every row of `harness/requirements.toml` verified in this run | names the row: `R-14  FAIL faithfulness >= 0.85 (actual 0.913, from eval)` |
| `contract-gate` | hermetic tests pass; no scratch files; no credential shapes; publishable content; shipped code imports only the standard library and `ragserve` | names the file or the import |
| `pr-hygiene` | branch name shape, every authored commit references an issue, PR body carries the evidence block | names the branch, the commit or the missing section |

`main` is protected: GitHub requires all three checks, so a red gate cannot be merged. The
protection was set through the API - the required contexts are `requirements-gate`,
`contract-gate`, `pr-hygiene`.

## The demonstration

| Stage | Commit | Harness run | pr-hygiene | contract-gate | requirements-gate |
|---|---|---|---|---|---|
| 1. three violations introduced | `398d4bd` | `40658409477` | red (branch name) | red (test suite) | red (row `R-99`) |
| 2. branch renamed, scratch file removed | `11dff69` | `40659130009` | **green** | red (test suite) | red (row `R-99`) |
| 3. impossible row removed | `df0f11d` | `40659725707` | **green** | **green** | **green** |

Stage 1 is PR #60 (closed - the branch was renamed to comply with the rule itself), stage 3 is
PR #61 (closed - its net diff against `main` is empty, so merging it would have added demo
commits to the history without changing a line).

## Two defects the demonstration found in the gate

Running the gate is the only way to find these; both were fixed on `main`:

1. **The scratch-file pattern matched `__init__.py`.** `(^|/)_[^/]*\.(py|txt|json)$` matches a
   leading `_` followed by `_init__.py`, so the check failed on a clean tree - a gate that cries
   wolf gets ignored, which is worse than no gate. Fixed to
   `(^|/)_[^_/][^/]*\.(py|txt|json)$` (commit `807065e`).
2. **Merge commits were required to reference an issue.** `git merge` writes its own message, so
   an ordinary merge turned the gate red. The rule now applies to authored commits only
   (`git rev-list --no-merges`, commit `7b63a29`).

A third change was ordering: the cheap checks run before the test suite, so a violation is
reported in seconds rather than after a 30-second suite (commit `f17c1dd`).

## A third defect the demonstration found: admins could walk through the gate

The first attempt to merge PR #62 **succeeded while the harness check was failing**:

```
GET /pulls/62      -> mergeable: true, mergeable_state: "blocked"
PUT /pulls/62/merge -> 200 {"merged": true, "message": "Pull Request successfully merged"}
```

GitHub knew the pull request was blocked and merged it anyway. The cause was in the protection
settings this repository had just applied: `enforce_admins: false`, which exempts administrators
from required checks. The token doing the merge belongs to the repository owner, so the gate was
bypassed by the one person it was meant to constrain. The proof that this was not a GitHub
fluke: the scratch file that the tree-hygiene check had rejected landed in `main` with the
merge.

Fixed by setting `enforce_admins: true` (commit `7b63a29` follows the same repository through
`main`; the protection update is in the same issue). A gate whose owner can walk through it is
not a gate, and no amount of green checks proves otherwise.

## What the gate cannot prove

* **That a test failed before the fix** (RULES R4). CI can only observe the final state. The
  red output is quoted in the PR body by the author, and reviewed by a human.
* **That the doer did not grade the doing** (RULES R5). A separate reviewer or agent reads the
  evidence; no automated check can stand in for that judgement.

## Reproducing it locally

```bash
python scripts/verify_requirements.py     # the requirements gate, ~17 s
python scripts/run_tests.py                # the contract gate's test suite
```

The workflow runs the same commands in the same order, on a clean checkout, with no
credentials and no network access.
