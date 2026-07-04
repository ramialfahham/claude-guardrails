---
description: Rebase the current feature branch onto its base (default main), auto-resolving only .claude/task/* conflicts, then force-push with lease.
argument-hint: "[base-branch]"
allowed-tools: Bash(git branch --show-current), Bash(git status --porcelain), Bash(git rev-parse *), Bash(test -d *), Bash(git fetch *), Bash(git diff *), Bash(git -c core.editor=true rebase *), Bash(git rebase --abort), Bash(git checkout --theirs *), Bash(git add *), Bash(git push --force-with-lease *), Bash(sha256sum *), Bash(grep *)
---

Rebase the current branch onto its base and force-push, resolving ONLY the
`.claude/task/*` bookkeeping conflicts that recur when a parallel PR merges first.
This is git-history surgery — run the steps in order and STOP (do nothing further) the
moment any guard fails. Never resolve a conflict outside `.claude/task/`.

Base branch = `$1` if given, else `main`.

## 1. Guards (stop, do nothing, if any fails)
- **No operation already in progress** — do NOT use `REBASE_HEAD`: it lingers as a stale
  ref after any rebase finishes, so it false-positives (it exists whenever the repo has
  ever rebased). Detect a live rebase by its state directory, and a live merge by
  `MERGE_HEAD` (which git *does* clear on completion/abort):
  - `test -d "$(git rev-parse --git-path rebase-merge)"` OR
    `test -d "$(git rev-parse --git-path rebase-apply)"` → a rebase is mid-flight.
  - `git rev-parse --verify -q MERGE_HEAD` succeeds → a merge is mid-flight.
  If any holds, STOP: "finish or abort the in-progress rebase/merge first
  (`git rebase --continue|--abort` or `git merge --continue|--abort`)." Do not start on
  top of it. (A mid-op also trips the clean-tree guard below; these give a precise message.)
- **On a feature branch:** `git branch --show-current` — if empty (detached HEAD) or
  `main`/`master`, STOP: "sync-branch only runs on a feature branch."
- **Clean tree:** if `git status --porcelain` prints ANY line, STOP: "commit or stash
  your changes first (including stray untracked files)." A rebase must start clean.

## 2. Fetch, then fingerprint the reviewed code BEFORE rebasing
- `git fetch origin`
- Write the branch's code changes (excluding the bookkeeping) to a scratch file and hash
  it — call the hash `CODE_BEFORE`. Three-dot = the branch's own side of the merge-base:
  - `git diff --output=.git/sync-before.diff --no-renames --no-abbrev origin/<base>...HEAD -- . ':(exclude).claude/task'`
  - `sha256sum .git/sync-before.diff` — the leading 64-hex value is `CODE_BEFORE`.
  (`.git/` is never committed; the file is throwaway. Writing to a file, not piping,
  keeps every step matchable by a single `allowed-tools` grant — no permission prompt.)

## 3. Rebase
- `git -c core.editor=true rebase origin/<base>` (`-c core.editor=true` suppresses the
  editor non-interactively as a single `git` call — no env prefix, no pipe).

## 4. Resolve conflicts — bookkeeping only
Whenever the rebase stops with conflicts, repeat:
- List conflicted paths NUL-safely (paths may contain spaces):
  `git diff --name-only --diff-filter=U -z`.
- **If every** conflicted path is under `.claude/task/`:
  - For each, quoting the path: `git checkout --theirs -- "<path>"` then
    `git add -- "<path>"`. (During a rebase, `--theirs` is THIS branch's version — the
    commit being replayed — which is what we keep.)
  - `git -c core.editor=true rebase --continue`
- **If any** conflicted path is NOT under `.claude/task/` (real code):
  - `git rebase --abort` and STOP. Report the conflicted code files; the user must
    rebase manually. This command never touches code conflicts.

## 5. Verify the rebase preserved the reviewed code
- Recompute the fingerprint now that HEAD sits directly on the base — call it `CODE_AFTER`:
  - `git diff --output=.git/sync-after.diff --no-renames --no-abbrev origin/<base> HEAD -- . ':(exclude).claude/task'`
  - `sha256sum .git/sync-after.diff` — the leading 64-hex value is `CODE_AFTER`.
- If `CODE_AFTER` != `CODE_BEFORE`, a silent auto-merge with the base changed reviewed
  code. The rebase is already applied (no `--abort`), so do NOT push — STOP and report:
  re-run the reviewers against the new code before pushing.
- Additionally, if `.claude/task/review.md` exists, read its recorded hash with
  `grep -oE 'diff_sha256:[[:space:]]*[0-9a-f]{64}' .claude/task/review.md` and require
  `CODE_AFTER` to equal that hash; if not, STOP the same way. (Defence in depth — the
  before/after check already guards branches that have no review yet.)

## 6. Push
- `git push --force-with-lease origin <branch>` (lease is safe: it refuses if origin
  moved unexpectedly; never a plain `--force`).

## 7. Report
State plainly: rebased `<branch>` onto `<base>`, which `.claude/task/*` files were
auto-resolved (if any), that the code fingerprint was unchanged (and matched `review.md`
if present), and that the branch was force-pushed with lease. If you STOPPED at a guard,
a code conflict, or a fingerprint mismatch, say exactly why and what the user should do
next. Take no other action.
