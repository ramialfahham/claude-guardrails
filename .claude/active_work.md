# Active work

## `claude-project-kit` — Phase 3 merged. Phase 4 next.

Full plan: `C:\Users\Rami\.claude\plans\happy-stargazing-mccarthy.md`. 7 phases +
1b, one task contract each.

**Merged**: Phase 1 (MR !2), Phase 1b (MR !3), Phase 2 (MR !4), Phase 3 (MR !6)
— all on `main`.

**Open, unmerged**: `!5` and `!7` — handover-only bookkeeping (no code).

**Phase 3 — hardened git-discipline hooks**: MERGED.
- `branch_discipline.py`: commit-form allowlist (refuses bundled short flags
  like `-am`, any pathspec on `git commit`), refuses staging bundled with
  committing in one Bash command, `checkout` exempted only for `-b`/`-B`.
- `commit_review_gate.py`: hashes the CUMULATIVE diff since the branch's
  merge-base with main (not staged-only) — use `--diff-hash` to get it now,
  not `--staged-hash` (still accepted as an alias). Self-reported `rounds:`
  field in review.md, capped at 3 before requiring a `CPO ANSWER:`. **Note**:
  the `artifact_only` bookkeeping exemption (e.g. a handover-only commit) is
  now evaluated against the CUMULATIVE path list, not just this commit's own
  staged files — so a docs-only commit on top of an already-substantive
  branch is NOT exempt anymore (only a branch that's entirely bookkeeping
  still is). This is exactly why `!7` hit a rebase conflict just now — not a
  bug, a real consequence of the new hashing worth knowing before it
  surprises you again.
- New `.claude/hooks/secret_scan.py`: blocks a commit whose staged diff
  contains a well-known credential shape.
- `_command_utils.py` gained `_degroup` (subshell/brace-group handling) and
  `is_commit_subcommand` (the "is this a real commit, not --dry-run"
  predicate, now shared by all three hooks instead of independently
  reimplemented — one copy had already drifted).
- `.claude/review_routing.json` now routes `.claude/settings.json` and
  itself to `cto-reviewer`.
- Five review rounds, each finding a real defect — full history in git log
  (`dbb6ba9`) and `.claude/task/review.md`/`contract.md` as of that commit.
- **The hardened hooks are LIVE now** — any commit in this repo (including
  yours) must use `-m`/allowed flags only, no pathspec, stage-then-commit as
  separate tool calls, and won't trigger the secret scanner.

**Next**: merge MR !7 (handover bookkeeping, rebased past the conflict above),
then start Phase 4 (model/effort routing convention + parity test —
`.claude/rules/guard-paths.md` template) as its own task contract. Do NOT
skip the contract step.

**Owner decisions still open**: rename this repo to `claude-project-kit`
(deferred); rename `.claude/agents/cto-reviewer.md` itself (deferred).

**Minor cleanup still NOT done** (came up repeatedly, always out of scope,
and just caused actual friction — a regenerated `.pyc` blocked a rebase):
`.claude/hooks/__pycache__/*.pyc` tracked in git from before `.gitignore`
existed — `git rm -r --cached .claude/hooks/__pycache__` as its own tiny
commit. Worth just doing next time, rather than deferring again.

## Also this session (2026-09-05/06)

- Global `~/.claude/CLAUDE.md` rewritten: critical-senior-engineer role,
  status-first communication, 95%-confidence autonomy, code/repo hygiene.
  Applies to every project.
- GitLab CI quota issue on this project fixed by enabling the account's
  existing self-hosted runner (`ci-runner-01`).

## Earlier, unrelated to the above

GitLab CI migration (`.gitlab-ci.yml`) — done and merged. Not open work.

`football-data-pipeline`'s past auto-merge incident is resolved in that repo
already — not open work here. Informed Phase 5 of the plan (CI-provider
automation audit).
