## Issue link

Fixes #__  <!-- the issue that this PR satisfies. No issue, no merge. -->

## What changed

Short, factual description of behaviour change. Not a list of files.

## Commands

The exact commands a reviewer runs, copy-pasteable:

```
python scripts/run.py --test -v
```

## Evidence

Mandatory. Paste **unedited** output.

Output:

```
paste here
```

Before / after (if latency, quality or cost is touched):

| Metric | Before | After | Delta | Provenance |
|---|---|---|---|---|
| | | | | deterministic |

## Checklist

- [ ] The change does what its issue asked, and nothing else (no drive-by refactors).
- [ ] Every claimed number carries a provenance tag.
- [ ] New tests fail without this change.
- [ ] `python scripts/run.py --test` passes with the real counts pasted above.
- [ ] No third-party dependency entered the critical path (PROJECT.md INV-1).
- [ ] No employer-specific or role-specific content anywhere in the diff.
- [ ] Scratch scripts created while debugging are deleted.
- [ ] Docs updated in the same PR if behaviour or commands changed.
