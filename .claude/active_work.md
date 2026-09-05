# Active work

## `claude-project-kit` — Phase 1 done, pending merge

Full plan: `C:\Users\Rami\.claude\plans\happy-stargazing-mccarthy.md` (approved
2026-09-03). 7 phases total, one task contract each. This session shipped Phase 1
only.

**Phase 1 — reviewer module library + naming lint**: MERGE-READY, not yet merged.
- Branch: `feat/reviewer-module-library`. MR:
  https://gitlab.com/rami.al-fahham/claude-guardrails/-/merge_requests/2 — MR
  pipeline green, job log confirms the new test actually ran (not just green).
- Added `templates/reviewers/{platform,security,data-engineer,analytics-engineer,
  frontend}-reviewer.md` + `_skeleton.md` fallback + `README.md`, each tagged
  `applies_when` for later phases to consume.
- Added `scripts/lint_reviewer_name.py` — rejects corporate-title reviewer names
  (cto/vp/director/...) as code, checked against BOTH filename and frontmatter
  `name:` (a mismatch between them is itself flagged).
- Added `.gitignore` (repo had none; caught mid-task when byte-compiling staged a
  stray `.pyc`).
- Review cycle: cto-reviewer FAILed round 1 on three real bugs (whitespace-bypass
  in the lint tokenizer, filename/frontmatter mismatch blind spot, a test that
  didn't test the path it claimed to) — all fixed and re-verified PASS. Full
  detail in `.claude/task/review.md`.
- **Owner decisions still open, carried in contract.md**: whether to eventually
  rename this repo to `claude-project-kit` (deferred — `dbt-agent-kit`'s
  `sync-base.sh` hardcodes this repo's GitHub URL, would need updating too);
  whether to rename the existing `.claude/agents/cto-reviewer.md` itself (deferred
  to a dedicated pass — this phase only added new, function-named modules).

**Next**: merge MR !2, then start Phase 2 (routing composition engine —
`scripts/compose_routing.py`, consumes Phase 1's `applies_when` tags) as its own
task contract. Do NOT jump ahead to Phase 2 without a fresh contract.md — each
phase is independently reviewed per the working agreement.

## Also this session

- Global `~/.claude/CLAUDE.md` created: plain-language communication rules
  (always explain a bare reference like "PR #55" in the same sentence; short
  answers by default) and token-saving habits (delegate broad search to
  subagents, don't re-read just-written files, read narrowly, pin cheaper models
  for mechanical reviewers). Applies to every project, not just this one.
- Evaluated 6 open-source "save tokens" tools from a LinkedIn post (caveman,
  claude-mem, serena, rtk, context-mode, jcodemunch) — verified real via web
  search, not fabricated, but decided against installing any of them: caveman
  trades away response clarity for token count (opposite of what was asked for);
  claude-mem duplicates Claude Code's built-in memory; installing third-party
  plugins is exactly the "global thing breaks something local" risk already
  flagged as a recurring problem. Kept the underlying techniques as habits
  instead (now in the global CLAUDE.md above).

## Earlier, unrelated to the above

GitLab CI migration (`.gitlab-ci.yml`) — fully done and merged, verified with a
real push-to-main pipeline. See git history (`ee86ee4`, `2a0b27c`) if detail is
ever needed; not carrying forward as open work.

`football-data-pipeline`'s past auto-merge incident (a paused GitHub Actions
workflow, `pr-autopilot.yml`) is resolved in that repo already, by the owner —
not open work here. It directly informed Phase 5 of the claude-project-kit plan
(CI-provider automation audit), which is why it's referenced in the plan file.
