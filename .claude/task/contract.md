# Task contract

objective: Fix two portability defects found battle-testing `bootstrap.sh` against a
  non-dbt (R/Quarto) repo, so a freshly bootstrapped repo is green and correctly
  branded out of the box: (1) the copied `test_bootstrap.py` fails in consumer repos
  because it needs the kit-only `scripts/bootstrap.sh`; (2) `preflight.sh` hardcodes
  "dbt-agent-kit" branding in its missing-Python warning.

scope_paths:
  - .claude/tests/test_bootstrap.py
  - .claude/hooks/preflight.sh

decisions_reserved:
  - Branding string in preflight.sh (user-visible warning text) — RESOLVED: owner
    approved "claude-guardrails:" via "go ahead as recommended" on the battle-test
    report, which named that exact string (2026-07-04).
  - Findings #3–#5 from the battle-test (Python-required caveat, dbt-flavored task
    template examples, branch_discipline CLAUDE_PROJECT_DIR scoping) are left as
    notes, NOT fixed in this task.

done_when:
  - In the KIT: `.claude/tests/test_*.py` all pass (test_bootstrap still runs here,
    since scripts/bootstrap.sh is present).
  - In a freshly BOOTSTRAPPED repo: the copied `.claude/tests/` suite is green
    (test_bootstrap self-skips when scripts/bootstrap.sh is absent), verified by
    re-running the battle-test.
  - preflight.sh emits "claude-guardrails:" (not "dbt-agent-kit:").
  - Hooks byte-compile; JSON parses. scope-auditor + cto-reviewer PASS; CI green.

amendments:
  - 2026-07-04 — contract created for PR B (bootstrap non-dbt portability fixes).
  - 2026-07-04 — recorded owner approval of the "claude-guardrails:" branding string
    (resolves scope-auditor ESCALATE).
  - 2026-07-04 — cto-reviewer FAIL addressed: test_bootstrap now raises
    `unittest.SkipTest` (a true skip pytest reports as skipped) instead of
    print+return, which had reported skips as false passes.
