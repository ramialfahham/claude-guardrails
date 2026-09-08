# The CI-automation audit is always advisory, never auto-fixing

**Status**: decided, shipped (Phase 5 of the master plan). Source:
`scripts/audit_ci_automation.py`'s own module docstring.

## Context

`scripts/audit_ci_automation.py` exists because of a real incident: a
project's GitHub Actions workflow auto-merged pull requests by trusting
`mergeable_state` alone, which only reflects checks branch protection actually
*requires* — the real build job wasn't in that required list, so PRs merged
before the build finished. No local git hook could ever have caught this: it's
a server-side CI-provider behavior, not a `git` operation any
`PreToolUse(Bash)` hook can see.

## Decision

Two checks, both read-only: a static scan of workflow files for a
schedule/dispatch trigger combined with an auto-merge action or merge-API
call, and a best-effort live check (via `gh`/`glab`, only if authenticated)
reporting branch-protection and auto-merge status. The script never modifies
branch protection, auto-merge settings, or any workflow file — `--strict`
only changes its own exit code, never anything about the repo or CI provider
it's reading.

## Why

Branch protection and auto-merge settings are project configuration a script
should never silently flip — the same principle already applied elsewhere in
this kit's own history (GitLab branch-protection changes were made by hand,
never scripted, during this kit's own CI migration). An earlier version of
this tool also tried to judge whether a project's required-status-checks list
"covers" its real CI jobs — that produced a long, non-converging series of
correctness bugs (trigger-detection edge cases, matrix/reusable-workflow
syntax collisions, provider mixing) across several review rounds and was
removed rather than continuing to chase; see `.claude/task/contract.md`'s
amendments log from that phase for the full history. Which jobs are
load-bearing is a project-specific judgment call a human makes by reading the
tool's printed `required_checks` output, not something inferable from parsing
arbitrary YAML with text patterns.

## Consequences

- The tool can flag a real risk and still requires a human to act on it —
  nothing here closes the gap that caused the original incident by itself,
  it only makes the gap visible.
- `--strict` (for CI wiring) only trips on the static scan reliably; the live
  check only governs it when exactly one GitHub/GitLab remote is unambiguous
  — with more than one remote, every live-check result is informational only,
  since there's no reliable way to guess which remote is "the real one."
