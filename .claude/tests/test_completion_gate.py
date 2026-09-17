"""Tests for .claude/hooks/completion_gate.py — the advisory PreToolUse hook.

Exercises the real hook through a simulated PreToolUse event against real
tempdir git repos, the same pattern test_commit_review_gate.py's own
_run_main_in uses. Central guarantee under test: this hook NEVER sets
permissionDecision — it only ever adds an advisory additionalContext note
next to the next tool call, or says nothing at all — and it suppresses
repeat nagging about an unchanged unreviewed state using exactly ONE marker
file per session (never one file per reason ever seen — that would grow
without bound), whose content is the last reason that fired, so it re-fires
whenever the current reason differs from that last value, including a
regression back to a previously-seen one.

This hook was originally built as a Stop hook; that design was scrapped
after discovering Anthropic's docs state that `additionalContext` on `Stop`
forces the same automatic-continuation loop as `decision: "block"` (see
completion_gate.py's own docstring) — i.e. it was never actually advisory.
Rebuilt as PreToolUse, whose additionalContext is genuinely non-blocking per
the same docs.

A later attempt to cache crg._gate()'s own expensive check behind a
fingerprint was tried and reverted (see completion_gate.py's own docstring,
"COST" section) after two review rounds found the fingerprint silently
missed real state changes (review_routing.json edits, the base branch
moving) — a correctness bug, not just an incomplete optimization. The real
fix for cost was a command self-gate instead: this hook only calls
crg._gate() for real when the Bash command is git status/commit/push (see
_is_relevant), matching every sibling hook in the same matcher group. It
still only suppresses the printed NOTE via the marker, not the check itself,
for whichever calls actually reach it.

Runnable with `pytest` or directly: `python .claude/tests/test_completion_gate.py`.
"""

import contextlib
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_CLAUDE_DIR = os.path.dirname(_TESTS_DIR)
_HOOKS = os.path.join(_CLAUDE_DIR, "hooks")
sys.path.insert(0, _HOOKS)

import completion_gate as cg  # noqa: E402
from commit_review_gate import _diff_to_hash  # noqa: E402

_GIT = shutil.which("git")


def _cleanup_markers(session_id: str) -> None:
    """Remove the single suppression-marker file this session_id may have
    created (cg._marker_path is the real, exact path — not a glob guess), so
    a test run leaves no state behind for a later run or a real session with
    the same generated id to trip over."""
    try:
        os.remove(cg._marker_path(session_id))
    except OSError:
        pass


@contextlib.contextmanager
def _run_main_in(repo: str, session_id: str | None = None, tool_name: str = "Bash",
                  agent_id: str | None = None, command: str = "git status"):
    """Simulate a real PreToolUse-event hook invocation: stdin carries the
    event JSON, CLAUDE_PROJECT_DIR points at `repo`. Yields (stdout,
    exit_code) — exit_code is main()'s own return value (this is an
    in-process call, not a subprocess), so callers can assert on what was
    actually emitted and on that return value, not on a real process's exit
    status. `tool_name` defaults to "Bash" to match the real matcher this
    hook is wired under in .claude/settings.json. `command` defaults to
    "git status" — one of the three commands _is_relevant actually matches —
    so callers exercising the review-gate logic don't also have to think
    about the command self-gate; pass an irrelevant command explicitly to
    test that self-gate itself. Pass `agent_id` to simulate a subagent-issued
    tool call (present only in that case, per Anthropic's own "common input
    fields" reference).

    If session_id is omitted, a fresh random one is used and its marker file
    (if any) is cleaned up automatically when this context exits — ordinary
    tests that don't care about suppression can't leak marker state into
    other tests or later runs. Pass an explicit session_id to exercise
    suppression across multiple calls; the caller then owns cleanup via
    _cleanup_markers when done."""
    auto_session = session_id is None
    if auto_session:
        session_id = f"test-{uuid.uuid4().hex}"
    event_dict = {
        "session_id": session_id,
        "cwd": repo,
        "hook_event_name": "PreToolUse",
        "tool_name": tool_name,
        "tool_input": {"command": command},
    }
    if agent_id:
        event_dict["agent_id"] = agent_id
    event = json.dumps(event_dict)
    old_argv, old_stdin = sys.argv, sys.stdin
    old_env = os.environ.get("CLAUDE_PROJECT_DIR")
    sys.argv = ["completion_gate.py"]
    sys.stdin = io.StringIO(event)
    os.environ["CLAUDE_PROJECT_DIR"] = repo
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            exit_code = cg.main()
        yield buf.getvalue(), exit_code
    finally:
        sys.argv, sys.stdin = old_argv, old_stdin
        if old_env is None:
            os.environ.pop("CLAUDE_PROJECT_DIR", None)
        else:
            os.environ["CLAUDE_PROJECT_DIR"] = old_env
        if auto_session:
            _cleanup_markers(session_id)


def _git(repo, *args):
    subprocess.run([_GIT, *args], cwd=repo, check=True,
                    capture_output=True, timeout=30)


def _init_repo(repo: str, routing: dict) -> None:
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t.t")
    _git(repo, "config", "user.name", "t")
    os.makedirs(os.path.join(repo, ".claude", "task"), exist_ok=True)
    with open(os.path.join(repo, ".claude", "review_routing.json"), "w", encoding="utf-8") as f:
        json.dump(routing, f)


def _assert_never_denies(output: str, exit_code: int) -> None:
    """The central guarantee: no matter what this hook prints or returns, it
    must never deny/block a tool call. Checked structurally (parse and
    inspect the JSON: no permissionDecision, since setting one — even
    "allow" — would mean this hook is making a permission decision rather
    than purely adding context) and via main()'s own return value (never 2 —
    the documented tool-call-blocking exit code for hooks generally)."""
    assert exit_code != 2, f"completion_gate.py must never exit 2 (blocks): got {exit_code!r}"
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        payload = json.loads(line)
        hook_output = payload.get("hookSpecificOutput", {})
        assert "permissionDecision" not in hook_output, (
            f"completion_gate.py must never set permissionDecision: {payload!r}")


def test_no_note_when_nothing_staged():
    if not _GIT:
        raise unittest.SkipTest("no git on PATH")
    with tempfile.TemporaryDirectory() as repo:
        _init_repo(repo, {"always": ["scope-auditor"], "paths": {}})
        with _run_main_in(repo) as (output, exit_code):
            pass
        assert output.strip() == "", "no staged changes should produce no note"
        _assert_never_denies(output, exit_code)


def test_note_emitted_for_unreviewed_real_work():
    if not _GIT:
        raise unittest.SkipTest("no git on PATH")
    with tempfile.TemporaryDirectory() as repo:
        _init_repo(repo, {"always": ["scope-auditor"], "paths": {}})
        with open(os.path.join(repo, "model.sql"), "w", encoding="utf-8") as f:
            f.write("select 1\n")
        _git(repo, "add", "model.sql")
        with _run_main_in(repo) as (output, exit_code):
            pass
        assert "COMPLETION GATE" in output, "unreviewed real staged work should get a note"
        payload = json.loads(output.strip())
        assert payload["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
        assert "additionalContext" in payload["hookSpecificOutput"]
        _assert_never_denies(output, exit_code)


def test_irrelevant_bash_command_skipped_without_running_gate():
    # The command self-gate: this hook must not even call crg._gate() for a
    # Bash command that isn't one of the "am I done" moments (git
    # status/commit/push) — proven by counting real _gate() calls, since "no
    # note" alone wouldn't distinguish "skipped" from "checked and
    # suppressed." git status/commit/push must each still reach the real
    # check.
    if not _GIT:
        raise unittest.SkipTest("no git on PATH")
    with tempfile.TemporaryDirectory() as repo:
        _init_repo(repo, {"always": ["scope-auditor"], "paths": {}})
        with open(os.path.join(repo, "model.sql"), "w", encoding="utf-8") as f:
            f.write("select 1\n")
        _git(repo, "add", "model.sql")

        calls = []
        original_gate = cg.crg._gate

        def _counting_gate(root):
            calls.append(1)
            return original_gate(root)

        cg.crg._gate = _counting_gate
        try:
            for irrelevant in ("ls -la", "pytest", "python foo.py", "git log", "git diff"):
                with _run_main_in(repo, command=irrelevant) as (output, exit_code):
                    pass
                assert output.strip() == "", f"{irrelevant!r} must not get a completion-gate note"
                _assert_never_denies(output, exit_code)
            assert not calls, "an irrelevant Bash command must never even call _gate()"

            for relevant in ("git status", "git commit -m x", "git push"):
                with _run_main_in(repo, command=relevant) as (output, exit_code):
                    pass
                assert "COMPLETION GATE" in output, f"{relevant!r} must still trigger the real check"
                _assert_never_denies(output, exit_code)
            assert len(calls) == 3, "each relevant command must have run the real gate check"
        finally:
            cg.crg._gate = original_gate


def test_no_note_for_bookkeeping_only_diff():
    # matches commit_review_gate._gate's own artifact_only exemption — a
    # diff touching only .claude/task/* is exempt from review entirely, so
    # _gate() itself returns None and this hook must stay silent
    if not _GIT:
        raise unittest.SkipTest("no git on PATH")
    with tempfile.TemporaryDirectory() as repo:
        _init_repo(repo, {
            "always": ["scope-auditor"], "paths": {},
            "artifact_only": [".claude/task/*"], "artifact_only_never": [],
        })
        with open(os.path.join(repo, ".claude", "task", "notes.md"), "w", encoding="utf-8") as f:
            f.write("scratch notes\n")
        _git(repo, "add", ".claude/task/notes.md")
        with _run_main_in(repo) as (output, exit_code):
            pass
        assert output.strip() == "", "bookkeeping-only staged diff should produce no note"
        _assert_never_denies(output, exit_code)


def test_no_note_when_properly_reviewed():
    if not _GIT:
        raise unittest.SkipTest("no git on PATH")
    with tempfile.TemporaryDirectory() as repo:
        _init_repo(repo, {"always": ["scope-auditor"], "paths": {}})
        with open(os.path.join(repo, "model.sql"), "w", encoding="utf-8") as f:
            f.write("select 1\n")
        _git(repo, "add", "model.sql")
        live = hashlib.sha256(_diff_to_hash(repo)).hexdigest()
        review = (f"diff_sha256: {live}\n"
                  "## scope-auditor\nVERDICT: PASS\nrisks_checked:\n- a\n- b\n")
        with open(os.path.join(repo, ".claude", "task", "review.md"), "w", encoding="utf-8") as f:
            f.write(review)
        with _run_main_in(repo) as (output, exit_code):
            pass
        assert output.strip() == "", "properly reviewed staged work should produce no note"
        _assert_never_denies(output, exit_code)


def test_no_note_for_subagent_issued_tool_call():
    # A subagent (this repo's own scope-auditor/platform-reviewer included) calls
    # tools with an `agent_id` in the event — a hook firing on those must be
    # skipped, since the diff under review is by definition unreviewed at
    # review time, and this note ("...run the required reviewers and write
    # .claude/task/review.md...") would otherwise leak into a blinded
    # reviewer's own context. Today's shipped reviewers can't trigger this
    # hook at all (Read/Grep/Glob only, no Bash), but the check must not
    # depend on that staying true.
    if not _GIT:
        raise unittest.SkipTest("no git on PATH")
    with tempfile.TemporaryDirectory() as repo:
        _init_repo(repo, {"always": ["scope-auditor"], "paths": {}})
        with open(os.path.join(repo, "model.sql"), "w", encoding="utf-8") as f:
            f.write("select 1\n")
        _git(repo, "add", "model.sql")
        with _run_main_in(repo, agent_id="agent-123") as (output, exit_code):
            pass
        assert output.strip() == "", (
            "a subagent-issued tool call must never get the completion-gate note")
        _assert_never_denies(output, exit_code)


def test_note_suppressed_on_repeat_but_refires_on_reason_change():
    # Noise-avoidance: this hook can fire before every matched tool call, so
    # without suppression it would nag before every single one while
    # unreviewed work sits staged — exactly the "cry-wolf" failure
    # _command_utils.py warns against. Suppression compares the CURRENT
    # reason to only the LAST one the session's single marker file recorded,
    # so three things must all hold: (1) an unchanged reason is suppressed,
    # (2) a changed reason
    # re-fires, and (3) a REGRESSION back to a previously-seen reason still
    # re-fires, since only the most recent value is compared, not the full
    # history.
    if not _GIT:
        raise unittest.SkipTest("no git on PATH")
    session_id = f"test-{uuid.uuid4().hex}"
    with tempfile.TemporaryDirectory() as repo:
        try:
            _init_repo(repo, {"always": ["scope-auditor"], "paths": {}})
            with open(os.path.join(repo, "model.sql"), "w", encoding="utf-8") as f:
                f.write("select 1\n")
            _git(repo, "add", "model.sql")
            review_path = os.path.join(repo, ".claude", "task", "review.md")

            # 1. no review.md at all -> reason A ("no review found")
            with _run_main_in(repo, session_id=session_id) as (output1, exit_code1):
                pass
            assert "COMPLETION GATE" in output1, "first call with unreviewed work should note"
            _assert_never_denies(output1, exit_code1)

            # 2. same session, unchanged reason A -> suppressed
            with _run_main_in(repo, session_id=session_id) as (output2, exit_code2):
                pass
            assert output2.strip() == "", (
                "same session + unchanged gate reason must be suppressed, "
                "not repeated before every tool call")
            _assert_never_denies(output2, exit_code2)

            # 3. a stale review.md changes the reason to B ("diff doesn't
            #    match") -> a real change, must re-fire
            stale_review = "diff_sha256: " + ("0" * 64) + "\n"
            with open(review_path, "w", encoding="utf-8") as f:
                f.write(stale_review)
            with _run_main_in(repo, session_id=session_id) as (output3, exit_code3):
                pass
            assert "COMPLETION GATE" in output3, (
                "a genuinely new unreviewed reason must re-fire even in the same session")
            _assert_never_denies(output3, exit_code3)

            # 4. remove review.md -> back to reason A. This is the case a
            #    naive "seen this exact reason before, ever" marker would
            #    wrongly suppress forever after step 1 -- it must re-fire,
            #    because the LAST fired reason was B, not A.
            os.remove(review_path)
            with _run_main_in(repo, session_id=session_id) as (output4, exit_code4):
                pass
            assert "COMPLETION GATE" in output4, (
                "a regression back to a previously-seen reason must still re-fire — "
                "suppression compares only the last-fired reason, not full history")
            _assert_never_denies(output4, exit_code4)

            # 5. session-scoping actually matters: a DIFFERENT session_id,
            #    same repo state (reason A again, just fired for session_id
            #    above) must still fire — proves the marker key includes the
            #    session, not just the reason.
            other_session_id = f"test-{uuid.uuid4().hex}"
            try:
                with _run_main_in(repo, session_id=other_session_id) as (output5, exit_code5):
                    pass
                assert "COMPLETION GATE" in output5, (
                    "a different session must not be suppressed by another "
                    "session's marker for the same reason")
                _assert_never_denies(output5, exit_code5)
            finally:
                _cleanup_markers(other_session_id)
        finally:
            _cleanup_markers(session_id)


def test_fails_open_when_gate_raises():
    # completion_gate.py's docstring promises it fails open on any error —
    # prove it, rather than trusting the try/except by inspection. Monkeypatch
    # the real _gate() (imported into completion_gate as crg._gate) to raise,
    # and confirm the hook still exits cleanly with no output.
    if not _GIT:
        raise unittest.SkipTest("no git on PATH")
    with tempfile.TemporaryDirectory() as repo:
        _init_repo(repo, {"always": ["scope-auditor"], "paths": {}})
        with open(os.path.join(repo, "model.sql"), "w", encoding="utf-8") as f:
            f.write("select 1\n")
        _git(repo, "add", "model.sql")

        def _boom(_root):
            raise RuntimeError("simulated _gate failure")

        original_gate = cg.crg._gate
        cg.crg._gate = _boom
        try:
            with _run_main_in(repo) as (output, exit_code):
                pass
        finally:
            cg.crg._gate = original_gate
        assert output.strip() == "", "a _gate() failure must fail open, not surface an error payload"
        assert exit_code == 0, "a _gate() failure must still exit cleanly"
        _assert_never_denies(output, exit_code)


def test_fails_open_on_non_dict_event():
    # Valid JSON that isn't an object (a list, null, a bare number) parses
    # without raising in json.loads, so read_event() returns it as-is rather
    # than {} — a naive event.get("agent_id") on that value would raise
    # AttributeError, uncaught, breaking the "fails open on any error"
    # promise. Must not happen for any of these shapes.
    for payload in ("[]", "null", "42", '"just a string"'):
        old_argv, old_stdin = sys.argv, sys.stdin
        old_env = os.environ.get("CLAUDE_PROJECT_DIR")
        sys.argv = ["completion_gate.py"]
        sys.stdin = io.StringIO(payload)
        os.environ["CLAUDE_PROJECT_DIR"] = tempfile.gettempdir()
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                exit_code = cg.main()
        finally:
            sys.argv, sys.stdin = old_argv, old_stdin
            if old_env is None:
                os.environ.pop("CLAUDE_PROJECT_DIR", None)
            else:
                os.environ["CLAUDE_PROJECT_DIR"] = old_env
        assert exit_code == 0, f"non-dict payload {payload!r} must still exit cleanly"
        assert buf.getvalue().strip() == "", f"non-dict payload {payload!r} must produce no output"


if __name__ == "__main__":
    _failed = 0
    for _name, _fn in sorted(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            try:
                _fn()
                print(f"ok   {_name}")
            except unittest.SkipTest as e:
                print(f"skip {_name}: {e}")
            except Exception as e:  # noqa: BLE001
                _failed += 1
                print(f"FAIL {_name}: {type(e).__name__}: {e}")
    print("all tests passed" if not _failed else f"{_failed} test(s) failed")
    sys.exit(1 if _failed else 0)
