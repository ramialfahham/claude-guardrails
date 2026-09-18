# Task contract

objective: Audit whether this kit's enforcement and workflow hold under Claude Code's headless
mode (`claude -p`) and the Agent SDK — record the documented facts, verify the load-bearing
undocumented ones by actually running `claude -p` against a throwaway bootstrapped repo, and
write the result up as an ADR; amend the auto-mode ADR's "not confirmed" section now that the
docs state a hook `deny` survives `bypassPermissions`.

tracking_issue: (none — this repo doesn't use an issue tracker for its own work yet;
`.claude/active_work.md` is the handover mechanism instead)

scope_paths:
  - .claude/task/contract.md
  - .claude/active_work.md
  - docs/decisions/headless-mode-compatibility.md
  - docs/decisions/auto-mode-and-bypass-compatibility.md
  - docs/project-kit-design.md

decisions_reserved:
  - Whether to do this at all and in which shape — owner chose "go" on the proposed scope (live
    runs + new ADR + one-paragraph amendment to the auto-mode ADR; doc-only) over a docs-only
    ADR or a "considered, not building" ADR, after the documented facts were laid out.
  - Any hook, script, template, or settings change — NOT in scope. If a live run shows a hook
    does not fire or `CLAUDE_PROJECT_DIR` does not resolve headless, that is recorded as a
    finding and gets its own contract; it is not fixed here.
  - Whether `--bare` (documented: skips hooks) or SDK `settingSources` opt-out warrant any
    mitigation (a README warning, a generated-project note, anything else) — recorded as an
    open owner call, not decided.

done_when:
  - `docs/decisions/headless-mode-compatibility.md` exists, in this repo's ADR shape, and every
    behavioural claim in it is either a direct doc quote with its URL or something observed in a
    `claude -p` run during this task — with the exact command and the relevant output recorded.
  - The live runs cover at least: hooks fire headless (SessionStart context present; a commit
    without `review.md` denied) — which is also the `CLAUDE_PROJECT_DIR` check; a commit under
    `--dangerously-skip-permissions` still denied; `--bare` skips the hooks; what the model does
    when pushed to `AskUserQuestion` in `-p`.
  - `docs/decisions/auto-mode-and-bypass-compatibility.md`'s "What is NOT confirmed" section is
    amended with the now-documented `bypassPermissions` quote and URL, without rewriting the rest.
  - `docs/project-kit-design.md` links the new ADR from the hardening section.
  - No hook, script, template, settings, or test changes; full suite still passes.

amendments:
  - 2026-09-18 — round 1: scope-auditor PASSed (judged run 4's `--bare` auth failure honestly
    recorded and `done_when` met); platform-reviewer (sonnet, spawned voluntarily — docs only)
    FAILed on three claims-against-source findings, all real, all fixed:
    1. "`/setup-project`'s interview is `AskUserQuestion` throughout" — false: `SKILL.md` steps
       3b-fallback and 7 are explicit plain-text questions. Reworded to name both kinds; the
       conclusion (can't run headless) stands on either.
    2. Conclusion 1 said "all three blocking hooks … nothing weakens them" while the doc's own
       not-covered list admitted only `commit_review_gate.py` was pushed to deny. Reworded: the
       review gate is observed; the other two are inference from shared wiring, stated as such.
    3. The auto-mode ADR's pre-existing "two enforcing hooks" count omits `secret_scan.py`; this
       diff touched that file without reconciling it. Added a parenthetical in the dated update
       block. First draft of that note said the count "predates `secret_scan.py`" — checked
       with `git log --diff-filter=A`: secret_scan.py (2026-09-06) predates the ADR
       (2026-09-11), so it was an omission, not a timing artefact; corrected before spawning
       round 2. Also verified none of the three reads `permission_mode`.
  - 2026-09-18 — round 2: scope-auditor PASSed; platform-reviewer FAILed on one new defect in
    round 1's own amendment text: it claimed `test_gate_hooks_never_branch_on_permission_mode`
    "already lists `secret_scan`" — false. A grep for `secret_scan` in `test_hooks_import.py` hit
    the importability list (line 28), which I read as the tripwire's `_MODE_INDEPENDENT_HOOKS`
    list (line 52: `commit_review_gate`, `branch_discipline`, `completion_gate` only). The
    shipped ADR text never made that claim; the audit trail did. Fixed: claim removed. Adding
    `secret_scan` to the tripwire list is a one-line test change — out of this contract's scope
    (no test changes), recorded in `active_work.md` as a follow-up instead of slipped in.
    Note for reviewers: `review_input.patch` excludes `.claude/task/*` by design (the commit
    gate's hash excludes it too); `contract.md` is read from disk, as the reviewer did.
    The research agent's Agent SDK "quote" turned out to be a paraphrase — caught by fetching
    the page myself under rule B before round 1; replaced with the page's actual sentences.
