#!/usr/bin/env python
"""PreToolUse guardrail — advisory reminder when unreviewed staged work exists.

PORTABLE / generic. commit_review_gate.py only enforces at commit time
(PreToolUse(Bash), matched to `git commit`): if a session stages real changes
and does other work without ever attempting a commit, nothing today tells
anyone that unreviewed work is sitting in the index. This hook closes that
gap by checking, before a relevant Bash call, whether commit_review_gate.py's
OWN gate would currently block a commit — reusing its real _gate() function
directly rather than re-deriving "is this reviewed" a second time.

Deliberately advisory-only: it injects a reminder Claude sees
(additionalContext) alongside the next Bash call, and never sets
permissionDecision — the call proceeds exactly as it would with no hook
attached. This is NOT a Stop hook, and that is a deliberate, load-bearing
choice, not a stylistic one: an earlier version of this hook used the `Stop`
event, and Anthropic's own docs (code.claude.com/docs/en/hooks, "Stop
decision control") say plainly that using `additionalContext` there "keeps
the conversation going through the same loop protections as
`decision: "block"`, namely the `stop_hook_active` input and the
8-consecutive-continuation cap" — i.e. on `Stop`, additionalContext forces an
automatic re-invocation, functionally indistinguishable from a block except
for how it's labeled in the transcript. There is no passive alternative on
that event either: plain stdout on `Stop` goes only to the debug log, per
the same docs' "Exit code 0" section (Stop is not in the short list of
events — UserPromptSubmit, UserPromptExpansion, SessionStart, PostModelSwitch
— where plain stdout reaches Claude). That directly contradicted the owner's
explicit decision (advisory only, never blocks the turn from ending) and was
discovered live, during this session's own review, by the hook repeatedly
forcing this very session to continue every time it fired. Rebuilt as a
PreToolUse hook instead: the docs' own "PreToolUse decision control" table
describes `additionalContext` there as just "String added to Claude's
context alongside the tool result" — with no continuation/loop language at
all — which matches this repo's own established, working precedent
(handover_plan_gate.py, plan_implement_gate.py: both PreToolUse hooks that
only ever inject additionalContext, never a decision, and neither forces
anything).

Matcher: `Bash` (see .claude/settings.json). SELF-GATES on the actual
command, matching every other hook in that same matcher group
(commit_review_gate.py, branch_discipline.py, secret_scan.py,
pre_push_gate.py, handover_out.py all extract the command and return early
before doing real work — _command_utils.py documents this as the house
rule: "the script decides whether the command actually matches," not the
matcher alone). An earlier draft ran crg._gate() unconditionally on every
Bash call regardless of command — review correctly flagged this as the one
hook in the group NOT following that rule, running its full expensive check
on `ls`, `pytest`, arbitrary Python, anything. Fixed by matching only the
three "am I done" moments staged work would actually show up at:
`git status`, `git commit`, `git push` — a plain command filter (reusing
_command_utils.git_subcommand/simple_commands, not a cache, not new
machinery), so a session doing unrelated work between edits doesn't pay
_gate()'s cost at all.

Explicitly skips subagent-issued tool calls (checks `agent_id`, present only
when a hook fires inside a subagent call — see "common input fields" in
Anthropic's hooks reference). This matters concretely for this repo's own
blinded reviewers (scope-auditor, platform-reviewer): without this check, a
Bash-capable future reviewer running mid-review — while the diff under
review is, by definition, not yet reviewed — would have this hook's note
("...run the required reviewers and write .claude/task/review.md...")
injected into its own blinded context. Today's shipped reviewers only have
Read/Grep/Glob and can't trigger this hook regardless, but the check is
cheap and removes the dependency on that happening to stay true.

_gate() already returns None for an empty/bookkeeping-only staged diff (see
its own artifact_only handling), so a non-None reason here already means
"something real is staged and unreviewed" — no need to re-check that here.

Fails open on any error, matching every other hook in this repo.

Suppression: exactly ONE marker file per session (same bounded footprint as
handover_plan_gate.py — not one file per distinct reason ever seen, which
would grow without bound). The marker's CONTENT is a hash of the last reason
that actually fired; each call compares the current reason's hash against
that stored value, fires only when they differ, then overwrites the marker
with the new hash. Comparing against only the LAST fired reason (not the
full set of reasons ever seen this session) is deliberate: a regression back
to a previously-seen reason (e.g. a regenerated review.md drops a reviewer's
section again after it was already fixed once) must still re-fire, since
that is a genuinely new lapse, not a repeat of the same unresolved state.
This suppression bounds the injected NOTE only — _gate() itself still runs
on every matched, relevant Bash call while something is staged (see COST
below); the marker is consulted only on its result.

COST: bounded by the command self-gate above, not by a cache. An earlier
version ran unconditionally on every Bash call; a version after that tried
to cache _gate()'s own expensive check behind a fingerprint, which two
independent review rounds found incomplete in ways that silently suppressed
real notes (missed review_routing.json edits and the base branch moving) —
that cache was dropped as unsound, not worth engineering further for a
purely advisory hook (see git history / .claude/task/contract.md's
amendments for the full account). The command self-gate here is the actual
fix: _gate()'s real cost (up to ~15+ git subprocesses once something is
staged — commit_review_gate.py's _cumulative_paths and _diff_to_hash each
independently redo the same base-ref/merge-base resolution) now only runs
on `git status`/`commit`/`push` attempts, not on every Bash call regardless
of content. Stated plainly, not minimized: this is NOT the same cadence
commit_review_gate.py pays. The trigger set is larger and dominated by
`git status` — far more frequent than `git commit` in a normal session.
`git commit` is separately covered by commit_review_gate.py's own blocking
gate, but `git push` is NOT covered by pre_push_gate.py — that hook only
emits a fixed local-validation/branch-target checklist and never reads
review state — so `git status` and `git push` are both genuine, otherwise-
uncovered triggers for this hook, not redundant with an existing gate. On an
actual `git commit`, _gate() runs TWICE — this hook and commit_review_gate.py
are separate processes in the same matcher group with no shared state, each
independently paying the full cost. The common idle case (nothing staged)
is cheaper: _gate() short-
circuits to a single `git diff --staged` before doing anything else.
"""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HOOKS_DIR)
import commit_review_gate as crg  # noqa: E402
from _command_utils import (  # noqa: E402
    bash_command,
    emit_context,
    git_subcommand,
    read_event,
    simple_commands,
)

MESSAGE_PREFIX = (
    "COMPLETION GATE: there are unreviewed staged changes in the working "
    "tree. This is advisory only — it does not block this tool call — but "
    "before treating the work as done, either run the required reviewers "
    "and write .claude/task/review.md, or explicitly tell the user the work "
    "is paused/incomplete. Reason from the review gate: "
)

_RELEVANT_SUBCOMMANDS = {"status", "commit", "push"}


def _is_relevant(cmd: str) -> bool:
    """True if any simple-command in `cmd` is one of the "am I done"
    git moments this hook cares about — matches commit_review_gate.py's own
    _is_commit shape (check the real subcommand, not a substring)."""
    return any(git_subcommand(part.split()) in _RELEVANT_SUBCOMMANDS
               for part in simple_commands(cmd))


def _marker_path(session_id: str) -> str:
    safe_session = "".join(c for c in (session_id or "nosession") if c.isalnum() or c in "-_")
    return os.path.join(tempfile.gettempdir(), f"claude_completion_gate_{safe_session}")


def _should_fire(marker: str, reason: str) -> bool:
    """True iff `reason` differs from the last one this marker recorded —
    comparing against only the most recent value (not the full history of
    reasons seen), so a regression back to a previously-fired reason still
    re-fires. Best-effort: a marker read/write failure never suppresses a
    real note, it only means suppression itself doesn't persist."""
    reason_key = hashlib.sha256(reason.encode("utf-8")).hexdigest()
    try:
        with open(marker, encoding="utf-8") as f:
            last = f.read().strip()
    except OSError:
        last = None
    if last == reason_key:
        return False
    try:
        with open(marker, "w", encoding="utf-8") as f:
            f.write(reason_key)
    except Exception:
        pass
    return True


def main() -> int:
    try:
        event = read_event()
        if event.get("agent_id"):
            return 0
        cmd = bash_command(event)
        if not cmd or not _is_relevant(cmd):
            return 0
        root = crg._repo_root()
        reason = crg._gate(root)
        if reason:
            marker = _marker_path(event.get("session_id", ""))
            if _should_fire(marker, reason):
                emit_context("PreToolUse", MESSAGE_PREFIX + reason)
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
