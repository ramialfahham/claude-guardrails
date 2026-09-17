# Active work

This file is a **current-state snapshot**, overwritten each time it's updated — not a log.
Merged work, review rounds, and lessons-learned live in MR descriptions and each merged
branch's `.claude/task/contract.md` amendments; don't re-narrate them here. If it isn't
still true or still open, it doesn't belong in this file.

## Where things stand

All planned work is merged to `main`. Nothing is in flight.

This repo was renamed `claude-guardrails` → `claude-project-kit`
(`rami.al-fahham/claude-project-kit` on GitLab; local `gitlab` remote repointed), and this
kit's own self-governance reviewer, `.claude/agents/cto-reviewer.md`, was retired in favor of
using `templates/reviewers/platform-reviewer.md` directly (a straight rename would have
collided by filename with that already-existing module) —
[MR !26](https://gitlab.com/rami.al-fahham/claude-project-kit/-/merge_requests/26), merged.
`dbt-agent-kit`'s `scripts/sync-base.sh` still hardcodes the old URL — flagged as a separate
follow-up task in that repo (`task_5ad700d5`), deliberately not fixed here (cross-repo).

The `origin` GitHub remote (`ramialfahham/claude-guardrails`) is permanently out of scope —
account suspended (403), treat `gitlab` as the only remote, don't re-flag this.

- The 7-phase `claude-project-kit` build (bootstrap + tailored `/setup-project` generation,
  reviewer module library, CI-provider audit) — complete. See `docs/project-kit-design.md`
  for the architecture and `docs/decisions/*.md` for the individual design calls.
- Post-plan hardening Phase 1 (completion-time advisory hook, auto-mode compatibility
  check, custom-review-gate-vs-`/code-review` rationale, sandboxing recommendation) —
  complete. See the same `docs/decisions/*.md`.

## Open owner decisions (none blocking, none scheduled)

- Whether/how to wire `templates/ci-audit/ci_automation_audit.py` as an actual
  `SessionStart` hook anywhere (currently inert everywhere, by design).
- Whether `templates/*` should be its own guard path in `review_routing.json`/
  `.claude/rules/guard-paths.md` (flagged end of Phase 5, still undecided).
- Drift between this kit's own hand-maintained `.claude/rules/guard-paths.md` and
  `templates/reviewers/routing/platform-reviewer.routing.json` — Phase 6b's generation
  logic avoids introducing this drift into *new* projects, but doesn't fix this kit's own
  existing copy.

## Next candidate work

- **Parallel-session/worktree safety audit** — research done, ADR not yet written.
  Branch `research/parallel-session-worktree-audit` exists with no commits; nothing is on
  disk yet. Verified live (real tempdir repos + a real `git worktree`), not theorized:
  - Worktrees are genuinely safe for parallel Claude Code sessions — separate index per
    worktree, `commit_review_gate.py`'s diff-hash isolation holds, git itself refuses to
    check out the same branch in two worktrees. **Recommendation the ADR should lead
    with**: use worktrees for parallel sessions.
  - Same directory, no worktree, is *mostly* safe: `commit_review_gate.py` recomputes the
    diff hash fresh at commit time so nothing unreviewed slips through, but two sessions
    can overwrite each other's `review.md` (forces a confusing but safe re-review), and
    there's a narrow, real TOCTOU gap between hook approval and commit execution that a
    `PreToolUse` hook can't close without OS-level locking (out of scope).
  - Next step: write a short ADR matching the sandboxing ADR's shape, not yet confirmed
    with the owner.
- **Headless-mode (`claude -p`) compatibility audit** — not started. Last of the originally
  deferred hardening phases; gets its own task contract when picked up, or a "considered,
  not building" ADR if it turns out not worth it.
