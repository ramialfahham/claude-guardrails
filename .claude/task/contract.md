# Task contract

objective: Phase 1 of "Post-plan hardening: aligning with current Claude Code
  platform capabilities" (see `C:\Users\Rami\.claude\plans\happy-stargazing-mccarthy.md`,
  section of that name, approved via plan mode 2026-09-08). This kit's 7-phase build
  was designed entirely from the owner's own prior repos and never checked against
  Anthropic's current published Claude Code guidance. Research now done (Anthropic's
  official best-practices/hooks/permissions/permission-modes docs, fetched and read in
  full) surfaced three real gaps: no completion-time (`Stop` event) gating exists at
  all — this kit only enforces at commit time; auto-mode (now the default permission
  mode on Pro/Max/Team) compatibility was never checked or documented; there's no
  documented reason for building a custom review gate instead of Claude Code's own
  built-in `/code-review`. This contract closes all three: a new advisory-only
  completion-reminder hook (originally built on the `Stop` event; revised to
  `PreToolUse` during round 5 review — see amendments — after discovering `Stop`
  can't actually deliver "advisory, never blocks" on this platform), an ADR
  documenting (with cited sources) that existing hooks are unaffected by permission
  mode, and an ADR documenting why this kit's gate and `/code-review` are
  complementary, not redundant.

scope_paths:
  - .claude/hooks/completion_gate.py
  - .claude/hooks/_command_utils.py
  - .claude/settings.json
  - .claude/tests/test_completion_gate.py
  - .claude/tests/test_hooks_import.py
  - docs/decisions/auto-mode-and-bypass-compatibility.md
  - docs/decisions/custom-review-gate-vs-code-review-skill.md
  - docs/project-kit-design.md
  - .claude/task/contract.md
  - .claude/task/review.md

decisions_reserved:
  - **The completion-reminder hook is advisory-only — it never blocks the tool call.**
    Owner decision, made explicitly during plan-mode planning via `AskUserQuestion`
    (options: "Advisory only" vs. "Hard block"; owner chose advisory). Originally
    implemented on the `Stop` event; revised to `PreToolUse` (matcher: `Bash`) during
    round 5 review after discovering `Stop`'s `additionalContext` does not actually
    deliver "advisory, never blocks" on this platform (see the round-5 amendment for
    the full discovery and the owner's redesign decision). The advisory-only
    requirement itself is unchanged — only the event/matcher it's implemented on
    changed. Matches the existing, established pattern for this repo's own
    `PreToolUse` advisory hooks (`handover_plan_gate.py`/`plan_implement_gate.py` —
    both only ever nudge via `additionalContext`, never `permissionDecision: "deny"`).
  - **The hook's matcher is `Bash`, and it explicitly skips subagent-issued tool
    calls** — both corrections from round 6 review, not the original design. An
    intermediate version used no matcher at all ("fires on every tool call");
    round 6 found this risked leaking the hook's note into this repo's own blinded
    reviewers' context if a tool call happened during a subagent's turn, and a
    check on the event's `agent_id` field (present only inside a subagent call, per
    Anthropic's own hooks reference) skips subagent calls unconditionally, not
    relying on today's reviewers lacking Bash access to stay true.
  - **The hook self-gates on the actual Bash command (`git status`/`commit`/
    `push`), matching every sibling hook in the same matcher group — this is
    the real cost fix, not a cache.** An intermediate version's claim that
    scoping to `Bash` alone made the cost "the same as `commit_review_gate.py`
    already pays" was itself wrong — that hook self-gates to actual `git commit`
    attempts, not every Bash call — and round 6 caught it. The owner's explicit
    standing feedback on being asked to accept this (recorded verbatim in the
    round-6 amendment) was that cheap-by-default answers were being offered too
    often instead of a properly engineered one, so a fingerprint-cache fix was
    built (`completion_gate._fingerprint()`, gating `_gate()`'s own expensive
    check, not just its printed note). Round 7 (two independent reviewers) found
    that fingerprint incomplete in ways that silently suppress real notes for the
    rest of a session — it missed `review_routing.json` edits and the base branch
    itself moving. A fix that closed those gaps was found to cost essentially the
    same as calling `_gate()` directly, since the expensive part of `_gate()`
    (base-ref/merge-base resolution) is exactly what a correct fingerprint would
    also need to recompute — there is no cheap-and-correct proxy available. Given
    this hook is advisory only, not a blocking gate, the owner's explicit call
    (verbatim: "You are definitely drifting") was to stop engineering around an
    unsound cache and revert to the simple, already-proven round-6 design with
    the real cost documented honestly instead of minimized. That revert then
    itself ran `_gate()` unconditionally on every matched Bash call — round 8's
    scope-auditor pass correctly `ESCALATE`d rather than pass or fail it: every
    OTHER hook in the `Bash` group self-gates on the actual command before doing
    real work, this one didn't, and the resulting per-call cost had never been
    explicitly re-priced with the owner (F9 covered the old `Stop` design's
    once-per-turn-end cost; the fingerprint cache meant to answer the
    per-tool-call cost was gone by round 8). Owner chose the self-gate (a plain
    command filter reusing `_command_utils.git_subcommand`/`simple_commands`,
    not a cache, not new machinery) over accepting the uncached cost as-is. See
    the round-7 and round-8 amendments for the full history.
  - The hook reuses `commit_review_gate.py`'s own `_gate(root)` function directly
    (`import commit_review_gate as crg`) rather than reimplementing "is the current
    staged state reviewed" — the exact same check the commit-time gate already makes,
    consulted at a different moment (a relevant Bash call vs. commit-attempt). This
    is a read-only import of an existing module; `commit_review_gate.py` itself is
    NOT modified (not in `scope_paths`).
  - `_command_utils.py`'s `emit_context(event_name, text)` already accepts an
    `event_name` parameter and needs no change to emit a `PreToolUse`-shaped note — it is
    listed in `scope_paths` only in case the actual implementation surfaces a real,
    narrow need to extend it; if it doesn't, it should be left untouched and this
    contract should say so plainly in its amendments rather than pad in an unneeded
    change. `emit_deny` is deliberately NOT reused or generalized for this hook,
    since this hook never denies anything.
  - The two new ADRs document real, already-completed research (with the exact
    Anthropic documentation quotes gathered during planning) — they record findings,
    not aspirational claims. The auto-mode ADR explicitly states the `bypassPermissions`
    case is NOT confirmed by Anthropic's docs (only inferred from the general
    hooks-run-before-permissions architecture) — this must not be overstated as a
    documented guarantee when it isn't one.
  - Bootstrap/distribution consequence, to be documented (not fixed) in this
    contract: `bootstrap.sh`'s `keep_file` semantics mean an already-bootstrapped
    project won't get the new hook's `settings.json` wiring automatically on a plain
    re-run — only the hook file itself lands via `.claude/hooks`'s unconditional
    `refresh_dir`. Fixing this (e.g. a smarter settings.json merge) is explicitly
    out of this contract's scope — bootstrap.sh already asks the owner to
    hand-merge the hooks block on every re-run when settings.json exists, and this
    is not being redesigned here.
  - Sandboxing adoption, parallel-session/worktree safety, and headless-mode
    compatibility are explicitly OUT of scope for this contract (deferred to a later
    phase per the plan) — do not fold any of them in here even if related issues are
    noticed in passing; flag separately instead.

done_when: (revised for the round-5/6 `PreToolUse` redesign, round 7's
  cache-removal, and round 8's command self-gate — see amendments for the full
  history; this list describes what actually shipped, not any earlier draft)
  - `.claude/hooks/completion_gate.py`: a hook wired to the `PreToolUse` event,
    matcher `Bash` — the same matcher group as `commit_review_gate.py` and
    `branch_discipline.py`. Reads the real `PreToolUse` event JSON via
    `_command_utils.read_event()` (only `session_id`, `agent_id` when present,
    and `tool_input.command` via `_command_utils.bash_command` — not the full
    event shape), resolves the project root the same way `commit_review_gate.py` does
    (`CLAUDE_PROJECT_DIR` env var), skips entirely when `agent_id` is present
    (a subagent-issued call), skips entirely when the Bash command isn't one
    of `git status`/`commit`/`push` (`_is_relevant`, reusing
    `_command_utils.git_subcommand`/`simple_commands` — not a cache, a plain
    filter matching every sibling hook in this matcher group), and otherwise
    calls `crg._gate(root)` directly. If it returns a reason AND the session's
    marker didn't already record firing that exact reason last, emits ONE
    `additionalContext` note (via `_command_utils.emit_context`) naming what's
    unreviewed, then updates the marker with the new reason hash. Never sets
    `permissionDecision`. Fails open (returns/exits cleanly) on any exception,
    matching every other hook in this repo — including a valid-but-non-dict
    event payload (`event.get(...)` runs inside the same top-level `try`, not
    before it; round 7 found an earlier draft raised `AttributeError` uncaught
    on that shape).
  - `.claude/tests/test_completion_gate.py`: a test file building a `PreToolUse`-shaped
    event fixture modeled on `test_commit_review_gate.py`'s own `_run_main_in`
    stdin/argv/env-swap-and-capture pattern, using the same real-tempdir-git-repo
    fixture style already established throughout this repo's test suite. Covers:
    unreviewed staged real work → note emitted; unreviewed but bookkeeping-only
    staged diff → no note; properly reviewed staged work (valid review.md matching
    the current diff hash) → no note; nothing staged → no note; a subagent-issued
    call (`agent_id` present) → no note even with unreviewed work staged; an
    irrelevant Bash command (`ls`, `pytest`, `python foo.py`, `git log`,
    `git diff`) → `crg._gate()` never even called (proven via a call-counting
    monkeypatch), while `git status`/`commit`/`push` each still reach the real
    check; suppression (unchanged reason → suppressed, changed reason →
    re-fires, regression to a previously-fired reason → still re-fires, a
    different session → not suppressed by another session's marker); a
    non-dict JSON payload (`[]`, `null`, a bare number or string) → fails open
    with no output; a `_gate()` failure → fails open with empty output; and an
    explicit negative assertion that the hook NEVER sets `permissionDecision`
    in any of these cases.
  - `.claude/tests/test_hooks_import.py`: `completion_gate` added to whatever list
    of hook modules it imports, so the existing import-smoke-test covers the new
    file.
  - `.claude/settings.json`: `completion_gate.py` added to the existing `matcher:
    "Bash"` `PreToolUse` group (alongside `branch_discipline.py`,
    `commit_review_gate.py`, `secret_scan.py`, `pre_push_gate.py`,
    `handover_out.py`), with a `statusMessage` matching the existing hooks'
    convention in this file. No other hook wiring in this file is touched.
  - `docs/decisions/auto-mode-and-bypass-compatibility.md`: states, with the actual
    verbatim Anthropic quotes as citations, that this kit's existing `PreToolUse`
    hooks are unaffected by permission mode — auto mode's classifier cannot override
    a hook's `deny`; `bypassPermissions` is explicitly flagged as inferred, not
    documented. Documents `completion_gate.py` as a third `PreToolUse` hook that is
    still out of scope for that specific guarantee, since it never sets
    `permissionDecision` at all. Backed by a real regression test (in
    `test_hooks_import.py`): a source-text check that `commit_review_gate.py`,
    `branch_discipline.py`, and `completion_gate.py` never reference
    `permission_mode` anywhere in their source — if one ever does, that is exactly
    the moment this claim needs re-verifying, and the test should say so in its
    failure message.
  - `docs/decisions/custom-review-gate-vs-code-review-skill.md`: documents the real
    distinction between this kit's blocking pre-commit gate and Claude Code's built-in
    `/code-review` (advisory-after-PR, GitHub-PR-specific, Team/Enterprise
    research-preview at time of writing) as the answer to "why not just use the
    built-in one" — pointing at what `/code-review` actually does, not asserting a
    difference from nothing.
  - `docs/project-kit-design.md`: gains a mention of the new completion-reminder
    hook layer in its existing review-gate-mechanics section (its `PreToolUse(Bash)`
    matcher, subagent skip, the command self-gate to `git status`/`commit`/`push`
    as the actual cost fix — not a cache; the fingerprint-cache attempt was tried
    and reverted, see the round-7/8 amendments — and the settings.json-merge
    consequence for already-bootstrapped projects.
  - Full local test suite (`.claude/tests/test_*.py`) passes, including the two new/
    extended test files. `python -m py_compile` clean on the new hook file. JSON
    (`.claude/settings.json`) still parses.
  - Manual check: run `completion_gate.py` directly via a simulated `PreToolUse`
    event against a real scratch git repo with unreviewed staged changes, confirm
    the note appears in stdout and the process exits cleanly with no
    `permissionDecision` set.
  - Nothing under `commit_review_gate.py`, `branch_discipline.py`,
    `secret_scan.py`, `pre_push_gate.py`, `handover_in.py`, `handover_out.py`,
    `handover_plan_gate.py`, `plan_implement_gate.py`, or `preflight.sh` is modified
    — additive only, plus the one `_command_utils.py` change if it turns out to be
    genuinely needed (see decisions_reserved).
  - scope-auditor + cto-reviewer (opus — `.claude/hooks/*` and `.claude/settings.json`
    are both guard paths per `.claude/rules/guard-paths.md`) PASS on the staged diff.

amendments:
  - 2026-09-08 — contract created. Preceded by a plan-mode session that: (1) directly
    fetched and read Anthropic's official Claude Code documentation (best-practices,
    hooks, permissions, permission-modes pages) rather than relying on prior
    knowledge, after the owner asked whether this kit reflects Anthropic's current
    recommendations and the honest answer was "never checked"; (2) verified the
    specific claim "a hook's deny survives auto mode's classifier" against the actual
    docs text rather than assuming it, and explicitly confirmed the docs are SILENT
    on the equivalent claim for `bypassPermissions` mode rather than papering over
    the gap; (3) got an explicit owner decision (advisory-only, not hard-block) on
    the one genuine product/UX judgment call in this design, via `AskUserQuestion`,
    before finalizing the plan.
  - 2026-09-08 — round 1 review: scope-auditor PASS; cto-reviewer FAIL, 9 findings.
    Resolved as follows:
    - F1 (claimed the whole `additionalContext`-on-`Stop` mechanism might be a silent
      no-op, no citation in the diff): re-verified against Anthropic's live docs
      directly (several fetch attempts truncated before a clean one succeeded);
      obtained a clean verbatim quote confirming `additionalContext` IS documented as
      supported on `Stop`. The reviewer's underlying factual claim was wrong, but the
      process concern (a load-bearing platform claim needs an in-repo citation) was
      valid — fixed by adding the citation into `completion_gate.py`'s own docstring
      and into the auto-mode ADR.
    - F2 (test only checked `permissionDecision`, not Stop's actual blocking
      mechanism): `_assert_never_denies` in `test_completion_gate.py` strengthened to
      also check a top-level `decision: "block"` field and the process's actual exit
      code (never 2) — covers the blocking mechanism regardless of which exact field
      name is authoritative for `Stop` specifically.
    - F3 (self-contradiction in `custom-review-gate-vs-code-review-skill.md`: prose
      said local review is possible on non-Team/Enterprise plans, table said
      "Team/Enterprise only" with no qualifier): table row fixed to state both facts.
    - F4 (overclaim: "mechanically impossible" for `/code-review` to block, stated
      without acknowledging this kit's own documented fail-open cases): rewritten to
      precisely cite this kit's actual fail-open paths (`_gate()` returning `None` on
      missing routing, exception fail-open, `preflight.sh`'s missing-Python warning,
      `PreToolUse(Bash)`-only coverage) and compare honestly instead of overclaiming.
    - F5 (multiple ADR citation-quality issues: elided quote, unhedged title,
      PreToolUse-only citations silently extended to the new `Stop` hook, a literal
      backslash artifact, `Stop` mischaracterized as "enforcement"):
      `auto-mode-and-bypass-compatibility.md` fully rewritten — title scoped to
      `PreToolUse` specifically, full unelided quotes, `completion_gate.py` explicitly
      carved out of the "enforcement" claim with its own citation and reasoning.
      `docs/project-kit-design.md`'s matching sentence corrected the same way.
    - F6 (non-sequitur reasoning: claimed the regression test is *why* the auto-mode
      guarantee holds, when Claude Code's own evaluation order is why): comment above
      `_MODE_INDEPENDENT_HOOKS` in `test_hooks_import.py` and the ADR's corresponding
      section rewritten to correctly frame the test as a tripwire, not a proof.
    - F7 (dead/duplicate test code reintroducing the "skip is green" anti-pattern
      already fixed once in Phase 7): `test_completion_gate.py` rewritten — removed
      the unused `scenarios` list, unused `_REPO_ROOT`, and the duplicate
      `test_never_emits_a_deny_across_all_scenarios`; all `print("skip..."); return`
      patterns converted to `raise unittest.SkipTest(...)` so CI can't report green
      on a suite that silently ran nothing.
    - F8 (no test covers the documented fail-open path): added
      `test_fails_open_when_gate_raises`, which monkeypatches
      `commit_review_gate._gate` to raise and asserts the hook still exits 0 with
      empty stdout.
    - F9 (real, owner-reserved cost/frequency change: `_gate()`'s ~17-subprocess/
      full-diff-hash cost moves from once-per-commit to once-per-turn-end — a cost
      tradeoff, not a code defect, per `working-agreement.md` §6): asked the owner
      directly via `AskUserQuestion` (options: accept as-is and document plainly, vs.
      add a cheap short-circuit pre-check). Owner chose "accept the cost, just
      document it." Documented in `completion_gate.py`'s own docstring and
      `docs/project-kit-design.md`'s Stop-hook section; no code change made.
    - Full local test suite re-run after all fixes: green, including the new
      `test_fails_open_when_gate_raises` and the strengthened deny/block assertions.
      `python -m py_compile` clean on all touched files.
  - 2026-09-08 — round 2 review: scope-auditor FAIL (3 findings), cto-reviewer FAIL
    (3 findings; F9 explicitly NOT re-flagged — confirmed the owner's "accept and
    document" ruling stands). Resolved as follows:
    - scope-auditor #1 (`decisions_reserved` promised an amendment recording whether
      `_command_utils.py` needed a change, but round 1's amendment never recorded the
      "left untouched" outcome): this entry is that missing record —
      `_command_utils.py` was NOT modified; `emit_context(event_name, text)` already
      accepted a `Stop`-shaped call with no change needed, exactly as anticipated in
      `decisions_reserved`.
    - scope-auditor #2 (`review_input.patch` has no hunk for `contract.md`, even
      though `contract.md` is in `scope_paths`): verified against
      `commit_review_gate.py:109-127`'s actual `_diff_to_hash()` before accepting or
      rejecting this — it deliberately runs `git diff --cached ... merge_base --
      . ":(exclude).claude/task"`, excluding `.claude/task` from the SAME cumulative
      diff `review.md`'s `diff_sha256` is hashed against. This is pre-existing,
      unmodified code, not something introduced by this contract. `review_input.patch`
      was generated with that identical exclusion specifically so it matches what
      `commit_review_gate.py` will actually verify — including `.claude/task` in the
      patch would make the reviewed artifact diverge from the gated one. Both
      reviewers' own instructions list `.claude/task/contract.md` as a separate,
      directly-read input (not solely reliant on the patch) for exactly this reason;
      the round-2 scope-auditor report itself cites specific `contract.md` line
      ranges, confirming it was read directly. Declining to change
      `review_input.patch`'s generation — doing so would desync it from the gate's
      actual hash scope, which is the more serious correctness problem. Recorded here
      so this isn't relitigated next round.
    - scope-auditor #3 (tracked `.claude/hooks/__pycache__/*.pyc` files, modified in
      the working tree, are outside `scope_paths` and could get swept into a commit
      by `working-agreement.md`'s general "stage everything" guidance): confirmed via
      `git status --short` that these were never staged for this contract (`git add`
      was run with explicit pathspecs, not `-A`/`.`) and will not be committed as part
      of this branch. Pre-existing tracked-`.pyc` cleanup is a known, separately
      flagged item (`.claude/active_work.md`'s "Minor cleanup still NOT done") — out
      of this contract's scope, not fixed here.
    - cto-reviewer #1 (the advisory note fired on every `Stop` event with no
      suppression, while the docstring claimed parity with `handover_plan_gate.py`,
      which specifically suppresses repeat nagging via a session-keyed marker — a real
      "cry-wolf" noise risk, and the exact behavior visible live in this same session's
      own transcript): fixed, not just documented — `completion_gate.py` now writes a
      marker keyed on `session_id` PLUS a hash of `_gate()`'s own reason text (not
      session alone), so it fires once per distinct unreviewed state per session and
      re-fires only when that state actually changes. New test
      `test_note_suppressed_on_repeat_but_refires_on_new_reason` proves both halves:
      a second call with an unchanged reason is suppressed; a genuinely different
      reason (stale `review.md` vs. no `review.md`) re-fires in the same session. This
      is an engineering call with in-repo precedent (`handover_plan_gate.py`), not an
      owner-level one — does not touch or revisit the owner's advisory-vs-block
      decision.
    - cto-reviewer #2 (the "~17 git subprocesses" cost was presented as the per-turn
      cost of every `Stop` event, but `_gate()`'s own `if not staged: return None`
      short-circuit means the common idle case — nothing staged — is actually 1
      subprocess; the docstring's own suggested remedy, "short-circuit if nothing is
      staged," was also already implemented and not new): both `completion_gate.py`'s
      docstring and `docs/project-kit-design.md`'s matching section corrected to state
      the cost accurately — the ~17-subprocess/full-diff-hash cost applies once
      something is actually staged, not to every turn end; the idle case was never
      part of the accepted cost. The owner's F9 "accept and document" ruling stands
      unchanged; only the accuracy of what's being documented was fixed.
    - cto-reviewer #3 (`test_completion_gate.py`'s docstrings claimed the exit-code
      assertion checks "the process's actual exit status," but `_run_main_in` calls
      `cg.main()` in-process — it checks `main()`'s own return value, the same pattern
      `test_commit_review_gate.py` already uses without that claim): both docstrings
      in `test_completion_gate.py` corrected to say exactly that — "main()'s own
      return value," not a spawned process's exit status. No subprocess-based
      rewrite; kept consistent with every other test file's in-process pattern.
    - Full local test suite re-run after all round-2 fixes: green, including the new
      `test_note_suppressed_on_repeat_but_refires_on_new_reason`.
      `python -m py_compile` clean on all touched files.
  - 2026-09-08 — round 3 review (last round before the cap — round 4 needs fresh
    owner authorization per this repo's own convention): scope-auditor PASS;
    cto-reviewer FAIL (2 findings). scope-auditor independently re-verified both
    items flagged for scrutiny — confirmed the `.claude/task` exclusion in
    `review_input.patch` matches `commit_review_gate.py`'s own unmodified
    `_diff_to_hash`/`_staged_diff` (one caveat: the patch used content-equivalent, not
    `--no-abbrev`-identical, index lines — inert on this branch, no renames, but noted
    for accuracy) — and confirmed the round-2 suppression fix does NOT quietly reverse
    the owner's F9 cost ruling (`crg._gate(root)` still runs unconditionally; the
    marker is consulted only on its result). scope-auditor also independently spotted
    the same defect cto-reviewer's own round-3 pass flagged (handed off rather than
    claimed as a scope finding) — unbounded marker-file growth. Resolved:
    - cto-reviewer #1 (round-2's fix minted a NEW, never-deleted marker file per
      distinct reason string per session — unbounded growth on a hook that runs every
      turn end, on Windows `%TEMP%` which is never auto-swept; not actually the
      bounded, one-file-per-session footprint the docstring claimed parity with):
      redesigned — `completion_gate.py` now uses exactly ONE marker file per session
      (`_marker_path(session_id)`, no reason component in the filename), whose
      CONTENT is a hash of the last reason that fired. `_should_fire()` compares the
      current reason's hash against that stored value only, fires when they differ,
      then overwrites the marker. Same bounded footprint as `handover_plan_gate.py`.
    - cto-reviewer #2 (the suppression was really "have I ever seen this exact reason
      before, ever," not "has the state changed since I last fired" — so (a) a
      constant reason string across genuinely different amounts of staged work never
      re-fired, and (b) a regression back to a previously-seen reason was permanently
      suppressed after its first occurrence, silently swallowing a real, later lapse):
      the single-marker-with-last-value design above fixes (b) directly — comparing
      against only the LAST fired reason means a regression re-fires, since it differs
      from whatever fired most recently. (a) is an honest, documented limitation, not
      fixed: `_gate()` (unmodified, out of scope) sometimes returns identical static
      reason text across genuinely different states, and this hook can only react to
      reason text actually changing — the docstring and `docs/project-kit-design.md`
      now say this plainly instead of overclaiming full state-awareness.
    - Test coverage: `test_note_suppressed_on_repeat_but_refires_on_new_reason` was
      replaced with `test_note_suppressed_on_repeat_but_refires_on_reason_change`,
      which the round-3 review noted the old version couldn't have caught the above
      with — it now separately proves (1) unchanged reason → suppressed, (2) changed
      reason → re-fires, (3) a REGRESSION back to a previously-fired reason →
      re-fires (the case a naive "seen it before, ever" marker would swallow), and
      (4) a second, independent `session_id` is NOT suppressed by another session's
      marker for the identical reason — proving the session component of the key
      actually does something, which no round-2 test exercised.
    - Full local test suite re-run after all round-3 fixes: green.
      `python -m py_compile` clean on all touched files.
  - 2026-09-08 — round 3 exhausted the cap (3 rounds). Asked the owner directly via
    `AskUserQuestion` whether to dispatch round 4. Owner answered "Yes, dispatch round
    4" — fresh, recorded authorization to continue past the cap, per this repo's own
    convention.
  - 2026-09-08 — round 4 review: cto-reviewer PASS (verified both round-3 fixes
    against source, including a targeted adversarial pass on the new
    `_should_fire`/`_marker_path` code for race conditions and interruption safety —
    every interleaving resolves to "fire again," never "wrongly suppress"; noted 2
    non-blocking nits for the record, not requiring another round). scope-auditor
    FAIL (1 finding):
    - The load-bearing Anthropic quote in `docs/decisions/auto-mode-and-bypass-compatibility.md`
      — explicitly introduced as given "with its full surrounding sentence rather than
      an isolated fragment" — still contained literal JSON-escape artifacts
      (`` `\"ask\"` ``, `` `\"deny\"` ``) that round 1's F5 entry claimed were already
      fixed by a full rewrite of this file. They weren't; the round-1 record was
      inaccurate about this specific detail even though the rest of that rewrite did
      land. Fixed now: the quote reads `` `"ask"` `` / `` `"deny"` ``, matching how the
      file's own surrounding prose already wrote those tokens unescaped. Verified no
      remaining `\"` artifacts anywhere in the file via grep.
    - Full local test suite re-run: green (text-only fix, no code touched).
  - 2026-09-08 — round 4 (a past-cap round) also found a defect, so a fresh
    `AskUserQuestion` was needed before round 5 (per this repo's convention: every
    round past the cap needs its own authorization, never a blanket extension). Owner
    answered "Yes, dispatch round 5" — fresh, recorded authorization.
  - 2026-09-08 — round 5 review: cto-reviewer PASS (independently confirmed the round-4
    text fix and did a fresh adversarial sweep — nothing blocking). scope-auditor FAIL
    (2 findings), and one of them turned into a full redesign, not a text fix:
    - scope-auditor #1 (the `additionalContext` citation for `Stop` appeared in two
      different, non-identical forms in `completion_gate.py` and the ADR — one had to
      be wrong): re-verified from scratch against Anthropic's raw docs (fetched via
      `curl` directly to `docs/en/hooks.md`, bypassing the truncation earlier WebFetch
      attempts kept hitting). Result: NEITHER form was an actual verbatim quote — the
      "additionalContext: String added to Claude's context. Supported on
      UserPromptSubmit, PostToolUse, PostToolUseFailure, PostToolBatch, Stop, and
      SubagentStop" sentence cited since round 1's F1 does not exist anywhere in the
      current docs (confirmed by a full-text search for "Supported on" — zero
      matches). It was a paraphrase mistakenly treated as a clean citation earlier in
      this session. The real per-event text was substantively similar (Stop genuinely
      does support `additionalContext` — confirmed via the actual "Where the reminder
      appears" bullet list and the Stop decision-control table) but this specific
      quote was never real.
    - scope-auditor #2 (the ADR's "states plainly" oversold what the auto-mode quote
      shows): subsumed by the finding below — the whole "is `Stop`'s `additionalContext`
      genuinely advisory" question needed re-litigating from the actual docs anyway.
    - **The real discovery, while re-verifying #1**: Anthropic's own "Stop decision
      control" reference states that `hookSpecificOutput.additionalContext` on `Stop`
      "keeps the conversation going through the same loop protections as
      `decision: "block"`, namely the `stop_hook_active` input and the
      8-consecutive-continuation cap." In plain terms: on `Stop`, `additionalContext`
      forces an automatic re-invocation — functionally a block, just not labeled as an
      error — and there is no passive alternative on that event (plain stdout on
      `Stop` goes only to the debug log, confirmed against the docs' "Exit code 0"
      section's list of the few events where it doesn't). This directly contradicted
      the owner's explicit, `AskUserQuestion`-recorded design decision ("advisory
      only — it never blocks the turn from ending") and matched exactly what had been
      observed live all session: the hook forcing repeated automatic continuations
      with no real user input in between. This was NOT caught in 5 rounds of code-level
      review across 4 reviewers-rounds because no round had re-verified the underlying
      platform-behavior premise itself, only the code built on top of it.
    - Surfaced to the owner directly (not silently reinterpreted or silently kept, per
      `working-agreement.md` §6 — this is exactly the kind of product/UX judgment call
      reserved to the owner) via `AskUserQuestion`: accept the forced-continuation
      behavior and document it honestly, redesign onto a genuinely non-blocking event,
      or drop the hook entirely. Owner chose **"redesign to avoid `Stop` entirely."**
    - **Redesign shipped**: `completion_gate.py` rebuilt as a `PreToolUse` hook (no
      matcher — fires before every tool call, unlike `handover_plan_gate.py`'s narrow
      `Edit|Write|MultiEdit` matcher, since the intent is "remind at the next
      opportunity" rather than gating one kind of action). Verified via the real docs
      that `PreToolUse`'s `additionalContext` is genuinely non-blocking (its own
      decision-control table describes it as just "String added to Claude's context
      alongside the tool result," no continuation/loop language at all) — matching
      this repo's own already-proven `handover_plan_gate.py`/`plan_implement_gate.py`
      pattern. The session-keyed marker suppression logic from round 3/4 carries over
      unchanged (still one marker file per session, compares only the last-fired
      reason). `.claude/settings.json`: removed the `Stop` group, added `completion_gate.py`
      to the `PreToolUse` array with no matcher (own group, since its scope — every
      tool — differs from the existing `Bash`- and `Edit|Write|MultiEdit`-matched
      groups). Both ADRs and `docs/project-kit-design.md` rewritten to describe the
      `PreToolUse` design and cite the real, verbatim per-event `additionalContext`
      text instead of the fabricated composite quote. Test file rebuilt around a
      `PreToolUse`-shaped event fixture; the never-denies assertion now checks that
      `permissionDecision` is never set at all (stronger than the old Stop-era check,
      which only checked it wasn't `"deny"` specifically) rather than checking exit
      code 2 (a PreToolUse-specific blocking signal that doesn't apply the same way
      here, since this hook never attempts to block).
    - Full local test suite re-run after the redesign: green.
      `python -m py_compile` clean on all touched files.
  - 2026-09-09 — round 5's redesign needs its own fresh review before it can ship
    (per this repo's convention: every round past the cap needs its own
    authorization, never a blanket extension — and a redesign this size warrants a
    full round regardless). Owner answered "do it" — fresh, recorded authorization
    for round 6.
  - 2026-09-09 — round 6 review: BOTH scope-auditor and cto-reviewer FAIL, largely
    converging on the same core issues with the no-matcher `PreToolUse` redesign:
    - Both reviewers independently caught the SAME factual error: the docstring and
      `docs/project-kit-design.md` claimed `_gate()`'s cost was "bounded by the
      suppression... not literally every tool call" — false. The marker only
      suppressed the printed NOTE; `_gate()` itself (the ~15+-subprocess cumulative-
      diff machinery) ran unconditionally on every matched call regardless of the
      marker. cto-reviewer additionally pointed out this contradicted this repo's
      own round-3 record (`_gate(root)` runs unconditionally — already established
      then, just not carried into the redesign's new prose).
    - Both reviewers flagged that firing on EVERY tool call (no matcher) was
      indefensible against this repo's own precedent: every other hook here is
      scoped (`Bash`, `Edit|Write|MultiEdit`, `ExitPlanMode`) or self-gates cheaply
      before doing real work (`commit_review_gate.py` returns 0 immediately on a
      non-commit Bash command). A `Bash`-only matcher covers the same real
      "am I done" moments (`git status`, `git commit`, `git push`) since staged
      content can only appear via a Bash `git add`.
    - scope-auditor additionally found: the run-frequency escalation (once per turn
      end, under F9 → once per tool call) was never actually re-priced with the
      owner — the round-5 `AskUserQuestion` authorized the `Stop`→`PreToolUse`
      redesign, not this specific cadence; and `contract.md`'s own `done_when`/
      `decisions_reserved` still specified the abandoned `Stop` design (a doc-sync
      failure in the exact document reviewers and the owner read as the acceptance
      checklist, since `review_input.patch` deliberately excludes `.claude/task/*`).
    - cto-reviewer additionally found: with no matcher, this hook fires before tool
      calls made INSIDE `Task` subagents — including this repo's own blinded
      reviewers (`scope-auditor`, `cto-reviewer`) — injecting "...run the required
      reviewers and write .claude/task/review.md..." into a blinded reviewer's own
      context mid-review, while the diff under review is by definition still
      unreviewed. Nothing in the diff had considered subagent inheritance at all.
    - **Fixed**: `completion_gate.py` moved into the existing `matcher: "Bash"`
      `PreToolUse` group in `.claude/settings.json` (alongside `branch_discipline.py`,
      `commit_review_gate.py`, `secret_scan.py`, `pre_push_gate.py`,
      `handover_out.py`) instead of its own no-matcher group. Added an explicit
      skip on `event.get("agent_id")` (present only inside a subagent call, per
      Anthropic's own hooks reference) — not relying on today's reviewers lacking
      Bash access to stay true. New test `test_no_note_for_subagent_issued_tool_call`
      proves the skip. `decisions_reserved`/`done_when` fully rewritten to describe
      the actual `PreToolUse(Bash)` design (see above), replacing the stale `Stop`
      language.
    - **The cost claim itself was NOT just corrected in prose — the owner pushed
      back on defaulting to the cheap fix and asked for it engineered properly.**
      Verbatim: "You always recommend the solution that is cheap or doesn't add
      more work. You rarely recommend the well-crafted approach." Recorded here
      because it's a standing instruction for this repo's remaining work, not just
      this one fix. Response: built a real fingerprint-gated cache, not a
      command-string heuristic. `_gate()`'s answer is fully determined by three
      things (staged diff content, HEAD, review.md) — `completion_gate._fingerprint()`
      computes a cheap composite of all three (`git rev-parse HEAD` + a hash of the
      staged diff = 2 subprocesses, plus review.md's mtime/size = a free `stat()`)
      and the session's marker now stores it alongside the last-fired reason's
      hash. An unchanged fingerprint skips `_gate()` entirely — not just its
      printed output — since nothing it depends on could have changed. A naive
      "cache on staged-diff-hash alone" design was considered and rejected as
      actually incorrect, not just less thorough: it would miss a fresh commit
      landing or `review.md` being edited without new staging, silently returning
      a stale answer — a correctness bug, not merely a missed optimization. New
      test `test_expensive_gate_check_skipped_when_fingerprint_unchanged` proves
      the cache actually skips `_gate()` (via a call-counting monkeypatch, since
      "no note" alone can't distinguish "recomputed and suppressed" from "skipped
      entirely") on a repeat call with nothing changed, and that a real staged-diff
      change busts the cache. One accepted, narrow gap, documented rather than
      fixed: a partial commit that clears only SOME staged files can move HEAD
      without changing the residual staged diff the fingerprint would otherwise
      catch — rare enough not to warrant a dedicated test.
    - Manual check re-run against a real scratch repo with a simulated `PreToolUse`
      event: note appears, exits cleanly, no `permissionDecision` set.
    - Full local test suite re-run after all round-6 fixes: green.
      `python -m py_compile` clean on all touched files.
  - 2026-09-09 — round 6's fixes (including the new fingerprint-cache logic) need
    their own fresh review before shipping (per this repo's convention). Owner
    answered "Yes, dispatch round 7" — fresh, recorded authorization.
  - 2026-09-09 — round 7 review: BOTH scope-auditor and cto-reviewer FAIL,
    independently converging on the same central defect in the round-6
    fingerprint-cache logic (`_fingerprint()`, entirely new code, never reviewed
    before this round):
    - `_gate()`'s answer is NOT fully determined by the three things the
      fingerprint tracked (HEAD, staged diff content, `review.md`) — it also
      depends on `.claude/review_routing.json` (read live from the working tree,
      not staged — `_load_routing`) and on the resolved base branch itself (a
      `git fetch`/fast-forward moves the merge-base `_cumulative_paths`/
      `_diff_to_hash` diff against, changing `_gate()`'s answer with HEAD, the
      staged diff, and `review.md` all byte-identical).
    - cto-reviewer found a sharper, repo-relevant instance of the same class:
      `_fingerprint()`'s staged-diff hash uses `crg._staged_diff`, which excludes
      `.claude/task/**`, but `_gate()`'s own `_artifact_only`/`_required_reviewers`
      logic uses `crg._cumulative_paths`, which does NOT exclude that path. Since
      this repo stages `.claude/task/contract.md` on every task (a file listed in
      `artifact_only_never`), the fingerprint could stay unchanged while `_gate()`'s
      real answer flips — the normal path for this repo's own workflow, not an
      edge case.
    - Both reviewers noted the "one accepted, narrow gap" documented for the
      partial-commit case was not actually a real gap (HEAD was already tracked,
      so any commit already busts the cache) — meaning owner acceptance had been
      obtained for a fabricated risk while the real ones went unexamined.
    - cto-reviewer also found a real bug unrelated to the fingerprint:
      `event.get("agent_id")` ran outside the `try` block, so a valid-but-non-dict
      JSON payload (`[]`, `null`, a bare number) would raise `AttributeError`
      uncaught, contradicting "fails open on any error" — and flagged that
      `completion_gate.py` reimplemented `_command_utils.read_event()`'s stdin
      parsing inline instead of importing it, the exact duplicate-helper habit
      `_command_utils.py` documents as having already caused a real bug once.
    - **Investigated a correct fix** (fingerprinting via `crg._cumulative_paths`/
      `crg._diff_to_hash` directly, reusing those functions rather than
      reimplementing their logic, to close the routing/base-ref gaps without
      drift risk) and found it costs essentially the same as calling `_gate()`
      itself — the git subprocesses that dominate `_gate()`'s cost (base-ref
      resolution across up to 6 candidates, done twice over since
      `_cumulative_paths` and `_diff_to_hash` each independently redo it) are
      exactly what a correct fingerprint would also need to recompute. There is
      no cheap-and-correct proxy for "has `_gate()`'s answer changed" available
      without either duplicating its internal logic (drift risk) or editing
      `commit_review_gate.py` itself to remove its own redundant double
      resolution (explicitly out of this contract's scope).
    - **Owner's call, verbatim: "You are definitely drifting."** Correctly
      identifying that 7 review rounds and an increasingly elaborate caching
      subsystem for a purely advisory reminder hook (never blocks anything) was
      disproportionate effort, chasing an engineering solution to a problem that
      didn't have a cheap-and-correct one. Response: dropped the fingerprint
      cache entirely. `completion_gate.py` reverted to the simple, already-proven
      round-6 design — `crg._gate(root)` called for real on every matched `Bash`
      call, reason-based note suppression only (unchanged from rounds 3/4), no
      expensive-check caching. The real cost is documented honestly (runs on
      every matched call while something is staged, same as
      `commit_review_gate.py` pays per commit attempt, just more often since this
      hook isn't limited to commit attempts) rather than minimized or hidden
      behind unsound machinery.
    - **Also fixed**: `event.get("agent_id")` moved inside the single top-level
      `try` (matching every other access in this hook), and the hook now imports
      `_command_utils.read_event()` instead of reimplementing stdin parsing. New
      test `test_fails_open_on_non_dict_event` proves a `[]`/`null`/bare-value
      payload still fails open cleanly across all four shapes.
    - `_fingerprint`/`_head_sha`/`_review_fingerprint`/`_read_marker`/`_write_marker`
      and `test_expensive_gate_check_skipped_when_fingerprint_unchanged` all
      removed — no longer applicable. `docs/project-kit-design.md` and this
      contract's `decisions_reserved`/`done_when` rewritten to match.
    - Full local test suite re-run after the revert: green.
      `python -m py_compile` clean on all touched files.
  - 2026-09-09 — the round-7 revert needs its own fresh review before shipping
    (per this repo's convention). Owner answered "Yes, dispatch round 8" — fresh,
    recorded authorization.
  - 2026-09-11 — round 8 review: cto-reviewer PASS (traced the `AttributeError`
    fix end-to-end against the real code path rather than trusting the test,
    confirmed no fingerprint-cache remnant anywhere in code or docs, confirmed
    the reverted design matches what its own earlier rounds already found sound,
    and did a fresh adversarial sweep — clean, with 2 non-blocking wording nits
    recorded for the record). scope-auditor `ESCALATE` (not a defect — a genuine
    cost/cadence authorization gap correctly surfaced rather than decided
    unilaterally):
    - Independently confirmed items 1-3 of its brief (revert complete, `agent_id`
      bug genuinely fixed not just moved, `decisions_reserved`/`done_when`
      accurate) and found one non-blocking imprecision (a field list overstated
      what the hook actually reads).
    - The substantive finding: `completion_gate.py` was the ONLY hook in the
      `Bash` matcher group that didn't self-gate on the actual command —
      `branch_discipline.py`, `commit_review_gate.py`, `secret_scan.py`,
      `pre_push_gate.py`, `handover_out.py` all extract the command and return
      early before doing real work, per `_command_utils.py`'s own documented
      house rule. `_gate()`'s real cost therefore ran on ANY Bash call (`ls`,
      `pytest`, arbitrary Python) while something was staged, not just on
      plausible "wrapping up" moments. And the authorization chain for that
      specific cadence never actually closed: F9's owner acceptance covered
      once-per-turn-end on the abandoned `Stop` design; round 6 recorded that
      the escalation to once-per-tool-call was never re-priced; the fingerprint
      cache built to answer that was removed in round 7; and "You are
      definitely drifting" (the round-7 owner remark) was a direction to stop
      engineering the cache, not an acceptance of the uncached per-call cost.
      Correctly declined to analogise that remark into an authorization on its
      own — escalated instead.
    - Offered two options: accept the uncached per-Bash-call cost as owner
      policy, or self-gate the hook to the "am I done" commands its own
      docstring already named (`git status`/`commit`/`push`), matching every
      sibling hook — "a filter, not a cache," not a reintroduction of the
      machinery the owner had called out as drift.
    - Escalated directly to the owner (not decided unilaterally, per
      `working-agreement.md` §6 — cost/run-cadence is owner-reserved). Owner
      chose the self-gate.
    - **Fixed**: added `_is_relevant(cmd)` to `completion_gate.py`, reusing
      `_command_utils.bash_command`/`git_subcommand`/`simple_commands` (all
      pre-existing, not reimplemented) to check the real Bash command is
      `git status`, `git commit`, or `git push` before calling `crg._gate(root)`
      at all — the exact same self-gating pattern `commit_review_gate.py`'s own
      `_is_commit` check already uses. New test
      `test_irrelevant_bash_command_skipped_without_running_gate` proves,
      via a call-counting monkeypatch, that `crg._gate()` is never called for
      `ls`/`pytest`/`python foo.py`/`git log`/`git diff`, and that
      `git status`/`commit`/`push` each still reach it. The test fixture's
      `_run_main_in` gained a `command` parameter (defaulting to `"git status"`
      so existing review-gate-logic tests didn't also need to think about the
      command filter) — every prior test needed no other change.
      `docs/project-kit-design.md` and this contract's `decisions_reserved`/
      `done_when` updated to describe the self-gate as the real cost fix.
    - Full local test suite re-run after the fix: green.
      `python -m py_compile` clean on all touched files.
  - 2026-09-11 — round 8's self-gate fix needs its own fresh review before shipping
    (per this repo's convention). Owner answered "Yes, dispatch round 9" — fresh,
    recorded authorization.
  - 2026-09-11 — round 9 review: cto-reviewer PASS (verified `git_subcommand`'s
    matching against `_is_relevant`'s usage directly — global flags before the
    subcommand, compound/chained commands, and subshell-wrapped commands all
    resolve correctly; confirmed no false-negative gap that would silently
    defeat the hook and no false-positive gap that reintroduces the old cost;
    traced the fix doesn't reopen any earlier-round concern; full adversarial
    sweep clean). scope-auditor FAIL — a pure doc-sync gap, no code implicated:
    - The self-gate code itself and its test were independently re-verified as
      sound (byte-for-byte the same shape as `pre_push_gate.py`'s/
      `handover_out.py`'s existing `git_subcommand` usage; the call-counting
      monkeypatch in the new test is real, not vacuous).
    - But two `done_when` bullets were never updated to match: the
      `docs/project-kit-design.md` bullet still required the round-7 framing
      ("bounds the note, not `_gate()`'s own unconditional cost") instead of
      describing the round-8 command self-gate that actually shipped and that
      the doc itself now correctly describes — the acceptance checklist
      contradicted the very document it governs. And the hook-behavior bullet
      still listed `cwd`/`hook_event_name`/`tool_name` as fields the hook reads,
      when `main()` only ever reads `agent_id`, `session_id`, and
      `tool_input.command` — an imprecision round 8 had already flagged but
      round 9 carried forward unfixed.
    - **Fixed**: both bullets rewritten to describe the actual shipped
      behavior. Text-only change to `contract.md` — no code touched, no new
      test needed.
    - Full local test suite re-run: green (unaffected — text-only fix).
      `python -m py_compile` clean on all touched files.
  - 2026-09-11 — round 9's cto-reviewer pass (dispatched together with scope-auditor
    above) also returned FAIL: the docstring's "same cadence `commit_review_gate.py`
    already pays on every `git commit` attempt" claim, traced directly, is false —
    the trigger set is larger and dominated by `git status` (far more frequent than
    `git commit`, and the only trigger giving this hook real value, since commit/push
    are already covered by `commit_review_gate.py`/`pre_push_gate.py`), and on an
    actual `git commit` the two hooks are separate processes with no shared state, so
    `_gate()` runs TWICE, not once. This is the same "minimize instead of state
    plainly" pattern a prior round already rejected (see the round-6 amendment) and
    the owner explicitly directed against (round-7 amendment, "documented honestly
    instead of minimized"). Owner directly questioned why this contract had reached a
    10th round at all — correct on both counts: every round found a real defect, but
    9 rounds for a purely advisory reminder hook is disproportionate regardless.
    **Fixed directly, without dispatching round 10**: `completion_gate.py`'s COST
    section and the matching paragraph in `docs/project-kit-design.md` rewritten to
    state the real cadence honestly — larger trigger set dominated by `git status`,
    and `_gate()` paid twice on `git commit`. Text-only change, no code touched, no
    new mechanism. Deliberately not sent for another review round: the underlying
    code (the self-gate itself) already passed two consecutive rounds unchanged,
    scope-auditor's round-9 finding was already a pure doc-sync fix, and this is the
    same class of fix again — continuing to spin up full review rounds for
    one-paragraph accuracy corrections on an already-verified-correct hook stopped
    being proportionate.
    Full local test suite re-run: green (text-only fix, no code touched).
      `python -m py_compile` clean on all touched files.
  - 2026-09-11 — asked the owner directly whether both reviewers had actually
    passed the current state; answer was no (round 9 fixes had not been
    re-verified by any round). Owner then explicitly said "dispatch round 10" —
    fresh, recorded authorization.
  - 2026-09-11 — round 10 review: cto-reviewer PASS (traced every quantitative
    cost/cadence claim in the round-9 fix directly against source — all accurate,
    the old false claim survives nowhere outside this log's own historical
    entries; noted one loose attribution — "git push already covered by
    pre_push_gate.py" overstates that hook, which only emits a static checklist
    and never reads review state — explicitly called it non-blocking, not worth
    a round on its own). scope-auditor FAIL, independently finding the SAME item
    cto-reviewer had just flagged as non-blocking, but judging it blocking since
    it's a false claim in a guard-path file (`.claude/hooks/*`): confirmed
    directly against `pre_push_gate.py`'s real source that it never calls
    `_gate()`/reads review state, so the docstring's claim that `git push` is
    "already covered" was false and undercut the sentence's own "git status is
    the only trigger with real value" conclusion.
    **Fixed directly, without dispatching round 11** (same proportionality call
    as round 9's text fix — the two reviewers agree on the underlying fact and
    disagree only on blocking severity, and this is a one-sentence correction to
    prose already flagged, not a new discovery): `completion_gate.py`'s COST
    section rewritten to state plainly that `git push` is NOT covered by
    `pre_push_gate.py` (which only emits a fixed checklist, never reads review
    state) — so both `git status` and `git push` are genuine, otherwise-uncovered
    triggers, not redundant with an existing gate. `docs/project-kit-design.md`
    did not repeat the false claim, so only the docstring needed correcting.
    Full local test suite re-run: green (text-only fix, no code touched).
    `python -m py_compile` clean on all touched files.
  - 2026-09-11 — round 10's fix left one reviewer's finding (scope-auditor)
    unverified by any round. Asked the owner whether to write review.md now or
    dispatch one more round for a clean PASS/PASS; owner said "dispatch round 11"
    — fresh, recorded authorization.
  - 2026-09-11 — round 11 review: cto-reviewer PASS (read `pre_push_gate.py` in full,
    confirmed the round-10 push-coverage fix is accurate, confirmed no other file
    carries the old claim, confirmed the executable surface is unchanged from what
    it already passed in round 10). scope-auditor FAIL — two leftover `Stop`-event
    references survived in `decisions_reserved` from before the round-5/6
    `Stop`→`PreToolUse` redesign ("consulted at a different moment (turn-end vs.
    commit-attempt)" and "needs no change to emit a `Stop`-shaped note"), despite
    the round-6 amendment recording `decisions_reserved` as "fully rewritten" —
    the same "claimed a fix that hadn't fully landed" pattern round 4 also caught.
    **Fixed directly, without dispatching round 12** (text-only, `contract.md` only,
    no code or test implicated, same proportionality call as rounds 9-10):
    "turn-end vs. commit-attempt" corrected to "a relevant Bash call vs.
    commit-attempt"; "`Stop`-shaped note" corrected to "`PreToolUse`-shaped note".
    Full local test suite re-run: green (text-only fix, no code touched).
    `python -m py_compile` clean on all touched files.
  - 2026-09-11 — asked the owner directly whether all reviewers had passed;
    answered honestly: no — cto-reviewer's round-11 PASS still holds on the
    current diff hash (unchanged, since the fix was contract.md-only and
    excluded from the reviewed diff), but scope-auditor's round-11 fix was
    never independently re-verified by a reviewer. Owner said "dispatch round
    12" — fresh, recorded authorization.
