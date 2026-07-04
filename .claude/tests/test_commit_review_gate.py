"""Regression tests for commit_review_gate._is_commit.

The gate must fire on a real `git commit` but NOT on read-only commands that
merely contain the word "commit" (the bug this guards against). Runnable with
`pytest` or directly: `python tests/test_commit_review_gate.py`.
"""

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_CLAUDE_DIR = os.path.dirname(_TESTS_DIR)
_REPO_ROOT = os.path.dirname(_CLAUDE_DIR)
_HOOKS = os.path.join(_CLAUDE_DIR, "hooks")
sys.path.insert(0, _HOOKS)

from commit_review_gate import (  # noqa: E402
    _is_commit,
    _load_routing,
    _required_reviewers,
    _sections,
    _staged_diff,
    _verdict,
)

_GIT = shutil.which("git")


def test_real_commit_is_detected():
    assert _is_commit("git commit")
    assert _is_commit("git commit -m 'x'")
    # global options before the subcommand must still be seen as a commit
    assert _is_commit("git -c user.email=x@y.z commit -m 'x'")
    assert _is_commit("git -C /repo commit")
    assert _is_commit("git --no-pager commit")


def test_readonly_commands_are_not_commits():
    # the bug: "commit" appears as an ARGUMENT, not the subcommand
    assert not _is_commit("git log --grep commit")
    assert not _is_commit("git log --format=%H --grep commit")
    assert not _is_commit("git show HEAD:commit")
    assert not _is_commit("git commit-tree -p HEAD")  # a different subcommand
    assert not _is_commit("echo git commit")           # not a git invocation


def test_dry_run_is_exempt():
    assert not _is_commit("git commit --dry-run")


def test_commit_in_a_compound_command():
    assert _is_commit("git add -A && git commit -m 'x'")
    assert not _is_commit("git add -A && git log --grep commit")


def test_verdict_reads_the_operative_block():
    assert _verdict("VERDICT: PASS\nrisks_checked:\n- a\n- b") == "PASS"
    assert _verdict("VERDICT: FAIL\nfindings:\n- x") == "FAIL"
    assert _verdict("VERDICT: ESCALATE\nquestions:\n- q") == "ESCALATE"
    assert _verdict("no verdict here at all") is None


def test_verdict_ignores_example_text_before_the_real_one():
    body = ("A FAIL would read `VERDICT: FAIL`, but I found nothing wrong.\n"
            "VERDICT: PASS\nrisks_checked:\n- a\n- b")
    assert _verdict(body) == "PASS"


def test_prose_fail_is_not_a_reviewer_fail():
    # the change-3 bug: 'VERDICT: FAIL' in preamble prose must not count as a fail
    text = ("Reviewers must block on VERDICT: FAIL.\n\n"
            "## scope-auditor\nVERDICT: PASS\nrisks_checked:\n- a\n- b\n")
    sections = _sections(text)
    verdicts = {n: _verdict(b) for n, b in sections.items() if n != "_preamble"}
    assert verdicts == {"scope-auditor": "PASS"}
    assert "FAIL" not in verdicts.values()


def test_a_real_reviewer_fail_is_still_caught():
    text = ("## scope-auditor\nVERDICT: PASS\nrisks_checked:\n- a\n- b\n\n"
            "## cto-reviewer\nVERDICT: FAIL\nfindings:\n- hooks/x.py:1 broke a rule\n")
    verdicts = {n: _verdict(b) for n, b in _sections(text).items() if n != "_preamble"}
    assert verdicts["cto-reviewer"] == "FAIL"


def test_escalation_answer_is_scoped_to_its_own_section():
    # an answered escalation in one section must not clear an unanswered one elsewhere
    text = ("## scope-auditor\nVERDICT: ESCALATE\nquestions:\n- q1\nCPO ANSWER: go with A\n\n"
            "## cto-reviewer\nVERDICT: ESCALATE\nquestions:\n- q2\n")
    sections = _sections(text)
    answered = "CPO ANSWER:" in sections["scope-auditor"]
    unanswered = "CPO ANSWER:" not in sections["cto-reviewer"]
    assert answered and unanswered


def _git(repo, *args):
    subprocess.run([_GIT, *args], cwd=repo, check=True,
                   capture_output=True, timeout=30)


def test_staged_diff_excludes_the_task_dir():
    # The self-reference fix: staging .claude/task/** (where review.md lives) must
    # NOT change the staged-diff hash, so review.md recording that hash can't
    # deadlock the gate.
    if not _GIT:
        print("skip (no git on PATH)")
        return
    with tempfile.TemporaryDirectory() as repo:
        _git(repo, "init", "-q")
        _git(repo, "config", "user.email", "t@t.t")
        _git(repo, "config", "user.name", "t")
        # A real change, staged.
        with open(os.path.join(repo, "model.sql"), "w", encoding="utf-8") as f:
            f.write("select 1\n")
        _git(repo, "add", "model.sql")
        hash_before = hashlib.sha256(_staged_diff(repo)).hexdigest()
        # Now stage a review artifact under .claude/task/ — must not move the hash.
        os.makedirs(os.path.join(repo, ".claude", "task"))
        with open(os.path.join(repo, ".claude", "task", "review.md"), "w", encoding="utf-8") as f:
            f.write("diff_sha256: " + hash_before + "\n## scope-auditor\nVERDICT: PASS\n")
        _git(repo, "add", ".claude/task/review.md")
        hash_after = hashlib.sha256(_staged_diff(repo)).hexdigest()
        assert hash_after == hash_before, "staging .claude/task/ changed the hash"
        # Sanity: a real second change DOES move the hash (exclusion isn't too broad).
        with open(os.path.join(repo, "model2.sql"), "w", encoding="utf-8") as f:
            f.write("select 2\n")
        _git(repo, "add", "model2.sql")
        assert hashlib.sha256(_staged_diff(repo)).hexdigest() != hash_before


def test_routing_matches_the_dotclaude_prefixed_paths():
    # Regression for the step-1 prefix gap: agents/ and tests/ moved under .claude/,
    # so the routing patterns must match the .claude/-prefixed paths or the gate
    # under-requires reviewers.
    routing = _load_routing(_REPO_ROOT)
    assert routing is not None, "review_routing.json should load from the repo root"
    assert "cto-reviewer" in _required_reviewers([".claude/agents/scope-auditor.md"], routing)
    assert "cto-reviewer" in _required_reviewers([".claude/tests/test_x.py"], routing)
    assert "cto-reviewer" in _required_reviewers([".claude/hooks/commit_review_gate.py"], routing)
    # scope-auditor always; a plain doc pulls in no domain reviewer.
    assert _required_reviewers(["README.md"], routing) == {"scope-auditor"}


if __name__ == "__main__":
    _failed = 0
    for _name, _fn in sorted(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            try:
                _fn()
                print(f"ok   {_name}")
            except Exception as e:  # noqa: BLE001 — surface subprocess/setup errors too
                _failed += 1
                print(f"FAIL {_name}: {type(e).__name__}: {e}")
    print("all tests passed" if not _failed else f"{_failed} test(s) failed")
    sys.exit(1 if _failed else 0)
