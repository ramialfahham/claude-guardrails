# A custom blocking review gate, not Claude Code's built-in `/code-review`

**Status**: verified, documented. Source: Anthropic's official Claude Code
documentation (`code.claude.com/docs/en/code-review`) and the
`anthropics/claude-code` repository's own `plugins/code-review/` — researched
directly, September 2026.

## Context

Claude Code now ships a built-in `/code-review` command/plugin. A technical
reviewer of this kit would reasonably ask: why build and maintain a custom
blinded review gate (`scope-auditor`/`platform-reviewer` plus
`commit_review_gate.py`'s enforcement) instead of just using the one that
already ships with the product? Until now, this repo had no answer to that
question anywhere — silence, not a considered decision.

## What `/code-review` actually does

- Analyzes a GitHub pull request's diff with a fleet of specialized subagents
  looking for logic errors, security vulnerabilities, broken edge cases, and
  regressions.
- Posts findings as **inline comments on the PR**, tagged by severity.
- Explicitly **does not gate anything**: "Findings are tagged by severity and
  don't approve or block your PR, so existing review workflows stay intact."
- Is **GitHub-PR-specific** — it operates against a PR already opened on
  GitHub.
- Is currently a **research preview**, available on Team and Enterprise
  plans (not available with Zero Data Retention enabled); on other plans, a
  diff can still be reviewed locally with the command.

## Why this kit's gate is different, not redundant

| | `/code-review` | This kit's gate |
|---|---|---|
| When it runs | After a PR exists, on demand | Before a commit is allowed to happen at all |
| Effect | Advisory comments only — never blocks | Hard-blocks the commit until required reviewers PASS |
| Scope | GitHub PRs specifically | Any git host — the gate is a local `PreToolUse` hook, not tied to a provider |
| Availability | GitHub-integrated posting is research preview, Team/Enterprise only; a diff can still be reviewed locally with the command on other plans | Works today, on any plan, in any repo |
| Review model | A fleet of subagents scoring a diff | Named, blinded reviewers (`scope-auditor`, tailored stack reviewers) with a recorded verdict and diff-hash binding |

The two operate at different points in the pipeline and give different
guarantees. `/code-review`'s own documentation is explicit that it leaves
existing review workflows — including a hard gate like this kit's — intact
by design; it is meant to layer on top of whatever review process already
exists, not replace it. `/code-review` cannot ever provide a *blocking*
guarantee — it only posts comments after the fact, by design, regardless of
how it's configured. This kit's gate can — but "can" is not "always does":
it deliberately fails open on error (`commit_review_gate.py`'s own comment:
"a gate bug must never block your workflow"), no routing config means no
gate at all, missing Python leaves the hooks silently not running at all
(per `preflight.sh`'s own warning), and it only covers commits made through
`PreToolUse(Bash)` — a commit from outside Claude Code entirely isn't gated.
Precisely stated: `/code-review` cannot block by design, in any
configuration; this kit's gate blocks by default and fails open only on
infrastructure problems (missing config, missing Python, a hook bug) that
are themselves visible and fixable, not silent gaps by design.

## Consequences

- This kit's gate is not redundant with `/code-review` — it solves the
  problem `/code-review` explicitly declines to solve (blocking, not just
  advising).
- A project using both gets real defense in depth: this kit's gate blocks
  commits made through Claude Code without a recorded, verdict-matched
  review (see the fail-open cases named above for where that stops
  applying); `/code-review`, where available, adds an independent second
  pass with different reviewers and a different vantage point (the PR diff
  on GitHub, rather than the local git state) regardless of how the commit
  was made.
- If `/code-review` (or a future built-in equivalent) ever gains a genuine
  *blocking* mode, this comparison should be revisited — the case for a
  fully custom gate weakens if the platform starts offering the same
  guarantee natively. That has not happened as of this writing.
