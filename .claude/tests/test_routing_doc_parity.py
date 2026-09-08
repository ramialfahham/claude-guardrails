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
    escalation") must not leak into the comparison. Strips a surrounding
    pair of backticks from each item (a no-op if there isn't one) — this
    kit's own hand-authored guard-paths.md writes plain `- scripts/*`, but
    scripts/generate_project_setup.py's renderer writes `` - `scripts/*` ``
    for a generated project, and both must parse to the same bare pattern."""
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
                paths.add(m.group(1).strip().strip("`"))
    return paths


# Reads the guard-path-routed reviewer's name FROM the doc's own "Convention"
# paragraph rather than hardcoding "cto-reviewer" — this file is copied
# VERBATIM into every project by scripts/bootstrap.sh's `refresh_dir
# ".claude/tests"`, where the name is "platform-reviewer", not this kit's
# own legacy name. Matches both this kit's own phrasing ("...reviewer(s) —
# currently `cto-reviewer`, and any future...") and a generated project's
# ("...reviewer(s) — `platform-reviewer` — with...") — anything between the
# dash and the first backtick-quoted name is skipped, non-greedily.
_ESCALATE_REVIEWER_RE = re.compile(
    r"spawn the required reviewer\(s\)\s*—.*?`([a-z][a-z0-9-]*)`", re.DOTALL)


def _escalate_reviewer_name(rules_text: str) -> str | None:
    m = _ESCALATE_REVIEWER_RE.search(rules_text)
    return m.group(1) if m else None


def _routed_to_reviewer(routing: dict, reviewer_name: str) -> set[str]:
    return {pattern for pattern, reviewers in (routing.get("paths") or {}).items()
            if reviewer_name in reviewers}


def _parity_diff(rules_text: str, routing: dict) -> tuple[set[str], set[str]]:
    """(only_in_doc, only_in_routing) — the actual comparison under test,
    shared by every test below so a fixture exercises the SAME code path the
    real check uses, not a hand-written re-implementation of it. Reads the
    escalate-reviewer name from rules_text itself (see
    _escalate_reviewer_name) — an empty routed set (rather than a crash) if
    the doc doesn't name one, since a doc that fails to name its own
    escalate reviewer is itself the defect the "only in doc" side of the
    diff will correctly surface."""
    documented = _parse_guard_paths_section(rules_text)
    reviewer_name = _escalate_reviewer_name(rules_text)
    routed = _routed_to_reviewer(routing, reviewer_name) if reviewer_name else set()
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


def test_routed_to_reviewer_ignores_other_reviewers():
    routing = {
        "paths": {
            "scripts/*": ["cto-reviewer"],
            "models/*": ["analytics-engineer-reviewer"],
            "*hooks/*": ["cto-reviewer", "security-reviewer"],
        }
    }
    assert _routed_to_reviewer(routing, "cto-reviewer") == {"scripts/*", "*hooks/*"}


def test_escalate_reviewer_name_reads_from_the_doc_not_hardcoded():
    # this file is copied VERBATIM into every project by bootstrap.sh, where
    # the name is "platform-reviewer", not this kit's own "cto-reviewer" —
    # both phrasings (this kit's own, and a generated project's) must parse
    cto_phrasing = ("spawn the required reviewer(s) — currently "
                     "`cto-reviewer`, and any future function-named reviewer")
    assert _escalate_reviewer_name(cto_phrasing) == "cto-reviewer"
    generated_phrasing = "spawn the required reviewer(s) — `platform-reviewer`\n— with"
    assert _escalate_reviewer_name(generated_phrasing) == "platform-reviewer"
    assert _escalate_reviewer_name("no convention sentence at all here") is None


_CONVENTION = "spawn the required reviewer(s) — `cto-reviewer` — with\n\n"


def test_parity_check_detects_a_missing_doc_entry():
    # the pin: a path routed to the escalate reviewer but never documented
    # must surface — through the REAL _parity_diff, not a re-implementation
    fixture_text = _CONVENTION + "## Guard paths\n- scripts/*\n"
    fixture_routing = {"paths": {"scripts/*": ["cto-reviewer"],
                                  "*hooks/*": ["cto-reviewer"]}}
    only_in_doc, only_in_routing = _parity_diff(fixture_text, fixture_routing)
    assert only_in_doc == set()
    assert only_in_routing == {"*hooks/*"}


def test_parity_check_detects_a_stale_doc_entry():
    # the pin: a documented path no longer routed to the escalate reviewer
    # must surface — through the REAL _parity_diff, not a re-implementation
    fixture_text = _CONVENTION + "## Guard paths\n- scripts/*\n- old/removed/*\n"
    fixture_routing = {"paths": {"scripts/*": ["cto-reviewer"]}}
    only_in_doc, only_in_routing = _parity_diff(fixture_text, fixture_routing)
    assert only_in_doc == {"old/removed/*"}
    assert only_in_routing == set()


def test_parity_check_handles_backtick_wrapped_list_items():
    # the round-2 fix: scripts/generate_project_setup.py's renderer writes
    # `` - `scripts/*` `` (backtick-wrapped); this kit's own hand-authored
    # doc writes plain `- scripts/*` — both must parse to the same pattern
    fixture_text = _CONVENTION + "## Guard paths\n- `scripts/*`\n- `*hooks/*`\n"
    fixture_routing = {"paths": {"scripts/*": ["cto-reviewer"],
                                  "*hooks/*": ["cto-reviewer"]}}
    assert _parity_diff(fixture_text, fixture_routing) == (set(), set())


def test_parity_check_passes_on_matching_fixtures():
    # the other direction: agreement must not be flagged
    fixture_text = _CONVENTION + "## Guard paths\n- scripts/*\n- *hooks/*\n"
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
