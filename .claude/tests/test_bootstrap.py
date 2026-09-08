"""Tests for scripts/bootstrap.sh — copying the guardrails into an existing repo.

Exercises the real script through bash against a throwaway target directory:
the copy set lands, no __pycache__ leaks, project-owned config is preserved on a
re-run (and overwritten with --force), and the script refuses to bootstrap the
kit into itself.

Skips cleanly if bash isn't on PATH (the hooks need bash anyway, but a dev box
without it shouldn't hard-fail this one test).

Runnable with `pytest` or directly: `python tests/test_bootstrap.py`.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

_KIT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SCRIPT = os.path.join(_KIT_ROOT, "scripts", "bootstrap.sh")
_BASH = shutil.which("bash")

# Files that MUST land in a freshly bootstrapped repo. .claude/.kit-version is
# NOT here deliberately — bootstrap.sh itself only writes it when the KIT
# checkout has real git history to read (see _kit_owed_a_stamp below), so
# asserting its presence unconditionally would turn that script's own
# documented, deliberate fail-open skip into a hard failure here. Checked
# separately, conditionally, in test_fresh_bootstrap_lands_the_guardrails
# below — conditionally on _kit_owed_a_stamp(), never on whether the file
# happens to exist (that would be circular: the file's existence is the
# very thing under test).
_EXPECTED = [
    ".claude/hooks/commit_review_gate.py",
    ".claude/hooks/preflight.sh",
    ".claude/agents/scope-auditor.md",
    ".claude/agents/cto-reviewer.md",
    ".claude/commands/status.md",
    ".claude/skills/setup-project/SKILL.md",
    ".claude/tests/test_commit_review_gate.py",
    ".claude/settings.json",
    ".claude/review_routing.json",
    ".claude/working-agreement.md",
    ".claude/active_work.md",
    "task/REVIEW_TEMPLATE.md",
    "task/CONTRACT_TEMPLATE.md",
]


def _unavailable():
    """Why this suite can't run here, or None if it can. bash is needed to run the
    script at all; scripts/bootstrap.sh only exists in the KIT — a repo that was
    itself bootstrapped gets the tests but not the script, so the suite must skip
    there rather than fail (the copied tests would otherwise be red out of the box)."""
    if not _BASH:
        return "no bash on PATH"
    if not os.path.isfile(_SCRIPT):
        return "scripts/bootstrap.sh not present (a bootstrapped repo, not the kit)"
    return None


def _run(*args, cwd=None):
    return subprocess.run(
        [_BASH, _SCRIPT, *args],
        cwd=cwd, capture_output=True, text=True, timeout=60,
    )


def _kit_owed_a_stamp() -> bool:
    """Independently determine whether THIS kit checkout should get a
    .kit-version stamp — mirrors bootstrap.sh's own condition, computed
    separately here rather than by checking whether the stamp file happens
    to exist. Checking the file's own existence would be circular: that
    existence is the thing under test, and a regression that silently stops
    bootstrap.sh from writing it would make this always look like "no stamp
    is owed" — the exact class of gap a round-2 review round found in the
    tautological version of this check (`if os.path.isfile(stamp): ...`).

    Deliberately a plain existence check on `_KIT_ROOT/.git`, not a
    `rev-parse --show-toplevel` PATH comparison — an earlier version of
    both this helper and bootstrap.sh's own matching logic compared
    absolute path TEXT, which broke twice on this exact dev box: once from
    a drive-letter vs MSYS path-format difference, then again because Git
    Bash mount-aliases %TEMP% to /tmp, so even a "normalised" path's string
    form isn't stable across different starting representations. A plain
    filesystem existence check has no path-text comparison in it at all."""
    if shutil.which("git") is None:
        return False
    if not os.path.exists(os.path.join(_KIT_ROOT, ".git")):
        return False
    head = subprocess.run(
        ["git", "-C", _KIT_ROOT, "rev-parse", "--verify", "HEAD"],
        capture_output=True, text=True, timeout=10,
    ).stdout.strip()
    return bool(head)


def test_fresh_bootstrap_lands_the_guardrails():
    reason = _unavailable()
    if reason:
        raise unittest.SkipTest(reason)
    with tempfile.TemporaryDirectory() as tmp:
        target = os.path.join(tmp, "repo")
        os.makedirs(target)
        res = _run(target)
        assert res.returncode == 0, res.stderr
        for rel in _EXPECTED:
            assert os.path.isfile(os.path.join(target, *rel.split("/"))), f"missing {rel}"
        # No __pycache__ carried along by the copy.
        leaked = [
            d for root, dirs, _ in os.walk(target) for d in dirs if d == "__pycache__"
        ]
        assert not leaked, f"__pycache__ leaked: {leaked}"
        # The starter handover is fresh, not the kit's own migration notes.
        with open(os.path.join(target, ".claude", "active_work.md"), encoding="utf-8") as f:
            body = f.read()
        assert "migration" not in body.lower(), "copied the kit's own active_work.md"
        # .claude/.kit-version: gated on _kit_owed_a_stamp(), determined
        # INDEPENDENTLY of whether the file happens to exist — bootstrap.sh
        # deliberately skips writing it when this KIT checkout itself has no
        # git history to read a SHA from (which is why it isn't in the
        # unconditional _EXPECTED list above), but when a stamp genuinely IS
        # owed, its absence must fail this test, not be quietly skipped past.
        stamp = os.path.join(target, ".claude", ".kit-version")
        if _kit_owed_a_stamp():
            assert os.path.isfile(stamp), (
                "this kit checkout has resolvable git history but "
                ".kit-version was not written — bootstrap.sh's version-stamp "
                "logic regressed")
            with open(stamp, encoding="utf-8") as f:
                sha = f.read().strip()
            assert len(sha) == 40 and all(c in "0123456789abcdef" for c in sha), (
                f".kit-version doesn't look like a git SHA: {sha!r}")


def test_rerun_preserves_project_config_unless_forced():
    reason = _unavailable()
    if reason:
        raise unittest.SkipTest(reason)
    with tempfile.TemporaryDirectory() as tmp:
        target = os.path.join(tmp, "repo")
        os.makedirs(target)
        assert _run(target).returncode == 0
        routing = os.path.join(target, ".claude", "review_routing.json")
        with open(routing, "w", encoding="utf-8") as f:
            f.write("SENTINEL")
        # Plain re-run must NOT clobber the customised config.
        assert _run(target).returncode == 0
        with open(routing, encoding="utf-8") as f:
            assert f.read() == "SENTINEL", "re-run clobbered project config"
        # --force restores the kit's version.
        assert _run("--force", target).returncode == 0
        with open(routing, encoding="utf-8") as f:
            assert f.read() != "SENTINEL", "--force did not overwrite"


def test_kit_version_stamp_matches_head_and_is_always_refreshed():
    reason = _unavailable()
    if reason:
        raise unittest.SkipTest(reason)
    if not _kit_owed_a_stamp():
        # Determined INDEPENDENTLY of the stamp file's own existence (see
        # _kit_owed_a_stamp's docstring) — this kit checkout genuinely has
        # no git history to read a SHA from (no git on PATH, not its own
        # toplevel, or an unborn HEAD), matching bootstrap.sh's own
        # documented skip. If a stamp IS owed, this test must not skip past
        # its absence — see the assert immediately below instead.
        raise unittest.SkipTest(
            "this kit checkout has no resolvable git history to stamp from")
    with tempfile.TemporaryDirectory() as tmp:
        target = os.path.join(tmp, "repo")
        os.makedirs(target)
        assert _run(target).returncode == 0
        stamp = os.path.join(target, ".claude", ".kit-version")
        assert os.path.isfile(stamp), (
            "this kit checkout has resolvable git history but "
            ".kit-version was not written — bootstrap.sh's version-stamp "
            "logic regressed")
        with open(stamp, encoding="utf-8") as f:
            sha = f.read().strip()
        assert len(sha) == 40 and all(c in "0123456789abcdef" for c in sha), (
            f".kit-version doesn't look like a git SHA: {sha!r}")
        head = subprocess.run(
            ["git", "-C", _KIT_ROOT, "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        assert sha == head, ".kit-version must match this checkout's actual HEAD"

        # Unlike project-owned config (review_routing.json etc.), this is a
        # fact about the KIT, not the project — a plain re-run (no --force)
        # must still overwrite a hand-edited value, never preserve it.
        with open(stamp, "w", encoding="utf-8") as f:
            f.write("SENTINEL\n")
        assert _run(target).returncode == 0
        with open(stamp, encoding="utf-8") as f:
            assert f.read().strip() == head, (
                "plain re-run did not refresh .kit-version — it must never "
                "use keep_file/project-owned semantics")


def test_dry_run_does_not_write_the_kit_version_stamp():
    reason = _unavailable()
    if reason:
        raise unittest.SkipTest(reason)
    with tempfile.TemporaryDirectory() as tmp:
        target = os.path.join(tmp, "repo")
        os.makedirs(target)
        res = _run("--dry-run", target)
        assert res.returncode == 0, res.stderr
        assert "DRY   write .claude/.kit-version" in res.stdout
        assert not os.path.isfile(os.path.join(target, ".claude", ".kit-version")), (
            "--dry-run must never actually write .kit-version")


def test_refuses_to_bootstrap_the_kit_into_itself():
    reason = _unavailable()
    if reason:
        raise unittest.SkipTest(reason)
    res = _run(_KIT_ROOT)
    assert res.returncode != 0, "should refuse to target the kit itself"
    assert "itself" in (res.stderr + res.stdout).lower()


def test_requires_a_target_argument():
    reason = _unavailable()
    if reason:
        raise unittest.SkipTest(reason)
    res = _run()
    assert res.returncode != 0, "missing target should be an error"


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
