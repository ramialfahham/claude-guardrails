"""Smoke test: every hook module imports cleanly.

Byte-compilation (CI's `compileall`) checks syntax but does NOT resolve imports,
so a broken `from _command_utils import <name>` would pass compile yet fail at
runtime. Importing each module here catches that — it matters most for the hooks
that have no other test importing them (pre_push_gate, handover_out, …).

Runnable with `pytest` or directly: `python tests/test_hooks_import.py`.
"""

import importlib
import os
import sys

_HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
sys.path.insert(0, _HOOKS)

_HOOK_MODULES = [
    "_command_utils",
    "branch_discipline",
    "commit_review_gate",
    "completion_gate",
    "handover_in",
    "handover_out",
    "handover_plan_gate",
    "plan_implement_gate",
    "pre_push_gate",
    "secret_scan",
]


def test_every_hook_module_imports():
    for name in _HOOK_MODULES:
        mod = importlib.import_module(name)
        assert mod is not None


# docs/decisions/auto-mode-and-bypass-compatibility.md claims
# commit_review_gate.py's and branch_discipline.py's DENY decisions survive
# auto mode's classifier — a guarantee Anthropic's own docs make about
# PreToolUse hooks generally, not about anything specific to this repo's
# code. This test is a TRIPWIRE, not the reason that guarantee holds: it
# doesn't prove the ADR's claim (Claude Code's own evaluation order does),
# it only catches the specific, easy-to-miss way this repo could
# accidentally invalidate the ADR's *scope* — if one of these hooks starts
# reading permission_mode and branching on it, its deny/allow could stop
# being purely a function of repo/diff state, and the ADR would need a
# fresh read against the current docs before anyone trusts it again.
# completion_gate.py is included too even though it never denies anything
# (so the auto-mode-deny question doesn't apply to it) — this is a plain
# hygiene check for it, not evidence for any guarantee.
_MODE_INDEPENDENT_HOOKS = ["commit_review_gate", "branch_discipline", "completion_gate"]


def test_gate_hooks_never_branch_on_permission_mode():
    hooks_dir = _HOOKS
    for name in _MODE_INDEPENDENT_HOOKS:
        path = os.path.join(hooks_dir, f"{name}.py")
        with open(path, encoding="utf-8") as f:
            source = f.read()
        assert "permission_mode" not in source, (
            f"{name}.py references permission_mode — this contradicts "
            "docs/decisions/auto-mode-and-bypass-compatibility.md's claim "
            "that this kit's hooks are unaffected by permission mode; "
            "re-verify that ADR against Anthropic's current docs before "
            "loosening this test")


if __name__ == "__main__":
    _failed = 0
    for _name, _fn in sorted(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            try:
                _fn()
                print(f"ok   {_name}")
            except Exception as e:  # noqa: BLE001 — surface import errors too
                _failed += 1
                print(f"FAIL {_name}: {type(e).__name__}: {e}")
    print("all tests passed" if not _failed else f"{_failed} test(s) failed")
    sys.exit(1 if _failed else 0)
