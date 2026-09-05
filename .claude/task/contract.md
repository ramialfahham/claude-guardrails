# Task contract

objective: Phase 1 of the `claude-project-kit` plan — a reusable library of
  function-named reviewer agent templates (platform/security/data-engineer/
  analytics-engineer/frontend, plus a drafted-skeleton fallback), each tagged with
  when it applies, and a naming lint that rejects corporate-title reviewer names
  (CTO, VP, Director, …) as code, not just as a rule someone has to remember.

scope_paths:
  - templates/reviewers/**
  - scripts/lint_reviewer_name.py
  - .claude/tests/test_reviewer_naming_lint.py
  - .gitignore
  - .claude/task/contract.md
  - .claude/task/review.md

decisions_reserved:
  - Where `claude-project-kit` lives (inside this repo vs. a rename vs. a new repo) —
    owner deferred to "build inside, revisit rename later" (plan approved 2026-09-03).
  - The existing `.claude/agents/cto-reviewer.md` in this repo is NOT renamed in this
    phase — owner's call, deferred to a dedicated pass once `dbt-agent-kit`'s sync
    impact is scoped (plan approved 2026-09-03). This phase only adds new,
    function-named modules to the template library; it does not touch the existing
    shipped agent.
  - The `applies_when` tag vocabulary and module-selection logic are this phase's own
    design (agent-executable, not owner-reserved) — Phase 2 (routing composition)
    consumes it; no interview/generation logic exists yet, so nothing user-facing is
    decided here.

done_when:
  - `templates/reviewers/` contains: `_skeleton.md` (fallback, explicitly marked
    "draft — read before use"), `platform-reviewer.md`, `security-reviewer.md`,
    `data-engineer-reviewer.md` (ported from `dbt-agent-kit`), `analytics-engineer-reviewer.md`
    (ported from `dbt-agent-kit`), `frontend-reviewer.md`. Each has `name`,
    `description`, `tools: Read, Grep, Glob`, `model:`, and `applies_when:` frontmatter,
    and the same PASS/FAIL/ESCALATE output contract as this repo's existing
    `cto-reviewer.md`/`scope-auditor.md` (the commit gate parses this format).
  - `scripts/lint_reviewer_name.py` rejects any reviewer name containing a
    whole-word corporate title (cto, cpo, ceo, coo, cio, ciso, vp, evp, svp, director,
    head, chief, president, founder, owner, manager, lead, boss, exec, executive),
    matched on `-`/`_`-separated tokens (not substrings — "leaderboard-reviewer" must
    NOT be flagged), and accepts every shipped template plus `cto-reviewer` itself
    (documented as a known-existing exception, not silently exempted).
  - `.claude/tests/test_reviewer_naming_lint.py` (plain-Python, matches this repo's
    existing `test_*.py` convention — `python .claude/tests/test_reviewer_naming_lint.py`)
    proves the lint rejects the denylist, accepts real examples, and — proving the
    pin actually fires — fails against a deliberately reintroduced `cto-reviewer.md`-
    shaped NEW filename before the fix, per this repo's own "a pin that never fired
    isn't a pin" standard.
  - All existing `.claude/tests/test_*.py` still pass; JSON configs still parse;
    hooks still byte-compile.
  - scope-auditor + cto-reviewer PASS on the staged diff; local GitLab CI would still
    pass (no changes to files that pipeline touches, but confirm no accidental scope
    creep into `.claude/hooks/**` or `.gitlab-ci.yml`).

amendments:
  - 2026-09-03 — contract created for Phase 1 of the approved `claude-project-kit`
    plan (`C:\Users\Rami\.claude\plans\happy-stargazing-mccarthy.md`).
  - 2026-09-03 — added `.gitignore` (`__pycache__/`, `*.pyc`) to scope_paths: this
    repo had none, and byte-compiling `scripts/` while verifying this phase staged a
    stray `.pyc` — a minimal, zero-risk hygiene fix caused directly by this phase's
    own work, not scope creep.
