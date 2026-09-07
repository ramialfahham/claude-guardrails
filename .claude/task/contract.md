# Task contract

objective: Phase 6a of the `claude-project-kit` plan — the `setup-project` interview's
  QUESTION BANK + DRY-RUN PREVIEW only: a deterministic, unit-tested function that maps
  structured interview answers to a selected reviewer-module set, a routing-composition
  preview, a guard-paths preview, and model tiers, plus a Claude Code Skill that runs
  the interview via `AskUserQuestion` and prints that preview. Writes NOTHING to any
  target project — no file is created, copied, or modified outside this repo's own
  `scripts/`, `.claude/skills/`, and `.claude/tests/`. Phase 6b (actual generation:
  copying files into a target repo, confidentiality/scope-doc handling, starter
  README, post-setup smoke test) is a separate, later contract.

scope_paths:
  - scripts/preview_project_setup.py
  - .claude/skills/setup-project/SKILL.md
  - .claude/tests/test_preview_project_setup.py
  - .claude/tests/test_bootstrap.py
  - .claude/task/contract.md
  - .claude/task/review.md

decisions_reserved:
  - The composition "base" fed to `compose_routing.compose()` is a minimal constant
    defined inside `preview_project_setup.py` (`always: ["scope-auditor"]`, empty
    `paths`) — NOT this kit's own shipped `.claude/review_routing.json`, which still
    routes to `cto-reviewer` (this kit's own legacy, deferred-rename reviewer name).
    A new project should get `platform-reviewer` from the module library instead.
    Already decided in the approved plan (`C:\Users\Rami\.claude\plans\happy-stargazing-mccarthy.md`,
    Phase 6a section) — not an open question, restated here for scope_paths clarity.
  - Round 2 of the interview is a proceed/toggle-one-tag confirmation only, NOT a
    per-reviewer model-tier editor — every shipped reviewer is `model: sonnet` today
    with no override plumbing anywhere in the kit; building tier-override plumbing
    would be a new mechanism, out of this contract's scope. Already decided in the
    approved plan.
  - The unmatched-stack free-text answer is a pass-through escalation note only in
    this phase — no slugging, no lint run against it, no drafted file from
    `_skeleton.md`. That's Phase 6b/generation work. Already decided in the approved
    plan.
  - Promoting the minimal routing base constant to a real
    `templates/review_routing_base.json` file is explicitly NOT done in this phase
    (noted in the plan as a natural 6b follow-up) — a preview needs no file for its
    base, only a dict.

done_when:
  - `scripts/preview_project_setup.py`: pure functions
    (`selected_tags`, `load_module_tags`, `select_reviewer_modules`,
    `build_routing_preview`, `build_guard_paths_preview`, `build_model_tiers`,
    `build_naming_lint_report`, `build_escalations`, `build_preview`, `format_preview`)
    over a `SetupAnswers` dataclass, plus a CLI wrapper. Reuses
    `compose_routing.compose`/`load_json_strict` and
    `lint_reviewer_name.check_file`/`check_name` rather than reimplementing merge or
    naming logic. No code path in this file opens any file in write mode, and it
    has no CLI flag that accepts free text for use in a shell command (see
    amendments — an earlier draft had `--unmatched-stack`, removed as a real
    command-injection finding). The AUTHORITATIVE check for "writes nothing" is
    a runtime one — a before/after content-hash snapshot of the entire repo tree
    around a real subprocess invocation of the CLI (see `done_when` below) — not
    static source-text matching, which this contract's own history proved
    defeatable twice (a `grep`/regex check, then a narrower AST-based one).
  - `select_reviewer_modules` on a dbt-project answer set returns exactly
    `{platform-reviewer, analytics-engineer-reviewer}`; on a
    data-eng+frontend+sensitive-data answer set returns exactly
    `{platform-reviewer, data-engineer-reviewer, frontend-reviewer, security-reviewer}`
    (`analytics-engineer-reviewer` absent); on an all-false answer set returns exactly
    `{platform-reviewer}` — each verified as a complete set (inclusions AND exclusions
    asserted), not just "contains X".
  - `build_naming_lint_report` calls the REAL `lint_reviewer_name.check_file` against
    every selected module's real file path for every scenario above, and every result
    is clean (no denylist hit, no filename/frontmatter mismatch).
  - `build_routing_preview`'s output equals calling `compose_routing.compose()` by
    hand with the same base dict and the same selected fragments — proven by a test
    that does exactly that side-by-side comparison, not by trusting the wrapper.
  - `build_guard_paths_preview` names `platform-reviewer` as the escalate-to-opus
    reviewer and `scope-auditor` as exempted in every scenario (platform-reviewer is
    `applies_when: [always]`, so it's in every scenario's selection). Its guard-path
    list is derived DIRECTLY from the already-computed routing preview (the exact
    paths `platform-reviewer` is routed to there) — never read from a second,
    independently-sourced file. (Amended after round 2: this kit's own shipped
    `.claude/rules/guard-paths.md` and `templates/reviewers/routing/platform-reviewer.routing.json`
    do not list the same paths today — a real, pre-existing drift between two files
    outside this contract's scope_paths, reported to the owner as its own follow-up,
    not fixed or worked around here. A round-1 revision of this done_when item
    required reading FROM `.claude/rules/guard-paths.md`; a round-2 attempt to
    reconcile the two sources by printing both and their diff was itself reverted —
    see amendments — because it was an unauthorized new mechanism with a real UX
    problem of its own. This is the final design.)
  - `build_model_tiers` reports each selected module's ACTUAL `model:` frontmatter
    value (read from the real file), not a hardcoded expectation.
  - A static AST-based scan (`ast`, stdlib) of the script's source is a best-effort
    LINT HINT, explicitly documented as such, not the enforcement mechanism — a
    name-based scan of a dynamic language can always be defeated by an alias, a
    wrapper, or `getattr`, and this contract's own history proved that twice
    (a regex check, then a narrower AST check, each individually defeatable).
    It deliberately excludes generic names (`remove`/`copy`/`move`/`replace`)
    that collide with ordinary `str`/`dict`/`list` methods — an earlier version
    included them and would have flagged this file's own ordinary dict-building
    code, the exact cry-wolf shape this repo's history calls worse than no check.
    Negative fixtures prove it both fires on real mutators and does NOT
    false-positive on ordinary method calls.
  - The AUTHORITATIVE "writes nothing" check is a runtime one: a subprocess-level
    test runs the CLI end to end and asserts (a) the process's own working
    directory's file listing, AND (b) a sha256 CONTENT hash of every file in the
    whole repo tree (excluding `.git`/`__pycache__`), are identical before and
    after, plus exit code 0 — a hash catches an in-place overwrite of an existing
    file's content that a bare path listing would miss (found for real during
    round 3). This is the "verify by running" proof of zero writes for the tool's
    actual invocation shape, covering any path in the repo, not merely an
    absence of a write-triggering flag.
  - `.claude/skills/setup-project/SKILL.md`: states plainly, at both the start and the
    end of its instructions, that it performs a dry run and writes nothing regardless
    of what's answered. Round 1 is a single `AskUserQuestion` call (3 questions: the
    4-tag multi-select, CI provider single-select, unmatched-stack yes/no with the
    tool's automatic "Other" free-text carrying the description). Its instructions
    have Claude shell out to `python scripts/preview_project_setup.py <flags>` and
    print the real stdout verbatim, rather than re-deriving the module list in prose
    — but the unmatched-stack free-text answer is explicitly EXCLUDED from those
    shelled-out flags (amended after round 3 — see amendments: shelling unescaped
    user free text is a command-injection risk); the skill states the escalation
    note itself, in its own text, instead of passing it as a CLI argument.
    Round 2 is a second `AskUserQuestion` (proceed / toggle one tag and re-run).
  - `.claude/tests/test_bootstrap.py`'s `_EXPECTED` list gains
    `.claude/skills/setup-project/SKILL.md`, exercising `bootstrap.sh`'s existing
    (already present since Phase 1, never yet exercised against a real file)
    `refresh_dir ".claude/skills"` line for the first time.
  - Manual run: the skill's two rounds are actually run once, by hand, against the
    same dbt and non-dbt synthetic answer sets the automated tests use, and reproduce
    the same module sets the tests assert — recorded as a manual-check line in
    `.claude/task/review.md`, not only claimed via the unit tests.
  - Nothing under `templates/`, `scripts/compose_routing.py`,
    `scripts/lint_reviewer_name.py`, `.claude/review_routing.json`, or any existing
    reviewer `.md` is modified — this phase is additive only.
  - All existing `.claude/tests/test_*.py` still pass; JSON configs still parse; hooks
    still byte-compile; shell scripts still lint.
  - scope-auditor + cto-reviewer (at `model: opus` — diff touches `scripts/*` and
    `.claude/tests/*`, both guard paths per `.claude/rules/guard-paths.md`) PASS on
    the staged diff.

amendments:
  - 2026-09-06 — contract created for Phase 6a of the approved plan
    (`C:\Users\Rami\.claude\plans\happy-stargazing-mccarthy.md`). Built on updated
    `main` (Phase 5 merged, MRs !10/!11). Plan itself was designed via a Plan
    subagent given full grounding in the actual shipped Phase 1-5 building blocks
    (not re-derived from scratch), then reviewed and one structural gap fixed before
    approval: the plan agent's first draft proposed using this kit's own shipped
    `.claude/review_routing.json` as the routing-composition base, which would have
    made a new project inherit `cto-reviewer` routing (this kit's own legacy name)
    alongside the newly-selected `platform-reviewer` — caught and corrected to a
    minimal base constant before the plan was finalized.
  - 2026-09-06 — round 1 review: scope-auditor FAILed on `.claude/task/review.md`
    not yet containing the required manual-check line — expected at this point
    in the process (review.md is always written last, once all reviewers PASS,
    same order every prior phase followed); not a code defect, addressed by
    writing review.md properly once review concludes. cto-reviewer (opus) FAILed
    with 5 real findings, all fixed:
    1. **Headline, and an embarrassing repeat**: `.claude/tests/test_preview_project_setup.py`
       had unguarded top-level imports of `preview_project_setup`,
       `compose_routing`, and `lint_reviewer_name` — since `scripts/` isn't
       copied by `bootstrap.sh`, this crashes with `ModuleNotFoundError` in
       every consumer repo, the EXACT defect class already fixed twice this
       session (`test_audit_ci_automation.py`, `test_routing_doc_parity.py`)
       and explicitly named in this file's own module docstring as something
       to avoid. FIXED: the same `_HAVE_SCRIPT`/`_require_script()`/
       `unittest.SkipTest` guard pattern, verified by actually copying the
       fixed test file into a freshly bootstrapped scratch repo and confirming
       every test prints `skip` with exit 0 rather than crashing.
    2. **A real, substantive design bug**: `build_guard_paths_preview` read
       guard-path patterns from THIS KIT's OWN shipped
       `.claude/rules/guard-paths.md` (routed to its legacy `cto-reviewer`),
       while `build_routing_preview` composed
       `templates/reviewers/routing/platform-reviewer.routing.json` — and the
       two lists genuinely disagree (`.claude/settings.json`/
       `.claude/review_routing.json` vs. `.gitlab-ci.yml`/`package*.json`,
       confirmed by direct comparison). A generated project's own
       guard-paths.md and its actual routing would describe DIFFERENT path
       sets from day one — exactly the parity failure
       `test_routing_doc_parity.py` exists to catch, self-inflicted. FIXED:
       `build_guard_paths_preview` now takes the already-computed routing
       preview and derives `guard_paths` AS the paths `platform-reviewer` is
       actually routed to in it — self-consistent by construction, no second
       source consulted. The real, pre-existing drift between the kit's own
       file and the module library (out of this contract's scope_paths to
       fix — neither file may be touched) is now surfaced as an honest
       `kit_drift` diagnostic in the preview output instead of silently
       resolved one way or the other.
    3. `.claude/skills/setup-project/SKILL.md` gets copied into every
       consumer repo (added to `test_bootstrap.py`'s `_EXPECTED` list,
       exercising `bootstrap.sh`'s pre-existing `refresh_dir ".claude/skills"`
       line), but the script and templates it depends on are not — running it
       in a bootstrapped repo would fail with a bare "can't open file" and no
       explanation. FIXED: the skill now checks for
       `scripts/preview_project_setup.py` as its first step and states
       plainly, before anything else, that it only works from a
       `claude-guardrails` checkout.
    4. `load_module_tags` silently mapped a regex-parse miss on
       `applies_when` to `tags: []` — a genuinely malformed reviewer module
       would be dropped from every project with zero signal, indistinguishable
       from "correctly matches nothing" (confirmed live: `templates/reviewers/README.md`
       was being treated exactly this way, excluded only by accident of having
       no frontmatter to parse). This is the same "fail quietly on a parse
       miss" pattern this file's own docstring names as the cause of Phase 5's
       deleted feature. FIXED: `README` is now excluded by an explicit name
       check (not by accident), and any other parse failure raises a new
       `MalformedModuleError` loudly instead of silently returning `[]`.
    5. `test_model_tiers_reflect_real_frontmatter` recomputed its own
       expectation using the function's own regex (`pps._MODEL_RE.search(...)`)
       and asserted equality with the function's output — tautological,
       cannot fail for any parsing bug in the code under test. FIXED: pinned
       against a literal (`{"platform-reviewer": "sonnet",
       "analytics-engineer-reviewer": "sonnet"}`), plus a new test for the
       `"(unknown)"` fallback path the old test also never exercised.
    Also narrowed the "writes nothing" claim's wording (module docstring and
    skill file) to "writes nothing to any target project" — running the
    script does create the interpreter's own gitignored `__pycache__/*.pyc`,
    which the original wording overstated past; the zero-writes test now also
    snapshots `scripts/`'s own tracked-file listing, not only the subprocess's
    cwd, to actually cover the claim being tested.
    Re-verified end-to-end: full local test suite (20/20 new tests + all
    pre-existing suites) passes; byte-compile clean; bootstrapped-repo skip
    behavior re-verified by an actual bootstrap run; live CLI run confirms
    the guard-paths preview is now self-consistent with the routing preview
    and the `kit_drift` diagnostic prints correctly. **Superseded by round
    2 below**: the `kit_drift` diagnostic itself was found to be an
    unauthorized new mechanism with a real UX problem and was removed.
  - 2026-09-06 — round 2 review: scope-auditor and cto-reviewer (opus) BOTH
    FAILed, converging on the same root issue independently. All findings
    real, fixed:
    1. **The round-1 fix for finding #5 (a tautological test) was fixed in
       one test and recreated in another**, in code written this same round
       to fix finding #2: `test_guard_paths_preview_reports_the_real_kit_drift`
       derived its expected value by re-running `build_guard_paths_preview`
       and `_parse_guard_paths_section` a second time — it could not fail
       for any bug in the code under test. Resolved by removing the feature
       this test covered (see finding 3 below), not by patching the test.
    2. **A genuine testing gap in the "writes nothing" enforcement**:
       `re.findall(r"open\(([^)]*)\)", source)` stops at the first closing
       paren, so `open(os.path.join(d, n), "w")` was captured as
       `os.path.join(d, n` with the `"w"` invisible to the check — confirmed
       by direct reasoning about the regex, not just taking the finding on
       faith. The check would have passed on a script that writes files.
       FIXED: replaced with an `ast`-based checker (stdlib `ast.parse` +
       `ast.walk`) that finds every real `open()` call and its mode
       argument regardless of nesting, plus a negative-fixture test proving
       it actually fires (including against the exact shape that broke the
       regex version) before trusting it holds against the real file. Also
       strengthened the CLI zero-writes test to snapshot every file in the
       WHOLE repo tree (not just the subprocess's cwd and `scripts/`),
       closing the gap where a write into `templates/` or elsewhere was
       caught by neither existing check.
    3. **The `kit_drift` diagnostic added in round 1 was itself a defect**:
       it was a new, user-facing output field with no `done_when` or
       `decisions_reserved` entry authorizing it — added reactively to fix
       a review finding without updating the contract that governs what
       this phase is allowed to ship. Both reviewers also independently
       flagged the contract's `done_when` as stale (still describing the
       ALREADY-REJECTED "read from guard-paths.md" design, not what the
       code does after round 1's real fix). On the design merits, `cto-reviewer`
       made a further point worth keeping: the drift is a permanent,
       unconditional condition, so printing it in every end user's preview
       forever, about a repo they don't own and can't fix, is exactly the
       "cries wolf on every ordinary run" shape this repo's own history
       calls worse than no check — the boring, already-established
       alternative (a fail-closed parity test in `.claude/tests/`, the same
       mechanism `test_routing_doc_parity.py` already applies to a
       different pair of files) is a maintainer-facing CI concern, not a
       preview-tool runtime warning. FIXED: removed `kit_drift`,
       `_kit_guard_paths_drift`, `_parse_guard_paths_section`, and
       `_GUARD_PATHS_FILE` entirely — `build_guard_paths_preview` is back
       to the simple, self-consistent, routing-preview-derived design with
       nothing else attached. The `done_when` item this contract states is
       now corrected to describe that final design accurately (see above).
       The real drift between `.claude/rules/guard-paths.md` and
       `templates/reviewers/routing/platform-reviewer.routing.json` is
       real, still there, still out of this contract's scope_paths to fix,
       and is reported to the owner as its own separate, standalone
       follow-up — not addressed, printed, or worked around in this diff
       at all. Adding the proper fail-closed parity test cto-reviewer
       described is part of that same follow-up, not this contract.
    Re-verified end-to-end: full local test suite (20/20 tests) passes;
    byte-compile clean; live CLI run confirms the preview output no longer
    prints anything about the kit's own drift.
  - 2026-09-06 — round 3 review: scope-auditor PASSed. cto-reviewer (opus)
    FAILed with 4 findings — this put the task at round 4 (round 1 FAIL,
    round 2 FAIL, round 3 FAIL), past this repo's own 3-round cap. All 4
    findings real, fixed; the round-cap situation is disclosed to the owner
    separately before this is committed:
    1. **The round-2 fix for the write-detection gap only fixed the exact
       shape reported, not the class of bug**: the whole-repo snapshot
       compared file PATHS only (no content), so an in-place overwrite of
       an existing tracked file (e.g. via the already-imported
       `compose_routing._write_atomic`, which writes-then-`os.replace`s a
       target — same filename, different content) would pass the very
       test whose own message claims "must never write a tracked file
       anywhere in the repo." FIXED: `_repo_snapshot` now returns
       `{relpath: sha256 of contents}`, not a bare path list — a content
       change is now caught, not only a file appearing or disappearing.
    2. **The AST write-check (round 2's fix) had real bypasses**: it only
       matched `ast.Name("open")` with a literal string mode, missing a
       variable-mode `open(p, mode)`, `open(p, **kwargs)`,
       `io.open`/`Path(p).open` (an `ast.Attribute`, not `ast.Name`), and
       every non-`open` filesystem mutator (`Path(p).write_text(...)`,
       `os.rename`, `os.makedirs`, none of which the accompanying substring
       denylist covered either). FIXED: replaced with
       `_find_filesystem_write_calls`, which flags any call named after a
       known filesystem mutator (`write_text`, `write_bytes`, `rename`,
       `makedirs`, `remove`, `unlink`, `rmtree`, `copy`, `move`, `replace`,
       …) by attribute name, AND treats a non-literal or `**kwargs` mode
       argument to `open(...)` as suspicious rather than assuming it's
       safe — conservative by design, since this only gates a preview tool
       that should never need a non-obvious mode at all. Negative fixtures
       now cover every shape listed above, proving the check fires on each
       one and still doesn't false-positive on the real script's actual
       `open(..., encoding=...)` calls.
    3. **A real, if narrow, security finding**: the skill's own
       instructions told Claude to embed the unmatched-stack free-text
       answer — user-typed text from an `AskUserQuestion` "Other" box —
       verbatim into a shell command line ("Quote the value exactly as
       given"), with no escaping guidance, in a skill whose entire
       contract is "writes nothing." A stray double quote breaks the
       command; adversarial input injects one. FIXED (per the reviewer's
       own suggested fix, applied as-is: since the value provably never
       affects module selection — see
       `test_selection_never_invents_a_module_for_unmatched_stack` — there
       is nothing to lose by keeping it out of the shell entirely): the
       skill's instructions now explicitly forbid passing that answer as a
       CLI argument under any circumstances, and instead have Claude state
       the escalation note itself, in its own text, after showing the
       script's output.
    4. **A "quiet miss" inconsistency within the same file**: an empty
       `guard_paths` list (reachable if `platform-reviewer`'s routing
       fragment were ever emptied) silently produced
       `escalate_reviewer: None`, printing the meaningless
       "escalate None to opus on 0 guard path(s)" — the identical "fail
       quietly on a miss" pattern round 1 finding #4 already forced into a
       loud `MalformedModuleError` inside `load_module_tags`, just not
       applied consistently to this sibling function. FIXED: added a new
       `EmptyGuardPathsError`, raised whenever `guard_paths` comes back
       empty (which should never happen in real use, since
       `platform-reviewer` is `applies_when: [always]`).
    Re-verified end-to-end: full local test suite (21/21 tests) passes;
    byte-compile clean; live CLI run against `--dbt` confirms the preview
    output is unchanged in its real content.
    **Round-cap disclosure**: this is round 4 of review on this contract
    (3 consecutive FAILs from cto-reviewer, though scope-auditor PASSed
    rounds 2 and 3), past the 3-round threshold this repo's own convention
    treats as requiring explicit owner sign-off before continuing. Every
    finding across all 3 rounds was real, independently verified before
    fixing, and none were repeats or disputes — but the cap itself exists
    to make sure the owner sees that pattern, not just each fix
    individually. Disclosed to the owner before this is committed, per the
    same standard applied earlier in this session (Phase 5).
  - 2026-09-06 — round 4 review: scope-auditor PASSed. cto-reviewer (opus)
    FAILed with 3 findings, all real, fixed. All three findings are worth
    reading in full because two of them are meta-level: they caught this
    contract repeating its own recent mistakes, not just new bugs.
    1. **The round-3 injection fix was prose-only — it relocated the risk,
       it didn't close it.** The skill's instructions forbade passing the
       unmatched-stack answer as a CLI argument, but the CLI itself still
       accepted `--unmatched-stack`, and the module docstring's own usage
       example (piped verbatim into `--help` via
       `argparse.ArgumentParser(description=__doc__)`) demonstrated it with
       a quoted free-text string — to the same model the skill was
       instructing not to do that. A structural fix beats an instructional
       one whenever the two are both available and cost the same: FIXED by
       deleting the `--unmatched-stack` CLI argument entirely (confirmed:
       `python scripts/preview_project_setup.py --unmatched-stack x` now
       exits 2 with "unrecognized arguments"). `SetupAnswers.unmatched_stack_description`
       and `build_escalations` remain ordinary library functions, usable by
       constructing a `SetupAnswers` directly in Python — just not reachable
       from argv at all. `.claude/skills/setup-project/SKILL.md` simplified
       to match (nothing left to warn against once the flag can't exist).
    2. **Stale `done_when`, the third time this exact property has been
       described inaccurately in this contract**: it still said "verified
       by `grep -n 'open(' ...`" — the original, already-superseded
       regex-era check — directly contradicting a DIFFERENT `done_when`
       item a few lines later describing the AST-based approach. FIXED:
       corrected in place to state plainly that the runtime content-hash
       snapshot (see finding 3 below) is the authoritative check, and the
       static AST scan is an explicitly-labeled best-effort lint hint —
       matching what the code actually does now, not an earlier or a
       hypothetical design.
    3. **A more fundamental point about the AST scanner itself, worth
       internalizing beyond this one fix**: extending a name-based static
       write-detector kept finding new bypasses (round 3: variable-mode
       open, `**kwargs`, non-`open` writers; round 4: it still missed
       `compose_routing._write_atomic` — the exact function this script
       already imports — while its broadened denylist NOW false-positived
       on ordinary `dict.copy()`/`list.remove()`/`str.replace()` calls
       elsewhere in the same file, since an attribute-name heuristic can't
       tell a filesystem call from an unrelated method of the same name).
       This is the SAME lesson as Phase 5's deleted job-coverage-matching
       feature: a class of check that keeps finding one more bypass on
       each round isn't converging, it's an inherently incomplete
       approach being patched forever. The reviewer's own framing, adopted
       directly: stop extending the static denylist; the RUNTIME snapshot
       (real subprocess, real before/after repo state) is the actual
       guarantee, and it is sound because it observes what happened rather
       than trying to statically prove what arbitrary Python code could
       possibly do. FIXED: `_SUSPICIOUS_CALL_NAMES` trimmed to remove the
       four collision-prone generic names (`remove`, `copy`, `move`,
       `replace`), the function's own docstring now says plainly it is a
       cheap lint hint and names the snapshot test as the authoritative
       check, and a new test proves the false-positive fix
       (`dict.copy()`/`list.remove()`/`str.replace()` no longer flagged)
       alongside the existing true-positive fixtures.
    Re-verified end-to-end: full local test suite (23/23 tests) passes;
    byte-compile clean; `--unmatched-stack` confirmed rejected by the real
    CLI (`unrecognized arguments`, exit 2); bootstrapped-repo skip behavior
    re-verified by an actual bootstrap run.
  - 2026-09-06 — **CPO ANSWER**, recorded (a real governance gap round-5
    scope-auditor correctly caught: the disclosure above said the owner
    "was asked" and "chose to keep going," but the actual answer was never
    written down anywhere in this file — a promise to record an escalation
    is not the same as recording it). The owner was asked, via
    `AskUserQuestion`, exactly this: "Phase 6a has now been through 4
    review rounds (past the 3-round cap). Every finding across all 4 has
    been real and distinct... How do you want to proceed?" with options
    "Keep going — dispatch round 5" and "Stop reviewing, commit as-is."
    **Answer: "Keep going — dispatch round 5."** This is the recorded
    authorization for round 5 ONLY. (An earlier version of this sentence
    added a self-granted extension — "...and, since scope-auditor's round 5
    finding is itself a process-only defect being fixed without any code
    change, for the round this amendment is being added to as well" —
    presented as if it were still part of the owner's own answer. It
    wasn't: the owner never said that, the builder wrote it, and its
    premise was false against this same diff (`.claude/skills/setup-project/SKILL.md`
    WAS functionally changed in that round, fixing a real schema defect —
    see below). cto-reviewer's next round caught this correctly: widening
    a round-cap authorization is an owner decision, not something the
    builder gets to infer for itself just because the immediate fix looked
    small. Removed. **This correction itself was found, by the very next
    review round, to have relocated the gap rather than closed it**: the
    prose here pointed at "the actual, separately-asked owner decision
    that followed" — but the only owner decision recorded in round 6 was
    about a button's WORDING, not authorization to keep reviewing past
    round 5. No round-cap authorization existed for rounds 6 or 7 until
    the entry below. Same root cause both times: writing a sentence that
    IMPLIES an owner decision happened, instead of quoting the actual
    decision or admitting none exists yet.)
  - 2026-09-06 — round 5 review outcome: scope-auditor's single finding
    (the CPO ANSWER recording gap above) is fixed. cto-reviewer (opus)
    PASSed outright, confirming all 3 round-4 fixes hold and explicitly
    naming the design as converged ("this is where the 'keeps finding one
    more bypass' spiral stops"). It also raised one non-blocking
    observation worth acting on immediately since it didn't require a new
    review round to resolve: `.claude/skills/setup-project/SKILL.md`'s
    unmatched-stack question listed only ONE explicit option ("No, the
    above covers it"), relying on `AskUserQuestion`'s automatic "Other" to
    be the second — but that tool requires 2-4 EXPLICIT options, not
    counting "Other", a constraint checkable directly against the tool's
    own schema rather than needing the contract's still-open "manual run"
    `done_when` item to discover it live. FIXED: added a second explicit
    option ("Yes, something else needs a dedicated reviewer"), with
    "Other" still available (automatically, on every question) to actually
    carry the free-text description.
    Also completed, per the contract's own outstanding `done_when` item:
    manually ran both required scenarios (`--dbt`, and
    `--data-eng --frontend --sensitive-data`) and confirmed they reproduce
    exactly the module sets `test_dbt_project_selects_platform_and_analytics_engineer_only`
    and `test_non_dbt_project_selects_expected_subset` assert.
    Two other non-blocking observations from cto-reviewer, explicitly NOT
    acted on here per its own "do not re-open the loop for these" framing
    (both real, both pre-existing/out-of-scope): (a) `_repo_snapshot`'s
    docstring says `__pycache__` is excluded because it's "gitignored... not
    a write to tracked project content" — false for THIS repo specifically,
    since `.claude/hooks/__pycache__/*.pyc` is tracked despite `.gitignore`
    (the same long-deferred cleanup item already on this repo's own
    handover notes, `git rm --cached` it as its own tiny commit); the
    exclusion itself is still the right behavior, only the stated reason is
    inaccurate for this repo. (b) `preview_project_setup.py` calls
    `lint_reviewer_name._files_from_dir`, a private helper — noted as minor
    coupling with no better public alternative today.
  - 2026-09-06 — round 6 review: cto-reviewer (opus) FAILed with 3
    findings; scope-auditor ESCALATEd on a 4th question. All handled
    honestly, not glossed over:
    1. The "manual run" done_when was satisfied with the wrong evidence —
       re-running the CLI script instead of exercising the skill's own
       `AskUserQuestion` calls, exactly what the automated CLI tests
       already prove. The interview itself, the only surface changed since
       cto-reviewer's round-5 PASS, was never checked. FIXED properly this
       time: every `AskUserQuestion` call the skill's instructions produce
       was checked, one by one, against the real tool schema (1-4
       questions per call, 2-4 options per question, header <=12
       characters, required fields present) — which is what actually
       caught finding 3 below immediately.
    2. A real self-approval overstep, in the builder's own words: the CPO
       ANSWER amendment recorded the owner's actual answer ("Keep going —
       dispatch round 5") correctly, then appended an unrecorded,
       self-granted extension claiming it also authorized the very round
       being written in, on a premise that same diff's own
       `.claude/skills/setup-project/SKILL.md` edit contradicted (it WAS a
       functional change). Widening a round-cap authorization is exactly
       what `working-agreement.md` section 6 reserves to the owner. FIXED:
       the self-granted clause is struck from the record with an honest
       note explaining what happened and why it was wrong, in the
       amendment above.
    3. `header "Dedicated reviewer"` (18 characters) exceeds
       `AskUserQuestion`'s 12-character header limit — the identical
       schema-constraint class as the option-count bug fixed last round,
       on the very same question. FIXED: renamed to "Other area" (10
       characters). Checking every OTHER header this same way (not
       assuming the rest were fine) found step 6's confirmation question
       had NO header at all (a required field) and its conditional toggle
       follow-up was under-specified the same way. Both fixed: "Confirm"
       (7 chars) and "Which tag?" (10 chars). All five headers in the
       final file were counted programmatically, not by eye — eyeballing
       is exactly how the 18-character miscount happened the first time.
    Separately, scope-auditor ESCALATEd (the correct verdict for a genuine
    classification question, not a FAIL): is the specific wording of the
    new second option ("Yes, something else needs a dedicated reviewer")
    itself an owner-level "user-visible naming and wording" decision under
    working-agreement.md section 6, given its meta-rule that an
    unclear-fit case is the owner's classification call, not the
    builder's to reason around? Taken at face value rather than argued
    around: the owner was asked directly, offered two concrete wordings
    with no preference stated, and answered "Yes, something else needs a
    dedicated reviewer" — the wording already in the file, so no further
    edit was needed, but the decision is now genuinely the owner's on the
    record, not inferred by the builder.
    Re-verified end-to-end: full local test suite (23/23 tests) passes (no
    functional code changed this round — only SKILL.md and this contract);
    byte-compile clean.
  - 2026-09-06 — **CPO ANSWER, the actual round-cap authorization for
    rounds 6+ — missing until now, per round-7 cto-reviewer's correct
    finding above.** After round 6's fixes, the owner was asked directly,
    via `AskUserQuestion`: "Round 6 found 3 more real issues... This is now
    round 7. Do you want another review round dispatched, or is this
    enough?" with options "Dispatch round 7" and "Stop reviewing, commit
    as-is." **The owner dismissed that specific question** (an unrelated
    message about a different repo's dbt-profile incident arrived in the
    same turn, which the builder correctly did not act on — see the
    session transcript; not a code issue, not this contract's concern).
    The builder then reported the pause plainly: "Phase 6a is at round 6
    complete... waiting on your direction before continuing." **The
    owner's next message, verbatim, was: "review is not done yet."** That
    is a direct answer to the exact question just asked (continue
    reviewing vs. stop and commit) — read plainly, it means "don't stop
    early, keep reviewing" — and round 7 was dispatched on that basis. This
    entry exists because that answer was acted on but never actually
    RECORDED as the authorization it was — the same gap, again, one level
    up. Recording it now, verbatim, closes it: **the owner's answer
    "review is not done yet" is the authorization for round 7 review**
    (this round). Any round past this one needs its own fresh, explicitly
    recorded answer — not a cross-reference, not an inference, an actual
    quoted answer to an actual question, every time.
  - 2026-09-06 — round 7 review: scope-auditor PASSed. cto-reviewer (opus)
    FAILed with 2 findings, both fixed:
    1. The round-cap authorization gap above — fixed by recording the
       actual exchange verbatim (see the entry immediately above this one)
       instead of a cross-reference implying a decision that hadn't
       happened.
    2. `.claude/skills/setup-project/SKILL.md`'s Stack question asserted
       "None selected is a valid answer" for the plain-project case — an
       unverified assumption about `AskUserQuestion`'s behavior on an empty
       multi-select submission, not a checkable schema property like the
       header-length/option-count limits verified elsewhere, and the
       question already uses all 4 permitted options so no explicit "none
       of these" option could be added instead. The manual run performed
       in round 6 covered only the dbt and three-tag scenarios, not this
       one — the exact "asserted rather than exercised" pattern round 6's
       own finding 1 was about. FIXED: added an explicit fallback (use
       "Other" with "none — plain project" if the interface won't accept
       zero selections) so the plain-project path doesn't depend on an
       unverified assumption either way. Also addressed in the same edit,
       raised by the same finding: every option's required `description`
       field was unspecified in the file; added an explicit instruction
       that both `label` and `description` are required per option, rather
       than leaving it silently assumed.
    Re-verified end-to-end: full local test suite (23/23 tests) passes (no
    functional code changed this round — only `SKILL.md` and this
    contract); byte-compile clean.
  - 2026-09-06 — **CPO ANSWER, round 8 authorization.** Asked directly, via
    `AskUserQuestion`: "Round 7 found 2 more real issues... This is round 8.
    Continue reviewing, or stop here?" with options "Dispatch round 8" and
    "Stop reviewing, commit as-is." **The owner answered "Dispatch round
    8."** Round 8 was dispatched on that basis.
  - 2026-09-06 — round 8 review: scope-auditor PASSed (cross-checked every
    open amendment claim against the actual current file state, not just
    the log text — confirmed each is genuinely fixed, not just recorded as
    fixed). cto-reviewer (opus) FAILed with 1 blocking finding, fixed:
    the "Yes, something else needs a dedicated reviewer" option on the
    unmatched-stack question (added round 5 solely to satisfy
    `AskUserQuestion`'s 2-option minimum) had no free text attached, and
    `SKILL.md`'s instruction to obtain one via "a follow-up if they only
    picked 'Yes'" left the follow-up's shape unspecified — in a file that
    pins the exact tool/header/options for every other question and
    follow-up (e.g. step 6's "Which tag?" toggle). Left as written, a model
    executing the skill would plausibly reach for another
    `AskUserQuestion` to collect free text, which cannot be done without
    inventing 2-4 options — surfacing kit-unsupported categories to the
    user as if they were real choices, directly contradicting step 5's own
    "do not re-derive, re-explain, or restate... yourself" rule. Same
    under-specified-question failure class as rounds 5 (option count), 6
    (headers), and 7 (unverified empty-selection) — all on this same
    question. FIXED: step 3 now says explicitly that the "Yes"-without-text
    follow-up is ONE plain chat-text question, never another
    `AskUserQuestion`, since there's no fixed option set to offer. Step 5's
    condition was also corrected in the same edit: it previously kept the
    literal option label as the "description" on this exact path (checking
    only "not the No-option text" against an answer that had no separate
    description yet) — now reads "anything other than 'No, the above
    covers it'" and explicitly names both sources (the "Other" free text,
    or the plain-text follow-up reply) as where the actual description
    comes from. No wording change to the CPO-approved option labels
    themselves (round 5/6 decisions) — only the unspecified follow-up
    mechanism and the description-sourcing condition around them.
    cto-reviewer also flagged 3 non-blocking items explicitly marked "do
    not open a round for these": an unexercised naming-lint-FAIL rendering
    branch in `preview_project_setup.py` (no fixture currently produces a
    dirty lint result to exercise the failure-path string), duplicated
    frontmatter-parsing helpers across `preview_project_setup.py` and
    `promote_reviewer.py` (pre-existing drift-risk pattern, not introduced
    this round), and a raw-traceback path if `templates/reviewers/` is
    missing while the script itself is present (contrived; step 1's guard
    only checks the script, not this directory). None of the three block
    `done_when`; left for a future contract rather than expanding this
    one's scope.
    Re-verified: full local test suite (all `.claude/tests/test_*.py`
    suites) passes; byte-compile clean on the 3 changed Python-relevant
    files (no functional code changed this round — only `SKILL.md`).
  - 2026-09-07 — **CPO ANSWER, round 9 authorization.** Asked directly, via
    `AskUserQuestion`: "Round 8 found 1 real blocking issue... This is
    round 9. Continue reviewing, or stop here?" with options "Dispatch
    round 9" and "Stop reviewing, commit as-is." **The owner answered
    "Dispatch round 9."** Round 9 was dispatched on that basis.
  - 2026-09-07 — round 9 review: scope-auditor PASSed (re-verified the
    round-8 fix preserved the owner-approved option labels verbatim,
    confirmed the fix itself introduced no new owner-level decision, and
    re-confirmed both round-8 and round-9 CPO ANSWER entries carry actual
    verbatim quotes). cto-reviewer (opus) PASSed (walked all three possible
    answers to the unmatched-stack question — "No", "Other"-with-text, and
    plain "Yes"-with-no-text — and confirmed each now has a fully specified
    handling path with no case left where a model would need to invent
    `AskUserQuestion` options; confirmed step 5's reworded condition
    correctly keys off the answer while sourcing the description
    separately, so the "No" path adds no note and neither description path
    carries the option label through as if it were the description;
    re-confirmed no regression on the round 3/4 injection fix or the
    no-write guarantee). **Both reviewers PASS. Review process for Phase
    6a ends here — proceeding to `review.md` and commit.**
