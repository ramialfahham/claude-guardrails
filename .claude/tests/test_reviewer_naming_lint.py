"""Tests for scripts/lint_reviewer_name.py — the naming lint for the reviewer
module library (templates/reviewers/).

Runnable with `pytest` or directly: `python .claude/tests/test_reviewer_naming_lint.py`.
"""

import os
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "scripts"))

from lint_reviewer_name import check_name, check_file, _names_from_dir  # noqa: E402

_REVIEWERS_DIR = os.path.join(_ROOT, "templates", "reviewers")

_SHIPPED_MODULES = [
    "platform-reviewer",
    "security-reviewer",
    "data-engineer-reviewer",
    "analytics-engineer-reviewer",
    "frontend-reviewer",
]


def _write_reviewer_md(directory: str, filename: str, frontmatter_name: str) -> str:
    path = os.path.join(directory, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"---\nname: {frontmatter_name}\ndescription: test fixture\n---\n\nbody\n")
    return path


def test_rejects_corporate_titles():
    assert check_name("cto-reviewer") == ["cto"]
    assert check_name("cpo-reviewer") == ["cpo"]
    assert check_name("vp-reviewer") == ["vp"]
    assert check_name("director-reviewer") == ["director"]
    assert check_name("team-lead-reviewer") == ["lead"]
    assert check_name("head-of-platform-reviewer") == ["head"]


def test_rejects_whitespace_separated_titles():
    # the exact bypass a hyphen/underscore-only splitter would miss
    assert check_name("chief reviewer") == ["chief"]
    assert check_name("Head Of Platform") == ["head"]


def test_accepts_function_named_reviewers():
    for name in _SHIPPED_MODULES:
        assert check_name(name) == [], f"{name} should not be flagged"


def test_leaderboard_is_not_flagged_as_lead():
    # the exact false-positive a substring match would produce
    assert check_name("leaderboard-reviewer") == []
    assert check_name("headline-reviewer") == []
    assert check_name("bossanova-reviewer") == []


def test_pin_fires_on_a_bad_filename_via_directory_scan():
    # proves the FILE-based path (not just the string helper) rejects a
    # reintroduced cto/cpo-style filename before trusting it
    with tempfile.TemporaryDirectory() as tmp:
        bad = _write_reviewer_md(tmp, "cpo-reviewer.md", "cpo-reviewer")
        stem, hits, mismatch = check_file(bad)
        assert hits == ["cpo"], f"expected the bad filename to be rejected, got {hits}"
        assert mismatch is None


def test_pin_fires_on_a_frontmatter_name_mismatch():
    # a filename can look innocuous while its OWN frontmatter `name:` — the
    # value Claude Code actually registers — carries the bad name
    with tempfile.TemporaryDirectory() as tmp:
        sneaky = _write_reviewer_md(tmp, "mobile-reviewer.md", "vp-mobile-reviewer")
        stem, hits, mismatch = check_file(sneaky)
        assert "vp" in hits, f"frontmatter name should have been checked too, got {hits}"
        assert mismatch is not None


def test_matching_filename_and_frontmatter_pass_clean():
    with tempfile.TemporaryDirectory() as tmp:
        clean = _write_reviewer_md(tmp, "mobile-reviewer.md", "mobile-reviewer")
        stem, hits, mismatch = check_file(clean)
        assert hits == []
        assert mismatch is None


def test_shipped_template_directory_passes_except_documented_exception():
    names = _names_from_dir(_REVIEWERS_DIR)
    assert set(_SHIPPED_MODULES).issubset(set(names)), (
        "expected shipped modules missing from templates/reviewers/ — "
        f"found {names}")
    for fname in sorted(os.listdir(_REVIEWERS_DIR)):
        if not fname.endswith(".md") or fname.startswith("_"):
            continue
        stem, hits, mismatch = check_file(os.path.join(_REVIEWERS_DIR, fname))
        assert not hits, f"{stem} in templates/reviewers/ was flagged: {hits}"
        assert mismatch is None, f"{stem}: {mismatch}"


def test_skeleton_is_excluded_from_directory_scan():
    # leading underscore keeps drafts out of the auto-selected module list
    names = _names_from_dir(_REVIEWERS_DIR)
    assert "_skeleton" not in names
    assert not any(n.startswith("_") for n in names)


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
