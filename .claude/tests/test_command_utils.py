"""Tests for _command_utils.git_subcommand — the shared git-subcommand detector
both hard guards (commit_review_gate, branch_discipline) rely on.

Runnable with `pytest` or directly: `python tests/test_command_utils.py`.
"""

import os
import sys

_HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
sys.path.insert(0, _HOOKS)

from _command_utils import git_subcommand  # noqa: E402


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
