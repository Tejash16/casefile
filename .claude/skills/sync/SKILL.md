---
name: sync
description: Rebase this worktree on origin/main, run this module's tests, and merge to main if green and only owned directories changed.
disable-model-invocation: true
---

Run these steps and report each result in one line:

1. `git add -A && git commit -m "[<session>] wip: $ARGUMENTS"` if there are uncommitted changes (use the session name from `CLAUDE.md` ownership for the directories you touched).
2. `git fetch origin && git rebase origin/main`. If the rebase conflicts, stop, list the conflicting files, and tell the human to involve a1. Do not resolve conflicts in files you do not own.
3. `uv sync` if `pyproject.toml` changed.
4. `uv run pytest -q tests/<your module>`. If red, stop and show the failures.
5. `git diff --name-only origin/main...HEAD` and confirm every path is inside your owned directories. If not, stop and explain.
6. `git push -u origin HEAD`, then `git checkout main && git pull --ff-only && git merge --ff-only <branch> || git merge --no-edit <branch>`, `uv run pytest -q`, `git push origin main`, `git checkout <branch>`.
7. Message the sessions that depend on what landed (see the interfaces in `docs/contract.md`) with one line: what is now on main and whether they should rebase.
