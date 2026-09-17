#!/usr/bin/env bash
# SessionStart preflight. The guardrail hooks are Python scripts run through a
# bash shell; when `python` is not on PATH they fail open — they silently do
# nothing. Warn loudly here so a missing interpreter is visible, instead of
# leaving the session unknowingly unguarded. Never blocks (exit 0 always).
if ! command -v python >/dev/null 2>&1; then
  printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"claude-project-kit: python was not found on PATH, so the guardrail hooks (branch discipline, review gate, handover, plan and pre-push gates) will silently NOT run. Install Python 3 and make sure the python command resolves in this shell."}}'
fi
exit 0
