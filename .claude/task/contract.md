# Task contract

objective: Phase 1 of turning this kit into a Claude Code plugin named `claude-project-kit` —
make the repo loadable as a plugin (`--plugin-dir`, later a marketplace) without moving or
changing what any hook, reviewer, or skill does, and make every hook a no-op in a project that
hasn't been set up (opt-in marker), since plugin hooks otherwise run in every project the
plugin is enabled in.

tracking_issue: (none — this repo doesn't use an issue tracker for its own work yet;
`.claude/active_work.md` is the handover mechanism instead)

scope_paths:
  - .claude/task/contract.md
  - .claude/active_work.md
  - .claude-plugin/plugin.json
  - .claude/hooks/hooks.json
  - .claude/hooks/_command_utils.py
  - .claude/hooks/*.py
  - .claude/hooks/preflight.sh
  - .claude/tests/test_plugin_manifest.py
  - .claude/tests/test_hooks_import.py
  - .claude/tests/test_command_utils.py
  - .claude/tests/test_completion_gate.py
  - docs/project-kit-design.md

decisions_reserved:
  - Plugin over bootstrap-copy, and the plugin name `claude-project-kit` — owner decided via
    AskUserQuestion after the website-project test showed `/setup-project` can't run from a
    project folder ("WRONG" to a path-stamp workaround; "Plugin (C)"; name
    "claude-project-kit").
  - Hooks fire only in opted-in projects — owner chose "Only set-up projects". The marker is the
    project's `.claude/review_routing.json` (the file the gate reads anyway; every project
    bootstrapped or generated so far has one). Changing the marker later is an owner call.
  - Layout: components stay under `.claude/` and the manifest declares those paths — chosen by
    the builder as the smallest phase-1 change (the reference documents custom component
    paths). Physically moving to top-level `hooks/`, `agents/`, `skills/` is NOT decided; if
    the marketplace-root source in phase 3 needs it, that's phase 3's call.
  - What `/setup-project` does from a target folder, `bootstrap.sh`'s retirement, README
    rewrite — phase 2. Marketplace, install path, migration of old-style projects, the
    kit-governs-itself-while-also-a-plugin double-firing question, headless re-check — phase 3.
  - No hook's decision logic changes. The only behavioural change to any hook is the opt-in
    short-circuit; a hook that previously would have denied still denies in an opted-in project.

done_when:
  - `.claude-plugin/plugin.json` exists (`name: claude-project-kit`), declares component paths
    under `./.claude/`, and Claude Code accepts it: `claude --plugin-dir <kit> -p ...` in a
    throwaway repo lists the plugin in `system/init`.
  - `.claude/hooks/hooks.json` wires the same hooks as `.claude/settings.json`, via
    `${CLAUDE_PLUGIN_ROOT}/.claude/hooks/...`; a parity test fails if the two lists drift.
  - Every hook (Python and `preflight.sh`) exits 0 with no output when the project has no
    `.claude/review_routing.json`; a test drives each hook that way with an event that would
    otherwise fire. In an opted-in project every existing hook test still passes unchanged.
  - Live, in a throwaway repo with the plugin loaded via `--plugin-dir`: a `git commit` is NOT
    gated before the marker exists and IS denied (REVIEW GATE) after it — recorded with the
    exact commands and output in the ADR-to-come's notes (`docs/project-kit-design.md` gets one
    paragraph now; the full ADR is phase 3's).
  - This kit's own gate keeps working on this branch (the commit that lands this passes
    through it) and the full suite is green.

amendments:
  - 2026-09-18 — round 1: scope-auditor PASSed; platform-reviewer (opus) FAILed on seven findings,
    all real, all fixed:
    1. `test_plugin_manifest.py` crashed on the on-disk manifest — written when `agents`/`commands`
       were directory strings, then the manifest was switched to file lists (Claude Code rejects a
       directory) and the test never re-run. That was the "1 failed" in the full suite the
       builder couldn't locate. Fixed: handles str-or-list, and now also asserts the lists cover
       every `.md` actually present (a new reviewer must be declared or it silently doesn't ship).
    2. The "silent without marker" test provoked only 4 of 10 hooks; the other six were silent
       for unrelated reasons (nothing staged, no push, no handover file, python on PATH). Fixed:
       the fixture stages a fake AWS key and carries `active_work.md`; `preflight` runs with a
       PATH lacking python; each hook has a named provocation. Verified by reverting
       `secret_scan`'s check: the silent test fails on exactly that hook. `commit_review_gate` and
       `completion_gate` are documented as undetectable by construction — the routing file IS
       their input and `_gate()` was already fail-open without it (pre-existing).
    3. `session_id` keyed on `os.getpid()` — PIDs recycle, markers never removed. Fixed: `uuid4`
       per run + marker cleanup, the pattern `test_completion_gate.py` already uses.
    4. `bootstrap.sh` copies `.claude/tests/` into targets, where the manifest doesn't exist —
       the new file would raise. Fixed: `_require_kit()` raises `SkipTest`, per
       `test_bootstrap.py`'s own rule.
    5. `_flatten` parity ignored `type`/`shell`/`statusMessage`/interpreter token. Fixed: whole
       `hooks` block equality after text-substituting `${CLAUDE_PLUGIN_ROOT}`.
    6. Design doc said "verified live" with no commands or output. Fixed: table with the exact
       invocation, the rejected-directory attempt, and each observed result.
    7. `import tempfile` after the `sys.path` insert in `handover_plan_gate.py`. Fixed.
    Also from the review: `test_completion_gate.py::test_fails_open_on_non_dict_event` pointed
    `CLAUDE_PROJECT_DIR` at a dir without the marker, so after this diff it returned at the
    opt-in check before reaching the non-dict path it exists to test. Fixed (temp dir now carries
    the marker) — `test_completion_gate.py` added to `scope_paths` for that one reason.
    Owner-level flags from the review, recorded in `active_work.md`, not acted on: per-Bash-call
    process cost of loading hooks everywhere; whether `.claude-plugin/*` should be a guard path.
  - 2026-09-18 — round 2: platform-reviewer (opus) FAILed on six findings, scope-auditor FAILed on
    one. All real, all fixed:
    1. (platform) The test fixture's fake AWS key was a contiguous `AKIA...` literal — this kit's
       own `secret_scan.py` would have denied the commit of this very branch. Fixed: built by
       concatenation, per `test_secret_scan.py`'s own precedent. Introduced by round 1's fix.
    2. (platform) `commit_review_gate` was wrongly declared undetectable: with no `main`/`master`
       ref it emits a no-base-ref NOTE even without routing. Fixed: fixture branch is `work`, the
       gate joins the provocations; verified by reverting its check — silent test fails on it.
       Only `completion_gate` remains undetectable by construction.
    3. (platform) preflight's "no python" provocation used `dirname(bash)` as PATH — true here and
       on GitLab's image, false on GitHub's ubuntu runner. Fixed: PATH is an empty dir in the
       fixture.
    4. (platform) `_require_kit()` (manifest present) also gated the two opt-in tests, so deleting
       the manifest would silently skip all opt-in coverage. Fixed: opt-in tests gate on bash+git
       only (`_require_tools()`).
    5. (platform) `mkdtemp` + trailing `rmtree` leaks on assertion failure. Fixed:
       `TemporaryDirectory`.
    6. (platform) `git` absence raised instead of skipping. Fixed (in `_require_tools`).
    7. (scope) Design-doc table listed `claude-project-kit:setup-project` as a "command" — it's
       the existing SKILL, which Claude Code also lists as a slash command; the manifest declares
       two commands. The observation was real; the label was wrong. Fixed in the doc and the
       handover (which now says the skill already ships under that name but still refuses
       outside a kit checkout until phase 2).
