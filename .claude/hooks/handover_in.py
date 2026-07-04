#!/usr/bin/env python
"""SessionStart guardrail — inject the project's active-work handover.

PORTABLE / generic: no project-specific paths. On every session start, reads
``<project>/.claude/active_work.md`` and injects it into the new chat so a fresh
agent continues from the exact documented state instead of re-deriving it from a
thin issue title or a long memory file (which is how scoped work gets silently
re-scoped). If the handover file is missing, says so explicitly.

This is the read-in half of the enforced handover. The write-out half is the
push reminder (handover_out.py); the safety net is the plan-back gate
(handover_plan_gate.py).

Fails open on any error (no output, exit 0).
"""

from __future__ import annotations

import json
import os
import sys

HANDOVER_REL = os.path.join(".claude", "active_work.md")
MAX_BYTES = 16000  # keep the injection bounded


def main() -> int:
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return 0
    try:
        root = event.get("cwd") or os.getcwd()
        path = os.path.join(root, HANDOVER_REL)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                content = f.read(MAX_BYTES)
            msg = (
                "ACTIVE WORK HANDOVER (.claude/active_work.md) — read this before doing "
                "anything else. Continue from this documented state. Do NOT re-scope, "
                "and do NOT infer the task from an issue title, a memory file, or your "
                "own judgement when this says otherwise. If you are about to write code "
                "on the work described below, first restate this spec back to the user "
                "and get approval.\n\n----- BEGIN HANDOVER -----\n"
                + content
                + "\n----- END HANDOVER -----"
            )
        else:
            msg = (
                "No .claude/active_work.md found in this project. If you are continuing "
                "prior work, ask the user for the current handover (or create "
                ".claude/active_work.md capturing it) BEFORE writing any code."
            )
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": msg,
            }
        }))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
