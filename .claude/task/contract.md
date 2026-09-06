# Task contract

objective: Phase 4 of the `claude-project-kit` plan — document the "promote to
  opus on guard-path diffs" model-routing convention (confirmed, per prior
  research, to be a procedural rule the orchestrator applies at spawn time in
  every precedent for it — never hook-enforced, since a `PreToolUse(Bash)`
  hook cannot see a Task-tool subagent spawn) as a real, dogfooded rule file
  in this repo, a reusable template for the library, and a parity test that
  fails if the documented guard-path list and `review_routing.json`'s actual
  cto-reviewer-routed paths ever silently drift apart.

scope_paths:
  - .claude/rules/guard-paths.md
  - templates/rules/guard-paths.md.tmpl
  - .claude/tests/test_routing_doc_parity.py
  - .claude/agents/cto-reviewer.md
  - .claude/task/contract.md
  - .claude/task/review.md

decisions_reserved:
  - No enforcement mechanism beyond documentation + parity test — reaffirms
    the Phase 3 contract's own decision on this exact question. Building a
    `PreToolUse(Task)` hook that inspects `subagent_type` and a guard-path-
    touched check to actually deny/rewrite a requested model would be a
    genuinely new, more invasive mechanism; out of scope here, flagged as a
    future option only if the convention is observed leaking in practice.
  - `scope-auditor` is explicitly EXEMPTED from the opus escalation (stays
    `haiku` always) — it's the one reviewer required on every commit
    regardless of path, so escalating it on guard-path touches would
    multiply cost for the highest-frequency reviewer. Matches the precedent
    this convention is drawn from.

done_when:
  - `.claude/rules/guard-paths.md` exists: states the convention in plain
    terms (when a diff touches a guard path, spawn `cto-reviewer` — or its
    future function-named equivalents — with `model: opus` instead of its
    frontmatter default, `scope-auditor` exempted), and lists the actual
    guard paths as a plain markdown list under a `## Guard paths` heading
    (not YAML frontmatter — this repo has no YAML-parsing dependency, and a
    flat list is simplest to keep in parity-tested sync).
  - `templates/rules/guard-paths.md.tmpl` exists: the same structure,
    generalized with placeholders for future projects (per-project reviewer
    names and guard paths aren't known until Phase 6's interview exists) —
    inert content, not wired into any generation logic yet.
  - `.claude/agents/cto-reviewer.md` gets a short cross-reference callout to
    `.claude/rules/guard-paths.md` (not a duplicated list — single source of
    truth stays in the rule file, since two copies of the same list is
    exactly the drift this phase exists to prevent).
  - `.claude/tests/test_routing_doc_parity.py` parses `.claude/rules/
    guard-paths.md`'s `## Guard paths` list and `.claude/review_routing.json`'s
    paths routed to `cto-reviewer`, and asserts they're the same set —
    failing with a message naming exactly which patterns are only on one
    side. Proven against a deliberately-diverged fixture first (a pin that
    never fired isn't a pin).
  - All existing `.claude/tests/test_*.py` still pass; JSON configs still
    parse; hooks still byte-compile; shell scripts still lint.
  - scope-auditor + cto-reviewer PASS on the staged diff.

amendments:
  - 2026-09-06 — contract created for Phase 4 of the approved plan
    (`C:\Users\Rami\.claude\plans\happy-stargazing-mccarthy.md`). Built on
    updated `main` (Phase 3 merged).
  - 2026-09-06 — cto-reviewer FAIL, two real defects, both fixed:
    1. `scripts/bootstrap.sh` (not in scope_paths) has no `refresh_dir
       ".claude/rules"` — `.claude/rules/` isn't distributed to any repo
       built from this kit yet (that's Phase 7's job). The parity test
       assumed the file it reads always exists; in a consumer repo it
       doesn't, `open()` raises `FileNotFoundError`, that's not an
       `AssertionError`, so it escapes the file's own `__main__` handler —
       a traceback and red CI in every downstream repo, `dbt-agent-kit`
       included. FIXED: `test_guard_paths_doc_matches_routing` now checks
       `os.path.isfile` first and skips cleanly when the file is absent,
       same pattern this repo's other tests already use for an unavailable
       precondition (e.g. `if not _GIT: print("skip ..."); return`).
       Flagged for whichever future phase actually wires `.claude/rules/`
       distribution: a consumer that customises its own
       `review_routing.json` (which `bootstrap.sh`'s own `keep_file`
       deliberately preserves) will diverge from a blindly-copied
       `guard-paths.md` — don't ship this file as a blind copy the way
       `.claude/tests/` is; it needs the same "generate/customize" treatment
       `review_routing.json` itself already gets.
    2. The two "detects drift" tests asserted on hand-written set literals
       (`routed - documented == {...}`) instead of calling `_parity_diff`
       (or any function from the module), so they stayed green through any
       break of the real comparison — the contract's own done_when required
       proof "against a deliberately-diverged fixture first," which these
       didn't provide. FIXED: extracted `_parity_diff(rules_text, routing)`
       as the one comparison function every test (including the real check
       against this repo's own files) now goes through; the two drift tests
       feed it fabricated fixture text/routing and assert on its actual
       return value, plus a new third test confirming matching fixtures
       produce no diff (the direction that was previously simply assumed).
