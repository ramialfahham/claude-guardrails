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


def test_dbt_scenario_installs_expected_modules():
    # the plan's own Phase 6 verification note: "at least one dbt project" —
    # same scenario test_preview_project_setup.py already uses, so the
    # generated file set is checked against the SAME expected module list
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        legacy_path = os.path.join(target, ".claude", "agents", "cto-reviewer.md")
        assert not os.path.isfile(legacy_path), (
            "a fresh bootstrap ships platform-reviewer.md directly, never the "
            "retired cto-reviewer.md legacy name")

        summary = gps.generate(target, pps.SetupAnswers(dbt=True))

        assert set(summary["modules_installed"]) == {
            "platform-reviewer", "analytics-engineer-reviewer"}
        assert summary["legacy_reviewer_removed"] is False
        for name in summary["modules_installed"]:
            assert os.path.isfile(
                os.path.join(target, ".claude", "agents", f"{name}.md"))


def test_generate_cleans_up_a_pre_rename_legacy_reviewer_file():
    # coverage for projects bootstrapped before cto-reviewer.md was retired:
    # bootstrap.sh's own refresh_dir never deletes a file that's merely
    # absent from a newer kit checkout (plain `cp -R`, no sync/prune), so a
    # stale copy can genuinely still be sitting in an old project's
    # .claude/agents/ the first time it's tailored under the new kit.
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        legacy_path = os.path.join(target, ".claude", "agents", "cto-reviewer.md")
        with open(legacy_path, "w", encoding="utf-8") as f:
            f.write("---\nname: cto-reviewer\nmodel: sonnet\n---\nbody\n")

        summary = gps.generate(target, pps.SetupAnswers(dbt=True))

        assert summary["legacy_reviewer_removed"] is True
        assert not os.path.isfile(legacy_path)


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


def test_readme_tracker_guidance_reflects_tracker_provider():
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        answers = pps.SetupAnswers(dbt=True, tracker_provider="gitlab")
        gps.generate(target, answers)
        readme_text = open(os.path.join(target, "README.md"), encoding="utf-8").read()
        assert "GitLab Issues" in readme_text
        assert "ROADMAP.md" in readme_text
        assert "<tracker guidance>" not in readme_text


def test_standard_tier_leaves_bootstrap_working_agreement_untouched():
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        wa_path = os.path.join(target, ".claude", "working-agreement.md")
        before = open(wa_path, encoding="utf-8").read()
        summary = gps.generate(target, pps.SetupAnswers(dbt=True))
        assert summary["working_agreement_written"] is False
        assert "recognised standard file" in summary["working_agreement_reason"]
        assert open(wa_path, encoding="utf-8").read() == before


def test_solo_tier_replaces_working_agreement_with_the_lightweight_template():
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        summary = gps.generate(target, pps.SetupAnswers(dbt=True, process_tier="solo"))
        assert summary["working_agreement_written"] is True
        assert "converted" in summary["working_agreement_reason"]
        wa_path = os.path.join(target, ".claude", "working-agreement.md")
        with open(wa_path, encoding="utf-8") as f:
            written = f.read()
        with open(gps._SOLO_WORKING_AGREEMENT_TMPL, encoding="utf-8") as f:
            expected = f.read()
        assert written == expected

        # re-running with the same tier is a no-op, not a forced overwrite
        summary2 = gps.generate(target, pps.SetupAnswers(dbt=True, process_tier="solo"))
        assert summary2["working_agreement_written"] is False
        assert "already the solo template" in summary2["working_agreement_reason"]


def test_generate_refuses_to_clobber_a_hand_customized_working_agreement_without_force():
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        wa_path = os.path.join(target, ".claude", "working-agreement.md")
        with open(wa_path, "w", encoding="utf-8") as f:
            f.write("hand-written process notes\n")

        try:
            gps.generate(target, pps.SetupAnswers(dbt=True, process_tier="solo"))
            assert False, "expected GenerationRefused"
        except gps.GenerationRefused:
            pass
        with open(wa_path, encoding="utf-8") as f:
            assert f.read() == "hand-written process notes\n"

        # force=True overrides it deliberately
        summary = gps.generate(target, pps.SetupAnswers(dbt=True, process_tier="solo"),
                                force=True)
        assert summary["working_agreement_written"] is True


def test_solo_tier_can_switch_back_to_standard():
    # the mechanism must be bidirectional: a target already on Solo must be
    # able to converge back to Standard, not get stuck one-way
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        gps.generate(target, pps.SetupAnswers(dbt=True, process_tier="solo"))
        wa_path = os.path.join(target, ".claude", "working-agreement.md")
        with open(gps._SOLO_WORKING_AGREEMENT_TMPL, encoding="utf-8") as f:
            solo_text = f.read()
        with open(wa_path, encoding="utf-8") as f:
            assert f.read() == solo_text

        summary = gps.generate(target, pps.SetupAnswers(dbt=True, process_tier="standard"))
        assert summary["working_agreement_written"] is True
        assert "reversed a recognised prior Solo choice" in summary["working_agreement_reason"]
        with open(gps._KIT_WORKING_AGREEMENT, encoding="utf-8") as f:
            standard_text = f.read()
        with open(wa_path, encoding="utf-8") as f:
            assert f.read() == standard_text


def test_generate_fills_in_a_missing_working_agreement_both_tiers():
    # round 6's finding: the current_working_agreement is None branch
    # (Standard fills in a genuinely missing file) had no test at all —
    # reachable in practice since _require_bootstrapped only requires
    # .claude/settings.json, not working-agreement.md, to exist
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        wa_path = os.path.join(target, ".claude", "working-agreement.md")
        os.remove(wa_path)

        summary = gps.generate(target, pps.SetupAnswers(dbt=True))
        assert summary["working_agreement_written"] is True
        assert "missing" in summary["working_agreement_reason"]
        with open(gps._KIT_WORKING_AGREEMENT, encoding="utf-8") as f:
            standard_text = f.read()
        with open(wa_path, encoding="utf-8") as f:
            assert f.read() == standard_text

        os.remove(wa_path)
        summary = gps.generate(target, pps.SetupAnswers(dbt=True, process_tier="solo"))
        assert summary["working_agreement_written"] is True
        # round 7's finding: solo's reason didn't distinguish "filled a
        # genuinely missing file" from "converted existing content" — both
        # said "converted", falsely implying a conversion of something that
        # never existed
        assert "missing" in summary["working_agreement_reason"]
        with open(gps._SOLO_WORKING_AGREEMENT_TMPL, encoding="utf-8") as f:
            solo_text = f.read()
        with open(wa_path, encoding="utf-8") as f:
            assert f.read() == solo_text


def test_load_known_working_agreement_digests_refuses_loudly_on_a_broken_file():
    # a missing/malformed shipped digests file must GenerationRefused, like
    # every other content problem in this file — not crash with a bare
    # exception, and not silently treat every file as unrecognised or (worse)
    # every file as recognised
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        missing = os.path.join(tmp, "does-not-exist.json")
        try:
            gps._load_known_working_agreement_digests(missing)
            assert False, "expected GenerationRefused for a missing file"
        except gps.GenerationRefused:
            pass

        not_json = os.path.join(tmp, "not-json.json")
        with open(not_json, "w", encoding="utf-8") as f:
            f.write("not valid json {{{")
        try:
            gps._load_known_working_agreement_digests(not_json)
            assert False, "expected GenerationRefused for malformed JSON"
        except gps.GenerationRefused:
            pass

        wrong_shape = os.path.join(tmp, "wrong-shape.json")
        with open(wrong_shape, "w", encoding="utf-8") as f:
            json.dump({"digests": ["not", "a", "map"]}, f)
        try:
            gps._load_known_working_agreement_digests(wrong_shape)
            assert False, "expected GenerationRefused for a non-dict digests value"
        except gps.GenerationRefused:
            pass

        no_digests_key = os.path.join(tmp, "no-key.json")
        with open(no_digests_key, "w", encoding="utf-8") as f:
            json.dump({"oops": {}}, f)
        try:
            gps._load_known_working_agreement_digests(no_digests_key)
            assert False, "expected GenerationRefused for a missing 'digests' key"
        except gps.GenerationRefused:
            pass

        # round 6's finding: a typo'd tier value (e.g. "Solo"/"std") must be
        # rejected here, not silently become a fourth _working_agreement_tier
        # value that could make write_working_agreement and its own
        # reported reason disagree
        bad_tier = os.path.join(tmp, "bad-tier.json")
        with open(bad_tier, "w", encoding="utf-8") as f:
            json.dump({"digests": {"a" * 64: "Solo"}}, f)
        try:
            gps._load_known_working_agreement_digests(bad_tier)
            assert False, "expected GenerationRefused for a tier value that isn't 'standard'/'solo'"
        except gps.GenerationRefused:
            pass


def test_known_working_agreement_digests_lists_both_current_templates():
    # the parity check: same shape as test_generated_targets_own_routing_doc_parity_test_actually_passes
    # — if either template's content changes without appending its digest, this
    # fails loudly instead of silently reintroducing round 1-3's version-skew bugs
    _require_env()
    digests = gps._load_known_working_agreement_digests()
    with open(gps._KIT_WORKING_AGREEMENT, encoding="utf-8") as f:
        standard_digest = hashlib.sha256(f.read().encode("utf-8")).hexdigest()
    with open(gps._SOLO_WORKING_AGREEMENT_TMPL, encoding="utf-8") as f:
        solo_digest = hashlib.sha256(f.read().encode("utf-8")).hexdigest()
    assert digests.get(standard_digest) == "standard", (
        ".claude/working-agreement.md changed without appending its new digest "
        "to templates/known-working-agreement-digests.json")
    assert digests.get(solo_digest) == "solo", (
        "templates/working-agreement-solo.md.tmpl changed without appending "
        "its new digest to templates/known-working-agreement-digests.json")


def test_working_agreement_tier_recognises_an_older_released_default():
    # a digest list has no version-skew problem BY CONSTRUCTION: an older
    # released default's digest, once appended, is recognised forever,
    # regardless of git history, clone depth, or bootstrap/kit-version timing
    # — the whole bug class rounds 1 and 3 found in the git-reconstruction
    # approach
    _require_env()
    older_content = "# Working agreement (older released default)\nolder rules\n"
    older_digest = hashlib.sha256(older_content.encode("utf-8")).hexdigest()
    digests = {older_digest: "standard"}
    assert gps._working_agreement_tier(older_content, digests=digests) == "standard"
    assert gps._working_agreement_tier("never released this text", digests=digests) is None


def test_working_agreement_not_flagged_hand_customized_for_an_older_released_default():
    # end-to-end through generate() itself, with a FABRICATED digest map
    # containing the historical entry — not just the unit-level lookup —
    # so this would actually fail if generate() stopped honouring an
    # injected digests parameter (round 4's review caught the first version
    # of this test asserting only the tautological unit-level lookup, then
    # calling generate() against the REAL digest list where the content was
    # unrecognised, so it passed for the wrong reason)
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        older_content = "# Working agreement (older released default)\nolder rules\n"
        older_digest = hashlib.sha256(older_content.encode("utf-8")).hexdigest()
        wa_path = os.path.join(target, ".claude", "working-agreement.md")
        with open(wa_path, "w", encoding="utf-8") as f:
            f.write(older_content)
        fake_digests = {older_digest: "standard"}

        # Standard tier must NOT touch an already-standard file, whatever vintage
        summary = gps.generate(target, pps.SetupAnswers(dbt=True),
                                working_agreement_digests=fake_digests)
        assert summary["working_agreement_written"] is False
        with open(wa_path, encoding="utf-8") as f:
            assert f.read() == older_content, (
                "standard tier must leave an already-standard file untouched, "
                "never opportunistically rewrite it")

        # and it must not have been wrongly REFUSED as hand-customized either
        # (that's the Solo-tier path's own gate, exercised here for the same
        # historical entry)
        summary = gps.generate(target, pps.SetupAnswers(dbt=True, process_tier="solo"),
                                working_agreement_digests=fake_digests)
        assert summary["working_agreement_written"] is True


def test_force_does_not_let_standard_tier_overwrite_a_recognised_older_vintage():
    # round 5's finding: round 4's fix (force only overrides an UNRECOGNISED
    # file) had no test that would fail if reverted to the broader `or
    # force` — every existing force+standard test used either an
    # unrecognised file or one byte-identical to the CURRENT kit default, so
    # a spuriously-broad revert would go undetected. This constructs exactly
    # the state the fix protects: a RECOGNISED older-standard-vintage file,
    # different from today's default, with force=True.
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        older_content = "# Working agreement (older released default)\nolder rules\n"
        older_digest = hashlib.sha256(older_content.encode("utf-8")).hexdigest()
        wa_path = os.path.join(target, ".claude", "working-agreement.md")
        with open(wa_path, "w", encoding="utf-8") as f:
            f.write(older_content)
        fake_digests = {older_digest: "standard"}

        summary = gps.generate(target, pps.SetupAnswers(dbt=True), force=True,
                                working_agreement_digests=fake_digests)
        assert summary["working_agreement_written"] is False, (
            "force must never let Standard tier overwrite a RECOGNISED "
            "older-standard-vintage file — only an unrecognised one")
        assert "recognised standard file" in summary["working_agreement_reason"]
        with open(wa_path, encoding="utf-8") as f:
            assert f.read() == older_content


def test_standard_tier_recognises_an_older_released_solo_default_as_a_prior_choice():
    # round 3's finding #3, mirrored: Standard's "was this a prior Solo
    # choice?" check must recognise ANY released Solo vintage, not just the
    # CURRENT solo template — otherwise editing that template silently
    # strands old-Solo targets on Standard's "leave it alone" path. Driven
    # through generate() itself with an injected digest map, not just the
    # unit-level lookup (see the comment on the sibling test above for why
    # that distinction matters).
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        older_solo_text = "# Working agreement (older solo revision)\nolder solo rules\n"
        older_solo_digest = hashlib.sha256(older_solo_text.encode("utf-8")).hexdigest()
        wa_path = os.path.join(target, ".claude", "working-agreement.md")
        with open(wa_path, "w", encoding="utf-8") as f:
            f.write(older_solo_text)
        fake_digests = {older_solo_digest: "solo"}

        summary = gps.generate(target, pps.SetupAnswers(dbt=True),
                                working_agreement_digests=fake_digests)
        assert summary["working_agreement_written"] is True, (
            "an older released Solo default must be recognised and reversed "
            "by Standard tier, not just the CURRENT solo template")
        with open(gps._KIT_WORKING_AGREEMENT, encoding="utf-8") as f:
            standard_text = f.read()
        with open(wa_path, encoding="utf-8") as f:
            assert f.read() == standard_text


def test_force_lets_standard_tier_overwrite_a_hand_customized_working_agreement():
    # round 3's finding #2: --help and SKILL.md both document force as
    # applying to working-agreement.md in EITHER tier, but the Standard
    # write path never actually checked force — a silent no-op with no
    # escape hatch
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        wa_path = os.path.join(target, ".claude", "working-agreement.md")
        with open(wa_path, "w", encoding="utf-8") as f:
            f.write("hand-written process notes\n")

        # without force: standard tier is a documented no-op on a customized file
        summary = gps.generate(target, pps.SetupAnswers(dbt=True))
        assert summary["working_agreement_written"] is False
        assert "force wasn't given" in summary["working_agreement_reason"]
        with open(wa_path, encoding="utf-8") as f:
            assert f.read() == "hand-written process notes\n"

        # force=True must actually restore the standard default
        summary = gps.generate(target, pps.SetupAnswers(dbt=True), force=True)
        assert summary["working_agreement_written"] is True
        assert "force-overwrote" in summary["working_agreement_reason"]
        with open(gps._KIT_WORKING_AGREEMENT, encoding="utf-8") as f:
            standard_text = f.read()
        with open(wa_path, encoding="utf-8") as f:
            assert f.read() == standard_text


def test_generate_refuses_an_unrecognised_process_tier():
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        try:
            gps.generate(target, pps.SetupAnswers(dbt=True, process_tier="bogus"))
            assert False, "expected GenerationRefused, not a silent default or a KeyError"
        except gps.GenerationRefused:
            pass


def test_generate_refuses_an_unrecognised_tracker_provider():
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        try:
            gps.generate(target, pps.SetupAnswers(dbt=True, tracker_provider="bogus"))
            assert False, "expected GenerationRefused, not a bare KeyError"
        except gps.GenerationRefused:
            pass


def test_generate_refuses_an_unrecognised_ci_provider():
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        try:
            gps.generate(target, pps.SetupAnswers(dbt=True, ci_provider="bogus"))
            assert False, "expected GenerationRefused, not a bare KeyError"
        except gps.GenerationRefused:
            pass


def _session_start_hooks(target: str) -> list[dict]:
    with open(os.path.join(target, ".claude", "settings.json"), encoding="utf-8") as f:
        data = json.load(f)
    return data["hooks"]["SessionStart"][0]["hooks"]


def test_ci_audit_hook_installed_and_wired_when_ci_provider_given():
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        summary = gps.generate(target, pps.SetupAnswers(dbt=True, ci_provider="gitlab"))
        assert summary["ci_audit_hook_installed"] is True
        assert summary["ci_audit_hook_wired"] is True
        assert summary["ci_audit_hook_reason"] == "installed and wired into settings.json"
        hook_path = os.path.join(target, ".claude", "hooks", "ci_automation_audit.py")
        assert os.path.isfile(hook_path)
        with open(gps._CI_AUDIT_HOOK_TMPL, encoding="utf-8") as f:
            expected = f.read()
        with open(hook_path, encoding="utf-8") as f:
            assert f.read() == expected
        commands = [h["command"] for h in _session_start_hooks(target)]
        assert any("ci_automation_audit.py" in c for c in commands)


def test_ci_audit_hook_not_installed_when_ci_provider_is_none():
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        summary = gps.generate(target, pps.SetupAnswers(dbt=True))  # ci_provider default "none"
        assert summary["ci_audit_hook_installed"] is False
        assert summary["ci_audit_hook_wired"] is False
        assert summary["ci_audit_hook_reason"] == "no CI provider given — hook not installed"
        assert not os.path.isfile(
            os.path.join(target, ".claude", "hooks", "ci_automation_audit.py"))
        commands = [h["command"] for h in _session_start_hooks(target)]
        assert not any("ci_automation_audit.py" in c for c in commands)


def test_ci_audit_hook_wiring_is_idempotent_on_a_second_run():
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        gps.generate(target, pps.SetupAnswers(dbt=True, ci_provider="github"))
        first_commands = [h["command"] for h in _session_start_hooks(target)]
        summary2 = gps.generate(target, pps.SetupAnswers(dbt=True, ci_provider="github"))
        assert summary2["ci_audit_hook_wired"] is False, (
            "an already-wired entry must not be duplicated on a second run")
        assert summary2["ci_audit_hook_installed"] is True, (
            "the hook FILE is still refreshed on every run, like reviewer modules")
        assert summary2["ci_audit_hook_reason"] == (
            "already wired (a prior run or a hand-edit already added the entry)")
        second_commands = [h["command"] for h in _session_start_hooks(target)]
        assert first_commands == second_commands
        assert sum("ci_automation_audit.py" in c for c in second_commands) == 1


def test_ci_audit_hook_left_alone_if_already_hand_wired():
    # simulates a project owner who already wired the hook by hand before
    # ever running /setup-project with a ci_provider answer
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        settings_path = os.path.join(target, ".claude", "settings.json")
        with open(settings_path, encoding="utf-8") as f:
            data = json.load(f)
        data["hooks"]["SessionStart"][0]["hooks"].append({
            "type": "command", "shell": "bash",
            "command": 'python "${CLAUDE_PROJECT_DIR}/.claude/hooks/ci_automation_audit.py"',
            "statusMessage": "hand-wired already",
        })
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        before_hooks = _session_start_hooks(target)

        summary = gps.generate(target, pps.SetupAnswers(dbt=True, ci_provider="gitlab"))
        assert summary["ci_audit_hook_wired"] is False
        assert summary["ci_audit_hook_reason"] == (
            "already wired (a prior run or a hand-edit already added the entry)")
        assert _session_start_hooks(target) == before_hooks


def test_ci_audit_hook_scan_tolerates_oddly_shaped_later_session_start_groups():
    # the duplicate scan walks EVERY SessionStart group, but only the first
    # is shape-validated — a project-owned settings.json with a later group
    # that isn't a dict, or whose "hooks" isn't a list, must be skipped, not
    # crash (the function's own docstring promises it never crashes)
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        settings_path = os.path.join(target, ".claude", "settings.json")
        with open(settings_path, encoding="utf-8") as f:
            data = json.load(f)
        data["hooks"]["SessionStart"].append("not-a-dict")
        data["hooks"]["SessionStart"].append({"hooks": "not-a-list"})
        data["hooks"]["SessionStart"].append({"hooks": ["not-a-dict-entry"]})
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        summary = gps.generate(target, pps.SetupAnswers(dbt=True, ci_provider="github"))
        assert summary["ci_audit_hook_wired"] is True
        with open(settings_path, encoding="utf-8") as f:
            after = json.load(f)
        # appended to the validated first group; the odd later groups survive untouched
        assert any("ci_automation_audit.py" in h["command"]
                   for h in after["hooks"]["SessionStart"][0]["hooks"])
        assert after["hooks"]["SessionStart"][1:] == data["hooks"]["SessionStart"][1:]


def test_ci_audit_hook_refuses_on_malformed_settings_json_writing_nothing():
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        settings_path = os.path.join(target, ".claude", "settings.json")
        with open(settings_path, "w", encoding="utf-8") as f:
            f.write('{"hooks": {}}')  # no SessionStart at all
        before = _repo_snapshot(target)

        try:
            gps.generate(target, pps.SetupAnswers(dbt=True, ci_provider="gitlab"))
            assert False, "expected GenerationRefused"
        except gps.GenerationRefused as e:
            assert "--ci-provider none" in str(e), (
                "the refusal must tell the user how to get unstuck, not just what's wrong")
        after = _repo_snapshot(target)
        assert before == after, "a refused generation must write nothing at all"


def test_ci_audit_hook_refuses_every_malformed_settings_shape_writing_nothing():
    # one case per refusal branch in _prepare_ci_audit_hook_settings — the
    # sibling test above covers only "no SessionStart key"; reverting any one
    # clause (e.g. the JSONDecodeError catch) would otherwise surface as a
    # raw traceback instead of a GenerationRefused carrying the remedy
    _require_env()
    shapes = {
        "not json at all": "{not json",
        "valid json, top level not an object": '[{"hooks": {}}]',
        "valid json, top level null": "null",
        "hooks not a dict": '{"hooks": []}',
        "SessionStart empty": '{"hooks": {"SessionStart": []}}',
        "SessionStart not a list": '{"hooks": {"SessionStart": {"hooks": []}}}',
        "first group hooks not a list": '{"hooks": {"SessionStart": [{"hooks": "x"}]}}',
        "first group not a dict": '{"hooks": {"SessionStart": ["x"]}}',
    }
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        settings_path = os.path.join(target, ".claude", "settings.json")
        for label, content in shapes.items():
            with open(settings_path, "w", encoding="utf-8") as f:
                f.write(content)
            before = _repo_snapshot(target)
            try:
                gps.generate(target, pps.SetupAnswers(dbt=True, ci_provider="github"))
                assert False, f"{label}: expected GenerationRefused"
            except gps.GenerationRefused as e:
                assert "--ci-provider none" in str(e), label
            assert _repo_snapshot(target) == before, f"{label}: wrote something"
        # Not UTF-8 at all — UTF-16 with a BOM is what PowerShell 5.1's
        # Out-File writes by default, so it's a realistic Windows artefact,
        # and it raises UnicodeDecodeError (a ValueError, NOT a
        # JSONDecodeError) before json.load ever sees a token
        with open(settings_path, "wb") as f:
            f.write('{"hooks": {"SessionStart": [{"hooks": []}]}}'.encode("utf-16"))
        before = _repo_snapshot(target)
        try:
            gps.generate(target, pps.SetupAnswers(dbt=True, ci_provider="github"))
            assert False, "utf-16 settings.json: expected GenerationRefused"
        except gps.GenerationRefused as e:
            assert "--ci-provider none" in str(e)
        assert _repo_snapshot(target) == before, "utf-16: wrote something"
        # The OSError half of the first clause can't be reached through
        # generate() with a MISSING file — _require_bootstrapped refuses on
        # that first — so drive the function directly: a nonexistent path is
        # the one OSError reproducible on every OS without permission games
        try:
            gps._prepare_ci_audit_hook_settings(os.path.join(tmp, "does-not-exist.json"))
            assert False, "unreadable settings.json: expected GenerationRefused"
        except gps.GenerationRefused as e:
            assert "--ci-provider none" in str(e)


def test_ci_audit_hook_splice_preserves_non_ascii_in_project_owned_settings():
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        settings_path = os.path.join(target, ".claude", "settings.json")
        with open(settings_path, encoding="utf-8") as f:
            data = json.load(f)
        data["hooks"]["SessionStart"][0]["hooks"][0]["statusMessage"] = "Prüfe Python…"
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        gps.generate(target, pps.SetupAnswers(dbt=True, ci_provider="github"))
        with open(settings_path, encoding="utf-8") as f:
            raw = f.read()
        assert "Prüfe Python…" in raw, "the owner's own text must round-trip, not become \\uXXXX"


def test_ci_audit_hook_actually_fires_end_to_end_from_the_generated_target():
    # not just "the file exists" — proves the copied hook actually runs and
    # emits its advisory note, the same technique smoke_test() uses for
    # commit_review_gate.py
    _require_env()
    with tempfile.TemporaryDirectory() as tmp:
        target = _bootstrapped_target(tmp)
        gps.generate(target, pps.SetupAnswers(dbt=True, ci_provider="github"))
        workflows_dir = os.path.join(target, ".github", "workflows")
        os.makedirs(workflows_dir, exist_ok=True)
        with open(os.path.join(workflows_dir, "auto-merge.yml"), "w", encoding="utf-8") as f:
            f.write(
                "on:\n  schedule:\n    - cron: '0 0 * * *'\n"
                "jobs:\n  merge:\n    steps:\n      - run: gh pr merge --auto\n")
        hook_path = os.path.join(target, ".claude", "hooks", "ci_automation_audit.py")
        env = dict(os.environ, CLAUDE_PROJECT_DIR=target)
        proc = subprocess.run([sys.executable, hook_path], input="{}", text=True,
                               capture_output=True, cwd=target, env=env, timeout=30)
        assert proc.returncode == 0
        assert "CI-AUTOMATION AUDIT" in proc.stdout

        # and silent when there's nothing to flag
        os.remove(os.path.join(workflows_dir, "auto-merge.yml"))
        proc2 = subprocess.run([sys.executable, hook_path], input="{}", text=True,
                                capture_output=True, cwd=target, env=env, timeout=30)
        assert proc2.returncode == 0
        assert proc2.stdout.strip() == ""


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
