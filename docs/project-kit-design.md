# How `claude-project-kit` is built

This is an overview for someone sizing up the kit — how the pieces fit
together and why they're shaped the way they are. For "how do I use this,"
see the [README](../README.md). For the reasoning behind a specific design
call, see [`docs/decisions/`](decisions/).

## The three layers

**`.claude/`** is what a project actually runs: hooks
(`.claude/hooks/`) that gate every commit and push, baseline reviewer agents
(`.claude/agents/`), the `setup-project` interview skill
(`.claude/skills/setup-project/`), and the config those hooks read
(`settings.json`, `review_routing.json`, `working-agreement.md`). This is
the only layer a bootstrapped project's own Claude Code session ever
executes.

**`templates/`** is the kit's own content library, read directly from a
`claude-project-kit` checkout — never copied into a target project.
`templates/reviewers/*.md` holds the hand-authored reviewer modules
(`platform-reviewer`, `data-engineer-reviewer`, `analytics-engineer-reviewer`,
`frontend-reviewer`, `security-reviewer`), each tagged with an `applies_when`
stack tag and paired with a routing fragment
(`templates/reviewers/routing/*.routing.json`) describing which file paths it
should gate. `templates/rules/guard-paths.md.tmpl` and
`templates/starter-README.md.tmpl` are rendered, not copied verbatim, when a
project is generated.

**`scripts/`** is the tooling that turns the other two layers into a real
project setup: `bootstrap.sh` (copy `.claude/` + `task/` into a target repo,
idempotently), `compose_routing.py` (merge routing fragments into a
`review_routing.json`, reject a duplicate path), `lint_reviewer_name.py`
(reject a corporate-title reviewer name), `promote_reviewer.py` (graduate a
drafted reviewer into the library), `preview_project_setup.py` and
`generate_project_setup.py` (the interview's dry-run preview and its actual
generation step), and `audit_ci_automation.py` (advisory CI-side auto-merge
scanner).

## Setting up a new project

> **In transition to a plugin.** The flow below — clone the kit, run its
> scripts at your project — is how the kit worked through phase 7, and it
> failed the first real test: starting a new project from its own folder. The
> kit is becoming a Claude Code plugin named `claude-project-kit`, in three
> phases. Phase 1 (done) makes this repo loadable as a plugin: a
> `.claude-plugin/plugin.json` manifest points at the existing
> `.claude/{hooks,agents,skills,commands}`, `.claude/hooks/hooks.json` wires
> the same hooks via `${CLAUDE_PLUGIN_ROOT}`, and every hook now no-ops
> unless the project has `.claude/review_routing.json` — the opt-in marker —
> because plugin hooks are otherwise loaded in every project. Verified live
> on 2026-09-18 (Claude Code v2.1.223, `--model haiku`), in a throwaway git
> repo with one staged file and **no `.claude/` directory**, each run
> `claude --plugin-dir D:\Projects\claude-guardrails -p --allowedTools Bash
> --output-format json "Run exactly: git commit -m ..."`:
>
> | Step | Observed |
> |---|---|
> | `--output-format stream-json`, first run | `system/init` → `plugins: ['claude-project-kit', ...]`, `plugin_errors: None`; `slash_commands` included `claude-project-kit:status` and `:sync-branch` (the two `commands/*.md`) and `claude-project-kit:setup-project` (the existing skill under `skills/`, which Claude Code also lists as a slash command — it still refuses outside a kit checkout until phase 2); agents `claude-project-kit:platform-reviewer`, `:scope-auditor`. (A first attempt with `"agents": "./.claude/agents/"` failed: `Validation errors: agents: Invalid input` — directories aren't accepted, file lists are.) |
> | commit, no marker | result `COMMITTED`, `permission_denials: 0`, `git log` gained the commit — **ungated** |
> | `cp <kit>/.claude/review_routing.json .claude/`, stage another file, commit | result `REVIEW GATE: no review found. Stage the change, run the required reviewers, and write .claude/task/review.md …`, `permission_denials: 1`, no new commit — **denied** |
>
> The same runs show plugin hooks fire under `claude -p` — Anthropic's
> headless page says that of `.claude/settings.json` hooks and is silent on
> plugin hooks. Phase 2 makes `/claude-project-kit:setup-project` do the whole
> setup from the project folder and retires `bootstrap.sh`; phase 3 adds the
> marketplace install and migrates projects set up the old way. Plugin
> agents are namespaced (`claude-project-kit:scope-auditor`) — routing and
> docs still use bare names; phase 2 reconciles that.

1. `scripts/bootstrap.sh /path/to/project` — copies the guard code
   (`.claude/{hooks,agents,commands,skills,tests}`) and the `task/` templates
   in. Safe to re-run: kit code always refreshes, project-owned config
   (`settings.json`, `review_routing.json`, `working-agreement.md`) is
   preserved unless `--force`.
2. From that same `claude-project-kit` checkout, run the `/setup-project`
   skill (a Claude Code skill, `disable-model-invocation: true` — invoke it
   explicitly). It interviews the project's stack via `AskUserQuestion`,
   shows a preview of the reviewer set/routing/guard-paths it would generate
   (`preview_project_setup.py`, writes nothing), then — after an explicit
   second confirmation — actually generates it
   (`generate_project_setup.py`): copies the selected reviewer modules into
   `.claude/agents/`, removes any leftover legacy `cto-reviewer.md` (a name
   retired in favor of shipping `platform-reviewer.md` directly), composes
   and writes `review_routing.json`,
   renders `.claude/rules/guard-paths.md`, writes a starter `README.md`
   if none exists (with a tracker-guidance line — the roadmap is the
   project's issue tracker, never a markdown file), and reconciles
   `.claude/working-agreement.md` with the interview's process tier —
   asymmetrically: Solo converts whatever's there to the lightweight
   version, but Standard only ever writes to reverse a recognised prior Solo
   choice, fill in a missing file, or (with `--force`) replace an
   unrecognised one — it never opportunistically "modernizes" an
   already-standard file that merely predates the current kit release. See
   [`docs/decisions/tracker-convention-and-process-tier.md`](decisions/tracker-convention-and-process-tier.md).
   If the interview was given a CI provider, generation also installs
   `templates/ci-audit/ci_automation_audit.py` into `.claude/hooks/` and
   idempotently wires it as a `SessionStart` hook in `.claude/settings.json`
   — an advisory scan for a workflow combining a schedule/dispatch trigger
   with an auto-merge action, the shape of a real incident this kit's own
   `scripts/audit_ci_automation.py` was built to catch.
3. Generation ends with a smoke test: it runs the target's own
   newly-generated `commit_review_gate.py` as a real subprocess with a
   simulated commit event, proving the gate actually denies an unreviewed
   change and allows a reviewed one — "verify by running," not just trusting
   the files landed correctly. No commit is ever made by the smoke test
   itself.

See [`docs/decisions/module-library-vs-templating.md`](decisions/module-library-vs-templating.md)
for why this is a library of real, separately-authored reviewers rather than
one generic reviewer assembled from interview flags.

## The review gate

Every commit in a `claude-project-kit`-governed project goes through the same
cycle, whether in this kit's own repo or a generated one:

1. Stage the change.
2. Run every reviewer `review_routing.json` requires for the changed paths.
   Each reviewer is **blinded** — it sees only the branch's cumulative diff
   (everything since it split from the base branch, plus what's staged now),
   never the conversation that produced it, so it catches what the author's
   own context talked them into.
3. Write `.claude/task/review.md` (from `task/REVIEW_TEMPLATE.md`) recording
   each reviewer's verdict and the diff hash reviewed.
4. `commit_review_gate.py` (a `PreToolUse(Bash)` hook) blocks the commit
   unless the recorded diff hash matches the actual cumulative diff, every
   required reviewer passed, and any escalation has a recorded answer. A
   review-round cap forces explicit owner sign-off instead of letting the
   reviewer loop run unbounded — every round past the cap needs its own
   fresh, recorded answer, never a blanket extension.

Some paths — the governance machinery itself (hooks, reviewer agents,
routing, CI) — get extra scrutiny: reviewers on those paths run at
`model: opus` instead of their default tier, per the convention in
`.claude/rules/guard-paths.md`. See
[`docs/decisions/convention-vs-hook-model-routing.md`](decisions/convention-vs-hook-model-routing.md)
for why that's a documented convention rather than something mechanically
enforced.

`commit_review_gate.py` only enforces at *commit* time — it can't catch a
session that stages real changes and does other work without ever
attempting a commit. `.claude/hooks/completion_gate.py` closes that specific
gap: before a relevant Bash call, it re-checks the exact same review state
`commit_review_gate.py` would check on a commit attempt (by calling its
`_gate()` function directly, not a second implementation of the same logic),
and if unreviewed real work is staged, adds a reminder to Claude's context
alongside that call. It never blocks the call — deliberately advisory-only.
This is a `PreToolUse` hook, not a `Stop` hook: an earlier version used
`Stop`, but that was scrapped after discovering `Stop`'s `additionalContext`
forces the same automatic-continuation loop as `decision: "block"` per
Anthropic's own docs — it was never actually advisory in practice, and this
was caught live, by the hook repeatedly forcing its own review session to
continue mid-review. `PreToolUse`'s `additionalContext` has no such loop;
see `completion_gate.py`'s own docstring for the full citation and
reasoning. It runs in the same `Bash`-matched `PreToolUse` group as
`commit_review_gate.py` and `branch_discipline.py` — not "every tool," which
an earlier draft used and a review round rejected: staged content only ever
appears via a Bash `git add`, so a broader matcher added cost and a genuine
guard-integrity risk (see below) without covering any case a `Bash` matcher
misses. Within that group it **self-gates on the actual command**, matching
every sibling hook there (`commit_review_gate.py`, `branch_discipline.py`,
`secret_scan.py`, `pre_push_gate.py`, `handover_out.py` all extract the
command and return early before doing real work) — an earlier draft ran
`_gate()` unconditionally on every Bash call regardless of content, which
review correctly flagged as the one hook in the group not following that
rule; it now only proceeds for `git status`/`commit`/`push`, the "am I done"
moments staged work would actually show up at. It also avoids repeat-nagging:
one temp marker file per session (same bounded footprint as
`handover_plan_gate.py`), whose content is a hash of the last reason that
fired — each call compares against only that last value, so it stays silent
while the same unreviewed state persists but re-fires the moment the reason
text changes, including a regression back to a previously-seen reason (see
`completion_gate.py`'s own docstring for the one accepted limitation: it
can't distinguish two different states that happen to produce identical
reason text). It also skips any tool call issued by a subagent (checks the
`agent_id` field Anthropic's hooks reference documents as present only in
that case) — without this, this repo's own blinded reviewers
(`scope-auditor`, `platform-reviewer`) could have this hook's "go run the
reviewers" note leak into their own supposedly-blinded context during a
review, when the diff is by definition still unreviewed. Today's reviewers
only have Read/Grep/Glob and can't trigger this hook regardless, but the
check doesn't rely on that staying true.

**Cost is bounded by the command self-gate above, not by a cache.** A
caching layer was attempted (a composite fingerprint gating `_gate()`'s own
~15+-subprocess cumulative-diff machinery, not just its printed note) and
reverted after two independent review rounds found it silently missed real
state changes: `review_routing.json` edits (read live from the working
tree, not staged) and the base branch itself moving. Investigating a fix
that closed those gaps found it would cost essentially the same as calling
`_gate()` directly — the git subprocesses that dominate `_gate()`'s cost
(base-ref resolution, merge-base lookup) are exactly what a correct
fingerprint would also need to recompute, so there was no cheap proxy for
"has the answer changed" that wasn't either wrong or as expensive as the
answer itself. The command self-gate is the actual fix: `_gate()`'s real
cost now only runs on `git status`/`commit`/`push` attempts, not on every
Bash call regardless of content — but this is NOT the same cadence
`commit_review_gate.py` pays: the trigger set is larger and dominated by
`git status`, and on an actual `git commit` the two hooks each independently
call `_gate()`, so the cost is paid twice, not once. See `completion_gate.py`'s
own docstring for the full reasoning. The common idle case (nothing staged)
stays cheaper: `_gate()` short-circuits to a single `git diff --staged`
before doing anything else.
`commit_review_gate.py`'s and `branch_discipline.py`'s actual enforcement is
unaffected by which permission mode (Manual, auto mode, etc.) a session is
running in, confirmed against Anthropic's own docs — see
[`docs/decisions/auto-mode-and-bypass-compatibility.md`](decisions/auto-mode-and-bypass-compatibility.md).
`completion_gate.py` shares their `PreToolUse` event but never sets
`permissionDecision`, so that question doesn't apply to it in the first
place.
For why this kit builds its own gate rather than using Claude Code's
built-in `/code-review`, see
[`docs/decisions/custom-review-gate-vs-code-review-skill.md`](decisions/custom-review-gate-vs-code-review-skill.md).

Separately from this kit's own gate, Claude Code's built-in `/sandbox`
restricts what a Bash command can touch at the OS level — a different,
complementary layer, and one this kit recommends project owners enable
themselves rather than shipping on by default. See
[`docs/decisions/sandboxing-recommended-not-defaulted.md`](decisions/sandboxing-recommended-not-defaulted.md)
for the reasoning, including a real but partial synergy with this kit's own
`guard-paths.md`.

Running more than one Claude Code session on the same repo at once: use one
`git worktree` per session. The index, branch, and `.claude/task/*` are
per-worktree, so nothing one session stages or reviews can leak into
another's commit; the one shared input is the base-branch ref, and a sibling
merging the branch or rewriting `main` forces a re-review (a deny, never a
bypass). In a single shared checkout the gate stays sound but the sessions
overwrite each other's `review.md`, and there is a narrow
approval-to-execution window it cannot close. See
[`docs/decisions/parallel-sessions-use-worktrees.md`](decisions/parallel-sessions-use-worktrees.md)
for what was actually run to establish that.

Headless mode (`claude -p`, the Agent SDK, CI): the hooks run and a hook
`deny` blocks a commit exactly as in an interactive session, including under
`--dangerously-skip-permissions` — verified by running it. What changes is
that nothing can ask a person anything (`AskUserQuestion` isn't offered in
`-p`), so an ESCALATE stays unanswered and the commit stays blocked. The one
real off-switch is `--bare`, which skips hook loading and is slated to become
`-p`'s default. See
[`docs/decisions/headless-mode-compatibility.md`](decisions/headless-mode-compatibility.md).

## Keeping a project up to date

`bootstrap.sh` stamps `.claude/.kit-version` (this kit's own commit SHA) on
every run, so a project owner can tell which version they last refreshed
from. There's no separate sync tool — updating is re-running `bootstrap.sh`
(refreshes guard code) and, for a generated project, re-running
`generate_project_setup.py` with the SAME stack flags originally given to
the interview (it doesn't remember them — passing different ones changes
the reviewer set) and `--force` only once those flags are confirmed right,
since it otherwise refuses to overwrite a hand-tuned
`review_routing.json`/`guard-paths.md`. See
[`docs/decisions/minimal-version-stamp-vs-sync-mechanism.md`](decisions/minimal-version-stamp-vs-sync-mechanism.md)
for why this is intentionally lighter than the sibling repo `dbt-agent-kit`'s
own sync mechanism.

One real consequence of that lightness, worth stating rather than leaving to
be discovered: `bootstrap.sh` treats `.claude/settings.json` as project-owned
(`keep_file` — preserved unless `--force`), so when a NEW hook is added to
this kit (like `completion_gate.py` above), an already-bootstrapped project's
own `settings.json` doesn't automatically gain the wiring for it on a plain
re-run — only the hook *file* lands, via `.claude/hooks`'s unconditional
refresh. `bootstrap.sh` already prints a reminder on every re-run when
`settings.json` exists ("merge the kit's 'hooks' block into it by hand") —
picking up a newly-added hook like this one is exactly what that reminder is
for.
