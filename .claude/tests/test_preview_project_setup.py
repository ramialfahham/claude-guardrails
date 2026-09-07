"""Tests for scripts/preview_project_setup.py — Phase 6a's dry-run preview
for the `setup-project` interview.

Runnable with `pytest` or directly: `python .claude/tests/test_preview_project_setup.py`.
"""

import inspect
import json
import os
import subprocess
import sys
import tempfile
import unittest

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_CLAUDE_DIR = os.path.dirname(_TESTS_DIR)
_REPO_ROOT = os.path.dirname(_CLAUDE_DIR)
_SCRIPTS_DIR = os.path.join(_REPO_ROOT, "scripts")
_SCRIPT_FILE = os.path.join(_SCRIPTS_DIR, "preview_project_setup.py")

# scripts/ and templates/ are NOT part of what scripts/bootstrap.sh copies
# into a consumer repo (only .claude/{hooks,agents,commands,skills,tests} —
# see bootstrap.sh's refresh_dir calls) — a bootstrapped repo gets this test
# file but none of the three modules it imports. A bare top-level import
# would raise ModuleNotFoundError before any test or the __main__ handler
# below runs, breaking CI in every consumer repo. Same class of defect
# already fixed twice in this repo (test_audit_ci_automation.py,
# test_routing_doc_parity.py); same fix here: guard, then skip cleanly
# per-test with unittest.SkipTest.
_HAVE_SCRIPT = os.path.isfile(_SCRIPT_FILE)
_SCRIPT_UNAVAILABLE = None if _HAVE_SCRIPT else (
    "scripts/preview_project_setup.py not present (a bootstrapped repo, not the kit)")

pps = compose_routing = lint_reviewer_name = None
if _HAVE_SCRIPT:
    sys.path.insert(0, _SCRIPTS_DIR)
    import preview_project_setup as pps  # noqa: E402
    import compose_routing  # noqa: E402
    import lint_reviewer_name  # noqa: E402


def _require_script():
    if _SCRIPT_UNAVAILABLE:
        raise unittest.SkipTest(_SCRIPT_UNAVAILABLE)


def test_dbt_project_selects_platform_and_analytics_engineer_only():
    # the plan's own Phase 6 verification note: "at least one dbt project"
    _require_script()
    answers = pps.SetupAnswers(dbt=True)
    selected = set(pps.select_reviewer_modules(answers))
    assert selected == {"platform-reviewer", "analytics-engineer-reviewer"}


def test_non_dbt_project_selects_expected_subset():
    # the plan's own Phase 6 verification note: "one non-dbt project"
    _require_script()
    answers = pps.SetupAnswers(data_eng=True, frontend=True, sensitive_data=True)
    selected = set(pps.select_reviewer_modules(answers))
    assert selected == {
        "platform-reviewer", "data-engineer-reviewer",
        "frontend-reviewer", "security-reviewer",
    }
    assert "analytics-engineer-reviewer" not in selected


def test_no_tags_selects_only_the_always_module():
    _require_script()
    answers = pps.SetupAnswers()
    assert pps.select_reviewer_modules(answers) == ["platform-reviewer"]


def test_selection_never_invents_a_module_for_unmatched_stack():
    _require_script()
    with_note = pps.SetupAnswers(unmatched_stack_description="a mobile app in Kotlin")
    without_note = pps.SetupAnswers()
    assert (pps.select_reviewer_modules(with_note)
            == pps.select_reviewer_modules(without_note))
    assert pps.build_escalations(with_note) != []
    assert pps.build_escalations(without_note) == []


def test_cli_has_no_unmatched_stack_flag():
    # structural fix for a real command-injection finding: the interview
    # skill must never be able to embed free-text user input into this
    # CLI's argv, so the flag itself must not exist — not just be
    # discouraged in the skill's own instructions, which is prose a model
    # could still be talked past
    _require_script()
    result = subprocess.run(
        [sys.executable, _SCRIPT_FILE, "--unmatched-stack", "x"],
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode != 0
    assert "unrecognized arguments" in result.stderr


def test_naming_lint_passes_on_every_selected_module_in_every_scenario():
    _require_script()
    scenarios = [
        pps.SetupAnswers(),
        pps.SetupAnswers(dbt=True),
        pps.SetupAnswers(data_eng=True, frontend=True, sensitive_data=True),
    ]
    for answers in scenarios:
        selected = pps.select_reviewer_modules(answers)
        report = pps.build_naming_lint_report(selected)
        for name in selected:
            assert report[name]["denylist_hits"] == [], (name, report[name])
            assert report[name]["mismatch"] is None, (name, report[name])
        # also drive the REAL lint function directly, not just this file's
        # wrapper, to prove the wrapper isn't hiding a divergence
        for name in selected:
            path = os.path.join(pps._REVIEWERS_DIR, f"{name}.md")
            _, hits, mismatch = lint_reviewer_name.check_file(path)
            assert hits == [] and mismatch is None


def test_load_module_tags_excludes_readme():
    _require_script()
    tags = pps.load_module_tags()
    assert "README" not in tags


def test_load_module_tags_raises_loudly_on_a_missing_applies_when():
    # an earlier version silently mapped a parse miss to tags=[] — module
    # excluded from every project with zero signal, indistinguishable from
    # "correctly matches nothing". A genuine parse failure must be loud.
    _require_script()
    with tempfile.TemporaryDirectory() as reviewers_dir:
        path = os.path.join(reviewers_dir, "broken-reviewer.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("---\nname: broken-reviewer\nmodel: sonnet\n---\nbody\n")
        try:
            pps.load_module_tags(reviewers_dir)
            assert False, "expected MalformedModuleError"
        except pps.MalformedModuleError:
            pass


def test_load_module_tags_raises_loudly_on_an_empty_applies_when():
    _require_script()
    with tempfile.TemporaryDirectory() as reviewers_dir:
        path = os.path.join(reviewers_dir, "broken-reviewer.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("---\nname: broken-reviewer\napplies_when: []\n---\nbody\n")
        try:
            pps.load_module_tags(reviewers_dir)
            assert False, "expected MalformedModuleError"
        except pps.MalformedModuleError:
            pass


def test_routing_preview_matches_compose_directly():
    _require_script()
    answers = pps.SetupAnswers(dbt=True)
    selected = pps.select_reviewer_modules(answers)
    preview = pps.build_routing_preview(selected)

    # hand-build the same composition using the real compose() function,
    # independent of build_routing_preview's own plumbing
    fragments = {
        name: compose_routing.load_json_strict(
            os.path.join(pps._FRAGMENTS_DIR, f"{name}.routing.json"))
        for name in selected
    }
    expected = compose_routing.compose(pps._BASE_ROUTING, fragments)
    assert preview == expected


def test_routing_preview_base_is_not_this_kits_own_routing_file():
    # the decision this contract records: a new project must NOT inherit
    # this kit's own cto-reviewer routing
    _require_script()
    preview = pps.build_routing_preview(["platform-reviewer"])
    for reviewers in preview["paths"].values():
        assert "cto-reviewer" not in reviewers


def test_guard_paths_preview_is_derived_from_routing_not_a_second_source():
    # the round-1 fix: guard_paths must be exactly the paths platform-reviewer
    # is routed to in the SAME routing preview — never an independently
    # sourced list that could (and, for real, does) disagree
    _require_script()
    routing_preview = pps.build_routing_preview(["platform-reviewer"])
    expected = sorted(
        pattern for pattern, reviewers in routing_preview["paths"].items()
        if "platform-reviewer" in reviewers
    )
    gp = pps.build_guard_paths_preview(routing_preview)
    assert gp["guard_paths"] == expected
    # also cross-check directly against the shipped fragment file, so this
    # doesn't only re-derive the expectation from build_routing_preview
    with open(os.path.join(pps._FRAGMENTS_DIR, "platform-reviewer.routing.json"),
              encoding="utf-8") as f:
        fragment_paths = sorted(json.load(f)["paths"])
    assert gp["guard_paths"] == fragment_paths


def test_guard_paths_preview_names_platform_reviewer_and_exempts_scope_auditor():
    _require_script()
    for selected in (["platform-reviewer"],
                      ["platform-reviewer", "analytics-engineer-reviewer"]):
        routing_preview = pps.build_routing_preview(selected)
        preview = pps.build_guard_paths_preview(routing_preview)
        assert preview["escalate_reviewer"] == "platform-reviewer"
        assert preview["exempted"] == "scope-auditor"


def test_guard_paths_preview_raises_loudly_on_an_empty_routing_preview():
    # platform-reviewer is applies_when: [always], so a routing preview
    # that routes nothing to it should never happen in real use — an
    # earlier version silently degraded to escalate_reviewer: None instead
    # of surfacing that something upstream is broken
    _require_script()
    empty_routing_preview = {"always": ["scope-auditor"], "paths": {}}
    try:
        pps.build_guard_paths_preview(empty_routing_preview)
        assert False, "expected EmptyGuardPathsError"
    except pps.EmptyGuardPathsError:
        pass


def test_model_tiers_reflect_real_frontmatter():
    # pinned against a literal, not recomputed with the function's own
    # regex — a test that re-derives its expectation from the code under
    # test can't fail for a parsing bug in that code
    _require_script()
    selected = pps.select_reviewer_modules(pps.SetupAnswers(dbt=True))
    tiers = pps.build_model_tiers(selected)
    assert tiers == {"platform-reviewer": "sonnet", "analytics-engineer-reviewer": "sonnet"}


def test_model_tiers_reports_unknown_for_a_module_with_no_model_field():
    _require_script()
    with tempfile.TemporaryDirectory() as reviewers_dir:
        with open(os.path.join(reviewers_dir, "x-reviewer.md"), "w", encoding="utf-8") as f:
            f.write("---\nname: x-reviewer\n---\nbody\n")
        tiers = pps.build_model_tiers(["x-reviewer"], reviewers_dir)
        assert tiers["x-reviewer"] == "(unknown)"


# Deliberately NOT "remove", "copy", "move", "replace" — those are also
# ordinary str/dict/list method names (`str.replace`, `dict.copy`,
# `list.remove`), and this checker can't tell `os.remove(...)` from
# `some_list.remove(...)` from an attribute name alone. An earlier version
# included them and would have gone red on ordinary dict-building code
# elsewhere in this same file the day someone wrote `result.copy()` — the
# exact cry-wolf shape this repo's own history calls worse than no check.
# The names kept below are specific enough (no common non-filesystem type
# has a `.write_text`, `.rmtree`, or `.copyfile` method) that a real
# collision is very unlikely, but this is inherently a NAME heuristic, not
# type-aware analysis — see `_find_filesystem_write_calls`'s docstring for
# what this function is (and, honestly, isn't) a guarantee of.
_SUSPICIOUS_CALL_NAMES = {
    "write_text", "write_bytes", "rename", "renames", "makedirs", "mkdir",
    "unlink", "rmtree", "copy2", "copyfile", "symlink", "link", "truncate",
}


def _called_name(func) -> str | None:
    """Best-effort callee name of an ast.Call's `func` node: 'open' for
    `open(...)`, 'write_text' for `x.write_text(...)` (an ast.Attribute),
    None for anything else (e.g. a call through a variable)."""
    import ast
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _find_filesystem_write_calls(source: str) -> list[str]:
    """BEST-EFFORT LINT HINT, not the enforcement mechanism — the authoritative
    guarantee that the CLI writes nothing is `test_cli_writes_nothing_into_its_cwd_or_anywhere_in_the_repo`'s
    runtime content-hash snapshot of the whole repo tree, which observes what
    actually happened rather than trying to statically prove what a piece of
    Python code *could* do (a name-based AST scan can always be defeated by a
    call through an alias, `getattr`, or a wrapper function — that is not a
    gap to keep patching, it is what static analysis of a dynamic language
    fundamentally is). This function still catches the common, honest
    mistakes cheaply and immediately (at test time, without running a
    subprocess):
    - `open(...)` (or `x.open(...)`, e.g. `Path(p).open(...)`) whose mode
      argument is an explicit write/append/exclusive/plus mode, OR isn't a
      string literal at all (a variable/expression mode, or `**kwargs`, is
      conservatively flagged too — this only gates a preview tool that
      should never need a non-obvious mode);
    - a call literally named after a specific, low-collision-risk
      filesystem mutator (`write_text`, `rename`, `makedirs`, `rmtree`,
      `copyfile`, …) — NOT generic names like `remove`/`copy`/`move`/`replace`
      that collide with ordinary `str`/`dict`/`list` methods (a false
      positive on every dict-building line in this file, which an earlier
      version of this list actually had)."""
    import ast
    tree = ast.parse(source)
    hits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _called_name(node.func)
        if name is None:
            continue
        if name in _SUSPICIOUS_CALL_NAMES:
            hits.append(f"{name}(...) at line {node.lineno}")
            continue
        if name != "open":
            continue
        mode = None
        mode_is_literal = True
        if len(node.args) >= 2:
            if isinstance(node.args[1], ast.Constant):
                mode = node.args[1].value
            else:
                mode_is_literal = False
        for kw in node.keywords:
            if kw.arg == "mode":
                if isinstance(kw.value, ast.Constant):
                    mode = kw.value.value
                else:
                    mode_is_literal = False
            elif kw.arg is None:  # a **kwargs spread — can't statically rule out "mode"
                mode_is_literal = False
        if not mode_is_literal:
            hits.append(f"open(...) with a non-literal mode at line {node.lineno}")
        elif isinstance(mode, str) and any(c in mode for c in "wax+"):
            hits.append(f"open(...) with mode {mode!r} at line {node.lineno}")
    return hits


def test_write_detection_actually_fires_on_real_writes():
    # negative fixtures proving the check isn't vacuous — including every
    # shape a prior round's narrower check missed
    assert _find_filesystem_write_calls('open(os.path.join(d, n), "w")\n') != []
    assert _find_filesystem_write_calls('open(path, mode="a")\n') != []
    assert _find_filesystem_write_calls('mode = "w"\nopen(path, mode)\n') != []
    assert _find_filesystem_write_calls('open(path, **kw)\n') != []
    assert _find_filesystem_write_calls('Path(path).write_text("x")\n') != []
    assert _find_filesystem_write_calls('os.rename(a, b)\n') != []
    assert _find_filesystem_write_calls('os.makedirs(d)\n') != []
    # and it must NOT flag the shapes this script actually uses
    assert _find_filesystem_write_calls('open(os.path.join(d, n), encoding="utf-8")\n') == []


def test_write_detection_does_not_false_positive_on_ordinary_methods():
    # remove/copy/move/replace collide with common str/dict/list methods —
    # an earlier version of the denylist included them and would have
    # flagged ordinary, non-filesystem code as a false positive
    assert _find_filesystem_write_calls('result.copy()\n') == []
    assert _find_filesystem_write_calls('some_list.remove(x)\n') == []
    assert _find_filesystem_write_calls('text.replace("a", "b")\n') == []
    assert _find_filesystem_write_calls('items.move(0, 1)\n') == []


def test_no_filesystem_write_call_anywhere_in_the_script():
    # the contract's own done_when check, run as an actual test rather than
    # only a manual grep
    _require_script()
    with open(_SCRIPT_FILE, encoding="utf-8") as f:
        source = f.read()
    hits = _find_filesystem_write_calls(source)
    assert hits == [], f"found filesystem-mutating call(s): {hits}"


def _repo_snapshot(root: str) -> dict[str, str]:
    """{relpath: sha256 of file contents} for every file under `root` —
    NOT just a path listing, which would pass on an in-place overwrite of
    an existing file (this script already imports `compose_routing`, whose
    `_write_atomic()` writes-and-`os.replace`s a target file with the SAME
    name — a leaked call to it would rewrite e.g. `.claude/review_routing.json`
    with the path listing unchanged). Excludes `.git` (its own internal
    state churns independently of this script) and `__pycache__`
    (gitignored interpreter bytecode, not a write to tracked project
    content)."""
    import hashlib
    snapshot = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__")]
        for fname in filenames:
            path = os.path.join(dirpath, fname)
            rel = os.path.relpath(path, root)
            with open(path, "rb") as f:
                snapshot[rel] = hashlib.sha256(f.read()).hexdigest()
    return snapshot


def test_cli_writes_nothing_into_its_cwd_or_anywhere_in_the_repo():
    # snapshots the WHOLE repo tree, not just scripts/ or the subprocess's
    # cwd — a write into templates/ or any other path is caught here too
    _require_script()
    with tempfile.TemporaryDirectory() as cwd:
        before_cwd = sorted(os.listdir(cwd))
        before_repo = _repo_snapshot(_REPO_ROOT)
        result = subprocess.run(
            [sys.executable, _SCRIPT_FILE, "--dbt"],
            cwd=cwd, capture_output=True, text=True, timeout=20,
        )
        after_cwd = sorted(os.listdir(cwd))
        after_repo = _repo_snapshot(_REPO_ROOT)
    assert result.returncode == 0, result.stderr
    assert before_cwd == after_cwd == [], "the CLI must never write into its cwd"
    changed = {
        rel for rel in set(before_repo) | set(after_repo)
        if before_repo.get(rel) != after_repo.get(rel)
    }
    assert not changed, (
        f"the CLI must never write a tracked file anywhere in the repo, "
        f"but these changed or appeared/disappeared: {sorted(changed)}")
    assert "DRY RUN" in result.stdout
    assert "analytics-engineer-reviewer" in result.stdout


def test_cli_matches_library_output_for_the_same_answers():
    _require_script()
    answers = pps.SetupAnswers(data_eng=True, frontend=True, sensitive_data=True)
    expected = pps.format_preview(pps.build_preview(answers))
    result = subprocess.run(
        [sys.executable, _SCRIPT_FILE, "--data-eng", "--frontend", "--sensitive-data"],
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.rstrip("\n") == expected


def test_build_preview_output_is_json_serializable():
    # the skill prints this via json.dumps for the routing sub-section, and
    # the whole structure should be safe to serialize wholesale too
    _require_script()
    preview = pps.build_preview(pps.SetupAnswers(dbt=True))
    json.dumps(preview)  # raises TypeError if anything isn't serializable


def test_ci_provider_is_recorded_but_does_not_affect_selection():
    _require_script()
    with_github = pps.select_reviewer_modules(pps.SetupAnswers(ci_provider="github"))
    with_gitlab = pps.select_reviewer_modules(pps.SetupAnswers(ci_provider="gitlab"))
    with_none = pps.select_reviewer_modules(pps.SetupAnswers(ci_provider="none"))
    assert with_github == with_gitlab == with_none


if __name__ == "__main__":
    _failed = 0
    for _name, _fn in sorted(globals().items()):
        if _name.startswith("test_") and callable(_fn) and not inspect.isclass(_fn):
            try:
                _fn()
                print(f"ok   {_name}")
            except unittest.SkipTest as e:
                print(f"skip {_name}: {e}")
            except AssertionError as e:
                _failed += 1
                print(f"FAIL {_name}: {e}")
    print("all tests passed" if not _failed else f"{_failed} test(s) failed")
    sys.exit(1 if _failed else 0)
