# Task contract

objective: Add a tracker-based roadmap convention (no roadmap/backlog markdown files, ever)
and a Solo/small vs. Standard process tier to `/setup-project`'s interview, generalizing two
things the owner had already validated for real: `football-data-pipeline`'s "roadmap lives
in the tracker" fix, and the observation that this kit's own process weight never scales
down for a small project.

tracking_issue: (none — this repo doesn't use an issue tracker for its own work yet;
`.claude/active_work.md` is the handover mechanism instead)

scope_paths:
  - .claude/task/contract.md
  - .claude/working-agreement.md
  - task/CONTRACT_TEMPLATE.md
  - templates/working-agreement-solo.md.tmpl
  - templates/known-working-agreement-digests.json
  - templates/starter-README.md.tmpl
  - scripts/preview_project_setup.py
  - scripts/generate_project_setup.py
  - .claude/skills/setup-project/SKILL.md
  - .claude/tests/test_preview_project_setup.py
  - .claude/tests/test_generate_project_setup.py
  - docs/project-kit-design.md
  - docs/decisions/tracker-convention-and-process-tier.md
  - README.md

decisions_reserved:
  - Whether to build this at all, and the two-tier shape (Solo/small vs. Standard) — owner
    confirmed via AskUserQuestion ("Yes, build as described").
  - Whether to invent the design from scratch or generalize an existing, validated pattern —
    owner explicitly redirected to check `football-data-pipeline` first ("You may check how
    it's done in football data repo... so you don't need to invent something that is already
    in place"). Result: the tracker convention is a direct generalization of that repo's real
    fix; the process-tier mechanism is NOT reused from anywhere, because that repo doesn't
    have one either — confirmed as genuinely new, not a duplicate.
  - This kit's own repo stays at Standard/full-weight regardless of tier — not offered as a
    choice, consistent with CLAUDE.md's existing "hold the bar accordingly" reasoning for
    other repos building on this one.

done_when:
  - working-agreement.md and CONTRACT_TEMPLATE.md state the tracker rule.
  - /setup-project's interview asks for a tracker and a process tier, mirroring the existing
    CI-provider question's shape (tracker-agnostic, not hardcoded to GitLab).
  - generate() writes a tracker-guidance line into the starter README regardless of tier, and
    reconciles working-agreement.md with the selected tier asymmetrically: Solo always
    converts (protected by a hand-customization check, overridable with --force); Standard
    only ever writes to reverse a recognized prior Solo choice, fill a missing file, or when
    --force is passed — never to opportunistically rewrite an existing standard file of any
    vintage. Recognition (both the hand-customization check and "was this Solo?") is based on
    a static, shipped digest list, not a git-history reconstruction.
  - Full test suite (.claude/tests/) passes.
  - A short ADR records the decision and its reasoning (docs/decisions/).

amendments:
  - 2026-09-17 — platform-reviewer's first review pass (opus) FAILed on four real
    defects, all fixed:
    1. `_working_agreement_needs_force` compared target content against the CURRENT
       checkout's `.claude/working-agreement.md` — a version-fragile reference that would
       misreport any target bootstrapped from an older kit as hand-customized the moment
       this file next changed, permanently locking it out of ever changing tier (since
       `bootstrap.sh`'s `keep_file` never refreshes an existing file and the interview never
       passes `--force`). Fixed: reconstructs the target's actual historical default via
       `.claude/.kit-version` + `git show <sha>:.claude/working-agreement.md` against the
       kit's own history, added to the recognised-states set.
    2. The tier switch was one-way (`process_tier="standard"` wrote nothing), while
       `preview_project_setup.py`'s note and the CLI's own printed summary both implied
       Standard was actively in place. Fixed: `generate()` now converges to whichever tier
       is selected, bidirectionally, with a corrected CLI summary line.
    3. The new tests could only exercise the same-checkout case, so they couldn't have
       caught #1. Fixed: added a test using this repo's own real git history to simulate a
       prior kit version, plus a bidirectional-restore test.
    4. `tracker_provider`/`process_tier` reached a bare dict lookup (`KeyError`) on any
       value outside the CLI's `choices=`, unlike every sibling check in the same functions
       which raises a clear, human-readable error. Fixed: explicit validation in both
       `generate()` (`GenerationRefused`) and `build_preview()` (`ValueError`).
    The ADR (`docs/decisions/tracker-convention-and-process-tier.md`) was updated to
    describe the fixed mechanism accurately instead of the version-fragile one it
    originally claimed was "the same check" as `guard-paths.md`'s.
  - 2026-09-17 — platform-reviewer's second review pass (opus, round 2) FAILed on four
    more real defects — round 1's fix for #1 above had a real side effect nobody caught
    at the time:
    1. Fix #1 correctly stopped *refusing* an old-but-genuine standard file — but the
       write logic converged BOTH tiers unconditionally, so "no longer refused" silently
       became "silently rewritten": a Standard-tier run against a target on an older kit
       release would overwrite its project-owned `working-agreement.md` (the same file
       `bootstrap.sh`'s `keep_file` treats as project-owned, never clobbered without
       `--force`) with no `--force` and no prompt — while `.claude/skills/setup-project/SKILL.md`'s
       own confirm prompt and closing summary still said the file is "only" ever replaced
       for Solo. Fixed: the write logic is now asymmetric — Solo converts whatever's
       there; Standard only ever writes to reverse an explicit prior Solo choice
       (current content is byte-for-byte the solo template) or fill in a missing file,
       never to "modernize" an already-standard file of any vintage. `SKILL.md` and
       `docs/project-kit-design.md` corrected to describe this precisely instead of the
       simpler-but-wrong "only Solo touches it" framing.
    2. The regression test for round 1's own fix depended on `git log --follow` against
       THIS repo's own git history, which a shallow `actions/checkout` (the default) never
       has enough of — the test silently `SkipTest`s in CI and the runner counts a skip as
       a pass, so the exact branch round 1 fixed was never actually exercised in the gate.
       Fixed: replaced with a throwaway git repo built inline in the test itself,
       independent of this repo's history or clone depth.
    3. The prior-kit-version test asserted only "must not raise," never what happened to
       the file — it couldn't have caught #1 even if it had run. Fixed: now asserts the
       file's exact content after both a Standard-tier run (untouched) and a Solo-tier run
       (converted), against the same throwaway-repo fixture.
    4. `.claude/.kit-version` content was interpolated into a `git show` argv element
       unvalidated (a leading `-` would be parsed as an option, not a rev) and
       `except OSError` didn't catch `subprocess.TimeoutExpired`. Fixed: a
       `re.fullmatch(r"[0-9a-fA-F]{7,40}", sha)` guard before the subprocess call, and the
       except clause now also catches `TimeoutExpired`.
  - 2026-09-17 — platform-reviewer's third review pass (opus, round 3 — this repo's cap)
    FAILed on three more real defects, the first a fundamental flaw in the git-reconstruction
    mechanism itself, not another edge case:
    1. `_historical_standard_working_agreement`'s whole premise breaks under this kit's own
       documented upgrade path (`README.md`: re-run `bootstrap.sh`, then re-run
       `/setup-project`): `bootstrap.sh` overwrites `.claude/.kit-version` on EVERY re-run
       (`always overwritten, never keep_file semantics`), while `working-agreement.md` is
       `keep_file`-protected (copied only if absent). After a routine re-bootstrap, the
       stamped SHA points at a newer kit release than the file actually on disk, so the
       git-reconstructed "historical" content doesn't match reality — reinstating the exact
       Solo-tier lockout round 1 was meant to fix, for the single most common real-world
       sequence (upgrade, then tailor).
    2. `--force` was documented (CLI `--help`, `SKILL.md`) as able to override a
       hand-customized `working-agreement.md` in Standard tier too, but the Standard write
       path never checked `force` — a silent no-op, no escape hatch, untested.
    3. Standard's "was this a prior Solo choice?" check only compared against the CURRENT
       solo template — no historical lookup on that side either — so once that template is
       ever edited, an older Solo file goes unrecognized and Standard silently leaves it
       alone while `SKILL.md` told the agent to narrate a false reason ("already standard").

    **CPO ANSWER** (owner decision via `AskUserQuestion`, "Rebuild on a static digest list
    (recommended)"): rounds 1-3 all trace to one root cause — choosing a clever mechanism
    (git-subprocess reconstruction of historical content from a stamped SHA) over a boring
    one, which turned out to have a real coupling assumption (`.kit-version` and
    `working-agreement.md` refresh in lockstep) that `bootstrap.sh`'s own documented
    conventions violate by design. Authorized: round 4 (past the 3-round cap) rebuilds the
    entire hand-customization/tier-recognition mechanism on a static, shipped digest list —
    `templates/known-working-agreement-digests.json`, one sha256 per released default per
    tier, appended whenever either template changes, verified by a parity test (same shape
    as the existing `test_routing_doc_parity.py`) — removing the git subprocess, the
    `.kit-version` dependency, and the clone-depth sensitivity entirely, and fixing #2 and #3
    above in the same pass (force now applies to Standard too; Standard's "was this Solo?"
    check becomes a digest-map lookup instead of a single current-template comparison).
  - 2026-09-17 — platform-reviewer's fourth review pass (opus, round 4 — the owner-authorized
    rebuild) FAILed on the first version of the rebuild, six findings (one about process, five
    real, two of them serious):
    1. The shipped digest list contained only the two CURRENT templates — no historical
       backfill — and this diff also modifies `.claude/working-agreement.md`, which
       `bootstrap.sh`'s `keep_file` never refreshes in an existing target. Every project
       bootstrapped before this merge therefore hashes to an unlisted digest, reproducing
       round 1's exact Solo-tier lockout on an untouched file. Fixed: backfilled every
       distinct historical version of `.claude/working-agreement.md` at AUTHORING time (a
       one-time `git log --follow` read of this repo's own history, computed once and baked
       into the static JSON file — never resolved again at runtime, so none of rounds 1-3's
       coupling problems apply).
    2. The `force=True` fix let Standard tier overwrite working-agreement.md in ANY state,
       including a RECOGNISED older-standard file — reintroducing round 2's silent-rewrite
       defect via the flag instead of via the recognition gap, and contradicting `README.md`
       and this file's own code comment. Fixed: narrowed to `current_tier is None and force`
       — force only ever overrides an unrecognised (hand-customized) file; a recognised
       standard or Solo file of any vintage is always left alone regardless of the flag.
    3. Two round-3 regression tests asserted only that a fabricated dict returned the value
       the test itself put into it, then separately called `generate()` against the REAL
       (at-the-time historyless) digest list where the content was unrecognised — so both
       passed for the wrong reason and neither would have caught finding 1 above. Fixed:
       `generate()` and `_working_agreement_needs_force` gained an injectable
       `working_agreement_digests` parameter (matching the existing
       `guard_paths_tmpl`/`readme_tmpl`/`kit_routing_file` pattern), and both tests rewritten
       to drive `generate()` end-to-end with a historical entry actually in scope.
    4. The review input patch handed to this round's reviewer was stale (generated before a
       proactive fix — digest-loader error handling, see below — was made, mid-round).
       Caught and flagged by the reviewer itself, who reviewed the real on-disk code instead
       of trusting the stale patch. Lesson: always regenerate `review_input.patch`
       immediately before spawning a review, not once at the start of a round.
    Separately (not a reviewer finding — proactively fixed before this round's review landed,
    once its absence became obvious while re-reading the digest-loading code): 
    `_load_known_working_agreement_digests` had no error handling for a missing/malformed
    digests file, unlike every other content check in this module. Fixed: raises
    `GenerationRefused` on a missing file, invalid JSON, or an unexpected shape, with a test
    covering all three cases plus a missing `"digests"` key.
  - 2026-09-17 — platform-reviewer's fifth review pass (opus, round 5) FAILed on four smaller
    findings — no more silent-data-loss-class bugs, but real gaps in coverage and reporting
    accuracy:
    1. Round 4 finding #2's fix (narrowing `force` to only override an unrecognised file) had
       no test that would fail if reverted to the broader `or force` — every existing
       force+standard test used either an unrecognised file or one byte-identical to the
       CURRENT kit default, so a spuriously-broad revert would go undetected. Fixed: added
       `test_force_does_not_let_standard_tier_overwrite_a_recognised_older_vintage`,
       constructing exactly the state the fix protects (a recognised, different-vintage
       standard file, `force=True`).
    2. `generate()`'s summary carried only a boolean for `working_agreement_written`, but
       `SKILL.md` instructed the agent to narrate one of two guessed reasons for "left
       alone" — neither of which is true for "standard tier + unrecognised file, no force"
       (same defect class as round 3 finding #3). Fixed: `generate()` now returns a
       `working_agreement_reason` string covering every real case, the CLI prints it
       verbatim, and `SKILL.md` quotes it instead of guessing between two options.
    3. `preview_project_setup.py`'s `process_tier_note` claimed Standard's working-agreement.md
       "is left as-is" unconditionally, contradicting `generate()` actually writing it to
       reverse a prior Solo choice or fill a missing file (and contradicting `SKILL.md`'s own
       confirm prompt in the same interview). Fixed: reworded to acknowledge both write
       conditions, with a new test asserting the note doesn't overclaim.
    4. `README.md` stated a recognized standard default is "always left alone regardless of
       the flag" without scoping that to Standard tier specifically — under Solo tier a
       recognized standard file IS converted, without needing `--force`. Fixed: reworded to
       describe both tiers' actual behaviour.
  - 2026-09-17 — platform-reviewer's sixth review pass (opus, round 6) FAILed on three more
    findings, then scope-auditor's own round-6 pass ESCALATEd a separate governance question:
    1. Round 5's own fix (the `working_agreement_reason` string) had ZERO test coverage — no
       test asserted any reason string, and the `current_working_agreement is None`
       (missing-file) write branch had no test at all. Fixed: added
       `test_generate_fills_in_a_missing_working_agreement_both_tiers` and reason-string
       assertions across the relevant existing tests.
    2. The reason was derived by RE-CHECKING the same conditions `write_working_agreement`
       already used, rather than from that decision directly — a not-yet-possible fourth
       digest-tier value (a typo like `"Solo"`/`"std"` in the shipped JSON) could have made
       the two silently disagree, and `_load_known_working_agreement_digests`'s shape check
       validated flat string values but not that they were `"standard"`/`"solo"` specifically.
       Fixed: the loader now validates the tier vocabulary itself, closing the value space
       structurally, AND each branch now sets `write_working_agreement` and
       `working_agreement_reason` together instead of separately re-deriving one from the
       other — the two literally cannot disagree now, not just "shouldn't in practice."
    3. `SKILL.md`'s write-CONSENT prompt (step 9, asked before writing — the load-bearing one,
       distinct from step 11's after-the-fact closing summary round 5 already fixed) still
       said "Standard never rewrites an existing, already-standard file... only Solo, or an
       explicit switch back from Solo, ever touches it" — false for the missing-file case,
       which is reachable (`_require_bootstrapped` only requires `.claude/settings.json` to
       exist, not `working-agreement.md`). Fixed: reworded to include filling in a missing
       file as a third case Standard can still write.

    **CPO ANSWER** (owner decision via `AskUserQuestion`, "It's in scope, keep it
    (recommended)"): scope-auditor asked whether adding the `working_agreement_reason` field
    in round 5 was a correctness fix within the original digest-rebuild authorization, or new
    user-facing wording needing its own separate sign-off. Owner's answer: in scope — the
    interview already claimed to explain its own behavior before round 5 (via the two
    hardcoded guesses this same string replaced), so making that explanation accurate is
    fixing a bug in existing behavior, not introducing a new one.
  - 2026-09-18 — platform-reviewer's seventh review pass (opus, round 7) FAILed on two small
    findings, scope-auditor PASSed clean:
    1. `docs/project-kit-design.md` (added by this diff) still said Standard "only ever writes
       to reverse an explicit prior Solo choice, never to opportunistically 'modernize' an
       already-standard file" — the identical false-universal sentence round 6 finding #3
       fixed in `SKILL.md` step 9, left stale here. Fixed: reworded to name all three
       Standard-tier write cases (reverse Solo, fill missing, force-override unrecognised).
    2. Solo tier's reason string said "converted to the lightweight template" even when the
       file was genuinely missing, falsely implying a conversion of something that never
       existed — Standard's branch already distinguished this case, Solo's didn't. Fixed:
       Solo now reports "filled in a missing file with the lightweight template" for that
       specific state, with a test assertion added to the existing missing-file test (which
       previously checked content but not the reason for the solo half).
  - 2026-09-18 — platform-reviewer's eighth review pass (opus, round 8) FAILed on two findings,
    both in `docs/decisions/tracker-convention-and-process-tier.md` — the one file the prior
    seven rounds' fixes never revisited:
    1. The ADR's own Decision section still carried the identical false-universal claim round
       7 fixed in `docs/project-kit-design.md` ("Standard only ever writes to reverse an
       explicit prior Solo choice or fill in a missing file" — omitting the force-override
       case), contradicting both the code and the ADR's own later text describing that exact
       case. Fixed: same three-case wording as the other two docs.
    2. A cross-reference ("see 'First attempt was wrong' below") pointed at a section heading
       that doesn't exist in the file — a dangling pointer left behind by rounds 4-7's
       rewrites. Fixed: repointed at the actual bolded phrase that carries the material.
  - 2026-09-18 — platform-reviewer's ninth review pass (opus, round 9) FAILed on the fix from
    round 8: the repointed cross-reference's TARGET sentence ("the last two of which were this
    ADR...") was itself wrong (attributed round 7's findings, which were about a different doc
    and a reason string, to the ADR) and its own "(see below)" pointed at nothing. Recognized
    this as the ADR repeating the exact pattern this whole feature exists to prevent — a doc
    accumulating narrative detail that goes stale faster than it can be kept in sync — and
    fixed it structurally instead of patching the sentence again: removed the round-by-round
    prose and live round-count tally from the ADR entirely (it had grown to 166 lines,
    essentially duplicating `.claude/task/contract.md`'s amendments log, which already carries
    the complete, accurate detail). The ADR is now ~85 lines — Context/Decision/one section
    explaining the design choice/Consequences, matching the shape of this repo's other ADRs —
    with a single sentence pointing at the contract log for full history instead of narrating
    it. No further per-round ADR edits should be needed; only the contract's own amendments
    log (this section) is expected to keep growing during review.
  - 2026-09-18 — platform-reviewer's tenth review pass (opus, round 10) confirmed the trimmed
    ADR is accurate and lean, but FAILed on the same live-round-count defect surviving in two
    other spots in the same diff: `scripts/generate_project_setup.py`'s module docstring still
    said "across four rounds" (stale — nine had run by then, six of them past the cap), and the
    ADR's own new text closed on an unverifiable claim about "the first two times this file
    tried to keep one" (a count) — a file added fresh by this branch cannot have a documented
    prior history to cite. Fixed both: the module docstring now says "several rounds... not
    repeated here or given a specific count that would only go stale" (same policy as the ADR,
    stated once more since that file is a separate audience — someone reading the code
    directly, not the ADR); the ADR's trailing clause removed, replaced with a forward-looking
    statement of policy instead of a historical claim it can't back up. A full sweep of every
    other round-N reference in the diff (`scripts/preview_project_setup.py`,
    `docs/project-kit-design.md`) confirmed those cite SPECIFIC, fixed historical facts about
    OTHER, already-concluded work (the deleted CI-audit inference feature, the fingerprint-cache
    saga) — not live tallies of this feature's own ongoing review — so left as-is.
  - 2026-09-18 — platform-reviewer's eleventh review pass (opus, round 11) confirmed the
    stale-count sweep was complete, but found one real remaining defect on a full fresh read:
    `preview_project_setup.py`'s `process_tier_note` Standard branch (fixed in round 5) mentions
    its own `--force` behavior, but the Solo branch never mentioned that an UNRECOGNISED
    (hand-customized) file makes `generate()` refuse the ENTIRE run, not just skip that one
    file — the same overclaim class as round 5 finding #3, just on the sibling branch of the
    same expression, and with no test that would have caught it (the existing preview-note test
    only asserted `"Solo" in note`). Fixed: Solo's note now states the refusal case explicitly,
    matching how `README.md` already described it correctly; added
    `test_solo_process_tier_note_mentions_the_refusal_case`, mirroring the existing Standard-side
    no-overclaim test.
