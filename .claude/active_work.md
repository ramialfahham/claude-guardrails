# Active work

## `claude-project-kit` — Phase 3 IN PROGRESS

Full plan: `C:\Users\Rami\.claude\plans\happy-stargazing-mccarthy.md`. 7 phases +
1b, one task contract each.

**Merged**: Phase 1 (MR !2), Phase 1b (MR !3), Phase 2 (MR !4) — all on `main`,
git history has full detail, not carrying forward as open work.

**Open, unmerged**: `!5` — handover-only bookkeeping update (no code), branch
`chore/handover-after-phase2`. Also enabled the account's self-hosted runner
(`ci-runner-01`) on this project, fixing a `ci_quota_exceeded` pipeline failure
that was unrelated to any code change.

**IN PROGRESS right now**: Phase 3 — hardened git-discipline hooks, branch
`feat/hardened-git-discipline`. This is the highest-scrutiny phase — it touches
the commit gate every other commit in every kit-derived repo depends on.
Scope: `branch_discipline.py` gains a commit-form allowlist (blocks `-a`/`-am`,
pathspecs, chained `git add && commit`) + a `core.hooksPath` tamper check;
`commit_review_gate.py` gains cumulative `base...HEAD` diff hashing (not
staged-only) + a review-round cap; plus a new secret-leak scanning hook.
**If you're picking this up fresh: this file was intentionally marked
IN-PROGRESS at the start of the phase, not just updated at the end — check
`git status`/`git log` on this branch for the actual current state before
trusting the description above as complete.**

**Owner decisions still open**: whether to rename this repo to
`claude-project-kit` (deferred); whether to rename `.claude/agents/cto-reviewer.md`
itself (deferred).

**Minor cleanup noticed but still NOT done (came up 3+ times, out of scope
every time)**: `.claude/hooks/__pycache__/*.pyc` files are tracked in git from
before `.gitignore` existed — worth `git rm -r --cached .claude/hooks/__pycache__`
as its own tiny standalone commit sometime.

## Also this session (2026-09-05)

- Global `~/.claude/CLAUDE.md` rewritten: critical-senior-engineer role (no
  praise filler, push back on wrong assumptions with technical reasons, don't
  fold under pushback without new evidence), status-first communication
  (plain terms, done/broken/blocked, before any narrative), 95%-confidence
  autonomy rule, code/repo hygiene (no inline comments by default, no
  timestamps/authorship in code, no unsolicited files except where a repo's
  own written rules require them), plus the earlier token-saving habits.
  Applies to every project, not just this one.
- Evaluated 6 open-source "save tokens" tools from a LinkedIn post — verified
  real via web search but decided against installing any. Kept the underlying
  techniques as habits in the global CLAUDE.md instead.

## Earlier, unrelated to the above

GitLab CI migration (`.gitlab-ci.yml`) — fully done and merged. Not open work.

`football-data-pipeline`'s past auto-merge incident is resolved in that repo
already, by the owner — not open work here. It informed Phase 5 of the
claude-project-kit plan (CI-provider automation audit).
