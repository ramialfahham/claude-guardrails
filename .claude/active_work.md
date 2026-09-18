# Active work

This file is a **current-state snapshot**, overwritten each time it's updated — not a log.
Merged work, review rounds, and lessons-learned live in MR descriptions and each merged
branch's `.claude/task/contract.md` amendments; don't re-narrate them here. If it isn't
still true or still open, it doesn't belong in this file.

## Where things stand

Nothing is in flight. Owner confirmed 4 items to do before moving to the website-project test;
3 of 4 are merged — [MR !31](https://gitlab.com/rami.al-fahham/claude-project-kit/-/merge_requests/31)
(CI-audit hook wired into generated projects; `templates/*` guard path + routing/doc drift fix)
and [MR !33](https://gitlab.com/rami.al-fahham/claude-project-kit/-/merge_requests/33)
(`docs/decisions/parallel-sessions-use-worktrees.md` — one `git worktree` per concurrent
session; every claim run live; the shared base-branch ref can only ever force a spurious
re-review, never a bypass). Both took 4 review rounds (owner authorised one past the cap each
time) — accounts in those merges' `.claude/task/contract.md` amendments.

Remaining: (4) scope the headless-mode (`claude -p`) audit — NOT STARTED. Then the
website-project test.

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

- **Review-process fix, proposed after MR !33, not yet decided.** Diagnosis from the last
  three branches (12, 4, 4 rounds): (1) reviewer definitions never ask for an exhaustive
  per-round finding list, so findings arrive serially — MR !33's round-3 finding was present
  in round 1's diff; (2) nothing makes the builder check code-behaviour claims against source
  before spawning reviewers; (3) the 3-round cap can't distinguish "design is wrong" (MR !28,
  where it correctly forced a rebuild) from "findings arriving one per round" (!31, !33, where
  it produced an `AskUserQuestion` for a two-line fix). Proposed: (A) a "round completeness"
  rule in `templates/reviewers/*.md` + this kit's `.claude/agents/*` — list every finding; a
  finding first raised in round N that existed in round 1's diff is labelled a reviewer defect;
  (B) a builder pre-review self-check for claims about code behaviour (claim → `file:line`) in
  the working agreement; (C) leave the cap at 3 until A+B show whether round counts drop.
  Owner to decide whether/when — before or after item 4.
- A generated project's routing (`templates/reviewers/routing/platform-reviewer.routing.json`
  + the empty `_BASE_ROUTING` in `scripts/preview_project_setup.py`) does not route edits to
  `.claude/settings.json` or `.claude/review_routing.json` to `platform-reviewer` — the very
  file `generate()` now writes into. This kit's own routing does. Flagged by review on the
  CI-audit wiring branch; whether to close that gap is a follow-up owner call.

## Next candidate work

- **Headless-mode (`claude -p`) compatibility audit** — not started. Last of the originally
  deferred hardening phases; gets its own task contract when picked up, or a "considered,
  not building" ADR if it turns out not worth it.
