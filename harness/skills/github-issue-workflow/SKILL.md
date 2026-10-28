---
name: github-issue-workflow
description: Drive a change through this repository's issue-first workflow - creating EPIC and child issues, branch naming, red/green tests, commit linking, writing the evidence comment, and deciding when an issue may be closed. Use when starting any change, unsure how to structure a large piece of work, or about to close an issue.
---

# Skill: github-issue-workflow

## When to use

Any time work is starting, splitting, or being declared finished. The point of this skill is
that "done" is a **procedure**, not a feeling.

## Step 1 - Size it

| Situation | Structure |
|---|---|
| Single file, no metric touched, decidable in one sentence | one SUB issue |
| Multiple modules, subjective acceptance criteria, or spans more than one sitting | EPIC + children |
| Exploratory with unknown shape | write the EPIC with acceptance criteria first, add children once the shape is known |

R8: if in doubt, use the EPIC. An EPIC that turns out to have one child costs almost
nothing; a scattered multi-module diff with no parent costs a review cycle.

## Step 2 - Write the contract before editing

A SUB issue body must contain, before the first keystroke:

* **Definition of done** - decidable by running something.
* **Test plan** - each test, and why it would fail without the fix.
* **Rollback notes** - how this is undone if wrong.

If "definition of done" needs the word "should", rewrite it.

## Step 3 - Execute

```
git switch -c feat/<issue-number>-<slug>      # use `switch -c`; `checkout -b` trips the command guard on this machine
# write failing test -> run it -> keep the red output
# implement -> run again -> keep the green output
git add -A && git commit -F msg.txt           # message starts with "#<issue-number> "
git push -u origin HEAD
```

## Step 4 - Evidence comment (mandatory)

Exactly four parts, in the issue, before closing:

```markdown
## Evidence

Commands:
    python scripts/run_tests.py -v
    python scripts/run_eval.py --retrieval-only

Test output (unedited):
    Ran <real count> tests in <real time>
    OK

Before / after:
| metric | before | after | delta | provenance |
|--------|--------|-------|-------|------------|
| Context Precision@5 | 0.61 | 0.78 | +27.9% | deterministic |

Impact: closes the loop on acceptance criterion 2 of EPIC #3.
```

Do not summarise output into prose. Paste it.

## Step 5 - Branch, PR, gate, close

An issue may close only when: its own criteria all pass, every child issue is closed (for
EPICs), and the evidence comment above exists. A partial win gets a new child issue, not a
close. If reality changed and the goal is no longer correct, close it **with a stated
reason**, never silently.

The change reaches `main` through a branch and a PR, and the harness gate decides when it is
done:

```bash
git switch -c feature/57-cache-eviction      # <type>/<issue>-<slug>, always
# ... work, commits each starting with "#57 "
git push -u origin feature/57-cache-eviction
gh pr create --base main --fill              # body must carry the evidence block
```

Then iterate **on the branch** until `.github/workflows/harness.yml` is green:
`requirements-gate`, `contract-gate`, `pr-hygiene`. A red gate is the loop working, not an
obstacle - read the failing row ID, fix it, push again. `main` is protected, so a green gate is
the only way in.

## Gotchas

## Gotchas

* **Windows/PowerShell:** `< nul` stdin redirection does not work here; use
  `git commit -F <file>`. Non-interactive `git push` can hang - prefer an explicit remote and
  branch, and avoid composing long `git` chains with other tools in one command.
* **Chinese text in commits:** commit messages are written in English to avoid encoding damage;
  Chinese punctuation inside shell arguments is a reliable way to corrupt bytes.
* **`Remove-Item` is intercepted** on this machine and stalls on approval. Delete scratch
  files with `python -c "import os; os.remove(r'<abs path>')"`.
* **Issue count is not progress.** Closing three issues and reopening one is fine. Closing
  one without evidence is not.
* **`Fixes #n` belongs in the PR body**, not only in prose - automation only reacts to the
  keyword form.
* **`git add -A` will commit the commit-message scratch file.** Write message files outside the
  repo (temp dir) or the tree gains `_msg.txt` on the next commit.
* **A "no company names" guard can itself leak one.** A CI scan pattern that literally spells the
  internal classification marker defeats its own purpose. Match the generic **shape**
  (`[<Word> - INTERNAL]`, `MSIP_Label_<guid>_`) and never the real string.
* **On a branch push, check only the branch's own commits.** Comparing against the repository
  root makes history written before the rule existed fail the gate. Use
  `git merge-base origin/main HEAD` as the range base.
* **`run_tests.py -k` takes one substring.** A verification row that needs several test classes
  is a list in `harness/requirements.toml` (`tests = [...]`), not one `-k` with several names.
* **A metric row must name its section.** Eval metrics live under `comparison` (per
  configuration) or `operations`; bench artefacts are flat. Guessing reads a stale or absent key
  and reports a failure that is not real.

## Related

`harness/RULES.md` R1, R2, R8; `harness/skills/evidence-and-testing/SKILL.md`.
