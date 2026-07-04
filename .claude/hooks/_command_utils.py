"""Shared helpers for self-gating Bash hooks.

Self-gating means: the hook matcher is just "Bash" (fires on every Bash call),
and the *script* decides whether the command actually matches. This avoids the
fragile `if: Bash(pattern*)` matcher, which in practice fires on unrelated
read-only commands (e.g. `git log --grep=merge`, `cat`) — a cry-wolf failure
that trains the agent to ignore the guardrail.

Every hook that uses these helpers must fail OPEN: on any unexpected error,
return without blocking, so a hook bug never breaks the user's workflow.
"""

from __future__ import annotations

import json
import re
import sys

# Shell operators that separate one simple-command from the next.
_SEP = re.compile(r"\|\||&&|[;|\n]")
# Leading noise to strip before reading the command's first real token:
# env assignments (FOO=bar), and common wrappers.
_PREFIX = re.compile(r"^(?:\w+=\S*\s+|sudo\s+|command\s+|nohup\s+|time\s+|env\s+)+")


def read_event() -> dict:
    """Read and parse the hook event JSON from stdin. {} on any failure."""
    try:
        return json.loads(sys.stdin.read() or "{}")
    except Exception:
        return {}


def bash_command(event: dict) -> str:
    """Extract the Bash command string from a hook event, or ''."""
    try:
        return (event.get("tool_input") or {}).get("command") or ""
    except Exception:
        return ""


def simple_commands(command: str):
    """Yield each simple-command in a (possibly compound) shell command,
    with leading env-assignments / wrappers stripped, so callers can match
    against the actual invocation rather than substrings anywhere in the line."""
    for part in _SEP.split(command or ""):
        part = part.strip()
        if not part:
            continue
        yield _PREFIX.sub("", part).strip()


# git global options that consume the FOLLOWING token as their argument, so we
# can skip past them to find the real subcommand (e.g. `git -c k=v commit`).
_GIT_OPTS_WITH_ARG = {"-C", "-c", "--git-dir", "--work-tree", "--namespace",
                      "--super-prefix"}


def git_subcommand(toks: list[str]) -> str | None:
    """The git subcommand in a token list, skipping global options and their
    arguments, or None if this isn't a `git` invocation. So `git log --grep
    commit` returns 'log' (not a commit) while `git -c k=v commit` returns
    'commit'. Matching the subcommand — not a substring anywhere in the line —
    is what keeps the guards from tripping on read-only commands that merely
    contain 'commit', and from missing a commit hidden behind global options."""
    if not toks or toks[0] != "git":
        return None
    i = 1
    while i < len(toks):
        tok = toks[i]
        if tok in _GIT_OPTS_WITH_ARG:
            i += 2  # option consumes the next token as its value
            continue
        if tok.startswith("-"):
            i += 1  # standalone global flag (e.g. --no-pager, --exec-path=x)
            continue
        return tok  # first non-option token is the subcommand
    return None


_HEREDOC_MARK = re.compile(r"<<-?\s*'?\"?\w+")
_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")


def strip_quoted_and_heredoc(command: str) -> str:
    """Command text with quoted substrings removed and everything from the first
    heredoc marker truncated. Lets callers scan for shell OPERATORS (redirects,
    flags) without false-positives on quoted SQL ("x > 0.5"), commit-message
    bodies, or heredoc content."""
    try:
        cut = _HEREDOC_MARK.search(command or "")
        head = command[: cut.start()] if cut else (command or "")
        return _QUOTED.sub(" ", head)
    except Exception:
        return command or ""


def emit_context(event_name: str, text: str) -> None:
    """Inject additional context for the model (non-blocking)."""
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "additionalContext": text,
        }
    }))


def emit_deny(reason: str) -> None:
    """Deny a PreToolUse tool call with a reason shown to the model."""
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
