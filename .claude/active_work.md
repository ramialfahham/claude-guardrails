# Active work

## `claude-project-kit` — Phase 1 merged, Phase 1b pending merge

Full plan: `C:\Users\Rami\.claude\plans\happy-stargazing-mccarthy.md` (approved
2026-09-03, amended 2026-09-05 to add Phase 1b). 7 phases + 1b, one task contract
each.

**Phase 1 — reviewer module library + naming lint**: MERGED (MR !2, `b1ed2c9` on
`main`). `templates/reviewers/{platform,security,data-engineer,analytics-engineer,
frontend}-reviewer.md` + `_skeleton.md` fallback + `README.md`; `scripts/
lint_reviewer_name.py` rejects corporate-title reviewer names as code. Also added
`.gitignore` (repo had none). Full detail/review history in git log — not carrying
forward as open work.

**Phase 1b — promote-to-library**: MERGE-READY, not yet merged.
- Branch: `feat/promote-reviewer`. MR:
  https://gitlab.com/rami.al-fahham/claude-guardrails/-/merge_requests/3 — MR
  pipeline green, job log confirms the new test actually ran.
- Added `scripts/promote_reviewer.py`: copies a drafted reviewer (started from
  `_skeleton.md`, refined on a real project) into `templates/reviewers/`, once
  its `draft: true` flag is removed and required fields are all present.
  Manual-only, by design — never wired to a hook/CI/count/schedule.
- Review cycle: cto-reviewer FAILed round 1 on a real path-traversal write
  vector (an unsanitized frontmatter `name:` could write outside
  `templates/reviewers/`), a regex-parsing inconsistency with
  `lint_reviewer_name.py`, and a crash on non-UTF-8 source files — all fixed
  and re-verified PASS. scope-auditor also FAILed round 1 (test only covered
  1 of 5 required fields) — fixed. Full detail in `.claude/task/review.md`.

**Owner decisions still open, carried in contract.md**: whether to eventually
rename this repo to `claude-project-kit` (deferred — `dbt-agent-kit`'s
`sync-base.sh` hardcodes this repo's GitHub URL, would need updating too);
whether to rename the existing `.claude/agents/cto-reviewer.md` itself (deferred
— this library only adds new, function-named modules so far).

**Next**: merge MR !3, then start Phase 2 (routing composition engine —
`scripts/compose_routing.py`, consumes Phase 1's `applies_when` tags) as its own
task contract. Do NOT jump ahead without a fresh contract.md — each phase is
independently reviewed per the working agreement.

**Minor cleanup noticed but NOT done (out of scope both times it came up)**:
`.claude/hooks/__pycache__/*.pyc` files are tracked in git from before
`.gitignore` existed — harmless, but worth a small standalone cleanup
(`git rm -r --cached .claude/hooks/__pycache__`) sometime.

## Also this session (2026-09-05)

- Global `~/.claude/CLAUDE.md` created: plain-language communication rules
  (always explain a bare reference like "PR #55" in the same sentence; short
  answers by default) and token-saving habits (delegate broad search to
  subagents, don't re-read just-written files, read narrowly, pin cheaper models
  for mechanical reviewers). Applies to every project, not just this one.
- Evaluated 6 open-source "save tokens" tools from a LinkedIn post (caveman,
  claude-mem, serena, rtk, context-mode, jcodemunch) — verified real via web
  search, not fabricated, but decided against installing any of them (caveman
  trades response clarity for token count; claude-mem duplicates Claude Code's
  built-in memory; third-party plugins are exactly the "global thing breaks
  local" risk already flagged). Kept the underlying techniques as habits in the
  global CLAUDE.md instead.

## Earlier, unrelated to the above

GitLab CI migration (`.gitlab-ci.yml`) — fully done and merged, verified with a
real push-to-main pipeline. Not carrying forward as open work.

`football-data-pipeline`'s past auto-merge incident (a paused GitHub Actions
workflow, `pr-autopilot.yml`) is resolved in that repo already, by the owner —
not open work here. It directly informed Phase 5 of the claude-project-kit plan
(CI-provider automation audit), which is why it's referenced in the plan file.
