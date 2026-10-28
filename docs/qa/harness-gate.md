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

Fixed by setting `enforce_admins: true`. A gate whose owner can walk through it is not a gate, and
no amount of green checks proves otherwise.

The fix was verified immediately, with a probe pull request that carried a scratch file on
purpose:

```
GET  /pulls/64      -> mergeable: true, mergeable_state: "blocked"
PUT  /pulls/64/merge -> 405
      {"message": "Required status check \"contract-gate\" is failing.",
       "documentation_url": ".../about-protected-branches"}
```

and, for contrast, a green pull request merged normally:

```
PUT  /pulls/63/merge -> 200 {"merged": true, "sha": "b6597a8"}
```

So the enforced rule now reads exactly as intended: **red blocks the merge, green allows it**.

## How fast the gate is, and why it is fast enough

The gate is the thing every pull request waits for, so its runtime is part of its design.

| Stage | Before | After | How |
|---|---|---|---|
| hermetic suite (160 tests) | 24.4 s | **7.8 s** | the test classes run in parallel worker processes with work stealing |
| the three generators (eval, bench, diagnosis) | 3.4 s | **1.5 s** | they are independent, so they run concurrently |
| the requirement rows | one process per test row | **one shared run** | all test rows read one machine-readable report |

Two design decisions matter:

* **Work stealing, not static partitioning.** The suite's cost is concentrated in four classes
  (each starts a server or runs the whole evaluation). A fixed split puts the slow classes in
  one worker while the others idle; pulling classes off a shared list makes the wall-clock time
  approach the slowest single class. The claim is atomic (exclusive file creation), so no class
  is run twice or left unrun.
* **One test run, many rows.** Ten requirement rows used to start ten interpreters, each paying
  for test discovery. They now share a single `--json` run and ask it per-class verdicts.

Measured on this machine (8 cores): 1 worker 24.4 s, 4 workers 9.0 s, 6 workers 6.5 s, 8 workers
6.5 s. The default is `min(6, cpu_count)`; beyond six the discovery overhead cancels the gain.

Two properties are preserved on purpose: the report is in manifest order regardless of which
row finished first, and concurrency never changes a verdict (a test asserts that the parallel
and serial runs report the same tests).

## A fourth defect the speed-up found: rows that passed without running anything

While measuring, seven of the seventeen test selections in the manifest were found to match
**zero** tests - `unittest` exits 0 when a filter matches nothing, so those requirement rows
were passing while asserting nothing. The names were also wrong (`TestGrounding` instead of
`TestGroundedAnswers`).

Fixed on both sides:

* the runner now reports per-class results (`--json --classes ...`) and **fails when a requested
  class does not exist**, instead of running an empty selection;
* the manifest names real classes, and each row now reports how many tests it actually ran
  (`R-08  PASS TestGroundedAnswers: 5 test(s) passed`).

A requirement row that cannot find its evidence is now a failure, which is the whole point of a
gate.

## What the parallel runner exposed: a flaky test

Making the suite parallel turned one test red that had been quietly racy: with six workers,
`TestPortFallback.test_busy_port_resolves_to_the_next_free_port_deterministically` failed with
`PermissionError: [WinError 10013]`.

The test took a port from the OS ephemeral range and then assumed the port *after* it was still
free. Another worker - or any process on the machine - can be handed that port in between, and
on Windows a second bind of a port someone else holds without `SO_REUSEADDR` is refused with
access-denied rather than "address in use".

The tests now reserve their ports explicitly, from a range the OS never hands out, and hold them
for the whole scenario. Three consecutive runs are green.

The general lesson: **a parallel runner turns latent races into visible ones**, which is a
reason to parallelise rather than a reason not to.

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
