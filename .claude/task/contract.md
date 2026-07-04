# Task contract

objective: Broaden `.gitattributes` to `* text=auto eol=lf` so the whole working
  tree is LF on Windows too — matching the dbt-agent-kit consumer and removing
  CRLF working-tree noise, while keeping shell scripts runnable on Linux/macOS.

scope_paths:
  - .gitattributes

decisions_reserved:
  - Whether to also untrack the committed `.claude/hooks/__pycache__/*.pyc` and add
    a `.gitignore` (adjacent tree-hygiene finding) — deferred to a separate change
    unless the owner folds it in.
  - Comment wording in `.gitattributes` — RESOLVED: owner approved keeping the
    committed 4-line comment as written (2026-07-04). A config-file code comment is
    developer-internal, not the user-visible product wording §6 governs, so it is
    not treated as an owner-reserved decision going forward.

done_when:
  - `git add --renormalize .` produces no unexpected content diffs (line-ending
    normalization only; the index is already LF so this is expected to be a no-op).
  - `.claude/tests/test_*.py` pass; hooks byte-compile; `settings.json` and
    `review_routing.json` parse as JSON.
  - scope-auditor PASS on the staged diff; CI green.

amendments:
  - 2026-07-04 — contract created for PR A (gitattributes LF normalization).
  - 2026-07-04 — owner approved the `.gitattributes` comment wording as written and
    agreed config-file comments are not owner-reserved; scope-auditor FAIL on that
    point resolved.
