#!/usr/bin/env python
"""PreToolUse(Bash) — block a commit until the change has been reviewed.

The blinded review gate. When you run `git commit`, this:
  1. hashes the staged diff,
  2. works out which reviewers are required for the staged files
     (.claude/review_routing.json in the project),
  3. reads .claude/task/review.md and BLOCKS the commit unless:
       - the recorded diff_sha256 matches the staged diff (so the review covers
         exactly what you are committing),
       - every required reviewer has a verdict and none is FAIL,
       - every ESCALATE has a recorded "CPO ANSWER:".
Commits that touch only bookkeeping files (.claude/task/**, active_work.md) are
exempt. Fails OPEN on any error — a gate bug must never block your workflow.

Wired in .claude/settings.json as:
  python "${CLAUDE_PROJECT_DIR}/.claude/hooks/commit_review_gate.py"
Run with a trailing --staged-hash to print the staged-diff hash for review.md.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
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
)

ROUTING_REL = os.path.join(".claude", "review_routing.json")
REVIEW_REL = os.path.join(".claude", "task", "review.md")


def _repo_root() -> str:
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def _staged_diff(root: str) -> bytes:
    # --no-renames + --no-abbrev pin the bytes so the hash is reproducible for
    # identical staged content (stable paths, full blob ids).
    # Exclude .claude/task/** so the hash covers ONLY the real change: review.md
    # records this very hash, so hashing it in would be a self-reference that can
    # never match once review.md is staged (the reported deadlock). Both the live
    # gate check and the --staged-hash printer go through here, so they always
    # apply the same exclusion and can't diverge.
    return subprocess.run(
        ["git", "diff", "--staged", "--no-renames", "--no-abbrev",
         "--", ".", ":(exclude).claude/task"],
        cwd=root, capture_output=True, timeout=30,
    ).stdout


def _staged_paths(root: str) -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--staged", "--name-only", "-z"],
        cwd=root, capture_output=True, text=True, timeout=30,
    ).stdout
    return [p.replace("\\", "/") for p in out.split("\0") if p]


def _load_routing(root: str) -> dict | None:
    try:
        with open(os.path.join(root, ROUTING_REL), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _required_reviewers(paths: list[str], routing: dict) -> set[str]:
    required = set(routing.get("always") or [])
    for path in paths:
        for pattern, reviewers in (routing.get("paths") or {}).items():
            if fnmatch.fnmatch(path, pattern):
                required.update(reviewers)
    return required


def _artifact_only(paths: list[str], routing: dict) -> bool:
    never = routing.get("artifact_only_never") or []
    if any(fnmatch.fnmatch(p, pat) for p in paths for pat in never):
        return False
    pats = routing.get("artifact_only") or []
    return bool(paths) and all(
        any(fnmatch.fnmatch(p, pat) for pat in pats) for p in paths
    )


def _sections(text: str) -> dict[str, str]:
    """Map '## name' -> body. Text before the first header is '_preamble'."""
    sections, name, buf = {}, "_preamble", []
    for line in text.splitlines():
        m = re.match(r"^##\s+(\S+)", line)
        if m:
            sections[name] = "\n".join(buf)
            name, buf = m.group(1), []
        else:
            buf.append(line)
    sections[name] = "\n".join(buf)
    return sections


_VERDICT_RE = re.compile(r"^VERDICT:\s*(PASS|FAIL|ESCALATE)\b", re.MULTILINE)


def _verdict(body: str) -> str | None:
    """The operative verdict in a reviewer's section body, or None. Reviewers end
    with the verdict block, so the LAST match wins — an earlier 'VERDICT: X' in
    prose or a quoted example doesn't override the real one."""
    matches = _VERDICT_RE.findall(body)
    return matches[-1] if matches else None


def _is_commit(cmd: str) -> bool:
    # Match `commit` only as the git SUBCOMMAND (git_subcommand, shared with
    # branch_discipline), not as a word anywhere in the line — otherwise
    # read-only commands like `git log --grep commit` trip the gate.
    for part in simple_commands(cmd):
        toks = part.split()
        if git_subcommand(toks) == "commit" and "--dry-run" not in toks:
            return True
    return False


def _gate(root: str) -> str | None:
    paths = _staged_paths(root)
    if not paths:
        return None  # nothing staged: let git complain
    routing = _load_routing(root)
    if routing is None:
        return None  # no routing anywhere: gate inactive (fail open)
    if _artifact_only(paths, routing):
        return None  # bookkeeping-only commit: exempt
    review_path = os.path.join(root, REVIEW_REL)
    if not os.path.isfile(review_path):
        return ("REVIEW GATE: no review found. Stage the change, run the required "
                "reviewers, and write .claude/task/review.md (see "
                "task/REVIEW_TEMPLATE.md), then commit.")
    text = open(review_path, encoding="utf-8", errors="replace").read()
    live = hashlib.sha256(_staged_diff(root)).hexdigest()
    m = re.search(r"diff_sha256:\s*([0-9a-fA-F]{64})", text)
    if not m or m.group(1).lower() != live:
        return ("REVIEW GATE: the staged change does not match the reviewed one "
                "(hash mismatch) — re-run the reviewers against the current "
                f"staged diff and update review.md. Current staged hash: {live}")
    # Read each verdict from its reviewer SECTION, not the raw text — a
    # 'VERDICT: FAIL' in prose or a quoted example must not block a review where
    # every real verdict passed, and a 'CPO ANSWER:' for one escalation must not
    # offset a different unanswered one.
    sections = _sections(text)
    verdicts = {name: _verdict(body) for name, body in sections.items()
                if name != "_preamble"}
    for reviewer in sorted(_required_reviewers(paths, routing)):
        if not verdicts.get(reviewer):
            return (f"REVIEW GATE: required reviewer '{reviewer}' has no verdict for "
                    "the staged files (see review_routing.json). Run it and record "
                    "its section in review.md.")
    failed = sorted(n for n, v in verdicts.items() if v == "FAIL")
    if failed:
        return (f"REVIEW GATE: reviewer '{failed[0]}' verdict is FAIL. Fix the "
                "findings and re-review.")
    for name in sorted(verdicts):
        if verdicts[name] == "ESCALATE" and "CPO ANSWER:" not in sections.get(name, ""):
            return (f"REVIEW GATE: reviewer '{name}' escalated with no recorded "
                    "'CPO ANSWER:'. Get the owner's decision, write it under the "
                    "question, then commit.")
    return None


def main() -> int:
    if "--staged-hash" in sys.argv:
        print(hashlib.sha256(_staged_diff(_repo_root())).hexdigest())
        return 0
    cmd = bash_command(read_event())
    if not cmd or not _is_commit(cmd):
        return 0
    try:
        reason = _gate(_repo_root())
    except Exception:
        return 0  # fail open
    if reason:
        emit_deny(reason)
    return 0


if __name__ == "__main__":
    sys.exit(main())
