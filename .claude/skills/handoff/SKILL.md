---
name: handoff
description: Write a short status note for the human and the other sessions, send it to a1, and commit current work.
disable-model-invocation: true
---

Produce, in under 120 words: what landed since the last handoff (file paths), what is in progress, what is blocked and on whom, the next 30 minutes, and whether `main` is safe to rebase on. Commit current work with `[<session>] handoff: <one line>`. Send the note as one message to `@a1`. Do not edit `PLAN.md` (a1 owns it).
