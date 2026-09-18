# Review

diff_sha256: 845cf557118635357834b30a65643a02b6fe8f16fe52be685695b34477289b96

rounds: 4

CPO ANSWER: round 3 (this repo's cap) FAILed on two validation gaps in
`_prepare_ci_audit_hook_settings` (non-object JSON top level → `AttributeError`; non-UTF-8 file →
`UnicodeDecodeError` escaping the `except`). Owner authorised round 4 via `AskUserQuestion`
("Yes, fix and run round 4") — see `.claude/task/contract.md`'s amendments for every round's
findings and fixes. Round 4 (both reviewers) is clean.

## scope-auditor
VERDICT: PASS (round 4, final)
risks_checked:
- Scope: all 10 changed files inside `contract.md`'s `scope_paths`; nothing outside the branch's
  objective (the worktree-safety ADR and headless-mode audit are explicitly NOT on this branch).
- `decisions_reserved` covers every owner-level choice the diff embodies: wiring the CI-audit hook
  at all, the programmatic `settings.json` splice, `templates/*` as a guard path, the drift fix.
  The past-the-cap round is backed by a recorded CPO ANSWER.
- User-visible wording (`ci_audit_hook_reason` strings, `ci_provider_note`, SKILL.md prompt,
  refusal remedy text) traces to the contract's `done_when` "describe the new behavior accurately",
  not to silent product decisions. `ensure_ascii=False` is a correctness fix under "never corrupt
  the highest-blast-radius file", not a new mechanism.
- `.claude/active_work.md` describes the state as of the commit; the three owner decisions this
  branch resolves are removed and the one new open call (generated-project routing not covering
  `.claude/settings.json`) is recorded as open, not acted on.

## platform-reviewer
VERDICT: PASS (round 4, final — opus, guard paths touched: scripts/*, .claude/tests/*,
templates/*, .claude/review_routing.json, .claude/skills/*)
risks_checked:
- Round-3 fix completeness: enumerated the full exception surface of `open(encoding="utf-8")` +
  `json.load` — every realistic operator artefact (missing file, permission, non-JSON, UTF-8 BOM,
  UTF-16 BOM, non-object top level) lands in `GenerationRefused` with the remedy text. Only
  `RecursionError` on adversarially nested JSON escapes, with nothing written — flagged
  non-blocking for the owner.
- `except ValueError` breadth: the `try` body is two statements with no callables of ours, so it
  can't mask a logic bug; `{e!r}` and `from e` preserve the cause.
- Every new test leg reaches the clause it claims (`_require_bootstrapped` is `isfile`-only; no
  other `settings.json` read precedes the prep call); `_repo_snapshot` reads bytes so the
  write-nothing assertion survives a UTF-16 file. Each fix verified to fail on revert.
- Fail-open of the wired hook verified from the template's code, not its docstring; `generate()`
  fails closed (every refusal precedes the first write).
- Re-run/interruption: `settings.json` via `_write_atomic`; idempotency asserts exactly one marker
  entry after two runs; `bootstrap.sh`'s `refresh_dir` is a non-deleting merge so a later
  re-bootstrap doesn't orphan the entry.
- Parity test is bidirectional, so the guard-path additions had to land in both files.
- No new dependency, no credential/CI-permission change. Recurring cost (one hook process per
  session in generated projects with a CI provider) is owner-decided in the contract.

Full test suite: 237 passed, 0 failed (`python -m pytest .claude/tests/ -q`, Windows).
