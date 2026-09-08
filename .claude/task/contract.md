# Task contract

objective: Phase 6b of the `claude-project-kit` plan — actual generation, wiring
  Phase 6a's dry-run preview into real writes. Given a bootstrapped target project
  and structured interview answers, generate the tailored governance files: copy
  the selected reviewer modules into the target's `.claude/agents/`, remove the
  bootstrap-default `cto-reviewer.md` (superseded by `platform-reviewer`), compose
  and write a real `.claude/review_routing.json`, render `.claude/rules/guard-paths.md`
  from the template, write a starter `README.md` if none exists, and extend the
  `setup-project` skill to run generation and a smoke test (a trivial commit proving
  the newly-generated hooks/routing actually block an unreviewed commit and allow a
  reviewed one). Full design: `C:\Users\Rami\.claude\plans\happy-stargazing-mccarthy.md`,
  "Phase 6b contract" section (approved via plan mode 2026-09-08).

scope_paths:
  - scripts/generate_project_setup.py
  - templates/starter-README.md.tmpl
  - .claude/skills/setup-project/SKILL.md
  - .claude/tests/test_generate_project_setup.py
  - .claude/tests/test_routing_doc_parity.py
  - .claude/task/contract.md
  - .claude/task/review.md

decisions_reserved:
  - **No confidential-scope-doc / summarization step.** Owner decision, 2026-09-08:
    the original Phase 6 idea (owner pastes project context, the kit summarizes it
    into `CLAUDE.md` with full detail kept in a separate `.claude/rules/` file) is
    cut entirely from this contract, not deferred. An automated setup step that
    invites pasting client names, internal system names, or business rules into a
    new repo is a bad default regardless of where the text ends up. No sibling repo
    (`dbt-agent-kit`, `football-data-pipeline`) has this pattern to build from —
    verified directly by reading both repos' setup skills and docs. Project-specific
    context is something the owner writes by hand later, deliberately.
  - **Remove the bootstrap-default `cto-reviewer.md` from a generated target.** Owner
    decision, 2026-09-08: `bootstrap.sh` ships `.claude/agents/cto-reviewer.md` into
    every project unconditionally today, regardless of stack — the exact "one
    overloaded generic reviewer" problem the module-library effort exists to fix.
    Since `platform-reviewer` (its direct successor) is `applies_when: [always]` and
    therefore always selected, generation removes the legacy file once tailored
    modules are installed. Deletes only this one known filename, never a glob.
  - Generation requires the target to already be bootstrapped
    (`scripts/bootstrap.sh <target>` already run) — refuses loudly
    (`GenerationRefused`, nothing written) if `target/.claude/settings.json` is
    missing, rather than generation also invoking bootstrap itself. Keeps the new
    script single-responsibility and matches the "validate everything, refuse
    loudly before writing" pattern already used by `promote_reviewer.py` and
    `compose_routing.py`.
  - **Smoke-test mechanism, corrected during implementation from the plan's
    original "make a real dummy commit" idea**: `commit_review_gate.py`'s
    `.claude/settings.json` wiring is a Claude-Code-session-level
    `PreToolUse(Bash)` hook — it only intercepts Bash TOOL calls made by a
    live agent session in ITS OWN project directory, never a plain
    `subprocess.run(["git", "commit"])` from arbitrary code, and never a
    different directory a Bash command happens to `cd`/`-C` into. A literal
    `git commit` run from this script would not actually be blocked by
    anything at the git layer regardless of the target's review state, so
    "make a real commit and see if it's blocked" cannot prove what it claims
    to prove. `commit_review_gate.py`'s own `_gate(root)` is a pure,
    directly-callable function — `.claude/tests/test_commit_review_gate.py`
    already verifies it this way. The smoke test instead runs the TARGET's
    own copied `commit_review_gate.py` as a real subprocess (not imported —
    a genuinely separate process against the genuinely generated file),
    feeding it the same PreToolUse JSON event shape the real hook wiring
    sends, with `CLAUDE_PROJECT_DIR` set to the target — the exact technique
    `test_commit_review_gate.py`'s `_run_main_in` helper already uses.
    Sequence: stage one trivial dummy file, confirm the simulated event is
    DENIED with no `review.md` present, write a minimal valid `review.md`
    (correct diff hash via the target's own `--diff-hash`, PASS verdicts for
    exactly the target's actually-required reviewers), confirm the simulated
    event is now ALLOWED, then unstage and delete the dummy file and
    `review.md` — no commit is ever made, so no `git reset --hard` or any
    other destructive git operation is needed. **Precondition, corrected
    during implementation**: not "the whole tree must be clean" (that would
    make the smoke test refuse immediately after every real `generate()`
    call, since generation itself necessarily leaves new files uncommitted
    — defeating the very chaining the skill relies on), but narrower and
    more precise — refuses only if either path this function itself writes
    (`.claude/_smoke_test_tmp`, `.claude/task/review.md`) already exists.
    That is the actual risk: this function only ever `git add`/`git reset`
    those two exact paths, never `-A`/`.`, so it cannot disturb any other
    pre-existing uncommitted change; a pre-existing real `review.md` is a
    plausible, meaningful file mid-workflow, and overwriting-then-deleting
    it would be the genuinely bad mistake to guard against.
  - Each individual file write in `generate()` is atomic (temp file + `os.replace`,
    reusing `compose_routing._write_atomic`), but the SEQUENCE of writes (copy
    modules -> remove legacy file -> write routing -> write guard-paths -> write
    README) is not one transaction. Recovery from a crash mid-sequence is
    "re-run `generate()`" (each step is independently idempotent), not a rollback
    mechanism — an explicit, deliberate scope limit, not an oversight.
  - `_GENERATION_BASE` (the base routing dict generation composes onto, distinct
    from `preview_project_setup._BASE_ROUTING`) adds `artifact_only` and
    `artifact_only_never` keys that the preview's base never needed. This closes a
    real gap `preview_project_setup.py`'s own docstring already flags: without
    these keys, every commit in a freshly generated project — including trivial
    task/handover file edits — would require full review, unlike this kit's own
    dogfooded config.
  - `guard-paths.md` is generated fresh per project from the same `routing_preview`
    data the routing file was just composed from (single source, no drift possible
    within one generation run). This does NOT fix the pre-existing, separately
    flagged drift between THIS kit's own hand-maintained `.claude/rules/guard-paths.md`
    and `templates/reviewers/routing/platform-reviewer.routing.json` — that stays a
    deferred, owner-level cleanup outside this contract's scope.

done_when:
  - `scripts/generate_project_setup.py`: `generate(target, answers) -> dict` plus a
    CLI (`--target`, `--dbt/--data-eng/--frontend/--sensitive-data/--ci-provider`,
    `--force` — added in round 1's fix 4, see amendments below; deliberately
    NOT wired into `.claude/skills/setup-project/SKILL.md`, which the skill
    is explicitly forbidden from passing itself, an owner-only escape hatch
    — no `--unmatched-stack`, unused by generation). Validates everything
    (target is bootstrapped; selected modules pass naming lint; target's
    routing/guard-paths aren't hand-customized unless `--force`) before any
    write; raises `GenerationRefused` and writes nothing on any check
    failure.
  - Reuses `scripts/preview_project_setup.py`'s `select_reviewer_modules`,
    `build_routing_preview`, `build_guard_paths_preview`, `build_naming_lint_report`
    directly (imported, not reimplemented) and `scripts/compose_routing.py`'s
    `compose()`/`_write_atomic()` directly.
  - Copies each selected module's `.md` into `target/.claude/agents/`; removes
    `target/.claude/agents/cto-reviewer.md` if present; writes
    `target/.claude/review_routing.json` (composed fresh, including
    `artifact_only`/`artifact_only_never`); writes `target/.claude/rules/guard-paths.md`
    (rendered from `templates/rules/guard-paths.md.tmpl`); writes `target/README.md`
    only if absent (never overwrites an existing one).
  - `templates/starter-README.md.tmpl`: short — project name (from target directory
    name), the selected module list, a link to `.claude/working-agreement.md`.
  - `.claude/skills/setup-project/SKILL.md` extended (not replaced) with new steps
    after the existing confirm loop: offer to bootstrap the target if not already;
    a second, explicit yes/no confirmation before any write; run generation and
    print its stdout verbatim; the smoke test (simulated block-then-allow via
    the target's own `commit_review_gate.py` run as a real subprocess, gated
    on a verified-clean target tree, no commit ever made); a closing summary.
    The old step 7 ("this doesn't exist yet") is replaced with what actually
    happened.
  - `.claude/tests/test_generate_project_setup.py`: real tempdir git repo,
    bootstrapped via a real `bootstrap.sh` run (not faked), then `generate()`
    exercised against it — dbt scenario and non-dbt scenario (same fixtures
    `test_preview_project_setup.py` uses); `cto-reviewer.md` removal; routing
    composed correctly including `artifact_only`/`artifact_only_never`;
    guard-paths.md content matches the composed routing (parity, not a hardcoded
    string); README written on a fresh target, not overwritten on an existing one;
    re-running `generate()` twice is a no-op diff on the second run (sha256
    content-hash snapshot, same technique as Phase 6a); a real subprocess
    smoke-test (target's own `commit_review_gate.py`, run as a real
    subprocess with a simulated PreToolUse event, matching
    `test_commit_review_gate.py`'s own `_run_main_in` technique) proving the
    generated routing/hooks deny an unreviewed change and allow a reviewed
    one, in that order, with no commit ever made, chained directly after a
    real `generate()` call in the same test (proving the precondition fix
    above actually allows that chaining, not just in isolation).
  - All existing `.claude/tests/test_*.py` still pass; JSON configs still parse;
    hooks still byte-compile.
  - Manual run of the extended skill against the same dbt/non-dbt scenarios into a
    real scratch directory (not this repo), confirming the generated `.claude/`
    passes this repo's own bootstrap-test pattern — recorded as a manual-check line
    in `.claude/task/review.md`, not merely asserted by unit tests.
  - Nothing under `templates/reviewers/`, `scripts/preview_project_setup.py`,
    `scripts/compose_routing.py`, `scripts/promote_reviewer.py`, or any existing
    reviewer `.md` is modified — additive only.
  - scope-auditor + cto-reviewer (opus — diff touches `scripts/*` and
    `.claude/tests/*`, both guard paths per `.claude/rules/guard-paths.md`) PASS on
    the staged diff.

amendments:
  - 2026-09-08 — round 4 review: cto-reviewer (opus) PASSed, and correctly
    scoped its own effort to what actually changed — verified independently
    (patch file diffs, file mtimes, and reading the actual current code)
    that nothing under `scripts/`/`.claude/tests/` changed since its round
    3 PASS, so it confirmed the round-3 fix was genuinely documentation-only
    rather than re-running a full adversarial audit against unchanged code.
    scope-auditor's substantive review (round-3 fix correctness, scope_paths
    compliance across all 6 files, both original owner decisions still
    holding) found nothing wrong; it ESCALATEd only on one specific,
    resolvable point — see the CPO ANSWER entry immediately below this one
    for that resolution. **Both reviewers' substantive findings: clean.**
    Re-verified: full local test suite passes; byte-compile clean.
  - 2026-09-08 — **CPO ANSWER, round 4 authorization.** Asked directly via
    `AskUserQuestion`: "Round 3 (this repo's cap) is done... This is round
    4 territory now. Continue reviewing, or stop here?" with options
    "Dispatch round 4" / "Stop reviewing, commit as-is." **The owner
    answered "Dispatch round 4."** Round 4 was dispatched on that basis.
    Round 4's own scope-auditor pass ESCALATEd (not FAILed) on this exact
    entry, correctly noting it has no access to the actual conversation and
    so cannot independently verify the quote is genuinely verbatim rather
    than paraphrased — a real structural limit of a reviewer subagent, not
    a defect in the entry. Resolved directly by the builder (who does have
    the real transcript, unlike the subagent): the `AskUserQuestion` call's
    actual `question` field was "Round 3 (this repo's cap) is done:
    scope-auditor found one small doc-sync gap (the --force flag wasn't
    listed in the contract's CLI flag documentation — fixed), cto-reviewer
    independently PASSed. This is round 4 territory now. Continue
    reviewing, or stop here?" and the tool result's recorded answer was the
    literal string "Dispatch round 4" — matching this entry exactly (the
    "..." above elides only the middle clause already given verbatim here,
    not anything material). No new owner input needed; this closes the
    ESCALATE.
  - 2026-09-08 — round 3 review: scope-auditor FAILed with 1 finding, fixed:
    round 1's `--force` CLI flag (a legitimate, needed addition, recorded
    narratively in round 1's own amendments entry) was never added to
    `done_when`'s exhaustive CLI-flag list itself — the exact same standard
    round 1's own scope-auditor finding applied to the (removed)
    `--skip-smoke-test` flag. FIXED: `done_when`'s CLI description now
    lists `--force` explicitly, with a note that `SKILL.md` is forbidden
    from passing it itself (already true of the code and SKILL.md's step
    10 text — this was a documentation-sync gap, not a behavior gap).
  - 2026-09-08 — round 2 review: scope-auditor PASSed (verified the
    `_generated_by`/force-protection mechanism and new `--force` flag added
    in round 1 are properly recorded, confirmed `--skip-smoke-test` is
    genuinely gone with its test removed, and re-confirmed the two original
    owner decisions still hold). cto-reviewer (opus) FAILed with 2 findings,
    both real, both fixed:
    1. **Writing guard-paths.md un-skips a test that then fails in every
       generated project.** `.claude/tests/test_routing_doc_parity.py` is
       shipped into every target unconditionally by `bootstrap.sh`'s
       `refresh_dir ".claude/tests"`, and skips itself only while
       `.claude/rules/guard-paths.md` is absent — which generation
       permanently ends. That test's `_routed_to_cto_reviewer` was
       hardcoded to the literal string `"cto-reviewer"`, but generation
       deliberately routes everything to `platform-reviewer` instead; and
       its `_parse_guard_paths_section` compared raw list-item text against
       `_render_guard_paths`'s backtick-wrapped output (`` - `scripts/*` ``
       vs `scripts/*`), which would never match even after fixing the
       reviewer name. This is the identical parity-check risk Phase 6a's
       own round 1 flagged in the abstract, now concretely triggered. FIXED
       by adding `.claude/tests/test_routing_doc_parity.py` to this
       contract's `scope_paths` (amendment to the original declaration —
       the fix genuinely requires touching a file outside it) and
       generalizing the test: `_parse_guard_paths_section` now strips a
       surrounding backtick pair from each list item (a no-op where there
       isn't one); the hardcoded reviewer name is replaced by
       `_escalate_reviewer_name()`, which reads the name from
       guard-paths.md's OWN "Convention" paragraph instead of assuming
       one — correct for both this kit's own phrasing ("...currently
       `cto-reviewer`...") and a generated project's
       ("...`platform-reviewer`..."). Existing tests updated to match (all
       fixture text now includes a real Convention sentence); new tests
       added: `test_escalate_reviewer_name_reads_from_the_doc_not_hardcoded`
       (both phrasings, plus the "no convention sentence" case returns
       `None` rather than crashing) and
       `test_parity_check_handles_backtick_wrapped_list_items`. In
       `.claude/tests/test_generate_project_setup.py`, a new
       `test_generated_targets_own_routing_doc_parity_test_actually_passes`
       runs the TARGET's own real copy of `test_routing_doc_parity.py` as a
       subprocess after `generate()` and asserts it exits 0 — the actual
       "generated `.claude/` passes this repo's own bootstrap-test pattern"
       proof this contract's `done_when` already claimed but that no test
       had actually performed until now.
    2. **The `_generated_by` marker proves authorship, not that content is
       unchanged — so it did not close round 1's finding 4 the way the
       amendments log claimed.** A `review_routing.json`/`guard-paths.md`
       hand-tuned AFTER generation (the exact edit `bootstrap.sh`'s own
       closing instructions tell the owner to make: "Review
       `.claude/review_routing.json` — tune which reviewers gate which
       paths") still carries the marker untouched, so a later `generate()`
       call (e.g. adding a stack tag) would silently discard the tuning —
       precisely the risk finding 4 was supposed to close, just narrowed to
       the bootstrap-to-first-generate window without anyone noticing the
       narrowing. FIXED: replaced presence-only marking with content-hash
       verification. `review_routing.json` gets a second field,
       `_generated_sha256` — a sha256 over the rest of the dict (sorted
       keys, so the hash is order-independent and reproducible from a
       fresh `json.load` regardless of on-disk formatting), computed and
       stamped by `generate()` right after composing, before the first
       write. `guard-paths.md`'s marker comment now embeds the same kind of
       hash over the body text that follows it
       (`<!-- generated by ...; sha256:...; safe to regenerate if
       unchanged -->`). `_routing_needs_force`/`_guard_paths_needs_force`
       now recompute the hash from the file's current content and compare
       against the recorded one: matches -> this tool's own unmodified
       output, safe (the crash-recovery idempotency guarantee this
       contract already makes, still honoured); marker present but hash
       mismatches -> hand-edited since generation, needs `--force`; no
       marker at all -> unchanged from round 1 (bootstrap default or
       genuinely hand-authored). New test,
       `test_generate_refuses_a_file_edited_after_generation_even_with_the_marker_still_present`,
       reproduces finding 2's exact scenario (edit `paths` through a
       JSON-preserving change that leaves `_generated_by` intact) and
       confirms it's now refused without `--force` and accepted with it.
    Re-verified end-to-end: full local test suite passes (20/20 in
    `test_generate_project_setup.py`, all 13 suites overall, including
    `.claude/tests/test_routing_doc_parity.py` itself both standalone and
    as exercised inside a real generated target); byte-compile clean.
  - 2026-09-08 — round 1 review: cto-reviewer (opus) FAILed with 6 findings
    (scope-auditor's single finding, on the same round, is recorded
    separately below). All 6 were real, none disputed, all fixed:
    1. **The actual correctness bug**: `smoke_test()` wrote review.md
       verdicts only for `routing["always"]`, but
       `commit_review_gate._required_reviewers` unions `always` with every
       reviewer named in a `paths` pattern matching the CUMULATIVE branch
       diff. Once a target commits its generated `.claude/` on a feature
       branch (bootstrap.sh's own instructed next step), that cumulative
       diff includes `.claude/hooks/*`/`.claude/agents/*`, which
       `platform-reviewer`'s own routing fragment matches — making it
       REQUIRED. The under-computed review.md made the "allow" simulation
       come back DENIED, reporting a correctly-working gate as broken.
       FIXED: `required` is now `always` UNION every reviewer named
       anywhere in `paths` — a safe superset (the gate only needs each
       REQUIRED reviewer to have a non-FAIL verdict; extra verdicts for
       reviewers that turn out not to be required are harmless) rather than
       reimplementing the gate's own pattern-matching logic a second time.
    2. The test fixture (`_bootstrapped_target`) never made any commit, so
       every smoke-test assertion ran against `commit_review_gate`'s
       no-base-ref FALLBACK path (well-tested elsewhere), never its real
       cumulative-diff-since-base-branch path — which is exactly why
       finding 1 was invisible to the suite. FIXED: the fixture now
       commits an initial baseline on `main` and branches to `feature`
       before bootstrapping (the realistic topology this repo's own
       working-agreement.md tells every project to use), and a new test,
       `test_smoke_test_correctly_requires_platform_reviewer_once_the_generated_setup_is_committed`,
       commits the generated `.claude/` on that feature branch before
       calling `smoke_test()` — reproducing finding 1's exact scenario.
    3. `GenerationRefused`'s own docstring promises "nothing is written
       before this can be raised," but `_render_guard_paths`/
       `_render_readme` (which can both raise it on template drift) were
       called AFTER the module copies, the legacy-file removal, and the
       routing write — so a drifted template left a half-generated target
       while reporting `REFUSED`. FIXED: `generate()` now computes and
       renders BOTH templates (and validates naming-lint) before any
       mutation; a new test,
       `test_generation_refusal_writes_nothing_even_when_a_template_has_drifted`,
       proves a template-drift refusal now leaves the target completely
       untouched.
    4. `review_routing.json`/`guard-paths.md` were unconditionally
       overwritten on every `generate()` call with no protection at all —
       inconsistent with `bootstrap.sh`'s own established convention
       (`keep_file`/`--force` for exactly this file) and a real risk: a
       team that hand-customized their routing after an earlier setup
       would have it silently discarded by a later re-run (e.g. toggling
       one stack tag). FIXED: added a `_generated_by` marker
       (`"claude-project-kit/generate_project_setup.py"`) to
       `_GENERATION_BASE`, which `compose_routing.compose()` passes through
       into every composed routing.json unchanged, and a matching HTML
       comment marker line prepended to every rendered guard-paths.md.
       `generate()` now refuses (`GenerationRefused`, `force=True` required
       to proceed) if an existing `review_routing.json` is neither this
       tool's own marked prior output NOR byte-identical to the untouched
       bootstrap default, or if an existing `guard-paths.md` lacks the
       marker. This deliberately does NOT block re-running `generate()`
       with different answers on a target this tool already generated
       (the marker makes that case recognizable as safe) — only genuine
       hand-customization is protected. New CLI `--force` flag added,
       mirroring `bootstrap.sh`'s own flag name/semantics exactly. Three
       new tests cover: refusal without `--force`, success with it, and
       that a PREVIOUSLY-generated (marker-tagged) target never needs
       `--force` to regenerate with new answers.
    5. Same finding as scope-auditor's (see below) — the undocumented
       `--skip-smoke-test` flag; fixed once, recorded once.
    6. A hard interruption between the smoke test's `git add` and its
       cleanup `finally` block could leave `.claude/_smoke_test_tmp`
       staged with no explanation of why the next run refuses. FIXED: the
       existing-file refusal message now names the exact recovery command
       (`git reset -- <path>` then remove the file), and the cleanup's own
       `git reset` failure is now surfaced as a stderr warning instead of
       silently swallowed (still never raised from the `finally`, so it
       can't mask whatever real exception is already propagating).
       `test_smoke_test_chains_directly_after_generate_with_no_commit_in_between`
       now also asserts the git INDEX is clean afterward (`git diff
       --cached --name-only` empty), not just the filesystem — closing the
       gap where a leaked `git add` with no matching `reset` would have
       still passed the old, filesystem-only content-hash comparison.
    Also flagged, not blocking, left as-is per the reviewer's own
    "do not open a round for these": routing-pattern strings used as
    `re.sub` replacement text (repo-controlled data today, not a live
    defect); `SKILL.md` step 10's `--target <target>` isn't shown quoted in
    the example command (a path with a space would break it) — worth
    pinning `--target "<target>"` at no cost, folded into this round's
    SKILL.md edit anyway since step 10 needed rewording for the REFUSED/
    exit-code handling below.
    Also fixed in the same round, prompted by tracing through the smoke
    test's full flow while addressing finding 3: `.claude/skills/setup-project/SKILL.md`
    step 10 said only "show its stdout VERBATIM," with no instruction to
    check the exit code or stderr — meaning a `REFUSED: ...`
    (generation itself refused, e.g. force-protection tripped) or
    `REFUSED (smoke test): ...` (generation succeeded, verification
    didn't) printed to STDERR with exit 1 could be silently missed. FIXED:
    step 10 now explicitly says to check the exit code, surface a REFUSED
    line to the user, and never treat generation as verified unless the
    command exited 0 with the smoke-test line printed. Step 10 also now
    explicitly forbids the skill from ever passing `--force` itself — that
    escape hatch is for the owner to invoke deliberately, never for the
    interview to reach for silently.
    Re-verified end-to-end: full local test suite passes (18/18 in
    `test_generate_project_setup.py`, all 13 suites overall); byte-compile
    clean; manual re-run against fresh dbt/non-dbt scratch scenarios
    (idempotent re-generation confirmed live, not just in the test
    fixture; the force-protection scenario is covered by the automated
    tests, since a manual hand-edit-then-regenerate check hit an unrelated
    Bash/Windows path-translation artifact in the throwaway verification
    script itself, not the tool under test).
  - 2026-09-08 — round 1 review: scope-auditor FAILed with 1 finding, fixed:
    an undocumented `--skip-smoke-test` CLI flag existed in
    `scripts/generate_project_setup.py` that wasn't part of the contract's
    exhaustive `done_when` CLI-flag list (which explicitly enumerates every
    flag, including a stated exclusion for `--unmatched-stack`) — a new
    mechanism (an escape hatch changing the tool's default verification
    behavior) added without being recorded as a decision. FIXED by removing
    the flag entirely rather than retroactively documenting it: it wasn't
    actually needed by anything the contract describes (SKILL.md's step 10
    always runs generation and the smoke test together as one operation;
    the flag existed only for a test's own convenience, and that test —
    `test_cli_skip_smoke_test_flag_skips_it` — is removed too, since
    `generate()` without `smoke_test()` is already exercised directly, as a
    library call, by every other test in the suite that calls `gps.generate()`
    alone).
  - 2026-09-08 — contract created for Phase 6b of the approved plan
    (`C:\Users\Rami\.claude\plans\happy-stargazing-mccarthy.md`). Built on updated
    `main` (Phase 6a merged, MR !12 and the handover-update MR !13). Preceded by an
    explicit plan-mode session in which two owner decisions were made and are
    recorded above under `decisions_reserved`: cutting the confidential-scope-doc
    feature entirely (not deferring it), and removing the legacy `cto-reviewer.md`
    from generated projects.
