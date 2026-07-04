# Task contract

objective: Add a `/sync-branch` slash command that rebases the current feature branch
  onto its base (default `main`) and auto-resolves ONLY `.claude/task/*` bookkeeping
  conflicts to the branch's versions — turning the recurring parallel-PR task-file
  conflict into a one-command non-event, without ever auto-resolving real code.

scope_paths:
  - .claude/commands/sync-branch.md
  - .claude/working-agreement.md
  - .claude/review_routing.json
  - .claude/task/contract.md
  - .claude/task/review.md

decisions_reserved:
  - Base branch defaults to `main`, overridable via an optional argument (owner
    approved this design on 2026-07-04).
  - The one-line discoverability wording added to working-agreement.md §3
    (user-visible doc text) — owner may adjust.

done_when:
  - `.claude/commands/sync-branch.md` exists with: guards (refuse when a rebase/merge is
    already in progress, on main/master or detached HEAD, or on a dirty tree), fetch +
    rebase onto the base, auto-resolve only when EVERY conflicted path is under
    `.claude/task/` (space-safe; abort + hand back on any other conflict), a before/after
    code-fingerprint check that STOPs before pushing if the rebase altered reviewed code
    (plus a `review.md` `diff_sha256` match when present), and `git push --force-with-lease`.
  - working-agreement.md §3 points at `/sync-branch` for falling-behind branches.
  - Existing `.claude/tests/test_*.py` still pass; JSON parses; hooks byte-compile.
  - scope-auditor + cto-reviewer PASS; CI green.

amendments:
  - 2026-07-04 — contract created for PR C (sync-branch command).
  - 2026-07-04 — reviewer-driven hardening (cto-reviewer + scope-auditor): added an
    in-progress-rebase guard, space-safe conflict-path handling, and a before/after code
    fingerprint so the integrity check no longer depends on `review.md` existing.
  - 2026-07-04 — second cto-reviewer round: added an explicit `MERGE_HEAD` check (not just
    `REBASE_HEAD`) and dropped the plain-`git status` reference; made step 5 use `grep` to
    read the recorded hash (removing the dead `grep` permission); and — scope widened with
    owner authority ("everything that reduces friction / makes the guardrails solid") —
    added `.claude/commands/*` to `review_routing.json` so command files durably require
    cto-reviewer, matching the existing `.claude/agents/*` and `*hooks/*` routing. This is
    a tightening (more review required), not a weakening.
  - 2026-07-04 — polish for full unattended run (owner: "ship it and polish"; resolves the
    third cto-reviewer ESCALATE): replaced the `GIT_EDITOR=` env prefix with
    `git -c core.editor=true rebase`, and the `| sha256sum` pipes with
    `git diff --output=<scratch>` + `sha256sum <file>`, so every step matches a single
    `allowed-tools` grant and cannot trigger a permission prompt. `allowed-tools` tightened
    to the exact command forms used.
