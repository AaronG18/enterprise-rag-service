# RULES.md - hard rules for this repository

Applies to humans and AI agents equally. These are not preferences. A change that violates
any rule below is invalid even if the code works, because this repository's product is
**justified confidence**, not just code.

Read order for a new session: this file -> `ROLES.md` -> the relevant skill.

---

## R1 - No issue, no code

Every commit traces to an open GitHub issue. Branch name follows
`<type>/<issue-number>-<slug>`; commit messages start with `#<n> `.
Refactors that "touch nothing functionally" still need an issue, because "nothing
functionally" needs proving.

## R2 - No evidence, no close

An issue closes only when its comments contain:

1. the exact commands run (copy-pasteable),
2. their **unedited** output including test counts,
3. a before/after table when any latency, quality or cost path was touched,
4. a provenance tag for every new number.

"Tests pass" written by hand is not evidence. Output is evidence.

## R3 - Every number has a provenance tag

| Tag | Means |
|---|---|
| `deterministic` | reproducible offline run, seeded, no network |
| `model-backed` | produced with a real provider; must name the model version |
| `estimate` | arithmetic from a stated price list, **not** measured |

Mixing them silently is fabrication. If a target is only reachable in one mode, say so in
the same sentence as the number. **Never emit a plausible-looking figure for something that
was not measured** - an absent number is recoverable, a fake one destroys the repository.

## R4 - Test first, and it must fail first

Write the failing test, run it, keep the red output, then implement. If the test passes
without the fix, it is decorative: delete it and write the real one.
Rationale: in this repo the unit of value is "this test would have caught that bug", and
only red-then-green proves it.

## R5 - The doer does not grade the doing

The role that wrote a change may not be the sole judge that it satisfies its acceptance
criteria. See `ROLES.md`. Self-generated confidence is the failure mode this whole harness
exists to prevent: an agent asked to review its own work reliably praises it.

## R6 - Keep it publishable

No employer names, no internal document text, no classification markers, no role-specific
content, no real credentials, no customer data. The corpus is synthetic by design
(PROJECT.md INV-5). When copying real-world data would be convenient, that is exactly when
this rule applies.

## R7 - Hermetic by default

Shipped code must use only the Python standard library plus the `ragserve` package - no
third-party imports on the critical path, and CI must run with no `pip install` step. A cold
clone + `python scripts/run_tests.py` must work with **no API key and no network**.

The delivered service is **keyless by default**. `configs/retrieval.json` ships the real
semantic model as the default - `embedding_provider: "openai-compatible"` pointing at a locally
served BGE-M3, and `reranker_provider: "cross-encoder"` pointing at a locally served
bge-reranker-v2-m3 - with an **empty `embedding_api_key_env`**, so no credential and no
third-party Python package are ever needed. A reviewer runs `scripts/setup_models.py` once and
starts the two servers (both plain executables in `vendor/`, gitignored) to get real semantics;
with no server running the run falls back to the deterministic backend **loudly** (a `WARNING` to
stderr, and the config is flagged `degraded_*`) rather than silently, so a report can never claim
model-backed numbers a model did not produce.

Real providers live behind adapters selectable by config, and are **pinned to the offline
deterministic backend inside CI** via `RAGSERVE_EMBEDDING_PROVIDER=deterministic` and
`RAGSERVE_RERANKER_PROVIDER=deterministic` (set in both workflow files and in
`run_tests.py`). `run_tests.py` also sets the embedding override via `os.environ.setdefault`, so
the test gate needs no model server and no network. Swapping models stays a configuration change,
never a code change, which is what FR1 asks for.

## R8 - Large changes hang off an EPIC

If a change touches more than one module, spans more than one review sitting, or cannot be
described in a single sentence, it gets an EPIC with child issues. An EPIC closes only when
all children close **and** its acceptance criteria are verified by command. Tree first,
code second.

## R9 - Small diffs, one purpose

A commit does one thing. Unrelated changes found in a diff must be split or reverted before
merge. Reviews that have to ask "is this intentional?" are reviews that failed.

## R10 - Clean up after yourself

Scratch scripts, temp dumps, one-off probes: deleted before the commit. If a script earned
its keep, it goes in `scripts/` with a test and a line in `PROJECT.md`.

## R14 - Branch and PR, never direct to main

Every change lands through a branch named `<type>/<issue>-<slug>` (e.g. `feature/57-cache-eviction`)
and a pull request. Direct commits to `main` are not part of the workflow: `main` is protected and
requires the harness checks. A branch that cannot be merged yet is the expected state while work
is in progress - fix on the branch, push, re-run.

## R15 - The harness gate is the definition of done

`harness/requirements.toml` lists every requirement with its verification. A change is not done
because the author says so; it is done when `.github/workflows/harness.yml` is green:

* `requirements-gate` - every row verified, failing rows reported by ID
* `contract-gate` - tests, tree hygiene (no scratch files, no credential shapes), publishable
  content, standard-library-only shipped code
* `pr-hygiene` - branch name shape, every commit references an issue, PR body carries the
  evidence block

What the gate **cannot** prove, and therefore what still requires a human or a separate agent:
that the test failed before the fix (R4), and that the doer did not grade the doing (R5). Those
are quoted in the PR body, not inferred by CI.

## R16 - The gate itself is code, and code needs tests

Changes to `harness/requirements.toml`, the verifier or the workflow require their own issue and
tests, like any other change. A gate that cannot fail is decoration; a gate that fails for the
wrong reason is worse than none. A new row must be red before it is green - the demo in SUB 58
exists to prove exactly that.

A pattern in a gate must not match a legitimate file, and the rule must bind the person who
normally bypasses it: `enforce_admins` is on, so the owner cannot merge a red change. Both
were found by running the gate for real - see `docs/qa/harness-gate.md`.

**A check that cannot fail is not a check.** Seven requirement rows were passing while
asserting nothing, because `unittest -k` exits 0 when the filter matches no test. A gate row
must fail when it cannot find its evidence, and it must report how much evidence it actually
ran. Speed work found this: counting the tests each row really executed made the empty rows
visible.

## R11 - Fold learning back

When something breaks in a way that a rule or skill did not anticipate, update the rule or
the skill in the same change or in its own follow-up issue. A harness that is not revised
by its own failures decays into decoration.

## R12 - Metric definitions are part of the change surface

If a metric cannot reach its target **by construction** - a cap imposed by corpus shape, `top_k`
or the denominator - the definition is the defect, not the system. Replace it, document both
forms and why the first one was structurally capped, and pin the new one with a test.
(Observed: "fraction of retrieved chunks that are relevant" could not exceed ~0.4 with ~2 chunks
per document at top_k=5, so the 0.70 target was unreachable no matter how good retrieval was.)

## R13 - Attribution must survive reproduction

A commit message may claim an improvement only if a command reproduces it. When a reconstruction
of the "before" state shows **no** difference, the attribution is withdrawn **in writing** - in
the relevant doc, not silently dropped from the message.
(Observed: rank damping was credited with fixing wrong-document answers; replaying the pre-fix
provider gave identical results, so the claim was withdrawn in `docs/diagnosis/INC-002-...`.)

---

## Enforcement map

| Rule | Where it is checked | Failure signal |
|---|---|---|
| R1 | PR template, `CONTRIBUTING.md` | PR with no `Fixes #` |
| R2 | closing comment review | "LGTM" without pasted output |
| R3 | `harness/skills/evidence-and-testing/`, eval report format | untagged metric in a report |
| R4 | reviewer requires red output | green-only test added with the fix |
| R5 | `ROLES.md`, verification step | same session wrote and approved |
| R6 | CI `no-secret-scan` job | CI red |
| R7 | CI runs with no install step | any `pip install` in CI |
| R8 | issue tree review | orphan diff with no parent EPIC |
| R9 | review | mixed-purpose commit |
| R10 | diff review | `_tmp.py` in the tree |
| R11 | EPIC #10 retro | repeated incident with no rule change |
| R14 | branch protection + `pr-hygiene` job | a commit landing on `main` without a branch |
| R15 | `.github/workflows/harness.yml` | a merged PR whose harness checks were red or absent |
| R16 | `tests/test_requirements_gate.py` | a manifest row added with no failing state first |
| R12 | metric review + `docs/metrics/` | a target that is unreachable by construction |
| R13 | replay harness (`scripts/diagnose.py`) | improvement claimed with no reproducing command |
