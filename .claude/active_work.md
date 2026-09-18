# Active work

This file is a **current-state snapshot**, overwritten each time it's updated — not a log.
Merged work, review rounds, and lessons-learned live in MR descriptions and each merged
branch's `.claude/task/contract.md` amendments; don't re-narrate them here. If it isn't
still true or still open, it doesn't belong in this file.

## Where things stand

Nothing is in flight. Owner confirmed 4 items to do before moving to the website-project test;
the first 2 are merged —
[MR !31](https://gitlab.com/rami.al-fahham/claude-project-kit/-/merge_requests/31): (1)
`templates/ci-audit/ci_automation_audit.py` is installed into a generated project's
`.claude/hooks/` and idempotently wired as a `SessionStart` hook in `settings.json` whenever
`/setup-project`'s interview is given a CI provider (`_prepare_ci_audit_hook_settings()` —
validate-then-return-text, so every `GenerationRefused` still precedes the first write; refuses
with a remedy on any unexpected `settings.json` shape); (2) `templates/*` is a guard path and the
`guard-paths.md`/`review_routing.json` drift against the shipped platform-reviewer routing
fragment is fixed. Review took 4 rounds (owner authorised one past the cap) — account in that
merge's `.claude/task/contract.md` amendments.

Remaining two, in order: (3) write the worktree-safety ADR (research done, see "Next candidate
work") — NOT STARTED; (4) scope the headless-mode audit — NOT STARTED. Then the website-project
test.

`/setup-project`'s interview now asks two more questions:
[MR !28](https://gitlab.com/rami.al-fahham/claude-project-kit/-/merge_requests/28) added a
tracker-based roadmap convention (roadmap is the tracker's issues/milestones, never a markdown
file — generalizes `football-data-pipeline`'s own real fix) and a Solo/Standard process-tier
question controlling how much process a generated project's `working-agreement.md` enforces.
Tier/hand-customization recognition is a static digest list
(`templates/known-working-agreement-digests.json`), not a git-history reconstruction — an
earlier design tried that and review (12 rounds, 3 past this repo's cap, owner-authorized
rebuild) found a real coupling bug with `bootstrap.sh`'s own conventions. Full account in
`main`'s `.claude/task/contract.md` history for that merge.

Also merged in the same wave: this repo was renamed
`claude-guardrails` → `claude-project-kit` (`rami.al-fahham/claude-project-kit` on GitLab;
local `gitlab` remote repointed), and this kit's own self-governance reviewer,
`.claude/agents/cto-reviewer.md`, was retired in favor of using
`templates/reviewers/platform-reviewer.md` directly (a straight rename would have collided by
filename with that already-existing module) —
[MR !26](https://gitlab.com/rami.al-fahham/claude-project-kit/-/merge_requests/26), merged.
`dbt-agent-kit`'s `scripts/sync-base.sh` still hardcodes the old URL — flagged as a separate
follow-up task in that repo (`task_5ad700d5`), deliberately not fixed here (cross-repo).

The `origin` GitHub remote (`ramialfahham/claude-guardrails`) came back after its 2026-09-17
suspension. GitLab (`claude-project-kit`) stays primary for all active work — MRs, CI, reviews.
GitHub is now a GitLab-native push mirror (Settings → Repository → Mirroring repositories,
protected branches only), auto-syncing on every push; confirmed healthy via GitLab's API
(`update_status: "finished"`, no error) and a matching `main` SHA on both remotes as of
2026-09-18. No manual sync needed going forward — don't re-flag GitHub as dead, and don't push
to it directly (the mirror handles it, and `branch_discipline.py` blocks a direct `main` push
to any remote regardless).

- The 7-phase `claude-project-kit` build (bootstrap + tailored `/setup-project` generation,
  reviewer module library, CI-provider audit) — complete. See `docs/project-kit-design.md`
  for the architecture and `docs/decisions/*.md` for the individual design calls.
- Post-plan hardening Phase 1 (completion-time advisory hook, auto-mode compatibility
  check, custom-review-gate-vs-`/code-review` rationale, sandboxing recommendation) —
  complete. See the same `docs/decisions/*.md`.

## Open owner decisions (none blocking, none scheduled)

- A generated project's routing (`templates/reviewers/routing/platform-reviewer.routing.json`
  + the empty `_BASE_ROUTING` in `scripts/preview_project_setup.py`) does not route edits to
  `.claude/settings.json` or `.claude/review_routing.json` to `platform-reviewer` — the very
  file `generate()` now writes into. This kit's own routing does. Flagged by review on the
  CI-audit wiring branch; whether to close that gap is a follow-up owner call.

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
