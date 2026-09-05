# Task contract

objective: Phase 1b of the `claude-project-kit` plan — `scripts/promote_reviewer.py`,
  a deliberate, manual way to copy a drafted reviewer (one hand-refined on a real
  project, started from `templates/reviewers/_skeleton.md`) into the shared
  `templates/reviewers/` library, so it's reusable next time instead of redrafted
  from scratch. Closes the gap the owner raised: nothing currently feeds a proven
  draft back into the library.

scope_paths:
  - scripts/promote_reviewer.py
  - .claude/tests/test_promote_reviewer.py
  - .claude/task/contract.md
  - .claude/task/review.md

decisions_reserved:
  - This stays a manual, explicitly-invoked action, never automatic — owner's own
    framing ("promoting is a judgment call that a draft has proven itself", plan
    addendum 2026-09-05). This phase must not add any automatic-promotion path
    (e.g. triggered by review count or usage).

done_when:
  - `scripts/promote_reviewer.py SOURCE_MD` copies `SOURCE_MD` into
    `templates/reviewers/<name>.md`, where `<name>` comes from the file's own
    frontmatter `name:` field (not the source filename, which may live anywhere).
  - Refuses (non-zero exit, no file written) when: the target name/frontmatter
    fails `lint_reviewer_name.check_file`-equivalent checks (denylisted token, or
    filename/frontmatter mismatch once copied); the source frontmatter still has
    `draft: true`; the source frontmatter has no `applies_when` field; a file
    already exists at the destination (no silent overwrite — pass `--force` to
    replace deliberately).
  - Refuses to promote a source file missing the required frontmatter fields this
    library's existing modules all have (`name`, `description`, `tools`, `model`,
    `applies_when`) — incomplete promotion produces a module Phase 2 can't route
    correctly.
  - `.claude/tests/test_promote_reviewer.py` (plain-Python, matches this repo's
    `test_*.py` convention) proves every refusal path actually refuses — using
    real fixture files via `tempfile`, not just asserting on library internals —
    and proves a valid promotion actually writes the file with the right content.
  - All existing `.claude/tests/test_*.py` still pass; JSON configs still parse;
    hooks still byte-compile; shell scripts still lint.
  - scope-auditor + cto-reviewer PASS on the staged diff.

amendments:
  - 2026-09-05 — contract created for Phase 1b, a small addition to the approved
    plan (`C:\Users\Rami\.claude\plans\happy-stargazing-mccarthy.md`) raised by the
    owner immediately after Phase 1 shipped. Built on top of
    `feat/reviewer-module-library` (not yet merged) since it depends only on that
    phase's `lint_reviewer_name.py`; push/MR held until that branch merges to keep
    the diff clean.
