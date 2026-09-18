#!/usr/bin/env python
"""PreToolUse(Bash) guardrail — pre-push checklist.

PORTABLE / generic: no project-specific paths. Self-gated to a real `git push`
via the shared `git_subcommand` (so `git log`, quoted echoes, `git -c k=v push`,
etc. are all handled correctly). Reminds the agent to run local validation before
incurring a CI round trip, and to confirm the push targets a feature branch
rather than main/master.

Fails open on any error.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _command_utils import (  # noqa: E402
    bash_command,
    emit_context,
    git_subcommand,
    project_opted_in,
    read_event,
    simple_commands,
)

MESSAGE = (
    "PRE-PUSH CHECK: "
    "(1) CI runs remotely and a red check means a fix-after-CI round trip — run this project's "
    "local validation first (linters, unit tests, build/parse, contract checks; e.g. a "
    "validate-local skill or the commands your CI workflow runs). "
    "(2) Confirm the push targets your feature branch, not main/master: check the refspec and the "
    "`-> <branch>` line in the push output. "
    "(3) Never force-push a shared branch."
)


def main() -> int:
    event = read_event()
    if not project_opted_in(event):
        return 0
    cmd = bash_command(event)
    if not cmd:
        return 0
    for part in simple_commands(cmd):
        if git_subcommand(part.split()) == "push":
            emit_context("PreToolUse", MESSAGE)
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
