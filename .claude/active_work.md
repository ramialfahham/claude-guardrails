# Active work

This file is a **current-state snapshot**, overwritten each time it's updated — not a log.
Merged work, review rounds, and lessons-learned live in MR descriptions and each merged
branch's `.claude/task/contract.md` amendments; don't re-narrate them here. If it isn't
still true or still open, it doesn't belong in this file.

## Where things stand

**Branch `research/headless-mode-audit` — committed, MR open on GitLab, awaiting owner
merge.** Item 4 of the owner's 4: `docs/decisions/headless-mode-compatibility.md`, doc-only.
Six `claude -p` runs against a throwaway bootstrapped repo (v2.1.223, haiku): the review gate
denies an unreviewed commit headless, denies it under `--dangerously-skip-permissions`, and
allows it with a valid `review.md`; `SessionStart` injects the handover (so
`${CLAUDE_PROJECT_DIR}` resolves); `AskUserQuestion` is not offered in `-p` at all. `--bare`
(documented: skips hooks; needs `ANTHROPIC_API_KEY`, not OAuth) could not be run here. Also
amends `auto-mode-and-bypass-compatibility.md`: its "not confirmed" bypass gap is now closed
by a direct doc quote. No hook/script/test changes.

Most recent merge before that —
[MR !35](https://gitlab.com/rami.al-fahham/claude-project-kit/-/merge_requests/35): the
review-process fix (round-completeness rule + claims-against-source hunt item in every
reviewer module; builder pre-spawn self-check in both working agreements; 3-round cap left
as-is — **revisit only if branches keep hitting the cap**).

All 4 pre-website items are now done or in review. Next: the website-project test.

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
local `gitlab` remote repointed; GitHub followed on 2026-09-18 — see below), and this kit's own
self-governance reviewer,
`.claude/agents/cto-reviewer.md`, was retired in favor of using
`templates/reviewers/platform-reviewer.md` directly (a straight rename would have collided by
filename with that already-existing module) —
[MR !26](https://gitlab.com/rami.al-fahham/claude-project-kit/-/merge_requests/26), merged.
`dbt-agent-kit`'s `scripts/sync-base.sh` still hardcodes the old URL — flagged as a separate
follow-up task in that repo (`task_5ad700d5`), deliberately not fixed here (cross-repo).

The `origin` GitHub remote came back after its 2026-09-17 suspension and was renamed to
`ramialfahham/claude-project-kit` on 2026-09-18 (owner-approved; local `origin` repointed).
GitHub redirects the old `claude-guardrails` URL until someone creates a new repo under that
name. Still on the old URL, both working via that redirect: the GitLab push-mirror target
(updating it means re-entering the mirror token in GitLab's UI — owner's call, not urgent) and
`dbt-agent-kit`'s `scripts/sync-base.sh` (that repo's own follow-up). The local folder is still
`D:\Projects\claude-guardrails`; renaming it moves the Claude Code project-memory path, so
that's an owner action outside a session, if ever. GitLab (`claude-project-kit`) stays primary
for all active work — MRs, CI, reviews. GitHub is a GitLab-native push mirror (protected
branches only), auto-syncing on every push — `main` SHAs matched on both remotes right after
the rename. Don't re-flag GitHub as dead, and don't push to it directly (the mirror handles it,
and `branch_discipline.py` blocks a direct `main` push to any remote regardless).

- The 7-phase `claude-project-kit` build (bootstrap + tailored `/setup-project` generation,
  reviewer module library, CI-provider audit) — complete. See `docs/project-kit-design.md`
  for the architecture and `docs/decisions/*.md` for the individual design calls.
- Post-plan hardening Phase 1 (completion-time advisory hook, auto-mode compatibility
  check, custom-review-gate-vs-`/code-review` rationale, sandboxing recommendation) —
  complete. See the same `docs/decisions/*.md`.

## Open owner decisions (none blocking, none scheduled)

- **`--bare` will become `claude -p`'s default** (Anthropic docs, 2026-09-18). Bare mode skips
  hook loading, so a CI script following Anthropic's own examples runs with this kit's gate
  silently off. Whether that deserves a warning in `README.md` or in `/setup-project`'s
  output is an owner call — flagged by the headless-mode ADR, not acted on.
- **One-line test follow-up**: `.claude/tests/test_hooks_import.py`'s `_MODE_INDEPENDENT_HOOKS`
  tripwire lists `commit_review_gate`, `branch_discipline`, `completion_gate` but not
  `secret_scan`, the third `deny`-capable hook — so nothing catches `secret_scan.py` ever
  branching on `permission_mode`, which the auto-mode ADR's update now says it doesn't. Found
  during the headless-mode audit; deliberately not changed on that doc-only branch.
- A generated project's routing (`templates/reviewers/routing/platform-reviewer.routing.json`
  + the empty `_BASE_ROUTING` in `scripts/preview_project_setup.py`) does not route edits to
  `.claude/settings.json` or `.claude/review_routing.json` to `platform-reviewer` — the very
  file `generate()` now writes into. This kit's own routing does. Flagged by review on the
  CI-audit wiring branch; whether to close that gap is a follow-up owner call.

## Next candidate work

- **Website-project test** — the owner's stated next step once the 4 pre-items were done.
  Not scoped; gets its own contract.
