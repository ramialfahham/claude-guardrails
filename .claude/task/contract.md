# Task contract

objective: Wire `templates/ci-audit/ci_automation_audit.py` into generated projects when a CI
provider is given, add `templates/*` as a guard path, and fix `guard-paths.md`/`review_routing.json`
drift against `templates/reviewers/routing/platform-reviewer.routing.json`.

tracking_issue: (none — this repo doesn't use an issue tracker for its own work yet;
`.claude/active_work.md` is the handover mechanism instead)

scope_paths:
  - .claude/task/contract.md
  - .claude/active_work.md
  - .claude/review_routing.json
  - .claude/rules/guard-paths.md
  - scripts/generate_project_setup.py
  - scripts/preview_project_setup.py
  - .claude/tests/test_generate_project_setup.py
  - .claude/tests/test_preview_project_setup.py
  - .claude/skills/setup-project/SKILL.md
  - templates/ci-audit/ci_automation_audit.py
  - docs/project-kit-design.md

decisions_reserved:
  - Whether to build any of this at all — owner selected all 4 items via AskUserQuestion
    ("Two quick decisions", "Fix guard-paths.md drift", "Write the worktree-safety ADR",
    "Scope the headless-mode audit") when asked what to finish before moving to the
    website-project test.
  - Whether `ci_automation_audit.py` gets wired into generated projects — owner chose "Yes,
    wire it into generated projects" over leaving it a template-only resource.
  - Whether `templates/*` becomes a guard path — owner chose "Yes, add templates/* as a guard
    path" over leaving it at normal review weight.
  - How `generate()` should register the CI-audit hook in a target's `settings.json` — owner
    was explicitly shown the tradeoff (print-instructions-for-a-human vs. programmatic JSON
    splice, the latter touching the highest-blast-radius file in the kit) and chose the
    programmatic splice.

done_when:
  - `templates/*`, `.gitlab-ci.yml`, and `package*.json` are guard paths in both
    `review_routing.json` and `guard-paths.md`; `test_routing_doc_parity.py` passes.
  - `generate()` installs `ci_automation_audit.py` into a target's `.claude/hooks/` and
    idempotently wires a `SessionStart` entry into `settings.json` whenever
    `answers.ci_provider != "none"`, raising `GenerationRefused` (nothing written) on an
    unexpected `settings.json` shape rather than guessing at a structure to bolt onto —
    consistent with every other check in this file (validate-then-write, never
    write-then-maybe-refuse).
  - The installed hook is proven to actually run and emit its advisory note against a real
    workflow file, not just proven to exist on disk.
  - `SKILL.md`, `preview_project_setup.py`'s `ci_provider_note`, and
    `docs/project-kit-design.md` all describe the new behavior accurately.
  - Full test suite (`.claude/tests/`) passes.

amendments:
  - 2026-09-18 — platform-reviewer's first review pass (opus) FAILed on two findings, scope-auditor
    PASSed clean. Both fixed:
    1. `_prepare_ci_audit_hook_settings` has five refusal branches but only "no SessionStart key"
       was tested — reverting e.g. the `JSONDecodeError` clause would have surfaced as a raw
       traceback with nothing catching it. Fixed:
       `test_ci_audit_hook_refuses_every_malformed_settings_shape_writing_nothing` drives every
       branch, asserting the remedy text and a byte-identical target each time.
    2. `.claude/active_work.md` described the branch as "uncommitted, awaiting verdicts" with a
       stale test count — false from the moment it's committed. Fixed: now describes the state as
       of the commit (committed, MR open, awaiting owner merge), no live test count. Also removed
       the three "open owner decisions" this very branch resolves, which the prior session left
       listed.
    Also taken from the reviewer's non-blocking notes: the settings.json splice now serialises
    with `ensure_ascii=False` (project-owned file — an owner's non-ASCII `statusMessage` must not
    be rewritten to `\uXXXX` escapes as a side effect of one append), with a round-trip test. The
    reviewer's third note — a generated project's routing doesn't cover `.claude/settings.json`
    — is an owner call, recorded in `active_work.md`'s open decisions, not acted on here.
  - 2026-09-18 — platform-reviewer's second review pass (opus, round 2) FAILed on one leftover
    hole in round 1's own fix: the new test's "missing file" leg went through `generate()`, which
    `_require_bootstrapped` refuses BEFORE `_prepare_ci_audit_hook_settings` is ever called — so
    the `OSError` half of that function's first clause had no test that fails on revert, and the
    test's comment claimed coverage that wasn't there. Fixed: that leg now calls the function
    directly on a nonexistent path and asserts the remedy text; comment and this log corrected.
  - 2026-09-18 — platform-reviewer's third review pass (opus, round 3 — this repo's cap)
    confirmed round 2's fix, then FAILed on two new inputs that escape
    `_prepare_ci_audit_hook_settings` as raw tracebacks instead of `GenerationRefused` (nothing
    written either way — wrong exception type and no remedy text, never corruption): valid JSON
    whose top level isn't an object (`[]`, `null`) hit `data.get` with no `isinstance` guard, and
    a non-UTF-8 file (UTF-16 with BOM — PowerShell 5.1's `Out-File` default) raised
    `UnicodeDecodeError`, a `ValueError` that isn't a `JSONDecodeError`.

    **CPO ANSWER** (owner decision via `AskUserQuestion`, "Yes, fix and run round 4"): authorised
    one round past the cap for this. Fixed: `isinstance(data, dict)` guard before the `hooks`
    lookup; the `except` widened to `(OSError, ValueError)`; three cases added to
    `test_ci_audit_hook_refuses_every_malformed_settings_shape_writing_nothing` (top-level list,
    top-level null, UTF-16 bytes), each verified to fail with the fix reverted.
