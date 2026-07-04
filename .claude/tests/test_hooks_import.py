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
    "handover_in",
    "handover_out",
    "handover_plan_gate",
    "plan_implement_gate",
    "pre_push_gate",
]


def test_every_hook_module_imports():
    for name in _HOOK_MODULES:
        mod = importlib.import_module(name)
        assert mod is not None


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
