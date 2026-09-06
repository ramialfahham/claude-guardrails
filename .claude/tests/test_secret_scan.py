"""Tests for secret_scan.py — the credential-shape scanner on staged diffs.

Runnable with `pytest` or directly: `python .claude/tests/test_secret_scan.py`.
"""

import os
import shutil
import subprocess
import sys
import tempfile

_HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
sys.path.insert(0, _HOOKS)

from secret_scan import _find_secrets, _is_commit_command  # noqa: E402

_GIT = shutil.which("git")

# One real-shaped (but fake) example per pattern. Built via concatenation, not
# a single literal, so the SOURCE TEXT of this file never contains a
# contiguous match — secret_scan.py's own commit hook (correctly) scans this
# file's staged diff too, and a literal token-shaped string here would be a
# real (if ironic) false trip on ourselves, caught live while committing this
# very phase.
_EXAMPLES = {
    "AWS access key": "AKIA" + "ABCDEFGHIJKLMNOP",
    "GitHub token": "ghp_" + "a" * 36,
    "Slack token": "xoxb-" + "1234567890-abcdefghij",
    "Google API key": "AIza" + "A" * 35,
    "OpenAI/Anthropic-style secret key": "sk-" + "a" * 25,
    "private key block": "-----BEGIN RSA PRIVATE KEY" + "-----",
}


def _diff_adding_line(content: str) -> str:
    return f"diff --git a/config.py b/config.py\n+++ b/config.py\n@@ -0,0 +1 @@\n+{content}\n"


def test_detects_each_known_pattern():
    for name, example in _EXAMPLES.items():
        diff = _diff_adding_line(f'API_KEY = "{example}"')
        findings = _find_secrets(diff)
        assert any(name in f for f in findings), f"{name} not detected in {findings}"


def test_ignores_removed_lines():
    diff = (
        "diff --git a/config.py b/config.py\n"
        "+++ b/config.py\n"
        "@@ -1 +1 @@\n"
        f"-API_KEY = \"{_EXAMPLES['AWS access key']}\"\n"
        "+API_KEY = os.environ[\"API_KEY\"]\n"
    )
    assert _find_secrets(diff) == []


def test_ignores_file_header_lines():
    # a filename that happens to contain something pattern-shaped must not
    # be scanned — only '+' CONTENT lines are, never '+++' headers
    diff = "diff --git a/sk-notasecret.py b/sk-notasecret.py\n+++ b/sk-notasecret.py\n@@ -0,0 +1 @@\n+x = 1\n"
    assert _find_secrets(diff) == []


def test_plain_code_is_not_flagged():
    diff = _diff_adding_line("def add(a, b):")
    assert _find_secrets(diff) == []


def test_finding_names_the_file():
    diff = _diff_adding_line(f'token = "{_EXAMPLES["GitHub token"]}"')
    findings = _find_secrets(diff)
    assert any("config.py" in f for f in findings)


def test_is_commit_command_matches_real_commit_not_readonly():
    assert _is_commit_command("git commit -m x")
    assert _is_commit_command("git add -A && git commit -m x")
    assert not _is_commit_command("git commit --dry-run")
    assert not _is_commit_command("git log --grep commit")
    assert not _is_commit_command("git status")


def _git(repo, *args):
    subprocess.run([_GIT, *args], cwd=repo, check=True, capture_output=True, timeout=30)


def test_end_to_end_against_a_real_staged_diff():
    if not _GIT:
        print("skip (no git on PATH)")
        return
    with tempfile.TemporaryDirectory() as repo:
        _git(repo, "init", "-q")
        _git(repo, "config", "user.email", "t@t.t")
        _git(repo, "config", "user.name", "t")
        with open(os.path.join(repo, "settings.py"), "w", encoding="utf-8") as f:
            f.write(f'AWS_KEY = "{_EXAMPLES["AWS access key"]}"\n')
        _git(repo, "add", "settings.py")
        diff_text = subprocess.run(
            ["git", "diff", "--staged", "--no-color"],
            cwd=repo, capture_output=True, text=True, timeout=30,
        ).stdout
        findings = _find_secrets(diff_text)
        assert any("settings.py" in f for f in findings)


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
