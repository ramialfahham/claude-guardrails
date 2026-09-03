# Task contract

objective: Migrate the repo's CI from GitHub Actions to GitLab CI — add `.gitlab-ci.yml`
  as a 1:1 port of the repo's only workflow (`.github/workflows/ci.yml`), verified by a
  real pipeline run on a new GitLab project, with `.github/workflows/ci.yml` kept in place
  for now.

scope_paths:
  - .gitlab-ci.yml
  - .claude/task/contract.md
  - .claude/task/review.md

decisions_reserved:
  - Whether to also route `.gitlab-ci.yml` through `cto-reviewer` in
    `.claude/review_routing.json` — owner declined (2026-09-03); routing is unchanged,
    left out of scope_paths.
  - GitLab project visibility — owner chose public (2026-09-03), mirroring the guardrails
    repo being consumed by other repos.
  - Whether to remove `.github/workflows/ci.yml` once GitLab is verified — owner chose to
    keep it for now (2026-09-03).

done_when:
  - `.gitlab-ci.yml` exists, ported 1:1 from `.github/workflows/ci.yml` (same steps,
    same trigger scope: MR pipelines + push to the default branch only).
  - A real pipeline has been run on `gitlab.com/rami.al-fahham/claude-guardrails` (not
    just `glab ci lint` / YAML parsing) and the job log confirms every step actually
    executed (hook tests, JSON validation, byte-compile, shell lint) — not just that the
    pipeline went green.
  - Branch protection on the GitLab project's default branch is read back and reported,
    not assumed (project config that a push does not carry).
  - scope-auditor PASSES; CI (GitHub, still active) stays green.

amendments:
  - 2026-09-03 — contract created for the GitLab CI migration (`/migrate-to-gitlab` skill).
  - 2026-09-03 — mid-task: discovered `glab`'s machine-wide stored GitLab credential had
    been silently swapped to a project access token from an unrelated project
    (`football-data-pipeline`), blocking `glab repo create`. Not caused by this session;
    resolved by the owner outside this session. No merge/push/commit happened in this
    repo while blocked — verified via `git log`/`git status` before and after.
