"""Tests for branch_discipline's command detection — the hard guard that blocks
commits/pushes on main, `gh pr merge`, and history-rewriting commit flags.

Runnable with `pytest` or directly: `python tests/test_branch_discipline.py`.
"""

import os
import sys

_HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
sys.path.insert(0, _HOOKS)

from _command_utils import git_subcommand, strip_quoted_and_heredoc  # noqa: E402
import branch_discipline as bd  # noqa: E402


def test_forbidden_commit_flags_detected():
    assert bd._COMMIT_FORBIDDEN.search("git commit --amend")
    assert bd._COMMIT_FORBIDDEN.search("git commit --no-verify")
    assert bd._COMMIT_FORBIDDEN.search("git commit -n")


def test_benign_commit_flags_not_flagged():
    assert not bd._COMMIT_FORBIDDEN.search("git commit --no-edit")  # not --no-verify
    assert not bd._COMMIT_FORBIDDEN.search("git commit -m msg")     # -m is fine


def test_quoted_dash_n_in_message_is_not_a_forbidden_flag():
    # a '-n' inside the commit message must not trip the --no-verify/-n guard
    stripped = strip_quoted_and_heredoc("git commit -m 'fixes -n handling'")
    assert not bd._COMMIT_FORBIDDEN.search(stripped)


def test_pushes_protected():
    assert bd._pushes_protected("git push", "main")                    # current branch protected
    assert bd._pushes_protected("git push origin main", "feature")     # explicit destination
    assert bd._pushes_protected("git push origin HEAD:main", "feature")  # refspec destination
    assert not bd._pushes_protected("git push origin feature", "feature")
    assert not bd._pushes_protected("git push", "feature")


def test_gh_pr_merge_detected():
    assert bd._GH_PR_MERGE.match("gh pr merge 12")
    assert not bd._GH_PR_MERGE.match("gh pr view 12")


def test_commit_and_push_detection_via_git_subcommand():
    # branch_discipline now identifies the git subcommand via git_subcommand
    # (shared with commit_review_gate), so a commit/push hidden behind global
    # options — previously missed — is recognised, and commit-tree no longer
    # false-positives as a commit.
    assert git_subcommand("git commit -m x".split()) == "commit"
    assert git_subcommand("git -c user.email=x commit".split()) == "commit"  # was missed before
    assert git_subcommand("git commit-tree".split()) != "commit"             # was a false positive before
    assert git_subcommand("git push origin feature".split()) == "push"
    assert git_subcommand("git status".split()) != "commit"


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
