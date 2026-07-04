# claude-guardrails

[![CI](https://github.com/ramialfahham/claude-guardrails/actions/workflows/ci.yml/badge.svg)](https://github.com/ramialfahham/claude-guardrails/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Repo-level guardrails for AI-assisted development, in any language. They live in a
self-contained `.claude/` committed to your repo — no plugin, no machine install, nothing
global. The agent agrees a plan with you before writing code, each change is reviewed before
it's committed, and your git history stays safe.

## What it does

- **Plans before coding.** The agent restates the task and waits for your approval before
  editing any files.
- **Reviews before committing.** Adversarial reviewers (scope, and platform/CI/tooling) check
  each change before the commit goes through.
- **Keeps git safe.** Work stays on a feature branch; committing or pushing to `main`,
  rewriting history, and merging your own PRs are blocked.
- **Carries context across sessions.** A short handover note records where you left off, so a
  new chat continues cleanly.

## Why repo-level, not a plugin

The guardrails live in your repo's own `.claude/`, not in machine-wide config:

- **Scoped, not leaking.** The gates apply to *this* repo only — they can't bleed into
  unrelated repos.
- **Visible and trusted.** The hook code is committed and shows up in the diff. Nobody has to
  install arbitrary global hook code; Claude Code prompts once to trust the project's hooks.
- **No install step.** You copy `.claude/` in (or start from the template) and the guardrails
  are already wired in `.claude/settings.json`. Nothing to add to `~/.claude/`.

## The checkpoints

The agent does the work along the arrows — explore, plan, implement, commit, push. The kit
adds five checkpoints where you stay in control: it carries your handover notes (blue), waits
for you to approve the plan before any code (yellow), and blocks the commit and the push until
their checks pass (red).

```mermaid
flowchart TD
    A[Session start] --> B[Handover in<br/>reads .claude/active_work.md]
    B -. agent: explore & plan .-> D{Plan-back gate<br/>agent restates the plan, waits for your go}
    D -. agent: implement .-> G{Review gate<br/>reviewers passed? blocks the commit}
    G -. agent: commit .-> I{Pre-push gate<br/>on a branch, checks run}
    I -. agent: push & open PR .-> K[Handover out<br/>agent updates .claude/active_work.md]

    style B fill:#dbeafe,stroke:#1e40af
    style K fill:#dbeafe,stroke:#1e40af
    style D fill:#fde68a,stroke:#b45309
    style G fill:#fecaca,stroke:#b91c1c
    style I fill:#fecaca,stroke:#b91c1c
```

Hooks fail open on error, so a bug can't lock you out; the guards that stop you block on purpose.

## Add it to a repo

Clone this and run the bootstrap script against your target repo:

```bash
git clone https://github.com/ramialfahham/claude-guardrails
claude-guardrails/scripts/bootstrap.sh /path/to/your-repo
```

It copies the `.claude/` guardrails and the `task/` templates in — no plugin, nothing global.
Safe to re-run to pull updates: the guard *code* is refreshed, while your own `settings.json`,
`review_routing.json`, and handover are left untouched (`--force` to overwrite, `--dry-run` to
preview). Then commit the new `.claude/` and approve the hooks on the next Claude Code session.
Run it with `--help` for the full usage.

## Requirements

The hooks are small Python scripts run through a bash shell, so the machine running Claude Code
needs **Python 3 reachable as `python` on `PATH`** and **a bash shell** (Git Bash or WSL on
Windows). If `python` isn't found the hooks fail open — a session-start preflight warns you
instead of leaving you unknowingly unguarded.

## What's in the repo

- **`.claude/`** — the guardrails, committed and readable: the hooks (`.claude/hooks/`), the two
  reviewers (`.claude/agents/` — `scope-auditor`, `cto-reviewer`), the `status` command,
  `settings.json` wiring the hooks, `working-agreement.md` (the rules the hooks and reviewers
  reference), and `review_routing.json`. The handover lives at `.claude/active_work.md`.
- **`scripts/bootstrap.sh`** — copies `.claude/` into an existing repo.
- **`task/`** — the contract + review templates the review cycle uses.

## Design decisions

- **Repo-level, not a global plugin.** The config lives in the repo, is scoped to it, shows up
  in the diff, and needs no machine install. The cost is that each repo carries its own copy of
  `.claude/`; the benefit is no leakage, a visible per-repo trust decision, and nothing to install.
- **Reviewers run blinded and adversarial.** Each reviewer sees the staged diff cold, with no
  memory of the conversation that produced it — so the review catches what the author's context
  talked them into.
- **The commit gate hard-blocks; it isn't advice.** A commit is refused until the review matches
  the staged diff and every required reviewer has passed.
- **Hooks fail open, guards fail closed.** A hook that errors lets you through — tooling shouldn't
  lock you out of your own repo. The guards whose whole job is to stop you (branch discipline, the
  review gate) block by design.

## How the review gate works

1. You stage your change (`git add ...`).
2. You run the reviewers the routing requires and write `.claude/task/review.md` (copy
   `task/REVIEW_TEMPLATE.md`), pasting the staged-diff hash.
3. `git commit` is blocked until the review matches the staged change, every required reviewer
   passed, and any escalation has an answer.

## Related

- **[dbt-agent-kit](https://github.com/ramialfahham/dbt-agent-kit)** — these guardrails plus a
  dbt overlay (dbt reviewers, a project scaffold, layer rules) for analytics-engineering repos.
- **[claude-skills](https://github.com/ramialfahham/claude-skills)** — general-purpose personal
  skills installed globally into `~/.claude/skills/`.
