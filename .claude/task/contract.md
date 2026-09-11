# Task contract

objective: Untrack `.claude/hooks/__pycache__/*.pyc` from git. These compiled
  bytecode files were committed before `.gitignore` existed (`__pycache__/` and
  `*.pyc` are both already ignored) and have already caused one real
  rebase-blocking incident. Long-deferred, flagged in `.claude/active_work.md`'s
  "Minor cleanup still NOT done" section. Pure index removal — `git rm -r
  --cached .claude/hooks/__pycache__` — the files stay on disk locally and
  regenerate automatically on next `python -m ...` import; no source/logic
  content changes anywhere.

scope_paths:
  - .claude/hooks/__pycache__/*
  - .claude/active_work.md
  - .claude/task/contract.md
  - .claude/task/review.md

decisions_reserved:
  - (none) — this is a pure git-index cleanup of already-gitignored generated
    files, not a design or product decision.

done_when:
  - `git diff --cached --stat` shows only deletions under
    `.claude/hooks/__pycache__/`, zero insertions, zero other paths touched.
  - `.gitignore` already covers both `__pycache__/` and `*.pyc` (confirmed,
    unmodified — no change needed here).
  - `.claude/active_work.md`'s "Minor cleanup" section updated to reflect this
    is done, in the same commit, so a future session doesn't re-discover and
    re-do it.
  - scope-auditor + cto-reviewer (opus — `.claude/hooks/*` is a guard path per
    `.claude/rules/guard-paths.md`, and `*hooks/*` in `review_routing.json`
    matches this path even though the content is binary/generated) PASS.

amendments:
  - 2026-09-11 — contract created. Prior attempt to dispatch review skipped this
    file (stale from the just-merged, unrelated `completion_gate.py` task) and
    `.claude/task/review_input.patch` (never generated) — both reviewers
    correctly refused to rubber-stamp a diff they couldn't actually see.
    Fixed: fresh contract for this specific task, patch regenerated before
    re-dispatch.
