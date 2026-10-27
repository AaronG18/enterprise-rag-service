# ROLES.md - role separation

Why this file exists: when a single agent both produces and grades its own work, the grade
drifts upward and stabilises at "good". Splitting generation from evaluation reliably
produces lower but honest scores, and lower honest scores are actionable. That is the whole
reason this file has more than one role in it.

This mirrors what long-horizon agent work converges on: **decompose, hand off through
artifacts, and never let the builder be the inspector.**

---

## The roles

| Role | Owns | Must never |
|---|---|---|
| **Planner** | Expanding a one-line intent into scope, acceptance criteria, and a child-issue tree. Writes the EPIC. | specify implementation details that would cascade into wrong code |
| **Generator** | Making one SUB issue's change: tests first, then code, then evidence. | grade its own output or weaken a criterion it is failing |
| **Evaluator** | Judging the finished change against the criteria written *before* implementation. Writes the pass/fail verdict. | modify the change it is judging (file findings instead) |
| **Verifier** | Re-running commands independently and asserting the pasted output actually reproduces. Detects stale or hand-edited evidence. | assume evidence is real because it is plausible |

In human terms: Planner writes the ticket, Generator writes the patch, Evaluator reviews it,
Verifier re-runs the pipeline to confirm the pasted numbers are real.

## Required artifacts per role

Role boundaries are enforced by **files**, not by intention:

| Produced by | Artifact | Consumer |
|---|---|---|
| Planner | EPIC issue with acceptance criteria + child list | Generator |
| Planner + Generator | **contract**: "done means X, proven by command Y" written before the first edit | Evaluator |
| Generator | branch + commit + pasted command output | Evaluator |
| Evaluator | verdict comment: which criteria pass, which fail, with specific evidence lines | Generator (to fix) |
| Verifier | reproduction comment: same commands, same numbers, fresh process | everyone |

## Context discipline

Long sessions degrade in two recognizable ways, and both have the same fix:

* **context anxiety** - the agent starts wrapping up prematurely as the window fills.
  Fix: stop, write the handoff artifact below, start fresh.
* **context rot** - earlier decisions get silently reinterpreted.
  Fix: every decision that survives a session break lives in a file (ADR, issue, RULES).

**Handoff artifact** (write before any long break):

```markdown
## Handoff
- Branch / issue: #__
- What is implemented, with file paths:
- What is verified, with the command that verified it:
- What is NOT verified yet:
- Exact next step (single action):
```

## Calibration of the Evaluator

An uncalibrated evaluator either accepts everything (useless) or nitpicks everything
(expensive). Calibration loop, run deliberately:

1. Evaluator grades a change.
2. A human compares that verdict with their own read.
3. Where they diverge, the divergence is written into the skill as a **Gotchas** entry or
   into a scoring rubric example.

Rubric examples are worth more than adjectives. "Be strict" changes nothing;
"a citation that does not resolve to a retrieved chunk is a fail, even if the answer is
factually right" changes outcomes.

## When an agent may skip role separation

Only when all three hold: the change touches a single file, no metric or latency path is
affected, and no acceptance criterion is subjective. Even then the Generator writes the
verdict explicitly *as* a Generator-led self-check, labelled as such, so nobody later
mistakes it for an independent review.
