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

# Files that MUST land in a freshly bootstrapped repo.
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
