# RULES.md - hard rules for this repository

Applies to humans and AI agents equally. These are not preferences. A change that violates
any rule below is invalid even if the code works, because this repository's product is
**justified confidence**, not just code.

Read order for a new session: this file -> `ROLES.md` -> the relevant skill. The skills are
`harness/skills/evidence-and-testing/SKILL.md` (before you claim anything),
`harness/skills/github-issue-workflow/SKILL.md` (before you start or finish a change),
`harness/skills/rag-eval/SKILL.md` (before you produce or quote a number) and
`harness/skills/harness-maintenance/SKILL.md` (before you change the harness itself).

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
clone + `python scripts/run.py --test` must work with **no API key and no network**.

The delivered service is **keyless by default**. `configs/retrieval.json` ships the real
semantic model as the default - `embedding_provider: "openai-compatible"` pointing at a locally
served BGE-M3, and `reranker_provider: "cross-encoder"` pointing at a locally served
bge-reranker-v2-m3 - with an **empty `embedding_api_key_env`**, so no credential and no
third-party Python package are ever needed. A reviewer runs `scripts/run.py` once and
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

**The same applies to this file.** The enforcement map below used to be prose a human was trusted
to keep true, and nothing checked it. It is now machine-verified by
`tests/test_harness_selfcheck.py`: a rule with no map row fails, a map row pointing at a file
that no longer exists fails, a rule that nothing enforces fails unless its row says `manual`, and
a reference to a rule id that does not exist fails. Adding a rule without adding its
enforcement is therefore a red build, not a silent promise.

**And the CI has to follow.** A rule enforced only by a test that no workflow runs is still a
promise. The same self-check therefore requires every rule not marked `manual` to be **named in a
workflow**, and requires the workflows to actually **run the gate commands**
(`run_tests.py`, `verify_requirements.py`). Adding a rule without touching CI is a red build too.
(Observed: R18 and R19 were added with map rows and tests while no workflow mentioned them, and
nothing would have failed if a job stopped running the suite.)

## R17 - No front end

This repository ships a **service**, not an application. There is no UI, no client-side build and
no npm dependency in the tree. The brief asks for a RAG service and its evidence; a front end is
scope that adds surfaces to maintain, artefacts to commit (a built bundle in the repository is
~1 MB of generated code) and claims a reviewer then has to verify.

The one exception is deliberate and minimal: `GET /` answers with a self-contained HTML string
held in `src/ragserve/api.py`, whose only job is to tell a reviewer which endpoints to call. It
is not an application, it is a signpost.

Enforced by `tests/test_harness_selfcheck.py`: no shipped file may reference a front-end
directory, the README and deployment guide must not advertise a UI, and a stray `web/` directory
must stay gitignored so a leftover `npm install` cannot re-enter the history.

## R18 - A capability is proven by its hardest input, not its easiest

Claiming support for a format, a language or a failure mode requires a hermetic fixture that
**actually exhibits it**, and a test asserting the **content** that comes out - not merely that the
code path executed. "It runs" is not "it works", and a green suite is not a working feature.

**Observed, and the reason this rule exists.** This repository passed 24/24 requirement rows, 253
tests and a 39/39 gate while a headline requirement was silently broken: handed real bilingual PDFs,
every Chinese PDF that subsets its font was destroyed, and the index received the string `Adobe UCS`
instead of Chinese. Nothing in the harness could catch it, because:

* the corpus fixtures were `.txt`, `.md` and one fake `.png.bin` - no fixture was a real PDF and none
  was a CJK PDF, so the hard code path had never executed;
* the `--corpus` requirement row verified that files are indexed and unreadable ones listed, never
  **what was extracted**;
* the tests that existed failed before the *mechanism* existed, not before the *content* was right.

So "every gate green" was true and the feature was broken. Name the hard case for each supported
input class: a CJK PDF means a **subset font with a ToUnicode CMap**, not a UTF-8 file containing
Chinese; "handles scanned PDFs" means a **pure image PDF and a text page mixed with image pages**;
"bilingual" means both languages in one document. A smoke test passes on garbage - assert the
characters.

## R19 - Evidence must be reproducible from the repository

A measured claim is evidence only if a **committed command** reproduces it from committed fixtures
or generators. Output produced by scratch scripts into `%TEMP%` - or any path outside the
repository - is an anecdote, not evidence, no matter how real the run was.

**Observed, and the reason this rule exists.** "28 mixed CN/EN PDFs were ingested end to end" was
true of one run and unreproducible by anyone else: the corpus lived in `%TEMP%`, built by scripts
that were never committed, while the repository itself carried six PDF fixtures of 1-3 KB. A
reviewer asking "where are the dozens? and why is each only a few KB?" was right on both counts -
the claimed scale existed nowhere in the repo, and nothing could re-run it. R19's first version
still allowed the corpus to be generated at run time into a temp directory; the reviewer's
requirement is stronger, and correct: **the data must be in the tree.**

Therefore:

* **test data lives in the repository**, under `tests/data/`, like every other fixture. A corpus
  that exists only while a test runs, generated into a temp directory, is invisible to a reviewer
  and deleted on cleanup - that is not test data, it is a side effect.
* a committed corpus must be **verified byte-for-byte against its generator** (on decompressed
  content - compressed bytes legitimately differ between zlib builds, which the first CI run of the
  identity test caught): re-running the generator and comparing every file proves the generator is
  deterministic and that the data cannot silently drift from it. A generator change without
  regenerating the data is a red build.
* a **scale claim** ("dozens of PDFs", "N documents") requires the committed corpus plus a test that
  asserts that scale and that the corpus is not a folder of stubs;
* numbers quoted in the README, the docs and PR bodies must **name the command that reproduces
  them**;
* if a scratch measurement earned its keep, the generator earns a commit (R10) - a measurement is
  not "done" until it is re-runnable by someone who has never spoken to its author.

## R20 - The deliverable is exactly what the brief asks for

The brief lists four deliverables, and one of them is "**One-click evaluation script**" - singular. A
`scripts/` folder holding twelve entry points has not delivered that, however good the twelve are:
the reviewer has to work out which to run, in what order, and which one the brief actually meant.

**Observed**: the repository shipped twelve scripts and a Quickstart that ran several of them in
sequence; the real models needed a separate `setup_models.py` before anything semantic worked; and
the performance target ("90% of QA requests within 10 s, >= 5 concurrent") was measured only against
85 cases the repository wrote for itself, never against a question the reviewer typed. A reviewer
reading the brief saw none of those three things.

Therefore:

* **one entry point** (`scripts/run.py`); everything else is a module it dispatches to, and the README
  offers the reviewer nothing else;
* **the first run prepares the environment** the deliverable needs - models installed, servers
  started, health-checked - and the second run reuses it. A reviewer must not have to assemble the
  system the document describes;
* when the brief states a target about **user requests**, the evidence comes from the reviewer's own
  input through that entry point, not only from cases written by the author.

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
| R1 | `.github/workflows/harness.yml` (pr-hygiene) + `CONTRIBUTING.md` | a PR with no `Fixes #`, or a branch/commit that does not name an issue |
| R2 | manual closing-comment review | "LGTM" without pasted output |
| R3 | `harness/skills/evidence-and-testing/SKILL.md` + manual report review | an untagged metric in a report |
| R4 | manual: the reviewer requires red output | a green-only test added together with the fix |
| R5 | `harness/ROLES.md` + manual review | the same session wrote and approved |
| R6 | `.github/workflows/ci.yml` (no-secret-scan) | CI red |
| R7 | `.github/workflows/ci.yml` + `scripts/run.py` + `tests/test_harness_selfcheck.py` | an install step in CI, or a workflow that runs the service without the offline pins |
| R8 | manual issue-tree review | an orphan diff with no parent EPIC |
| R9 | manual diff review | a mixed-purpose commit |
| R10 | `.github/workflows/ci.yml` (contract-gate) | a scratch file in the tree |
| R11 | manual EPIC retro | a repeated incident with no rule change |
| R12 | `docs/metrics/` + manual metric review | a target that is unreachable by construction |
| R13 | `scripts/run.py` + manual review | an improvement claimed with no reproducing command |
| R14 | `.github/workflows/harness.yml` (pr-hygiene) | a commit landing on `main` without a branch |
| R15 | `.github/workflows/harness.yml` | a merged PR whose harness checks were red or absent |
| R16 | `tests/test_requirements_gate.py` + `tests/test_harness_selfcheck.py` | a manifest row added with no failing state first, or a rule with no enforcement |
| R17 | `tests/test_harness_selfcheck.py` | shipped code referencing a front end, or documentation advertising a UI |
| R18 | `tests/test_harness_selfcheck.py` (`TestCapabilityProvenByHardestInput`) + `tests/data/cjk-pdf/` | a supported input class whose hard case has no fixture, or a test that never asserts the extracted content |
| R19 | `tests/test_review_corpus_scale.py` + `scripts/run.py` + `tests/data/review-corpus/` | a scale claim with no committed corpus behind it, a corpus that exists only at run time, committed data drifted from its generator, or a corpus that has quietly shrunk back to stubs |
| R20 | `tests/test_harness_selfcheck.py` (`test_scripts_holds_exactly_one_entry_point`) | a second script in `scripts/`, or README instructions that send a reviewer to anything but `run.py` |
