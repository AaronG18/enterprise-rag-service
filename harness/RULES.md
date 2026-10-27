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

Nothing on the critical path may require a network call, a credential, or a third-party
package. `python scripts/run_tests.py` must work on a cold clone. Real providers live
behind adapters that are off by default, so the default path is always reproducible.

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

## R11 - Fold learning back

When something breaks in a way that a rule or skill did not anticipate, update the rule or
the skill in the same change or in its own follow-up issue. A harness that is not revised
by its own failures decays into decoration.

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
