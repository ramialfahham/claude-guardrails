#!/usr/bin/env python
"""PreToolUse(Edit/Write/MultiEdit) guardrail — plan-back before code.

PORTABLE / generic. The first time a session edits a code file while an
``.claude/active_work.md`` handover exists, this injects a requirement to restate
the handover spec and get the user's approval before continuing. It is the safety
net: even if the handover is slightly stale, the user is put back in the loop
before any work happens — which is exactly what stops a fresh agent silently
building the wrong thing.

Fires at most once per session (a temp marker keyed by session_id) so it does not
become noise. Skips edits to the handover file itself. Fails open on any error.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

HANDOVER_REL = os.path.join(".claude", "active_work.md")

MESSAGE = (
    "PLAN-BACK GATE: there is an active-work handover (.claude/active_work.md) and you "
    "are about to edit code. Before proceeding: (1) restate, in your own words, the "
    "current task and its locked spec from the handover; (2) confirm the file(s) you are "
    "about to change match that spec and the documented next action; (3) get the user's "
    "approval. If the handover does not fully specify what to build, STOP and ask — do "
    "not infer scope. (This fires once per session.)"
)


def _marker_path(session_id: str) -> str:
    safe = "".join(c for c in (session_id or "nosession") if c.isalnum() or c in "-_")
    return os.path.join(tempfile.gettempdir(), f"claude_handover_gate_{safe}")


def main() -> int:
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return 0
    try:
        root = event.get("cwd") or os.getcwd()
        if not os.path.isfile(os.path.join(root, HANDOVER_REL)):
            return 0  # no handover → nothing to gate against

        # Don't gate edits to the handover file itself (that IS the write-out).
        file_path = (event.get("tool_input") or {}).get("file_path") or ""
        if file_path.replace("\\", "/").endswith(".claude/active_work.md"):
            return 0

        marker = _marker_path(event.get("session_id", ""))
        if os.path.exists(marker):
            return 0  # already fired this session

        try:
            with open(marker, "w", encoding="utf-8") as f:
                f.write("fired")
        except Exception:
            pass  # marker is best-effort; still inject this once

        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": MESSAGE,
            }
        }))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
