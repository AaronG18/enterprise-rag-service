# AGENTS.md

This repository is operated by AI agents under a written contract. If you are an AI
agent working here, read these three files **before** your first edit, in this order:

1. [`harness/RULES.md`](harness/RULES.md) - hard rules. Violating any rule invalidates the change.
2. [`harness/ROLES.md`](harness/ROLES.md) - the planner / generator / evaluator / verifier split. You must know which role you are currently playing.
3. [`harness/skills/`](harness/skills/) - executable know-how. Load the skill that matches the current task instead of improvising.

Then read, depending on intent:

* implementing a feature - [`PROGRESS.md`](PROGRESS.md), `docs/REQUIREMENTS.md`
* writing or re-running an evaluation - `harness/skills/rag-eval/SKILL.md`
* changing anything that affects the service - [`CONTRIBUTING.md`](CONTRIBUTING.md)

## Non-negotiable in one paragraph

No code change without an open issue that you reference from the commit message. Every
issue is closed only by pasting the exact command you ran and its unedited output. A
number in this repository without a provenance tag (`deterministic` / `model-backed` /
`estimate`) is treated as fabricated. Test first, then implement; never write a test that
passes without the fix you claim to have made. The agent that wrote the change is not
allowed to be the sole judge of that change.

## Repo facts at a glance

| Item | Value |
|---|---|
| Language | Python 3.11+ |
| Third-party dependencies | **none** for anything that must run in CI or from a clean clone |
| Test entrypoint | `python scripts/run.py --test` |
| Evaluation entrypoint | `python scripts/run.py --eval --all` |
| Default LLM/embedding provider | deterministic local stub (seeded, offline) |
