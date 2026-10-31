---
name: review
description: Fresh-context review of this worktree's diff against origin/main for correctness and contract compliance only.
disable-model-invocation: true
---

Spawn a subagent with a fresh context that reads only `docs/contract.md`, `CLAUDE.md`, the rule file for this directory, and `git diff origin/main...HEAD`. It must report at most five findings, each a concrete defect (wrong field name, missing audit record, hard-coded threshold, uncited evidence, network call outside the allowed modules, model call outside `agents/`) with file and line. Style comments are not wanted. Fix what it finds, re-run the module's tests, and summarise in three lines.
