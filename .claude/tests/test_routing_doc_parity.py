"""Tests for the guard-paths.md <-> review_routing.json parity check.

Runnable with `pytest` or directly: `python .claude/tests/test_routing_doc_parity.py`.
"""

import json
import os
import re
import sys

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_CLAUDE_DIR = os.path.dirname(_TESTS_DIR)
_REPO_ROOT = os.path.dirname(_CLAUDE_DIR)
_RULES_FILE = os.path.join(_CLAUDE_DIR, "rules", "guard-paths.md")
_ROUTING_FILE = os.path.join(_CLAUDE_DIR, "review_routing.json")


def _parse_guard_paths_section(text: str) -> set[str]:
    """The `## Guard paths` section's list items, as a set. Deliberately
    matches only that ONE heading — other `##` sections (e.g. "Exempted from
    escalation") must not leak into the comparison."""
    in_section = False
    paths = set()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            in_section = stripped == "## Guard paths"
            continue
        if in_section:
            m = re.match(r"^-\s+(.+)$", stripped)
            if m:
                paths.add(m.group(1).strip())
    return paths


def _routed_to_cto_reviewer(routing: dict) -> set[str]:
    return {pattern for pattern, reviewers in (routing.get("paths") or {}).items()
            if "cto-reviewer" in reviewers}


def _parity_diff(rules_text: str, routing: dict) -> tuple[set[str], set[str]]:
    """(only_in_doc, only_in_routing) — the actual comparison under test,
    shared by every test below so a fixture exercises the SAME code path the
    real check uses, not a hand-written re-implementation of it."""
    documented = _parse_guard_paths_section(rules_text)
    routed = _routed_to_cto_reviewer(routing)
    return documented - routed, routed - documented


def test_parse_guard_paths_section_extracts_only_that_section():
    text = (
        "# Title\n\n"
        "## Guard paths\n"
        "- scripts/*\n"
        "- .claude/hooks/*\n\n"
        "## Exempted from escalation\n"
        "- scope-auditor\n"
    )
    assert _parse_guard_paths_section(text) == {"scripts/*", ".claude/hooks/*"}


def test_routed_to_cto_reviewer_ignores_other_reviewers():
    routing = {
        "paths": {
            "scripts/*": ["cto-reviewer"],
            "models/*": ["analytics-engineer-reviewer"],
            "*hooks/*": ["cto-reviewer", "security-reviewer"],
        }
    }
    assert _routed_to_cto_reviewer(routing) == {"scripts/*", "*hooks/*"}


def test_parity_check_detects_a_missing_doc_entry():
    # the pin: a path routed to cto-reviewer but never documented must
    # surface — through the REAL _parity_diff, not a re-implementation
    fixture_text = "## Guard paths\n- scripts/*\n"
    fixture_routing = {"paths": {"scripts/*": ["cto-reviewer"],
                                  "*hooks/*": ["cto-reviewer"]}}
    only_in_doc, only_in_routing = _parity_diff(fixture_text, fixture_routing)
    assert only_in_doc == set()
    assert only_in_routing == {"*hooks/*"}


def test_parity_check_detects_a_stale_doc_entry():
    # the pin: a documented path no longer routed to cto-reviewer must
    # surface — through the REAL _parity_diff, not a re-implementation
    fixture_text = "## Guard paths\n- scripts/*\n- old/removed/*\n"
    fixture_routing = {"paths": {"scripts/*": ["cto-reviewer"]}}
    only_in_doc, only_in_routing = _parity_diff(fixture_text, fixture_routing)
    assert only_in_doc == {"old/removed/*"}
    assert only_in_routing == set()


def test_parity_check_passes_on_matching_fixtures():
    # the other direction: agreement must not be flagged
    fixture_text = "## Guard paths\n- scripts/*\n- *hooks/*\n"
    fixture_routing = {"paths": {"scripts/*": ["cto-reviewer"],
                                  "*hooks/*": ["cto-reviewer"]}}
    assert _parity_diff(fixture_text, fixture_routing) == (set(), set())


def test_guard_paths_doc_matches_routing():
    # `.claude/rules/` is NOT synced by scripts/bootstrap.sh (that's Phase 7's
    # distribution work) — a repo built from this kit today has no
    # guard-paths.md at all, and that must be a clean skip, never a crash.
    # FileNotFoundError is not an AssertionError, so letting it propagate
    # would escape this file's own __main__ handler and break CI in every
    # consumer repo (e.g. dbt-agent-kit) that hasn't opted into this file yet.
    if not os.path.isfile(_RULES_FILE):
        print("skip (.claude/rules/guard-paths.md not present in this repo)")
        return
    text = open(_RULES_FILE, encoding="utf-8").read()
    routing = json.load(open(_ROUTING_FILE, encoding="utf-8"))
    only_in_doc, only_in_routing = _parity_diff(text, routing)
    assert not only_in_doc and not only_in_routing, (
        "guard-paths.md and review_routing.json have drifted — "
        f"only in doc: {sorted(only_in_doc)}; only in routing: {sorted(only_in_routing)}"
    )


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
