"""Tests for scripts/generate_project_setup.py — Phase 6b's actual generation
for the `setup-project` interview.

Runnable with `pytest` or directly: `python .claude/tests/test_generate_project_setup.py`.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_CLAUDE_DIR = os.path.dirname(_TESTS_DIR)
_REPO_ROOT = os.path.dirname(_CLAUDE_DIR)
_SCRIPTS_DIR = os.path.join(_REPO_ROOT, "scripts")
_SCRIPT_FILE = os.path.join(_SCRIPTS_DIR, "generate_project_setup.py")
_BOOTSTRAP_SH = os.path.join(_SCRIPTS_DIR, "bootstrap.sh")

_BASH = shutil.which("bash")
_GIT = shutil.which("git")

# scripts/ and templates/ are NOT part of what scripts/bootstrap.sh copies
# into a consumer repo (only .claude/{hooks,agents,commands,skills,tests} —
# see bootstrap.sh's own refresh_dir calls), so a bootstrapped repo gets this
# test file but none of the modules it imports, nor bootstrap.sh itself. Same
# guard-then-skip pattern as test_preview_project_setup.py and test_bootstrap.py.
_HAVE_SCRIPT = os.path.isfile(_SCRIPT_FILE)
_SCRIPT_UNAVAILABLE = None if _HAVE_SCRIPT else (
    "scripts/generate_project_setup.py not present (a bootstrapped repo, not the kit)")

gps = pps = None
if _HAVE_SCRIPT:
    sys.path.insert(0, _SCRIPTS_DIR)
    import generate_project_setup as gps  # noqa: E402
    import preview_project_setup as pps  # noqa: E402


def _require_env():
    if _SCRIPT_UNAVAILABLE:
        raise unittest.SkipTest(_SCRIPT_UNAVAILABLE)
    if not _BASH:
        raise unittest.SkipTest("no bash on PATH (needed to run bootstrap.sh)")
    if not _GIT:
        raise unittest.SkipTest("no git on PATH")
    if not os.path.isfile(_BOOTSTRAP_SH):
        raise unittest.SkipTest(
            "scripts/bootstrap.sh not present (a bootstrapped repo, not the kit)")


def _git(repo, *args):
    subprocess.run([_GIT, *args], cwd=repo, check=True,
                    capture_output=True, timeout=30)


def _bootstrapped_target(base_dir: str) -> str:
    """A fresh git repo at base_dir/target, bootstrapped by the REAL
    bootstrap.sh (not faked), on a 'feature' branch one commit ahead of
    'main' — the realistic topology this repo's own working-agreement.md
    tells every bootstrapped project to use (never commit to main directly),
    and the ONE topology that actually exercises commit_review_gate.py's
    real cumulative-diff-since-base-branch code path rather than its
    no-base-ref fallback (see test_commit_review_gate.py's own
    test_diff_to_hash_covers_earlier_commits_on_the_branch for the same
    pattern). A round-1 review finding on this exact test file was invisible
    specifically because an earlier version never made ANY commit at all,
    which took the (well-tested-elsewhere) fallback branch instead."""
    target = os.path.join(base_dir, "target")
    os.makedirs(target)
    _git(target, "init", "-q", "-b", "main")
    _git(target, "config", "user.email", "t@t.t")
    _git(target, "config", "user.name", "t")
    with open(os.path.join(target, ".gitkeep"), "w", encoding="utf-8") as f:
        f.write("")
    _git(target, "add", ".gitkeep")
    _git(target, "commit", "-q", "-m", "baseline")
    _git(target, "checkout", "-q", "-b", "feature")
    result = subprocess.run(
        [_BASH, _BOOTSTRAP_SH, target], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    return target


def _repo_snapshot(root: str) -> dict[str, str]:
    """{relpath: sha256 of file contents} for every file under `root` — NOT
    just a path listing, which would pass on an in-place overwrite of a
    same-named file. Excludes `.git` (churns independently) and
    `__pycache__` (gitignored bytecode)."""
    snapshot = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__")]
        for fname in filenames:
            path = os.path.join(dirpath, fname)
            rel = os.path.relpath(path, root)
            with open(path, "rb") as f:
                snapshot[rel] = hashlib.sha256(f.read()).hexdigest()
    return snapshot


def test_generate_refuses_on_an_unbootstrapped_target():
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = os.path.join(tmp, "not-bootstrapped")
        os.makedirs(target)
        try:
            gps.generate(target, pps.SetupAnswers(dbt=True))
            assert False, "expected GenerationRefused"
        except gps.GenerationRefused:
            pass
        # nothing should have been created at all
        assert os.listdir(target) == []


def test_dbt_scenario_installs_expected_modules_and_removes_legacy_reviewer():
    # the plan's own Phase 6 verification note: "at least one dbt project" —
    # same scenario test_preview_project_setup.py already uses, so the
    # generated file set is checked against the SAME expected module list
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        legacy_path = os.path.join(target, ".claude", "agents", "cto-reviewer.md")
        assert os.path.isfile(legacy_path), "bootstrap.sh should ship the legacy reviewer"

        summary = gps.generate(target, pps.SetupAnswers(dbt=True))

        assert set(summary["modules_installed"]) == {
            "platform-reviewer", "analytics-engineer-reviewer"}
        assert summary["legacy_reviewer_removed"] is True
        assert not os.path.isfile(legacy_path)
        for name in summary["modules_installed"]:
            assert os.path.isfile(
                os.path.join(target, ".claude", "agents", f"{name}.md"))


def test_non_dbt_scenario_installs_expected_modules():
    # the plan's own Phase 6 verification note: "one non-dbt project"
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        answers = pps.SetupAnswers(data_eng=True, frontend=True, sensitive_data=True)
        summary = gps.generate(target, answers)
        assert set(summary["modules_installed"]) == {
            "platform-reviewer", "data-engineer-reviewer",
            "frontend-reviewer", "security-reviewer",
        }
        assert "analytics-engineer-reviewer" not in summary["modules_installed"]


def test_naming_lint_refusal_writes_nothing():
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        with tempfile.TemporaryDirectory() as bad_reviewers_dir:
            with open(os.path.join(bad_reviewers_dir, "cto-reviewer.md"),
                      "w", encoding="utf-8") as f:
                f.write("---\nname: cto-reviewer\napplies_when: [always]\n"
                        "model: sonnet\n---\nbody\n")
            before = _repo_snapshot(target)
            try:
                gps.generate(target, pps.SetupAnswers(), reviewers_dir=bad_reviewers_dir)
                assert False, "expected GenerationRefused"
            except gps.GenerationRefused:
                pass
            after = _repo_snapshot(target)
            assert before == after, "a refused generation must write nothing"


def test_routing_written_includes_artifact_only_defaults_and_no_legacy_name():
    # closes the real gap preview_project_setup.py's own docstring flags:
    # without these keys every commit (even trivial task/handover edits)
    # would require full review
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        gps.generate(target, pps.SetupAnswers(dbt=True))
        with open(os.path.join(target, ".claude", "review_routing.json"),
                  encoding="utf-8") as f:
            routing = json.load(f)
        assert routing["artifact_only"] == [".claude/task/*", ".claude/active_work.md"]
        assert routing["artifact_only_never"] == [".claude/task/contract.md"]
        assert "cto-reviewer" not in routing.get("always", [])
        for reviewers in routing.get("paths", {}).values():
            assert "cto-reviewer" not in reviewers


def test_routing_written_matches_build_routing_preview_directly():
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        answers = pps.SetupAnswers(dbt=True)
        gps.generate(target, answers)
        with open(os.path.join(target, ".claude", "review_routing.json"),
                  encoding="utf-8") as f:
            written = json.load(f)
        selected = pps.select_reviewer_modules(answers)
        expected = pps.build_routing_preview(selected, base_routing=gps._GENERATION_BASE)
        # generate() stamps one extra key, _generated_sha256, that
        # build_routing_preview itself never adds (see generate()'s own
        # comment on why it's computed after composing) — everything else
        # must match exactly, and the stamped hash must be genuinely correct
        # for what was actually written, not just present.
        written_hash = written.pop("_generated_sha256")
        assert written == expected
        assert written_hash == gps._routing_content_hash(written)


def test_guard_paths_md_matches_the_composed_routing_not_a_hardcoded_copy():
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        gps.generate(target, pps.SetupAnswers(dbt=True))
        with open(os.path.join(target, ".claude", "review_routing.json"),
                  encoding="utf-8") as f:
            routing = json.load(f)
        expected_paths = sorted(
            pattern for pattern, reviewers in routing["paths"].items()
            if "platform-reviewer" in reviewers)
        with open(os.path.join(target, ".claude", "rules", "guard-paths.md"),
                  encoding="utf-8") as f:
            content = f.read()
        for pattern in expected_paths:
            assert f"- `{pattern}`" in content
        assert "`platform-reviewer`" in content
        assert "`scope-auditor`" in content
        assert "<REPLACE" not in content and "<path pattern" not in content


def test_generated_targets_own_routing_doc_parity_test_actually_passes():
    # the round-2 finding this pins: writing guard-paths.md un-skips
    # .claude/tests/test_routing_doc_parity.py (which bootstrap.sh already
    # copied into every target) — that test used to be hardcoded to look
    # for "cto-reviewer" and compare against un-backticked list items,
    # neither of which matches what a generated project actually has
    # (platform-reviewer, backtick-wrapped items), so it failed in EVERY
    # generated project until .claude/tests/test_routing_doc_parity.py
    # itself was fixed in this same round. Running the target's own real
    # copy of that file — not this repo's — is what actually proves a
    # generated project passes its own bootstrap-test pattern, matching
    # this contract's own done_when wording.
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        gps.generate(target, pps.SetupAnswers(dbt=True))
        parity_test = os.path.join(target, ".claude", "tests", "test_routing_doc_parity.py")
        assert os.path.isfile(parity_test)
        result = subprocess.run(
            [sys.executable, parity_test], capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "all tests passed" in result.stdout


def test_readme_written_on_a_fresh_target_and_preserved_on_a_second_run():
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        summary = gps.generate(target, pps.SetupAnswers(dbt=True))
        assert summary["readme_written"] is True
        readme_path = os.path.join(target, "README.md")
        assert os.path.isfile(readme_path)
        assert "analytics-engineer-reviewer" in open(readme_path, encoding="utf-8").read()

        with open(readme_path, "w", encoding="utf-8") as f:
            f.write("hand-written project content\n")
        summary2 = gps.generate(target, pps.SetupAnswers(dbt=True))
        assert summary2["readme_written"] is False
        with open(readme_path, encoding="utf-8") as f:
            assert f.read() == "hand-written project content\n", (
                "generate() must never overwrite an existing README.md")


def test_generate_is_idempotent_on_a_second_run():
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        answers = pps.SetupAnswers(dbt=True)
        gps.generate(target, answers)
        before = _repo_snapshot(target)
        gps.generate(target, answers)
        after = _repo_snapshot(target)
        assert before == after, (
            "re-running generate() with the same answers must converge to "
            "the same end state")


def test_smoke_test_refuses_if_a_real_review_md_already_exists():
    # the actual risk this precondition guards: a pre-existing, meaningful
    # review.md must never be silently overwritten and then deleted
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        gps.generate(target, pps.SetupAnswers(dbt=True))
        task_dir = os.path.join(target, ".claude", "task")
        os.makedirs(task_dir, exist_ok=True)
        review_path = os.path.join(task_dir, "review.md")
        with open(review_path, "w", encoding="utf-8") as f:
            f.write("a real, pre-existing review\n")
        try:
            gps.smoke_test(target)
            assert False, "expected SmokeTestRefused"
        except gps.SmokeTestRefused:
            pass
        with open(review_path, encoding="utf-8") as f:
            assert f.read() == "a real, pre-existing review\n", (
                "the smoke test must never touch a pre-existing review.md")


def test_smoke_test_chains_directly_after_generate_with_no_commit_in_between():
    # the regression this pins: an earlier version required the WHOLE tree
    # clean, which made the smoke test refuse immediately after every real
    # generate() call (generation itself necessarily leaves new files
    # uncommitted) — defeating the exact chaining the skill relies on
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        gps.generate(target, pps.SetupAnswers(dbt=True))
        # the target's tree is now genuinely dirty (new, uncommitted files) —
        # deliberately NOT committing before calling smoke_test()
        before = _repo_snapshot(target)

        result = gps.smoke_test(target)

        assert result == {"blocked_without_review": True, "allowed_with_review": True}
        after = _repo_snapshot(target)
        assert before == after, (
            "the smoke test must leave the target exactly as generate() left "
            "it, with no trace of its own dummy file or review.md")
        # filesystem state alone isn't enough — a leaked `git add` with no
        # matching `git reset` would still pass a content-hash comparison
        staged = subprocess.run(
            [_GIT, "diff", "--cached", "--name-only"], cwd=target,
            capture_output=True, text=True, timeout=30).stdout
        assert staged.strip() == "", (
            f"smoke test must leave the git index exactly as it found it, "
            f"but these paths are staged: {staged!r}")


def test_smoke_test_correctly_requires_platform_reviewer_once_the_generated_setup_is_committed():
    # the round-1 finding this pins: an earlier version wrote review.md
    # verdicts only for routing["always"], but commit_review_gate's real
    # _required_reviewers unions 'always' with every reviewer whose 'paths'
    # pattern matches the CUMULATIVE diff (everything committed since the
    # base branch, plus staged) — once the generated .claude/ is committed
    # on the feature branch (bootstrap.sh's own instructed next step), that
    # cumulative diff includes .claude/hooks/* and .claude/agents/*, which
    # platform-reviewer's own routing fragment matches, making it REQUIRED.
    # An under-computed review.md would make the "allow" simulation still
    # come back DENIED, reporting a correctly-working gate as broken.
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        gps.generate(target, pps.SetupAnswers(dbt=True))
        _git(target, "add", "-A")
        _git(target, "commit", "-q", "-m", "generated setup")

        result = gps.smoke_test(target)
        assert result == {"blocked_without_review": True, "allowed_with_review": True}


def test_generate_refuses_to_clobber_a_hand_customized_routing_file_without_force():
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        gps.generate(target, pps.SetupAnswers(dbt=True))
        routing_path = os.path.join(target, ".claude", "review_routing.json")
        with open(routing_path, "w", encoding="utf-8") as f:
            json.dump({"always": ["scope-auditor"],
                       "paths": {"custom/*": ["some-hand-added-reviewer"]}}, f)
        before = open(routing_path, encoding="utf-8").read()

        try:
            gps.generate(target, pps.SetupAnswers(dbt=True))
            assert False, "expected GenerationRefused"
        except gps.GenerationRefused:
            pass
        assert open(routing_path, encoding="utf-8").read() == before, (
            "a refused generation must never touch a hand-customized routing file")

        # force=True overrides it deliberately
        gps.generate(target, pps.SetupAnswers(dbt=True), force=True)
        with open(routing_path, encoding="utf-8") as f:
            written = json.load(f)
        assert written.get("_generated_by") == gps._GENERATED_BY_MARKER


def test_generate_refuses_a_file_edited_after_generation_even_with_the_marker_still_present():
    # the round-2 finding this pins: the _generated_by marker on its own
    # proves AUTHORSHIP, not that the file is unchanged SINCE — a marker
    # that merely checks for presence would let exactly this slip through:
    # bootstrap.sh's own closing instructions literally tell the owner to
    # "review .claude/review_routing.json — tune which reviewers gate which
    # paths," and a hand-edit made through a JSON-preserving tool (or by
    # hand, careful not to delete the marker) would keep _generated_by
    # intact while genuinely changing the routing. The content-hash check
    # must catch this even though the marker itself is untouched.
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        gps.generate(target, pps.SetupAnswers(dbt=True))
        routing_path = os.path.join(target, ".claude", "review_routing.json")
        with open(routing_path, encoding="utf-8") as f:
            routing = json.load(f)
        assert routing.get("_generated_by") == gps._GENERATED_BY_MARKER  # sanity
        routing["paths"]["custom/*"] = ["hand-added-reviewer"]  # marker left intact
        with open(routing_path, "w", encoding="utf-8") as f:
            json.dump(routing, f)
        before = open(routing_path, encoding="utf-8").read()

        assert gps._routing_needs_force(target), (
            "a marker-present-but-hash-mismatched file must need force")
        try:
            gps.generate(target, pps.SetupAnswers(dbt=True))
            assert False, "expected GenerationRefused"
        except gps.GenerationRefused:
            pass
        assert open(routing_path, encoding="utf-8").read() == before

        gps.generate(target, pps.SetupAnswers(dbt=True), force=True)
        assert not gps._routing_needs_force(target)


def test_generate_refuses_to_clobber_a_hand_authored_guard_paths_file_without_force():
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        rules_dir = os.path.join(target, ".claude", "rules")
        os.makedirs(rules_dir)
        guard_path = os.path.join(rules_dir, "guard-paths.md")
        with open(guard_path, "w", encoding="utf-8") as f:
            f.write("# Hand-authored guard paths\n\n- some/custom/*\n")
        before = open(guard_path, encoding="utf-8").read()

        try:
            gps.generate(target, pps.SetupAnswers(dbt=True))
            assert False, "expected GenerationRefused"
        except gps.GenerationRefused:
            pass
        assert open(guard_path, encoding="utf-8").read() == before

        gps.generate(target, pps.SetupAnswers(dbt=True), force=True)
        with open(guard_path, encoding="utf-8") as f:
            content = f.read()
        assert gps._GUARD_PATHS_MARKER_PREFIX in content
        assert not gps._guard_paths_needs_force(target), (
            "the freshly (force-)generated file must verify as this tool's "
            "own unmodified output")


def test_a_previously_generated_target_does_not_need_force_to_regenerate():
    # the idempotency guarantee this contract makes: THIS tool's own prior
    # output (tagged with the _generated_by marker) is safe to regenerate
    # without --force, even with different answers
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        gps.generate(target, pps.SetupAnswers(dbt=True))
        summary = gps.generate(target, pps.SetupAnswers(
            data_eng=True, frontend=True, sensitive_data=True))
        assert set(summary["modules_installed"]) == {
            "platform-reviewer", "data-engineer-reviewer",
            "frontend-reviewer", "security-reviewer",
        }


def test_generation_refusal_writes_nothing_even_when_a_template_has_drifted():
    # the round-1 finding this pins: template rendering used to happen AFTER
    # some writes (module copies, the legacy-file removal, the routing
    # write) had already occurred, contradicting GenerationRefused's own
    # documented "nothing is written before this can be raised" guarantee
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        with tempfile.TemporaryDirectory() as tmpl_dir:
            broken_tmpl = os.path.join(tmpl_dir, "guard-paths.md.tmpl")
            with open(broken_tmpl, "w", encoding="utf-8") as f:
                # still LOOKS like the real template's placeholders, but
                # reworded just enough that none of _render_guard_paths's
                # anchored regexes match — the realistic "someone edited the
                # prose around a marker" drift, as opposed to a template with
                # no placeholder-shaped text at all (which this function
                # can't distinguish from "nothing needed substituting")
                f.write("**Convention**: <REPLACE: a differently worded "
                        "placeholder that no longer matches>\n\n"
                        "## Guard paths\n\n- <path pattern 1>\n- <path pattern 2>\n\n"
                        "## Exempted from escalation\n\n"
                        "- <always-required reviewer name(s)>\n")
            before = _repo_snapshot(target)
            try:
                gps.generate(target, pps.SetupAnswers(dbt=True),
                              guard_paths_tmpl=broken_tmpl)
                assert False, "expected GenerationRefused"
            except gps.GenerationRefused:
                pass
            after = _repo_snapshot(target)
            assert before == after, (
                "a GenerationRefused from template rendering must still "
                "leave the target completely untouched — no module copies, "
                "no legacy-file removal, no routing write")


def test_cli_end_to_end_generates_and_runs_the_smoke_test():
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        result = subprocess.run(
            [sys.executable, _SCRIPT_FILE, "--target", target, "--dbt"],
            capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stderr
        assert "analytics-engineer-reviewer" in result.stdout
        assert ("smoke test: blocked without review = True, "
                "allowed with review = True") in result.stdout


def test_cli_has_no_unmatched_stack_flag():
    # same structural fix as preview_project_setup.py, for the same reason:
    # a real command-injection finding on an earlier draft of the skill
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        result = subprocess.run(
            [sys.executable, _SCRIPT_FILE, "--target", target, "--unmatched-stack", "x"],
            capture_output=True, text=True, timeout=20)
        assert result.returncode != 0
        assert "unrecognized arguments" in result.stderr


if __name__ == "__main__":
    _failed = 0
    for _name, _fn in sorted(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            try:
                _fn()
                print(f"ok   {_name}")
            except unittest.SkipTest as e:
                print(f"skip {_name}: {e}")
            except AssertionError as e:
                _failed += 1
                print(f"FAIL {_name}: {e}")
            except Exception as e:  # noqa: BLE001 — surface setup/subprocess errors too
                _failed += 1
                print(f"FAIL {_name}: {type(e).__name__}: {e}")
    print("all tests passed" if not _failed else f"{_failed} test(s) failed")
    sys.exit(1 if _failed else 0)
