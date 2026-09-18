# Active work

This file is a **current-state snapshot**, overwritten each time it's updated — not a log.
Merged work, review rounds, and lessons-learned live in MR descriptions and each merged
branch's `.claude/task/contract.md` amendments; don't re-narrate them here. If it isn't
still true or still open, it doesn't belong in this file.

## Where things stand

Nothing is in flight. **Plugin phase 1 merged** —
[MR !39](https://gitlab.com/rami.al-fahham/claude-project-kit/-/merge_requests/39). Phase 2 is
next and is what unblocks the owner's website project.

**Why (locked, don't re-litigate):** the website-project test — the kit's stated purpose, a new
project set up from its own folder — failed on the first step: `/setup-project` only runs from
a kit checkout. Owner rejected a path-stamp workaround ("just a hack") and chose the plugin
shape (AskUserQuestion: "Plugin (C)"), the name `claude-project-kit`, and hooks that fire ONLY
in opted-in projects (marker: the project's `.claude/review_routing.json`). The owner's website
project waits for phase 2 — do not set it up the old way.

**Phase 1 (merged, MR !39):** `.claude-plugin/plugin.json` (components stay under `.claude/`;
`agents`/`commands` must be file lists, not dirs — Claude Code rejects a dir); `.claude/hooks/hooks.json`
mirrors `settings.json` via `${CLAUDE_PLUGIN_ROOT}` with a parity test; every hook short-circuits
on `_command_utils.project_opted_in()`; `test_plugin_manifest.py` covers manifest, parity, and
silent-vs-speaking per hook. Verified live with `claude --plugin-dir <kit> -p` in a repo with no
`.claude/`: plugin listed in `system/init`, commit ungated without the marker, denied with it.
No hook decision logic changed; `bootstrap.sh` untouched (still works, now also copies the
harmless `hooks.json`).

**Phase 2 (next):** `/claude-project-kit:setup-project` — the existing skill already ships in the
plugin under that name, but still refuses outside a kit checkout — runs from the target folder: absorbs
`bootstrap.sh` (`git init` if needed, interview, preview, generate; writes only project-owned
files, copies no hooks), retires `bootstrap.sh`, README quickstart rewritten for "new project,
from its folder". Must reconcile agent namespacing: plugin agents are
`claude-project-kit:scope-auditor` etc. while `review_routing.json`, `review.md` sections, the
working agreement, and the skills say bare names — decide whether generated projects get
project-level copies (bare names, override plugin ones) or routing learns the prefix.
**Phase 3:** `marketplace.json` + `/plugin install` from the GitLab URL; migration for old-style
projects (copied hooks + plugin hooks fire twice — `football-data-pipeline`, `dbt-agent-kit`);
the kit governing itself while also installed as a plugin (same double-fire); ADR "plugin over
bootstrap" superseding `minimal-version-stamp-vs-sync-mechanism.md`.

Before this: all 4 pre-website items merged (MR !31 CI-audit wiring, !33 worktree ADR,
!35 review-process fix, !37 headless ADR).

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

- **Plugin cost** (flagged by review on phase 1): as a plugin, every Bash call in every project
  where the plugin is enabled spawns the six `PreToolUse(Bash)` hook processes, each of which
  stats the marker and exits when not opted in. Fires only in set-up projects, as decided, but
  LOADS everywhere. Whether that's acceptable, or whether a lighter first check is worth a
  mechanism, is an owner call.
- **`.claude-plugin/*` as a guard path?** The manifest decides what loads in every consumer
  project and matches nothing in `review_routing.json` / `guard-paths.md`. Owner call.
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

- **Plugin phase 2** (above) — then the owner's website project is set up from its folder as
  the first real run.
