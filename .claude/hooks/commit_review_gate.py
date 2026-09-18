#!/usr/bin/env python
"""PreToolUse(Bash) — block a commit until the change has been reviewed.

The blinded review gate. When you run `git commit`, this:
  1. hashes the CUMULATIVE diff — everything already committed on this branch
     since it split from the base branch (main/master, local or remote),
     PLUS what's currently staged — not just the staged diff alone. A
     multi-commit branch's review must cover the whole branch, not silently
     just its last increment; this also matches what the reviewer agent
     prompts (platform-reviewer.md, scope-auditor.md) already say their own input
     is ("the cumulative branch diff vs the base branch").
  2. works out which reviewers are required for the changed files
     (.claude/review_routing.json in the project),
  3. reads .claude/task/review.md and BLOCKS the commit unless:
       - the recorded diff_sha256 matches the cumulative diff (so the review
         covers exactly what the branch will contain after this commit),
       - every required reviewer has a verdict and none is FAIL,
       - every ESCALATE has a recorded "CPO ANSWER:",
       - if review.md's optional `rounds:` counter exceeds a cap, a recorded
         "CPO ANSWER:" is present somewhere — forces escalation to the owner
         instead of an unbounded reviewer back-and-forth. `rounds:` is
         SELF-REPORTED (whoever re-reviews increments it) — the hook enforces
         the cap once recorded, it doesn't independently derive the count.
Commits that touch only bookkeeping files (.claude/task/**, active_work.md) are
exempt. Fails OPEN on any error — a gate bug must never block your workflow.

Wired in .claude/settings.json as:
  python "${CLAUDE_PROJECT_DIR}/.claude/hooks/commit_review_gate.py"
Run with a trailing --diff-hash to print the diff hash for review.md
(--staged-hash also accepted, for anything already using that name).
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
    emit_context,
    emit_deny,
    is_commit_subcommand,
    project_opted_in,
    read_event,
    simple_commands,
)

ROUTING_REL = os.path.join(".claude", "review_routing.json")
REVIEW_REL = os.path.join(".claude", "task", "review.md")

# Candidate base-branch refs, checked in order — first one that actually
# resolves wins. Local before remote, main before master; a repo can have
# either remote name depending on which provider it was migrated to/from.
_BASE_REF_CANDIDATES = (
    "main", "master",
    "origin/main", "origin/master",
    "gitlab/main", "gitlab/master",
)
_ROUNDS_RE = re.compile(r"^rounds:\s*(\d+)", re.MULTILINE)
_ROUNDS_CAP = 3


def _repo_root() -> str:
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def _rev_parse_ok(root: str, ref: str) -> bool:
    return subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", ref],
        cwd=root, capture_output=True, timeout=10,
    ).returncode == 0


def _base_ref(root: str) -> str | None:
    for ref in _BASE_REF_CANDIDATES:
        if _rev_parse_ok(root, ref):
            return ref
    return None


def _merge_base(root: str, base_ref: str) -> str | None:
    out = subprocess.run(
        ["git", "merge-base", base_ref, "HEAD"],
        cwd=root, capture_output=True, text=True, timeout=10,
    ).stdout.strip()
    return out or None


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


def _diff_to_hash(root: str) -> bytes:
    """The diff review.md's hash must cover: everything since the branch split
    from its base, PLUS what's currently staged. Falls back to staged-only
    (the old behavior) when no base ref is discoverable at all — e.g. a
    shallow clone with no main/master ref reachable — so this never blocks on
    an environment quirk; it only widens coverage when it safely can."""
    base = _base_ref(root)
    merge_base = _merge_base(root, base) if base else None
    if not merge_base:
        return _staged_diff(root)
    # `git diff --cached <commit>`: commit vs the INDEX (staged state), which
    # for a clean working tree is exactly "everything committed since
    # <commit> plus what's staged now" — the cumulative diff this commit is
    # about to extend the branch to.
    return subprocess.run(
        ["git", "diff", "--cached", "--no-renames", "--no-abbrev", merge_base,
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
    # is_commit_subcommand (shared with branch_discipline, secret_scan) matches
    # `commit` only as the git SUBCOMMAND, not as a word anywhere in the line —
    # otherwise read-only commands like `git log --grep commit` trip the gate —
    # and excludes --dry-run, which commits nothing.
    return any(is_commit_subcommand(part.split()) for part in simple_commands(cmd))


def _cumulative_paths(root: str) -> list[str]:
    """Same cumulative scope as _diff_to_hash, as a path list — so which
    reviewers are required (and whether this is bookkeeping-only) reflects
    the whole branch, not just this commit's staged files. Falls back to the
    staged-only list under the same no-base-ref condition as _diff_to_hash."""
    base = _base_ref(root)
    merge_base = _merge_base(root, base) if base else None
    if not merge_base:
        return _staged_paths(root)
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "-z", merge_base],
        cwd=root, capture_output=True, text=True, timeout=30,
    ).stdout
    return [p.replace("\\", "/") for p in out.split("\0") if p]


def _rounds(text: str) -> int:
    m = _ROUNDS_RE.search(text)
    return int(m.group(1)) if m else 1


def _gate(root: str) -> str | None:
    staged = _staged_paths(root)
    if not staged:
        return None  # nothing staged: let git complain
    routing = _load_routing(root)
    if routing is None:
        return None  # no routing anywhere: gate inactive (fail open)
    paths = _cumulative_paths(root) or staged
    if _artifact_only(paths, routing):
        return None  # bookkeeping-only for the WHOLE branch: exempt
    review_path = os.path.join(root, REVIEW_REL)
    if not os.path.isfile(review_path):
        return ("REVIEW GATE: no review found. Stage the change, run the required "
                "reviewers, and write .claude/task/review.md (see "
                "task/REVIEW_TEMPLATE.md), then commit.")
    text = open(review_path, encoding="utf-8", errors="replace").read()
    live = hashlib.sha256(_diff_to_hash(root)).hexdigest()
    m = re.search(r"diff_sha256:\s*([0-9a-fA-F]{64})", text)
    if not m or m.group(1).lower() != live:
        return ("REVIEW GATE: the reviewed diff doesn't match the branch's current "
                "cumulative diff (everything committed since the base branch, plus "
                "what's staged now) — re-run the reviewers and update review.md. "
                f"Current hash: {live}")
    if _rounds(text) > _ROUNDS_CAP and "CPO ANSWER:" not in text:
        return (f"REVIEW GATE: review.md reports round {_rounds(text)}, past the "
                f"cap of {_ROUNDS_CAP}. Get the owner's decision on why this keeps "
                "failing review, record it as a 'CPO ANSWER:' anywhere in "
                "review.md, then commit.")
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
                    "the changed files (see review_routing.json). Run it and record "
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
    # --diff-hash is the current name (it's the cumulative diff, not just
    # staged); --staged-hash kept as an alias so nothing that already calls
    # it breaks.
    if "--diff-hash" in sys.argv or "--staged-hash" in sys.argv:
        print(hashlib.sha256(_diff_to_hash(_repo_root())).hexdigest())
        return 0
    event = read_event()
    if not project_opted_in(event):
        return 0
    cmd = bash_command(event)
    if not cmd or not _is_commit(cmd):
        return 0
    root = _repo_root()
    try:
        reason = _gate(root)
    except Exception:
        return 0  # fail open
    if reason:
        emit_deny(reason)
        return 0
    # Only reachable when ALLOWING — never combine with emit_deny above.
    # Every other emit_context call in this repo is the sole output of its
    # invocation; printing a context note AND a deny would put two JSON
    # objects on one hook's stdout, an untested shape that could make the
    # harness treat the whole output as malformed and silently drop the deny.
    try:
        if _base_ref(root) is None:
            emit_context(
                "PreToolUse",
                "REVIEW GATE NOTE: no base branch (main/master, local or remote) "
                "could be resolved, so the review hash covered only the currently "
                "staged diff, not the whole branch. If this branch has multiple "
                "commits, the review may not have covered all of them."
            )
    except Exception:
        pass  # the note is a courtesy; never let it turn into a false block
    return 0


if __name__ == "__main__":
    sys.exit(main())
