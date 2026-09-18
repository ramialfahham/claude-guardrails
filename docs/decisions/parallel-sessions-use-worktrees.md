# Parallel sessions: use a git worktree per session

**Status**: verified, documented. Doc-only — no hook, script, template, or test
changes. Source: reproduced by running it, in a throwaway repo bootstrapped with
this kit's real `bootstrap.sh` and a real `git worktree`, on Windows, during the
task that wrote this file. The claims below are what was observed, not what
the design implies.

## Context

People run more than one Claude Code session against the same repository at
once — one finishing a review round while another starts the next task. The
three hooks that can actually block — `commit_review_gate.py`,
`branch_discipline.py`, and `secret_scan.py` (the only three that call
`emit_deny`, checked by grep across `.claude/hooks/`) — are stateless: each
reads git's current state (and, for the review gate, `.claude/task/review.md`)
at the moment it fires, and decides from that; none keeps a marker file. The
two advisory hooks (`completion_gate.py`, `handover_plan_gate.py`) do keep
state — a small marker file in the OS temp directory, keyed by the Claude
Code `session_id`. They use it differently: `handover_plan_gate.py` checks
the marker exists and so fires once per session; `completion_gate.py`
stores a hash of the last reason it reported and re-fires whenever the
current reason differs, so it can fire several times in one session. Either
way, neither ever sets a `permissionDecision`, so that state can only
change what gets *said*, never what gets *blocked*. The question is whether
the blocking hooks still hold when two sessions share a checkout, and
whether `git worktree` — a second working directory and index attached to
the same `.git` — changes the answer.

## Decision

Run parallel sessions in separate worktrees, one per session. Same-directory
parallel sessions are tolerated, not recommended: the gate stays sound, but
the two sessions will trip over each other's review state, and there is one
narrow gap it cannot close.

## Why — what was observed

Setup: `repo/` on branch `feat-a`, `git worktree add ../wt-b -b feat-b`.

| # | Observation | Implication for the gate |
|---|---|---|
| 1 | `git worktree add ../wt-c feat-a` → `fatal: 'feat-a' is already used by worktree at .../repo` | Git itself refuses to check out one branch in two worktrees, so two sessions can't commit to the same branch from two worktrees by accident. |
| 2 | `git add a.txt` in `repo/` → `git diff --cached --name-only` lists `a.txt` there, and nothing in `wt-b/` | Each worktree has its own index. What one session stages is invisible to the other. |
| 3 | `commit_review_gate.py --diff-hash` run with `CLAUDE_PROJECT_DIR` pointing at each worktree → two different hashes (`repo/` has the staged file, `wt-b/` hashes empty) | The gate's "was THIS diff reviewed?" check is per-worktree, because it's computed from that worktree's own index against the base branch. |
| 4 | `repo/.claude/task/` and `wt-b/.claude/task/` are distinct paths | `review.md`, `contract.md`, and `review_input.patch` are ordinary tracked-directory files, so each worktree has its own — one session's review round can't overwrite another's. |
| 5 | A `git commit` event fed to the hook in `repo/` with no `review.md` → `permissionDecision: deny` ("no review found") | The gate is live and blocking inside a worktree exactly as in a plain checkout. Hook commands are wired as `${CLAUDE_PROJECT_DIR}/.claude/hooks/...` and the hook files are present in each worktree, so nothing resolves back to a sibling checkout. |
| 6 | Same directory, no worktree: session 1 writes `review.md` for hash `H1`; session 2 stages `b.txt`; the commit event now → `deny` ("the reviewed diff doesn't match the branch's current cumulative diff") | The gate recomputes the hash at commit time, so a second session staging into the shared index invalidates the first session's review rather than sneaking past it. Safe, but the first session sees a confusing forced re-review it didn't cause. |

Most of what the gate relies on — index, `HEAD`, branch name,
`.claude/task/*` — is per-worktree. One input is not: the **base branch
ref** (`main`/`master`, local or remote) that `commit_review_gate.py` uses
to find the merge-base for the cumulative diff. Branch refs live in the
shared `.git`, so a sibling worktree can move them. Whether that actually
changes another worktree's hash depends on *how* the ref moves — tested
with the branch carrying one committed file plus one staged file, and a
sibling worktree with `main` checked out:

| # | Sibling worktree does to `main` | Hash in the other worktree |
|---|---|---|
| 7 | Fast-forwards it (a new commit — what `git pull` does every day) | Unchanged. The fork point is still the merge-base. |
| 8a | Amends its tip, *after* row 7 — so the amended commit is past the fork point | Unchanged, same reason: the fork point is untouched. |
| 8b | Amends its tip when that tip *is* the fork point (`main` never advanced since the branch was cut) | **Changes** — the fork-point commit is rewritten, merge-base falls back to the previous shared commit, the cumulative diff grows. |
| 9 | Merges the branch into `main` | **Changes** — merge-base jumps to the branch tip, the cumulative diff shrinks to just what's staged. |
| 10 | Replaces its history so there's no common ancestor | **Changes** — no merge-base, so the gate falls back to a staged-only diff (its documented shallow-clone fallback). |

Rows 8b, 9 and 10 mean a review can be invalidated *across* worktrees — by
merging the branch or rewriting any commit on `main` that the branch still
forks from, not by ordinary fetching — and always in the safe direction: a
hash mismatch is a `deny` and a forced re-review, never a bypass (a moved
merge-base changes the diff's bytes, and only byte-identical content
reproduces a recorded SHA-256). Everything the gate can be fooled *into
allowing* is per-worktree. That's the actual argument, and it needed
running rather than reasoning: rows 7–10 are exactly the cases where the
first draft of this document got it wrong by inferring from git's ref model
instead of checking — and row 8 was first written without the 8a/8b
distinction, from a run that happened to satisfy 8a's precondition.

## What same-directory sessions actually risk

With two sessions in one checkout there is one index and one
`.claude/task/review.md`:

- **Shared `review.md`.** Session 2's review round overwrites session 1's.
  Session 1's next commit is then denied — either the hash no longer matches
  (row 6) or the recorded verdict is for a different diff. Harmless to the
  codebase, costly in confusion: the session that gets denied did nothing
  wrong and has to re-run its reviewers.
- **Shared index.** Session 2's `git add` silently becomes part of what
  session 1's `git commit` would include. Row 6 shows the gate catches this
  at commit time.
- **The one real gap: approval-to-execution.** `commit_review_gate.py` is a
  `PreToolUse` hook. It approves the commit, returns, and only *then* does
  Claude Code run `git commit`. If another session runs `git add` in that
  window — milliseconds, but real — the commit includes content the hash
  never covered. `secret_scan.py` has the identical shape: it scans the
  staged diff at approval time, so content staged in the same window is
  committed unscanned. A `PreToolUse` hook cannot hold a lock across the
  tool's execution; closing this needs OS-level locking or a git-side check
  (`pre-commit` hook comparing the index again), both new mechanisms and
  therefore an owner decision, not something this ADR introduces. In a
  worktree-per-session setup the window can't be exploited, because no other
  session shares the index (row 2).
- **Shared `.claude/active_work.md`.** Two sessions each "keeping the handover
  current" overwrite each other. A process problem, not a gate problem, and
  worktrees don't fix it either — the handover is one file per branch, and
  the second session should be on its own branch with its own contract
  anyway.

## What this does NOT cover — stated so it isn't assumed

- The verification was a throwaway script run during this task, not a test
  in `.claude/tests/`. Rows 1–10 are reproducible from the description, but
  nothing in CI re-runs them. Adding a permanent test would be a small,
  separate change.
- It was run on Windows with Git for Windows. Nothing in it is
  platform-specific, but it wasn't repeated on macOS or Linux.
- It verified the hooks' behaviour given `CLAUDE_PROJECT_DIR`; it did not
  open two real interactive Claude Code sessions side by side. Whether a
  session started inside a worktree (by `cd`-ing there, or via Claude Code's
  own worktree support) gets `CLAUDE_PROJECT_DIR` set to the worktree path
  rather than the main checkout was NOT checked here. If it resolved to the
  main checkout, the hooks would still run but would hash the wrong index —
  the one thing that would undermine rows 3 and 5. Worth a one-line check
  (`echo $CLAUDE_PROJECT_DIR`) the first time anyone actually does this.
- `branch_discipline.py` and `secret_scan.py` were not exercised beyond
  confirming they are wired in each worktree. `branch_discipline.py` checks
  the branch name, per-worktree by git's own rules (row 1); `secret_scan.py`
  reads the staged diff, per-worktree by row 2. Neither was run against a
  sibling-worktree scenario the way the review gate was.
- Rows 7–10 move `main` from a sibling worktree with `main` checked out. A
  bare `git fetch` updating `origin/main` while a local `main` exists was
  not run separately — the gate prefers local `main` when it resolves, so
  that case reduces to "local `main` unchanged", but it wasn't observed.

## Consequences

- No code in this kit changes. `bootstrap.sh`, every hook, and every
  generated project are unaffected.
- Recommendation for any project on this kit: one worktree per concurrent
  session. `git worktree add ../<name> -b <branch>` from the main checkout,
  then start the session in that directory. The branch, contract, review
  file, and handover are then naturally separate.
- If the approval-to-execution gap ever matters in practice — a real
  same-directory incident rather than a theoretical one — the fix is a
  git-side `pre-commit` re-check or a lock file, and it gets its own
  contract. Until then it is recorded here as a known, narrow limit.
