# Task contract

objective: Rename this repo (GitLab) from claude-guardrails to claude-project-kit, and retire
`.claude/agents/cto-reviewer.md` in favor of this kit's own copy of the module-library's
`platform-reviewer.md`, updating every in-repo reference to both.

scope_paths:
  - .claude/active_work.md
  - .claude/task/contract.md
  - .claude/agents/cto-reviewer.md (deleted)
  - .claude/agents/platform-reviewer.md (added)
  - .claude/hooks/commit_review_gate.py
  - .claude/hooks/completion_gate.py
  - .claude/hooks/preflight.sh
  - .claude/review_routing.json
  - .claude/rules/guard-paths.md
  - .claude/skills/setup-project/SKILL.md
  - .claude/tests/test_bootstrap.py
  - .claude/tests/test_commit_review_gate.py
  - .claude/tests/test_completion_gate.py
  - .claude/tests/test_generate_project_setup.py
  - .claude/tests/test_preview_project_setup.py
  - .claude/tests/test_routing_doc_parity.py
  - CLAUDE.md
  - README.md
  - docs/decisions/custom-review-gate-vs-code-review-skill.md
  - docs/project-kit-design.md
  - scripts/bootstrap.sh
  - scripts/generate_project_setup.py
  - scripts/preview_project_setup.py
  - templates/ci-audit/ci_automation_audit.py
  - templates/reviewers/README.md
  - templates/reviewers/platform-reviewer.md
  - templates/reviewers/routing/README.md
  - templates/rules/guard-paths.md.tmpl
  - templates/starter-README.md.tmpl

decisions_reserved:
  - Whether to rename the repo at all, and to what name — owner explicitly chose
    "claude-project-kit" via AskUserQuestion.
  - Whether/how to resolve the cto-reviewer.md / platform-reviewer.md naming collision
    discovered mid-task (a straight rename would have collided with the already-existing
    module-library file of the same name) — owner chose: delete cto-reviewer.md, use the
    module's platform-reviewer.md directly, rather than picking a different non-colliding
    name or leaving cto-reviewer.md as-is.
  - dbt-agent-kit's scripts/sync-base.sh fix — explicitly out of scope for this task
    (cross-repo), flagged as a separate follow-up task (task_5ad700d5) instead.

done_when:
  - Every in-repo reference to the old repo name (claude-guardrails) is updated, except
    genuinely historical citations (the suspended GitHub remote's own name, which was never
    renamed; football-data-pipeline's own historical incident record).
  - review_routing.json, guard-paths.md, and every test/doc referencing cto-reviewer route
    to platform-reviewer instead, with no functional reference to the retired name left
    except the deliberately-kept `_LEGACY_REVIEWER_FILE` cleanup path (for projects
    bootstrapped before this rename, whose stale copy bootstrap.sh's own cp -R never prunes).
  - Full test suite (.claude/tests/) passes.
  - .claude/active_work.md reflects only the current, completed state — no item marked both
    done and still-open.

amendments:
  - 2026-09-17 — contract written retroactively, after implementation and after platform-reviewer's
    first review pass (opus) correctly FAILed on exactly this gap: no contract existed to
    authorize scripts/bootstrap.sh, .claude/hooks/*, .claude/tests/*, and templates/* being
    touched, since the on-disk contract.md was still the already-merged sandboxing-ADR task.
    Owner authority for the underlying work itself: AskUserQuestion answers this session
    ("Rename to claude-project-kit", "Rename to platform-reviewer.md" superseded mid-task by
    "Delete cto-reviewer.md, use the module directly" after the collision was escalated).
  - 2026-09-17 — same review pass also found: .claude/active_work.md listed both retired
    items as still "deferred" under Open owner decisions, contradicting its own "Where things
    stand" section (fixed); .claude/hooks/preflight.sh:7 still said "claude-guardrails" in a
    user-facing SessionStart message (fixed).
  - 2026-09-17 — platform-reviewer's SECOND pass (re-reviewing after the above) FAILed again:
    scope_paths omitted .claude/task/contract.md itself, which the diff modifies (added);
    .claude/tests/test_completion_gate.py:266 and .claude/tests/test_routing_doc_parity.py
    (two comment blocks) still stated "cto-reviewer" as this kit's own CURRENT name, not
    caught by the first pass's grep-driven sweep since these were prose claims embedded in
    comments about a still-true general mechanism, not simple substring mentions (fixed —
    reworded to past-tense/generic framing that doesn't assert a currently-false distinction);
    active_work.md's "Where things stand" claimed this work as merged/done while still on an
    unreviewed branch, with no branch or MR reference — the same defect class as its own
    round-3-equivalent finding here (fixed — reframed as in-flight, branch named explicitly).
