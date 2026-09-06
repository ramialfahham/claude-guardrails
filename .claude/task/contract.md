# Task contract

objective: Phase 3 of the `claude-project-kit` plan — harden the two hooks that
  gate every commit (`branch_discipline.py`, `commit_review_gate.py`), close a
  found-in-review-history bypass class (bundled short flags, pathspec commits,
  restage-after-hash-check), fix a real inconsistency between what this repo's
  reviewer prompts assume (a cumulative branch diff) and what the gate actually
  hashes (staged-only), add a review-round cap, and add a secret-leak scanning
  hook. Corrected from the originally-described scope: the planned
  "`core.hooksPath` tamper check" doesn't apply to this repo's enforcement
  model (Claude Code `PreToolUse` hooks, not native git hooks) — replaced with
  closing a real gap found while implementing: `.claude/settings.json` (where
  the hooks are registered) and `.claude/review_routing.json` itself were not
  in the routed paths, so a commit removing the hook registrations would only
  require `scope-auditor`, not `cto-reviewer`.

scope_paths:
  - .claude/hooks/branch_discipline.py
  - .claude/hooks/commit_review_gate.py
  - .claude/hooks/secret_scan.py
  - .claude/hooks/_command_utils.py
  - .claude/settings.json
  - .claude/review_routing.json
  - .claude/working-agreement.md
  - README.md
  - task/REVIEW_TEMPLATE.md
  - .claude/tests/test_branch_discipline.py
  - .claude/tests/test_commit_review_gate.py
  - .claude/tests/test_secret_scan.py
  - .claude/tests/test_hooks_import.py
  - .claude/tests/test_command_utils.py
  - .claude/task/contract.md
  - .claude/task/review.md

decisions_reserved:
  - Swapping the `core.hooksPath` check for `.claude/settings.json`/
    `review_routing.json` routing coverage — agent-executable correction
    (same "harden the guard" objective, more accurate to this repo's actual
    architecture), not an owner-reserved scope change. Stated plainly to the
    owner before implementing, per the working agreement's transparency
    requirement, not silently substituted.
  - The review-round cap is a SELF-REPORTED counter (`rounds:` in review.md,
    incremented by whoever re-reviews), not independently derived by the hook
    from git history — same trust level as `contract.md`'s own amendments
    log. Stated explicitly, not presented as stronger than it is.
  - Secret-scan pattern set is deliberately limited to well-known TOKEN SHAPES
    (AWS, GitHub, Slack, OpenAI/Anthropic-style, Google API keys, private-key
    headers) — no generic `password=`/`secret=` keyword heuristic, which this
    repo's own `_command_utils.py` design note warns against: a noisy,
    false-positive-prone guard trains the agent to ignore it. If a real secret
    doesn't match a known shape, this gate won't catch it — a stated
    limitation, not a silent gap.

done_when:
  - `branch_discipline.py` gains a commit-form allowlist: `git commit` is
    refused unless every flag is on an explicit allowlist (`-m`/`--message`,
    `-F`/`--file`, `--author`, `--date`, `-S`/`--gpg-sign`, `--no-edit`,
    `-e`/`--edit`, `--dry-run`, with-arg forms handled) AND no positional
    pathspec argument is present. Also refuses any SINGLE Bash command that
    bundles an index-mutating subcommand (`add`, `rm`, `mv`, `reset`,
    `restore`, `stage`, `checkout`) together with `commit` — forces staging
    and committing into separate tool calls, so the review gate's pre-check
    always reflects the true index state at commit time (this is exactly the
    `git add extra-file && git commit` bypass: reviewing a smaller staged
    diff, then silently including more in the same compound command).
  - `commit_review_gate.py` hashes the CUMULATIVE diff against the branch's
    merge-base with `main` (falling back to `origin/main`/`gitlab/main` if
    `main` isn't a local ref), not staged-only — fixes a real, already-hit
    inconsistency: this session had to manually generate
    `.claude/task/review_input.patch` because the reviewer agent prompts
    (`cto-reviewer.md`, `scope-auditor.md`) already describe their input as
    "the cumulative branch diff vs the base branch," while the hook itself
    only ever hashed `git diff --staged`.
  - `commit_review_gate.py` reads an optional `rounds: N` field from
    `review.md`; past a cap (3), blocks unless a recorded
    `CPO ANSWER:`-style override for the cap itself is present. Absence of
    the field defaults to round 1 (no behavior change for the common case).
  - `.claude/hooks/secret_scan.py` (new): scans ADDED lines (`+` lines) of the
    staged diff for well-known credential shapes; blocks the commit if found,
    naming the pattern type and file without echoing the matched secret text
    into the deny message.
  - `.claude/review_routing.json` routes `.claude/settings.json` and
    `.claude/review_routing.json` itself to `cto-reviewer`.
  - `task/REVIEW_TEMPLATE.md` documents the new `rounds:` field.
  - Every new behavior is tested against its BROKEN form first (bundled
    `-am`, a pathspec commit, a chained `add && commit`, staged-only vs.
    cumulative hashing diverging, a round count past the cap, each secret
    pattern) — confirming the hook actually denies it, not just that a clean
    case passes.
  - All existing `.claude/tests/test_*.py` still pass; JSON configs still
    parse; hooks still byte-compile; shell scripts still lint.
  - scope-auditor + cto-reviewer PASS on the staged diff.

amendments:
  - 2026-09-05 — contract created for Phase 3 of the approved plan
    (`C:\Users\Rami\.claude\plans\happy-stargazing-mccarthy.md`), with the
    `core.hooksPath` → `settings.json`/`review_routing.json` routing
    correction stated above.
  - 2026-09-05 — added `.claude/tests/test_hooks_import.py` to scope_paths:
    the new `secret_scan.py` hook needs adding to that file's `_HOOK_MODULES`
    smoke-test list, a necessary companion change omitted from the original
    scope_paths by oversight — caught by scope-auditor's own round-1 review.
  - 2026-09-05 — cto-reviewer round-1 FAIL, four findings, three fixed and
    one defended rather than changed:
    1. FIXED (real defect) — `git_subcommand` required the first token to be
       EXACTLY `"git"`, so a subshell/brace-grouped command (`(git commit -m
       x)`, `{ git commit -m x; }`) was invisible to every check in
       `branch_discipline.py`, old and new. Added `.claude/hooks/
       _command_utils.py` and `.claude/tests/test_command_utils.py` to
       scope_paths for a narrow, targeted fix (`_degroup`, strips one layer
       of wrapping punctuation) — NOT a general shell parser; a git
       invocation nested deeper than one group level still isn't caught, a
       stated residual limitation, not a claim of full coverage.
    2. FIXED (real defect) — `checkout` was unconditionally treated as
       index-mutating, so a benign `git checkout -b <branch> && git commit`
       was wrongly blocked (the cry-wolf failure mode this repo's own
       hook-design note warns against). First attempt exempted `checkout`
       whenever `--` was absent from its arguments — WRONG, and caught in
       round 2 (below): git accepts `checkout <ref> <path>` without `--`
       (it's an optional disambiguator, not required), so that first fix
       reopened the exact bypass it was meant to close.
    3. FIXED (real defect, non-blocking) — the no-base-ref fallback to
       staged-only hashing was completely silent. First attempt called
       `emit_context` from inside `_gate()` itself — WRONG, and caught in
       round 2 (below): `_gate()` can still return a deny reason afterward,
       which would have meant two JSON objects printed for one hook
       invocation, an untested shape this repo's harness has never had to
       handle from this hook.
    4. DEFENDED, not changed — the self-reported `rounds:` counter has no
       independent enforcement if never incremented. Already disclosed
       plainly in `decisions_reserved` before this round; cto-reviewer
       itself framed this as a build-or-skip judgment call, not a verified
       defect. Judgment: keep it — a fully tamper-proof counter needs real
       complexity (parsing review.md's own git-log history, cross-referencing
       hash changes) disproportionate to what's a forcing function for an
       owner-visible, transparently-conducted review process, not a security
       boundary against an adversarial builder. Reaffirmed in round 2.
  - 2026-09-05 — cto-reviewer round 2 FAIL (re-review of round-1's fixes),
    two more real defects, both fixed; scope-auditor round 2 FAIL (separate
    pass), one doc-sync gap, fixed:
    5. FIXED — round-1's `--`-based `checkout` exemption (item 2 above) still
       let `git checkout <ref> <path>` (no `--`, valid git syntax) through
       unflagged. Replaced with a narrower, unambiguous exemption: only
       `-b`/`-B` (branch creation) is safe regardless of what follows it,
       since those flags can never restore file content. Everything else
       about `checkout` — including a bare `checkout <existing-branch>`,
       token-indistinguishable from `checkout <path>` — is now conservatively
       flagged. Accepts forcing a rare, benign branch-switch-then-commit
       bundle into two calls as the safe direction to be wrong in.
    6. FIXED — round-1's `emit_context` call (item 3 above), still inside
       `_gate()`, could fire and THEN have `_gate()` return a deny reason
       that `main()` turns into a second `emit_deny` print — two JSON blobs
       from one invocation, risking the harness treating the output as
       malformed and silently dropping the deny. Moved the check out of
       `_gate()` into `main()`, gated so it only ever fires on the branch
       where `_gate()` returned `None` (allow) — mutually exclusive with
       `emit_deny` by construction, matching how every other `emit_context`
       call in this repo is the sole output of its invocation.
    7. FIXED — added `.claude/working-agreement.md` to scope_paths: it still
       described the review cycle in terms of "the staged diff" and "the
       staged-diff hash" after the switch to cumulative hashing, which would
       have told a future session to prepare and record the wrong thing.
       Updated both mentions, plus the hook-enforcement summary in §3 to
       name the two new hard-blocked commit forms.
  - 2026-09-05 — cto-reviewer round 3 FAIL (independently converging with a
    concurrent scope-auditor finding on the same gap): `README.md` — this
    repo's public entry point, explicitly read by downstream repos per this
    repo's own `CLAUDE.md` — still had the identical stale "staged diff"/
    "staged-diff hash" wording round 2 fixed in `working-agreement.md`, just
    never added to scope_paths. FIXED: added `README.md` to scope_paths,
    updated the same two spots (the "Reviewers run blinded" design-decision
    bullet and the "How the review gate works" walkthrough) to describe
    cumulative hashing and `--diff-hash`.
  - 2026-09-05 — cto-reviewer round 4 FAIL, two real defects (scope-auditor
    round 4 ran the same diff and PASSed, but cto-reviewer's pass found what
    it missed):
    8. FIXED (real regression, introduced by this same PR) — round 1's
       `_bundled_index_mutation` used a bare `git_subcommand(...) ==
       "commit"` check with no `--dry-run` exemption, so
       `git add -A && git commit --dry-run` — which commits nothing — was
       denied as a bundling violation. The exact cry-wolf failure class this
       PR already had to fix once for `checkout`, now found in the sibling
       check.
    9. FIXED (root cause of #8) — "is this a real commit" was independently
       reimplemented three times (`commit_review_gate._is_commit`,
       `secret_scan._is_commit_command`, and `branch_discipline`'s bare
       subcommand check), two of which agreed and one of which had silently
       drifted. Centralized as `is_commit_subcommand()` in
       `_command_utils.py` (the file that exists specifically to prevent
       this kind of guard-to-guard drift); all three hooks now call it.
