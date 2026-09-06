#!/usr/bin/env python
"""PreToolUse(Bash) — block a commit whose staged changes contain something
shaped like a real credential.

Deliberately narrow: matches well-known TOKEN SHAPES (AWS, GitHub, Slack,
Google, OpenAI/Anthropic-style keys, private-key headers) in ADDED lines of
the staged diff only. No generic `password=`/`secret=` keyword heuristic —
this repo's own _command_utils.py design note applies here too: a noisy,
false-positive-prone guard trains the agent to ignore it. A real secret that
doesn't match a known shape won't be caught — a stated limitation, not a
silent one.

Fails OPEN: any error (including `git diff` itself failing) exits 0 with no
output, same as every other hook here.
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
    is_commit_subcommand,
    read_event,
    simple_commands,
)

_PATTERNS = [
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("Slack token", re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}")),
    ("Google API key", re.compile(r"AIza[0-9A-Za-z\-_]{35}")),
    ("OpenAI/Anthropic-style secret key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("private key block",
     re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----")),
]


def _repo_root() -> str:
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def _is_commit_command(cmd: str) -> bool:
    return any(is_commit_subcommand(part.split()) for part in simple_commands(cmd))


def _added_lines_by_file(diff_text: str):
    """Yield (file, content) for every added line in a unified diff — content
    with the leading '+' stripped, file from the most recent '+++' header."""
    current_file = "?"
    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            f = line[4:].strip()
            current_file = f[2:] if f.startswith("b/") else f
            continue
        if line.startswith("+") and not line.startswith("+++"):
            yield current_file, line[1:]


def _find_secrets(diff_text: str) -> list[str]:
    findings = set()
    for file, content in _added_lines_by_file(diff_text):
        for name, pattern in _PATTERNS:
            if pattern.search(content):
                findings.add(f"{name} in {file}")
    return sorted(findings)


def main() -> int:
    cmd = bash_command(read_event())
    if not cmd or not _is_commit_command(cmd):
        return 0
    try:
        diff_text = subprocess.run(
            ["git", "diff", "--staged", "--no-color"],
            cwd=_repo_root(), capture_output=True, text=True, timeout=30,
        ).stdout
        findings = _find_secrets(diff_text)
    except Exception:
        return 0  # fail open
    if findings:
        emit_deny(
            "SECRET SCAN BLOCKED: staged changes look like they contain a "
            "credential — " + "; ".join(findings) + ". Remove it, rotate the "
            "credential if it's real, and use an environment variable or a "
            "secret manager instead. If this is a false positive (a test "
            "fixture, a placeholder), rewrite it so the value doesn't match "
            "a real token shape."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
