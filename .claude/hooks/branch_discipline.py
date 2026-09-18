#!/usr/bin/env python
"""PreToolUse(Bash) guardrail — branch discipline (hard enforcement).

Self-gated to the actual command. Hard-blocks the shortcuts so the
new-branch -> PR -> user-merges workflow is enforced, not just advised:

  1. `git commit` while on `main`/`master`  -> blocked: branch first.
  2. `git push` of the `main`/`master` branch -> blocked: push a feature branch.
  3. `gh pr merge`                           -> blocked: the user merges, not the agent.
  4. `git commit --amend` / `--no-verify` / `-n` -> blocked: history stays
     append-only and hook-verified.
  5. `git commit` with any flag not on the allowlist, or a pathspec argument
     -> blocked: a bundled `-am` or `commit <file>` silently commits changes
     the review gate's hash never covered.
  6. A single Bash command bundling an index-mutating subcommand (`add`,
     `rm`, `mv`, `reset`, `restore`, `stage`, `checkout`) with `commit`
     -> blocked: staging and committing must be separate tool calls, so the
     review gate's pre-check always reflects the real staged state at commit
     time (`git add extra-file && git commit` would otherwise let a smaller,
     already-reviewed diff be the one hashed while a larger one gets committed).

Fails OPEN: any error or non-matching command exits 0 with no output.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _command_utils import (  # noqa: E402
    _degroup,
    _GIT_OPTS_WITH_ARG,
    bash_command,
    emit_deny,
    git_subcommand,
    is_commit_subcommand,
    project_opted_in,
    read_event,
    simple_commands,
    strip_quoted_and_heredoc,
)

_GH_PR_MERGE = re.compile(r"gh\s+pr\s+merge\b")
_COMMIT_FORBIDDEN = re.compile(r"(?:^|\s)(--no-verify|--amend|-n)(?=\s|$)")
_PROTECTED = {"main", "master"}

# git commit flags allowed here. Anything else — including a bundled short
# flag like `-am` (not the literal string "-a" or "-m") — falls through to
# "not on the allowlist" and is refused. That's deliberate: an exact-match
# allowlist can't be fooled by bundling, only by adding a new flag to this set.
_COMMIT_FLAGS_WITH_VALUE = {
    "-m", "--message", "-F", "--file", "--author", "--date",
    "-S", "--gpg-sign", "-c", "--reedit-message", "-C", "--reuse-message",
}
_COMMIT_FLAGS_BARE = {"--no-edit", "-e", "--edit", "--dry-run"}

# Subcommands that change the index. Bundled with `commit` in one Bash
# command, they're refused outright — see reason 6 above.
_INDEX_MUTATING = {"add", "rm", "mv", "reset", "restore", "stage", "checkout"}


def _args_after_subcommand(toks: list[str]) -> list[str]:
    """Tokens after the git subcommand itself, skipping the same global
    options `git_subcommand` skips to find it. [] if this isn't `git ...`.
    Degroups the same way `git_subcommand` does — must agree with it on what
    counts as `git ...`, or a grouped command (`(git commit -m x)`) would be
    correctly recognised as a commit by one and silently invisible to the
    other, skipping the commit-form check instead of enforcing it."""
    toks = _degroup(toks)
    if not toks or toks[0] != "git":
        return []
    i = 1
    while i < len(toks):
        tok = toks[i]
        if tok in _GIT_OPTS_WITH_ARG:
            i += 2
            continue
        if tok.startswith("-"):
            i += 1
            continue
        return toks[i + 1:]
    return []


def _commit_form_violation(args: list[str]) -> str | None:
    """None if `args` (the tokens after `commit`) are all allowlisted flags
    with no pathspec; otherwise a human-readable reason."""
    i = 0
    while i < len(args):
        tok = args[i]
        if tok.startswith("-"):
            flag = tok.split("=", 1)[0]
            if flag in _COMMIT_FLAGS_WITH_VALUE:
                i += 1 if "=" in tok else 2
                continue
            if flag in _COMMIT_FLAGS_BARE:
                i += 1
                continue
            return f"flag `{tok}` is not on the allowed commit-flag list"
        return (f"pathspec `{tok}` is not allowed on `git commit` — "
                "commit must cover exactly what was staged and reviewed")
    return None


def _bundled_index_mutation(stripped_parts: list[str]) -> str | None:
    """The index-mutating subcommand bundled with `commit` in the same Bash
    command, or None. Checked across ALL simple-commands in one invocation —
    see reason 6 in the module docstring.

    `checkout` is special-cased, narrowly: `git checkout -b/-B <branch>`
    (branch creation) is exempted — that flag can only create/reset a branch,
    never restore file content, so it's unambiguously safe regardless of what
    follows it. Nothing else about `checkout` is exempted: `git checkout
    <ref> <path>` restores file content into the index/working tree WITHOUT
    requiring `--` (`--` only disambiguates a path that could also be read as
    a branch name; git accepts the bare form) — a token-level check can't
    reliably tell "<ref> <path>" apart from a plain branch switch the way git
    itself does (by checking the working tree), so anything other than the
    `-b`/`-B` form is treated conservatively as index-mutating. A rare, benign
    `git checkout <existing-branch> && git commit` bundle gets forced into two
    calls too — the safe direction to be wrong in.

    Uses `is_commit_subcommand` (shared with commit_review_gate, secret_scan),
    not a bare `git_subcommand(...) == "commit"` check — `git commit
    --dry-run` commits nothing, so `git add -A && git commit --dry-run` must
    not be blocked; an earlier version of this function used the bare check
    and did block it, a real false positive."""
    has_commit = any(is_commit_subcommand(p.split()) for p in stripped_parts)
    if not has_commit:
        return None
    for part in stripped_parts:
        toks = part.split()
        sub = git_subcommand(toks)
        if sub == "checkout" and ("-b" in toks or "-B" in toks):
            continue
        if sub in _INDEX_MUTATING:
            return sub
    return None


def _repo_root() -> str:
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def _current_branch(root: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=root, capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        return out or None
    except Exception:
        return None


def _pushes_protected(part: str, branch: str | None) -> bool:
    if branch in _PROTECTED:
        return True
    # an explicit `... push <remote> main` or `... HEAD:main` destination
    for tok in part.split()[2:]:
        if tok in _PROTECTED or (":" in tok and tok.rsplit(":", 1)[-1] in _PROTECTED):
            return True
    return False


def main() -> int:
    event = read_event()
    if not project_opted_in(event):
        return 0
    cmd = bash_command(event)
    if not cmd:
        return 0
    parts = list(simple_commands(cmd))
    stripped_parts = list(simple_commands(strip_quoted_and_heredoc(cmd)))

    for part in parts:
        if _GH_PR_MERGE.match(part):
            emit_deny(
                "MERGE BLOCKED: `gh pr merge` is the user's action, not the agent's. "
                "Open the PR, get CI green, and stop — the user merges. "
                "(Proceed only if the user explicitly said 'merge it'.)"
            )
            return 0

    bundled = _bundled_index_mutation(stripped_parts)
    if bundled:
        emit_deny(
            f"COMMIT BLOCKED: `git {bundled}` and `git commit` in the same command. "
            "Stage first, confirm the staged diff, THEN commit as a separate "
            "tool call — bundling them lets more get committed than the review "
            "gate's hash ever covered."
        )
        return 0

    for part in stripped_parts:
        sub = git_subcommand(part.split())
        if sub == "commit":
            flag = _COMMIT_FORBIDDEN.search(part)
            if flag:
                emit_deny(
                    f"COMMIT FLAG BLOCKED: `{flag.group(1)}` is not allowed — `--amend` "
                    "rewrites history and `--no-verify`/`-n` skips the hooks. Make a new, "
                    "hook-verified commit instead."
                )
                return 0
            violation = _commit_form_violation(_args_after_subcommand(part.split()))
            if violation:
                emit_deny(f"COMMIT FORM BLOCKED: {violation}.")
                return 0
            if _current_branch(_repo_root()) in _PROTECTED:
                emit_deny(
                    "BRANCH BLOCKED: you are on a protected branch (`main`/`master`). "
                    "Never commit there — create a feature branch first "
                    "(`git checkout -b feature/<name>`), commit, push, and open a PR for "
                    "the user to merge."
                )
                return 0
        if sub == "push" and _pushes_protected(part, _current_branch(_repo_root())):
            emit_deny(
                "PUSH BLOCKED: pushing `main`/`master` is not allowed. Push your feature "
                "branch with an explicit refspec (`git push origin <branch>`) and open a PR."
            )
            return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
