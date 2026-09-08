# How `claude-guardrails` is built

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
`claude-guardrails` checkout — never copied into a target project.
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

1. `scripts/bootstrap.sh /path/to/project` — copies the guard code
   (`.claude/{hooks,agents,commands,skills,tests}`) and the `task/` templates
   in. Safe to re-run: kit code always refreshes, project-owned config
   (`settings.json`, `review_routing.json`, `working-agreement.md`) is
   preserved unless `--force`.
2. From that same `claude-guardrails` checkout, run the `/setup-project`
   skill (a Claude Code skill, `disable-model-invocation: true` — invoke it
   explicitly). It interviews the project's stack via `AskUserQuestion`,
   shows a preview of the reviewer set/routing/guard-paths it would generate
   (`preview_project_setup.py`, writes nothing), then — after an explicit
   second confirmation — actually generates it
   (`generate_project_setup.py`): copies the selected reviewer modules into
   `.claude/agents/`, removes the bootstrap-default `cto-reviewer.md` in
   favor of the tailored set, composes and writes `review_routing.json`,
   renders `.claude/rules/guard-paths.md`, and writes a starter `README.md`
   if none exists.
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

Every commit in a `claude-guardrails`-governed project goes through the same
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
