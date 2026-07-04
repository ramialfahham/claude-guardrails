#!/usr/bin/env python
"""PreToolUse(Bash) guardrail — branch discipline (hard enforcement).

Self-gated to the actual command. Hard-blocks the shortcuts so the
new-branch -> PR -> user-merges workflow is enforced, not just advised:

  1. `git commit` while on `main`/`master`  -> blocked: branch first.
  2. `git push` of the `main`/`master` branch -> blocked: push a feature branch.
  3. `gh pr merge`                           -> blocked: the user merges, not the agent.
  4. `git commit --amend` / `--no-verify` / `-n` -> blocked: history stays
     append-only and hook-verified.

Fails OPEN: any error or non-matching command exits 0 with no output.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _command_utils import (  # noqa: E402
    bash_command,
    emit_deny,
    git_subcommand,
    read_event,
    simple_commands,
    strip_quoted_and_heredoc,
)

_GH_PR_MERGE = re.compile(r"gh\s+pr\s+merge\b")
_COMMIT_FORBIDDEN = re.compile(r"(?:^|\s)(--no-verify|--amend|-n)(?=\s|$)")
_PROTECTED = {"main", "master"}


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
    cmd = bash_command(read_event())
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
