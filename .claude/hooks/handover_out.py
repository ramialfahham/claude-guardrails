#!/usr/bin/env python
"""PreToolUse(Bash) guardrail — handover write-out reminder on push.

PORTABLE / generic. Self-gated to a real ``git push`` via the shared
`git_subcommand`. When a handover exists (.claude/active_work.md), reminds the
agent to update it to reflect the new state (done / in-progress / next action)
so the next session continues correctly.

Deliberately a reminder, not a hard block: this project's own guardrails note that
a hook which cries wolf gets ignored, and hard-blocking every code push is too
blunt. The hard enforcement lives in the read-in (handover_in.py) and the
plan-back gate (handover_plan_gate.py); this keeps the doc current.

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
    read_event,
    simple_commands,
)

HANDOVER_REL = os.path.join(".claude", "active_work.md")

MESSAGE = (
    "HANDOVER WRITE-OUT: before you finish, update .claude/active_work.md so the next "
    "session can continue safely — set status (done / in-progress / next concrete action), "
    "record any decision locked this session, and keep the do-NOT list current. The next "
    "fresh chat will be handed exactly this file and nothing else."
)


def main() -> int:
    event = read_event()
    cmd = bash_command(event)
    if not cmd:
        return 0
    try:
        root = event.get("cwd") or os.getcwd()
        if not os.path.isfile(os.path.join(root, HANDOVER_REL)):
            return 0  # no handover in this project → nothing to remind about
        for part in simple_commands(cmd):
            if git_subcommand(part.split()) == "push":
                emit_context("PreToolUse", MESSAGE)
                return 0
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
