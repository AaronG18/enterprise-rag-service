---
name: SUB issue
about: One reviewable unit of work under an EPIC. Needs evidence to close.
title: "<type>: <short title>"
labels: ["sub"]
assignees: []
---

## Parent

Closes nothing. Refines part of EPIC #__.

## Context

What exists today, with a pointer to the exact file and why it is insufficient. Do not
re-explain the EPIC.

## Definition of done

Written **before** implementation starts, ideally with the reviewer in mind. "Done" must be
decidable by running something, not by reading the diff and feeling good about it.

- [ ]

## Test plan

Which tests will be added, and - importantly - why each one would **fail before** the fix.
A test that passes with and without the change is decorative and will be rejected.

| Test | Fails before fix because | Provenance tag |
|---|---|---|
| | | deterministic |

## Evidence to paste before closing

Required, verbatim, in the closing comment:

1. Exact commands run.
2. Unedited output, including test counts.
3. Before/after table if any latency or quality metric is touched.
4. Provenance tag for every new number.

## Rollback notes

How this change is reverted if it turns out wrong.
