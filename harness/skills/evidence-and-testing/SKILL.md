---
name: evidence-and-testing
description: Produce test evidence that survives review - hermetic tests that fail before the fix, provenance tags for every metric, correct before/after comparisons, and detection of numbers nobody actually measured. Use when writing tests, preparing a closing comment, reviewing someone's evidence, or when a result looks suspiciously good.
---

# Skill: evidence-and-testing

## When to use

Any time a claim is about to be made. If you are tempted to write "this improves quality",
this skill applies.

## The three failure modes this skill exists to catch

1. **Decorative tests** - added alongside the fix, pass with and without it. Detect by
   temporarily reverting the fix and re-running; the test must go red. If it stays green, it
   never tested anything.
2. **Untagged numbers** - a metric presented without saying how it was produced.
   `deterministic` / `model-backed` / `estimate`, no exceptions.
3. **Gaming by omission** - reporting only the headline metric. Ask what got worse:
   compliance up with refusal rate up is not an improvement, it is a retreat.

## Test layers in this repository

| Layer | Purpose | Rules |
|---|---|---|
| Unit | pure logic: scoring, chunking, config resolution, redaction | no network, no fs writes outside tmp, deterministic |
| Golden | metric values frozen per corpus version | changes to a golden value require explaining the corpus or intentional behaviour change |
| Integration | whole request through the service with stub providers | must still be hermetic |
| Eval / bench | quality and latency numbers | reported with provenance; never used as the *only* correctness gate |

## Rules for a credible before/after comparison

Change exactly one variable. Held constant:

* corpus version **and** seed,
* provider mode and model version string,
* candidate depth (top-k) and rerank window,
* cache state (warm caches fake latency improvements),
* concurrency level.

If any of those moved, the delta is not attributable and must be re-measured.

## Device-specific gotchas (this machine)

* Metric numbers must not be copied from terminal scrollback by hand. Write the script's
  output to `artifacts/` and paste from the file.
* PowerShell displays UTF-8 Chinese wrongly (GBK console); **never** judge file encoding from
  terminal display. Verify bytes if it matters.
* Do not use `Remove-Item` for cleanup here - it stalls on approval. Use
  `python -c "import os; os.remove(r'<abs path>')"`.

## Reconstructing a "before" state

Incident replays need a failing state that can be re-run. Rules learned here:

* Prefer a **reconstructed** pre-fix component (a subclass in the diagnosis module) over
  reintroducing broken code into the shipped path.
* Assert that the reconstruction is **measurably worse**. If it is not, the incident attribution
  is unsupported and must be withdrawn (R13) - do not publish it anyway.
* Reconstructions that produce identical numbers are information: they mean the measured gain
  came from something else, and the other candidate changes must be measured separately.

## Reviewer checklist (use when judging someone else's evidence)

- [ ] Does each claimed test fail without the fix?
- [ ] Is every number tagged, and does the tag match how it was actually produced?
- [ ] Does the before/after hold every other variable constant?
- [ ] Did any metric move **down** that is not mentioned? Ask about it explicitly.
- [ ] Do the commands in the comment actually exist in the repo right now?
- [ ] Does the pasted output look like machine output (counts, timings), not prose?

## Related

`harness/RULES.md` R2, R3, R4; `harness/skills/rag-eval/SKILL.md`.
