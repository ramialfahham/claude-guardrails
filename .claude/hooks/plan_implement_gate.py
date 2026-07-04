#!/usr/bin/env python
"""PostToolUse(ExitPlanMode) guardrail — re-ground before implementing.

PORTABLE / generic: no project-specific paths. Fires right after a plan is
approved (the "before you start implementing" moment) and injects a short
checklist that targets the two top causes of rework: scope drift and putting
logic in the wrong place.

Fails open on any error.
"""

from __future__ import annotations

import json
import sys

MESSAGE = (
    "BEFORE YOU IMPLEMENT (plan just approved): "
    "(1) Re-read the standards/contract docs that govern the files you're about to change — "
    "architecture, layering, working-agreement, CONTRIBUTING, or an AGENTS/CLAUDE file — whichever exist in this repo. "
    "(2) For each change, name the layer / module / component it belongs in and confirm that's the right place "
    "(don't put logic where it's merely convenient). "
    "(3) Hold strictly to the approved scope — if you spot an adjacent issue, flag it separately, don't fold it in. "
    "(4) Plan to run the project's local validation before pushing. "
    "Scope drift and misplaced logic are the top causes of revert-and-rework."
)


def main() -> int:
    try:
        sys.stdin.read()  # drain the event; we fire unconditionally on ExitPlanMode
    except Exception:
        pass
    try:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": MESSAGE,
            }
        }))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
