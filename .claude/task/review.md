# Review

diff_sha256: dcfa42e9a9243c4942f69961ee747caaf3f864823441879bfeb9eb286bb30cc1

## scope-auditor
VERDICT: PASS
risks_checked:
- Complete field validation coverage — `test_refuses_each_missing_required_field()`
  iterates over all five required fields (name, description, tools, model,
  applies_when), removes each individually from a real fixture, and asserts
  `PromotionRefused`, the field name in the message, and no file written.
- Error message precision — each refusal includes the missing field name as a
  single-item list, so the substring assertion in the test matches exactly the
  field that was actually removed.
- Scope and decisions_reserved — all changes inside scope_paths; script remains
  manual-only (no hook/CI/settings.json wiring); no file outside scope touched.

## cto-reviewer
VERDICT: PASS
risks_checked:
- Path traversal via frontmatter `name:` (prior FAIL) — `_SAFE_NAME` is an anchored
  allowlist regex checked inside `validate_source()`, which runs before `dest_path`
  construction and `shutil.copyfile` in both the default and `--force` branches.
  Traced against all 4 fixture payloads plus additional hand-traced variants
  (backslash, embedded dots, uppercase) — all rejected.
- Regex drift between promote_reviewer.py and lint_reviewer_name.py (prior FAIL) —
  confirmed promote_reviewer.py imports and reuses the actual `_FRONTMATTER_NAME`
  compiled regex object from lint_reviewer_name.py (not a re-typed copy of the
  pattern), so the two scripts share one source of truth for what "the name" is.
- Non-UTF-8 source crash (prior FAIL) — the file read is wrapped in
  `try/except UnicodeDecodeError` → `PromotionRefused`, while `FileNotFoundError`
  still propagates untouched to its own handler in `main()`.
- Guard integrity / cost — no CI or routing edit needed or made; `review_routing.json`
  already routes `scripts/*`/`.claude/tests/*` to `cto-reviewer`; both CI files
  already glob `test_*.py`.

Prior round FAILed on three real defects: a path-traversal write vector via the
frontmatter `name:` field, a regex-parsing inconsistency between this script and
lint_reviewer_name.py that could let the two disagree on what "the name" is, and an
unhandled crash on non-UTF-8 source files. All three fixed and independently
re-verified above by reading the actual code, not the fix description.
