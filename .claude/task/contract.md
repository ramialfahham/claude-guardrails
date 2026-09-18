# Task contract

objective: Write the parallel-session/worktree safety ADR — record, with live evidence, whether
this kit's review gate holds when more than one Claude Code session works on the same repo at
once, and recommend `git worktree` for that case.

tracking_issue: (none — this repo doesn't use an issue tracker for its own work yet;
`.claude/active_work.md` is the handover mechanism instead)

scope_paths:
  - .claude/task/contract.md
  - .claude/active_work.md
  - docs/decisions/parallel-sessions-use-worktrees.md
  - docs/project-kit-design.md

decisions_reserved:
  - Whether to write this at all — owner selected "Write the worktree-safety ADR" via
    AskUserQuestion as item 3 of 4, and gave "go" after a plain-language restatement of the
    ADR's scope (doc-only, leads with the worktree recommendation, records the same-directory
    caveats, no hook changes).
  - Anything that would close the same-directory TOCTOU gap (OS-level locking, a new hook, a
    change to `commit_review_gate.py`) — explicitly NOT in scope; the ADR records it as a known
    limit for the owner to decide on separately, if ever.
  - Whether the recommendation becomes something `bootstrap.sh` or `/setup-project` prints or
    enforces — not decided here; the ADR is documentation only.

done_when:
  - `docs/decisions/parallel-sessions-use-worktrees.md` exists, matches the shape of this repo's
    other ADRs (Status / Context / Decision / Why / what is NOT covered / Consequences), and
    every behavioural claim in it was reproduced by actually running it in a throwaway repo
    during this task — not carried over from an earlier session's notes.
  - `docs/project-kit-design.md` links to it from the hardening section, next to the sandboxing
    ADR.
  - No code, hook, template, or test changes.
  - Full test suite (`.claude/tests/`) still passes (nothing should have changed — a sanity check
    that nothing did).

amendments:
  - 2026-09-18 — platform-reviewer's first pass (sonnet, spawned voluntarily — `docs/*` isn't
    routed to it — because the ADR makes claims about hook behaviour) FAILed on two findings;
    scope-auditor PASSed. Both were real and both fixed:
    1. The ADR's central sentence — "nothing the gate relies on lives in the shared `.git`" —
       was false: the base-branch ref `commit_review_gate.py` uses for the merge-base is shared
       across worktrees. The first draft inferred this from git's model and presented it as
       observed. Fixed by actually running it (rows 7–10): a sibling fast-forwarding or amending
       `main` leaves the hash unchanged; merging the branch into `main` or rewriting `main`'s
       history changes it — always as a spurious deny, never a bypass. ADR argument and the
       `docs/project-kit-design.md` paragraph rewritten to say exactly that.
    2. "Stateless" was claimed for `completion_gate.py`, which (like `handover_plan_gate.py`,
       previously unmentioned) keeps a session-keyed marker in the OS temp dir. Fixed: the ADR
       now distinguishes the two blocking hooks (stateless) from the two advisory ones (marker
       state, never a `permissionDecision`).
    The first re-run of row 9/10's check was itself invalid (a scripted edit adding the branch
    commit silently failed to apply, so "cumulative" and "staged-only" coincided and every case
    read UNCHANGED); caught by noticing the hash was byte-identical to a different fixture's,
    fixed, re-run. Noted here because it's the same trap the ADR warns about — an "observation"
    that observed nothing.
  - 2026-09-18 — platform-reviewer's second pass (sonnet, round 2) FAILed on two more claims,
    scope-auditor PASSed. Both real, both fixed:
    1. Round 1's fix said both advisory hooks fire "once per session". True for
       `handover_plan_gate.py` (existence marker); false for `completion_gate.py`, whose marker
       is a hash of the last reason and re-fires on any change. Fixed: the ADR now describes
       the two mechanisms separately.
    2. Row 8 ("amend `main`'s tip → unchanged") was stated unconditionally but only holds when
       the amended commit isn't the fork point. Run live: amending the fork-point commit itself
       moves the merge-base back one commit and changes the hash. Fixed: split into 8a
       (past the fork point — unchanged) and 8b (is the fork point — changes), both observed,
       with the ADR noting that row 8 was first written from a run that happened to satisfy
       8a's precondition.
  - 2026-09-18 — platform-reviewer's third pass (sonnet, round 3 — this repo's cap) confirmed
    round 2's fixes, then FAILed on one enumeration error: "the two hooks that can block" —
    `secret_scan.py` is a third (denies a commit when the staged diff matches a credential
    shape), wired in the same PreToolUse group, unmentioned anywhere in the ADR. scope-auditor
    PASSed.

    **CPO ANSWER** (owner decision via `AskUserQuestion`, "Yes, fix and run round 4"): authorised
    one round past the cap. Fixed: grep across `.claude/hooks/` confirms exactly three hooks call
    `emit_deny` (`commit_review_gate`, `branch_discipline`, `secret_scan`), all stateless; the ADR
    now names all three, notes `secret_scan.py` shares the approval-to-execution window, and
    lists it alongside `branch_discipline.py` in "not covered" as wired-but-not-exercised.
