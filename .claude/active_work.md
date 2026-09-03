# Active work

## GitLab CI migration — done, pending merge

Branch: `feat/gitlab-ci-migration`. Contract: `.claude/task/contract.md`. Review:
`.claude/task/review.md` (scope-auditor + cto-reviewer, both PASS on the final diff).

- `.gitlab-ci.yml` added — 1:1 port of `.github/workflows/ci.yml` (the repo's only
  workflow). Hermetic, no cloud auth, no deploy, no schedule.
- GitLab project created: https://gitlab.com/rami.al-fahham/claude-guardrails (public).
  `main` pushed, set as default branch, protected (Maintainer push/merge, no
  force-push). Feature branch unprotected.
- MR open: https://gitlab.com/rami.al-fahham/claude-guardrails/-/merge_requests/1 —
  verified with a real MR pipeline run (job log read, all 4 steps confirmed executed,
  not just green).
- `.github/workflows/ci.yml` deliberately kept in place (owner's call, 2026-09-03).

Still open: merging `!1` (owner's action). Once merged, worth confirming a genuine
push-to-`main` pipeline fires correctly now that `main` is the real default (the one
push-triggered pipeline that ran so far happened while the feature branch was still
mistakenly the default, before branch protection was fixed).

## Note from this session — unrelated to the above

Mid-task, `glab`'s machine-wide GitLab credential (OS keyring, one token per host) was
found switched from the owner's personal account to a project access token / bot
account (`project_85168767_bot_...`), likely originating from project id 85168767
(probably `football-data-pipeline`). This blocked `glab repo create` until the owner
re-authenticated outside this session. Separately, that other repo's `git log --merges`
shows frequent automated-looking merges into `main` (GitLab-native merge-commit format,
several per day, many `chore/handover-after-*`) — the owner is investigating in that
session, not this one. No merge/push/commit happened in claude-guardrails while blocked.
