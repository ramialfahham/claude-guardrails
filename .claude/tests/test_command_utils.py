"""Tests for _command_utils.git_subcommand — the shared git-subcommand detector
both hard guards (commit_review_gate, branch_discipline) rely on.

Runnable with `pytest` or directly: `python tests/test_command_utils.py`.
"""

import os
import sys

_HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
sys.path.insert(0, _HOOKS)

from _command_utils import (  # noqa: E402
    _degroup,
    git_subcommand,
    is_commit_subcommand,
    simple_commands,
)


def test_plain_subcommand():
    assert git_subcommand("git commit".split()) == "commit"
    assert git_subcommand("git push origin main".split()) == "push"
    assert git_subcommand("git log --oneline".split()) == "log"
    assert git_subcommand("git status".split()) == "status"


def test_global_options_are_skipped():
    # the gap this fixes: a real commit/push hidden behind global options
    assert git_subcommand("git -c user.email=x@y.z commit -m m".split()) == "commit"
    assert git_subcommand("git -C /repo commit".split()) == "commit"
    assert git_subcommand("git --no-pager commit".split()) == "commit"
    assert git_subcommand("git -c http.x=y push origin main".split()) == "push"


def test_word_commit_as_argument_is_not_the_subcommand():
    assert git_subcommand("git log --grep commit".split()) == "log"
    assert git_subcommand("git show HEAD:commit".split()) == "show"


def test_commit_tree_is_not_commit():
    # a different subcommand that merely starts with 'commit'
    assert git_subcommand("git commit-tree -p HEAD".split()) == "commit-tree"


def test_non_git_is_none():
    assert git_subcommand("echo git commit".split()) is None
    assert git_subcommand("".split()) is None
    assert git_subcommand([]) is None


def test_degroup_strips_wrapping_punctuation():
    assert _degroup(["(git", "commit", "-m", "x)"]) == ["git", "commit", "-m", "x"]
    assert _degroup(["{", "git", "commit", "-m", "x"]) == ["git", "commit", "-m", "x"]
    assert _degroup(["git", "commit"]) == ["git", "commit"]  # unwrapped: unchanged
    assert _degroup([]) == []


def test_subshell_wrapped_commit_is_still_detected():
    # (git commit -m x) — a single-command subshell with no operator inside,
    # so simple_commands doesn't split it; without degrouping this would be
    # invisible to every guard in the repo
    for part in simple_commands("(git commit -m x)"):
        assert git_subcommand(part.split()) == "commit"


def test_brace_grouped_commit_is_still_detected():
    # { git commit -m x; } splits on the internal ';', so the group's braces
    # end up attached to different simple-commands than in the subshell case
    parts = list(simple_commands("{ git commit -m x; }"))
    assert any(git_subcommand(p.split()) == "commit" for p in parts)


def test_is_commit_subcommand_excludes_dry_run():
    # every guard that cares about a REAL commit shares this predicate now —
    # a --dry-run commits nothing, so it must never read as a commit
    assert is_commit_subcommand("git commit -m x".split()) is True
    assert is_commit_subcommand("git commit --dry-run".split()) is False
    assert is_commit_subcommand("git log --grep commit".split()) is False
    assert is_commit_subcommand("git status".split()) is False


def test_grouping_does_not_create_a_false_positive():
    # a group around something that ISN'T a commit must still resolve to
    # None, not accidentally become "commit" through overzealous stripping
    for part in simple_commands("(git status)"):
        assert git_subcommand(part.split()) != "commit"


if __name__ == "__main__":
    _failed = 0
    for _name, _fn in sorted(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            try:
                _fn()
                print(f"ok   {_name}")
            except AssertionError as e:
                _failed += 1
                print(f"FAIL {_name}: {e}")
    print("all tests passed" if not _failed else f"{_failed} test(s) failed")
    sys.exit(1 if _failed else 0)
