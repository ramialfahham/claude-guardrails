"""Tests for branch_discipline's command detection — the hard guard that blocks
commits/pushes on main, `gh pr merge`, and history-rewriting commit flags.

Runnable with `pytest` or directly: `python tests/test_branch_discipline.py`.
"""

import os
import sys

_HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
sys.path.insert(0, _HOOKS)

from _command_utils import git_subcommand, simple_commands, strip_quoted_and_heredoc  # noqa: E402
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


def test_commit_form_accepts_allowlisted_flags():
    assert bd._commit_form_violation(["-m"]) is None
    assert bd._commit_form_violation(["--message=hi"]) is None
    assert bd._commit_form_violation(["-m", "message", "--author", "X <x@y.z>"]) is None
    assert bd._commit_form_violation(["--no-edit"]) is None
    assert bd._commit_form_violation([]) is None


def test_commit_form_rejects_bundled_short_flags():
    # -am bundles -a (auto-stage, the real bypass) with -m; exact-match
    # allowlisting refuses the whole unrecognised token rather than trying
    # to unbundle it
    violation = bd._commit_form_violation(["-am"])
    assert violation and "-am" in violation


def test_commit_form_rejects_pathspec():
    # -m consumes the NEXT token as its message value (real git semantics
    # too) — a pathspec must come AFTER that value is consumed
    violation = bd._commit_form_violation(["-m", "message", "file.py"])
    assert violation and "file.py" in violation


def test_commit_form_rejects_unknown_flag():
    violation = bd._commit_form_violation(["--all"])
    assert violation and "--all" in violation


def test_commit_form_survives_heredoc_shaped_message():
    # the actual pattern used all session: git commit -m "$(cat <<'EOF' ... )"
    # — strip_quoted_and_heredoc truncates at the heredoc marker, leaving a
    # garbled but harmless "value" token after -m, which must NOT be treated
    # as a pathspec violation
    raw = 'git commit -m "$(cat <<\'EOF\'\nSome commit message\nEOF\n)"'
    stripped = strip_quoted_and_heredoc(raw)
    toks = stripped.split()
    args = bd._args_after_subcommand(toks)
    assert bd._commit_form_violation(args) is None


def test_bundled_index_mutation_detects_add_and_commit():
    stripped_parts = ["git add -A", "git commit -m x"]
    assert bd._bundled_index_mutation(stripped_parts) == "add"


def test_bundled_index_mutation_exempts_dry_run():
    # git commit --dry-run commits nothing — bundling it with add must not
    # be blocked; an earlier version of this check used a bare
    # git_subcommand(...) == "commit" comparison and DID block this, a real
    # false positive caught in review
    stripped_parts = ["git add -A", "git commit --dry-run"]
    assert bd._bundled_index_mutation(stripped_parts) is None


def test_bundled_index_mutation_allows_separate_calls():
    # each of these is a SEPARATE hook invocation in practice (one Bash call
    # each); simulating that here as two single-part lists, neither of which
    # bundles add with commit
    assert bd._bundled_index_mutation(["git add -A"]) is None
    assert bd._bundled_index_mutation(["git commit -m x"]) is None


def test_bundled_checkout_branch_creation_is_not_flagged():
    # -b/-B can only create/reset a branch, never restore file content — the
    # one checkout form that's unambiguously safe regardless of what follows
    assert bd._bundled_index_mutation(["git checkout -b feature", "git commit -m x"]) is None
    assert bd._bundled_index_mutation(["git checkout -B feature", "git commit -m x"]) is None


def test_bundled_checkout_with_pathspec_is_flagged():
    # `checkout ... -- <path>` restores file content into the index/working
    # tree — the real risk this check exists for
    stripped_parts = ["git checkout main -- file.py", "git commit -m x"]
    assert bd._bundled_index_mutation(stripped_parts) == "checkout"


def test_bundled_checkout_without_double_dash_is_still_flagged():
    # git accepts `checkout <ref> <path>` WITHOUT `--` — `--` only
    # disambiguates, it isn't required, so checking for it alone would miss
    # this real bypass
    stripped_parts = ["git checkout main file.py", "git commit -m x"]
    assert bd._bundled_index_mutation(stripped_parts) == "checkout"


def test_bundled_checkout_plain_branch_switch_is_conservatively_flagged():
    # a bare `checkout <branch>` (no -b) is token-indistinguishable from
    # `checkout <path>` — conservatively flagged too, the safe direction
    stripped_parts = ["git checkout main", "git commit -m x"]
    assert bd._bundled_index_mutation(stripped_parts) == "checkout"


def test_grouped_commit_is_still_subject_to_the_form_allowlist():
    # (git commit -am x) must not bypass the allowlist just because it's
    # wrapped in a subshell — _args_after_subcommand degroups the same way
    # git_subcommand does
    for part in simple_commands("(git commit -am x)"):
        toks = part.split()
        if git_subcommand(toks) == "commit":
            violation = bd._commit_form_violation(bd._args_after_subcommand(toks))
            assert violation and "-am" in violation
            break
    else:
        raise AssertionError("no part in the grouped command was recognised as commit")


def test_bundled_index_mutation_ignores_unrelated_compound_commands():
    assert bd._bundled_index_mutation(["git status", "git log"]) is None
    assert bd._bundled_index_mutation(["git add -A", "git status"]) is None


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
