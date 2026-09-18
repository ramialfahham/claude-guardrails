# Task contract

objective: Cut serial review rounds — (A) require reviewers to report every finding per round
and to label a finding that was present in round 1's diff as a review miss; (B) require the
builder to check any claim about code behaviour against source before spawning reviewers.
The 3-round cap is deliberately untouched.

tracking_issue: (none — this repo doesn't use an issue tracker for its own work yet;
`.claude/active_work.md` is the handover mechanism instead)

scope_paths:
  - .claude/task/contract.md
  - .claude/active_work.md
  - templates/reviewers/_skeleton.md
  - templates/reviewers/analytics-engineer-reviewer.md
  - templates/reviewers/data-engineer-reviewer.md
  - templates/reviewers/frontend-reviewer.md
  - templates/reviewers/platform-reviewer.md
  - templates/reviewers/security-reviewer.md
  - .claude/agents/platform-reviewer.md
  - .claude/agents/scope-auditor.md
  - .claude/working-agreement.md
  - templates/working-agreement-solo.md.tmpl
  - templates/known-working-agreement-digests.json

decisions_reserved:
  - Whether to change the review process at all, and which of the three diagnosed causes to
    act on — owner chose "now, go" on the proposal (A + B now, C: leave the cap at 3 until
    A + B show whether round counts drop) after the diagnosis was laid out following MR !33.
  - The cap itself (`_ROUNDS_CAP` in `commit_review_gate.py`, its meaning, or the CPO ANSWER
    convention) — explicitly NOT changed here.
  - Any hook enforcement of A or B — not built; both are procedural rules, same status as
    `guard-paths.md`'s opus convention. Whether to mechanise them later is an owner call.

done_when:
  - Every reviewer module in `templates/reviewers/` (skeleton included) and both of this kit's
    own `.claude/agents/*.md` carry the same round-completeness rule under "Verdict rules";
    `.claude/agents/platform-reviewer.md` remains byte-identical to its template.
  - `.claude/working-agreement.md` §2 and `templates/working-agreement-solo.md.tmpl` §2 carry
    the builder pre-spawn self-check; both new digests are appended to
    `templates/known-working-agreement-digests.json` (never removing old ones).
  - No hook, script, or test-logic changes.
  - Full test suite (`.claude/tests/`) passes — the digest-parity and routing-doc-parity tests
    are the ones this diff can break.

amendments:
  - 2026-09-18 — round 1: platform-reviewer (opus) PASSed; scope-auditor FAILed on one finding —
    the solo working agreement's copy of the self-check listed fewer claim types ("ADR", "test
    name" missing) than the standard one, i.e. a different rule, not a lighter statement of the
    same one. Fixed: solo now states the same rule with the same list. Also taken from the
    platform-reviewer's non-blocking note: "Reviewers will check exactly this" was itself an
    unbacked behaviour claim (no reviewer module has an explicit claims-vs-source hunt item) —
    softened to "are asked to" in both files. The two digests appended earlier on this branch
    were never released, so they were replaced rather than accumulated (the "never remove"
    rule protects shipped defaults an older target may hold; these had shipped nowhere).
  - 2026-09-18 — round 2: scope-auditor PASSed; platform-reviewer (opus) FAILed on two findings,
    BOTH self-labelled "present since round 1 — review miss" under the rule this very diff adds
    (the first time the rule has fired, and on its own author). Both fixed:
    1. "Reviewers are asked to check exactly this" was still unbacked — no reviewer module had a
       claims-vs-source hunt item, so the verb change in round 1 fixed nothing. Fixed by making
       it true: every module (skeleton included, with a keep-this-item note) gained a numbered
       hunt item "Claims against source" — confirm any behaviour assertion in the diff against
       the code it describes; mismatch → FAIL with the contradicting `file:line`. Chosen over
       dropping the sentence because it's the half of (B) that actually closes the loop.
    2. The "present since round 1" half of (A) depended on an input reviewers aren't given (the
       round number and round 1's findings live in `review.md`, which they don't read). Fixed
       using an input they already have: the bullet now says both are in `contract.md`'s
       `amendments`, and step 3 of both working agreements tells the builder to record each
       round there before re-spawning — the convention this repo already follows by hand.
    Digests refreshed again (same unreleased-replacement reasoning as round 1).
