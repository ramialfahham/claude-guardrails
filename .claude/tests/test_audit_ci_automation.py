"""Tests for scripts/audit_ci_automation.py and its SessionStart hook
template counterpart.

Runnable with `pytest` or directly: `python .claude/tests/test_audit_ci_automation.py`.
"""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

_GIT = shutil.which("git")

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_CLAUDE_DIR = os.path.dirname(_TESTS_DIR)
_REPO_ROOT = os.path.dirname(_CLAUDE_DIR)
_SCRIPTS_DIR = os.path.join(_REPO_ROOT, "scripts")
_TEMPLATE_DIR = os.path.join(_REPO_ROOT, "templates", "ci-audit")
_SCRIPT_FILE = os.path.join(_SCRIPTS_DIR, "audit_ci_automation.py")
_TEMPLATE_FILE = os.path.join(_TEMPLATE_DIR, "ci_automation_audit.py")

# scripts/ and templates/ are NOT part of what scripts/bootstrap.sh copies
# into a consumer repo (only .claude/{hooks,agents,commands,skills,tests} —
# see bootstrap.sh's refresh_dir calls) — a bootstrapped repo gets this test
# file but neither module it imports. A bare top-level import would raise
# ModuleNotFoundError before any test or the __main__ handler below runs,
# breaking CI in every consumer repo. Same class of defect already fixed
# once in this repo for test_routing_doc_parity.py; same fix here: guard,
# then skip cleanly per-test with unittest.SkipTest (recognized by both the
# __main__ runner below and pytest).
_HAVE_SCRIPT = os.path.isfile(_SCRIPT_FILE)
_HAVE_TEMPLATE = os.path.isfile(_TEMPLATE_FILE)
_SCRIPT_UNAVAILABLE = None if _HAVE_SCRIPT else (
    "scripts/audit_ci_automation.py not present (a bootstrapped repo, not the kit)")
_TEMPLATE_UNAVAILABLE = None if _HAVE_TEMPLATE else (
    "templates/ci-audit/ci_automation_audit.py not present (a bootstrapped repo, not the kit)")

aca = None
tmpl = None
if _HAVE_SCRIPT:
    sys.path.insert(0, _SCRIPTS_DIR)
    import audit_ci_automation as aca  # noqa: E402
if _HAVE_TEMPLATE:
    sys.path.insert(0, _TEMPLATE_DIR)
    import ci_automation_audit as tmpl  # noqa: E402

# The actual shape of the real incident: a scheduled workflow that
# auto-merges. Structural reproduction only, no repo-specific detail.
_DANGEROUS_WORKFLOW = """\
name: pr-autopilot
on:
  schedule:
    - cron: '0 * * * *'
jobs:
  autopilot:
    runs-on: ubuntu-latest
    steps:
      - run: gh pr merge --auto --squash "$PR"
"""

_SAFE_SCHEDULE_ONLY = """\
name: nightly-report
on:
  schedule:
    - cron: '0 6 * * *'
jobs:
  report:
    runs-on: ubuntu-latest
    steps:
      - run: python generate_report.py
"""

_SAFE_MERGE_ONLY = """\
name: notify
on:
  pull_request:
    types: [closed]
jobs:
  notify:
    runs-on: ubuntu-latest
    steps:
      - run: echo "a human merged this, we are just logging it, automerge"
"""

_GITLAB_SCHEDULE_AUTOMERGE = """\
workflow:
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"
autopilot:
  script:
    - glab mr merge $CI_MERGE_REQUEST_IID
"""

# The real cry-wolf trap: a dispatchable workflow that only ever MENTIONS
# auto-merge to disclaim it. An earlier pattern list matched the bare word
# "auto-merge" anywhere (case-insensitive), which would have flagged this.
_DISPATCH_WITH_AUTOMERGE_DISCLAIMER = """\
name: build
on:
  workflow_dispatch:
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      # we deliberately do NOT auto-merge here, a human always approves
      - run: make build
"""

# The actual Octokit/github-script incident shape this repo's earlier
# pattern list had no coverage for at all.
_DISPATCH_WITH_OCTOKIT_MERGE = """\
name: pr-autopilot-js
on:
  workflow_dispatch:
jobs:
  autopilot:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/github-script@v7
        with:
          script: |
            await github.rest.pulls.merge({owner, repo, pull_number});
"""

# repository_dispatch is an externally-poked trigger (a webhook/API call
# fires it) — the closest cousin of the real incident's own trigger shape,
# and was missing from the trigger pattern list entirely.
_REPOSITORY_DISPATCH_AUTOMERGE = """\
name: external-autopilot
on:
  repository_dispatch:
    types: [merge-ready]
jobs:
  autopilot:
    runs-on: ubuntu-latest
    steps:
      - run: gh pr merge --auto --squash "$PR"
"""


def _require_script():
    if _SCRIPT_UNAVAILABLE:
        raise unittest.SkipTest(_SCRIPT_UNAVAILABLE)


def _require_template():
    if _TEMPLATE_UNAVAILABLE:
        raise unittest.SkipTest(_TEMPLATE_UNAVAILABLE)


def _require_git():
    if not _GIT:
        raise unittest.SkipTest("no git on PATH")


def _git(repo, *args):
    # Matches this repo's own established pattern
    # (.claude/tests/test_commit_review_gate.py's `_git` helper) rather
    # than reinventing one — `timeout=` bounds a wedged git call, and
    # `check=True` surfaces a real git failure as a normal exception inside
    # the caller's own `with tempfile.TemporaryDirectory()` block, where
    # __main__'s per-test try/except (or pytest) reports just that one
    # test's failure instead of leaking a directory and aborting the file.
    subprocess.run([_GIT, *args], cwd=repo, check=True, capture_output=True, timeout=30)


def _add_remotes(repo: str, remotes: dict) -> None:
    """Configures the given {name: url} remotes in an already-`git init`'d
    repo — exercises the actual `git` subprocess calls `_detect_remotes`
    shells out to, which had ZERO test coverage before this (it's the sole
    input to `--strict` on the default, no-`--slug` invocation — the
    tool's primary documented usage)."""
    for name, url in remotes.items():
        _git(repo, "remote", "add", name, url)


def _write(directory: str, rel_path: str, content: str) -> str:
    path = os.path.join(directory, rel_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def _run_script(argv: list[str], repo_root: str = _REPO_ROOT) -> tuple[int, str]:
    """Invoke aca.main() in-process (argparse errors call sys.exit(2), a
    real script invocation would too) — avoids a subprocess round-trip."""
    buf = io.StringIO()
    old_argv = sys.argv
    sys.argv = ["audit_ci_automation.py", "--repo-root", repo_root] + argv
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                code = aca.main()
            except SystemExit as e:
                code = e.code
    finally:
        sys.argv = old_argv
    return code, buf.getvalue()


def test_flags_the_actual_incident_shape():
    _require_script()
    with tempfile.TemporaryDirectory() as repo:
        _write(repo, ".github/workflows/pr-autopilot.yml", _DANGEROUS_WORKFLOW)
        findings = aca.scan_repo(repo)
        assert len(findings) == 1
        assert "GitHub schedule trigger" in findings[0]["triggers"]
        assert any("gh pr merge" in a for a in findings[0]["actions"])


def test_gitlab_shape_is_also_flagged():
    _require_script()
    with tempfile.TemporaryDirectory() as repo:
        _write(repo, ".gitlab-ci.yml", _GITLAB_SCHEDULE_AUTOMERGE)
        findings = aca.scan_repo(repo)
        assert len(findings) == 1
        assert "GitLab schedule pipeline source" in findings[0]["triggers"]


def test_schedule_alone_is_not_flagged():
    _require_script()
    with tempfile.TemporaryDirectory() as repo:
        _write(repo, ".github/workflows/nightly.yml", _SAFE_SCHEDULE_ONLY)
        assert aca.scan_repo(repo) == []


def test_merge_mention_alone_is_not_flagged():
    _require_script()
    with tempfile.TemporaryDirectory() as repo:
        _write(repo, ".github/workflows/notify.yml", _SAFE_MERGE_ONLY)
        assert aca.scan_repo(repo) == []


def test_dispatch_with_automerge_disclaimer_is_not_flagged():
    # the actual cry-wolf case: a comment disclaiming auto-merge, combined
    # with the very common workflow_dispatch trigger, must NOT fire
    _require_script()
    with tempfile.TemporaryDirectory() as repo:
        _write(repo, ".github/workflows/build.yml", _DISPATCH_WITH_AUTOMERGE_DISCLAIMER)
        assert aca.scan_repo(repo) == []


def test_octokit_pulls_merge_is_flagged():
    _require_script()
    with tempfile.TemporaryDirectory() as repo:
        _write(repo, ".github/workflows/pr-autopilot-js.yml", _DISPATCH_WITH_OCTOKIT_MERGE)
        findings = aca.scan_repo(repo)
        assert len(findings) == 1
        assert any("pulls.merge" in a for a in findings[0]["actions"])


def test_repository_dispatch_trigger_is_flagged():
    _require_script()
    with tempfile.TemporaryDirectory() as repo:
        _write(repo, ".github/workflows/external-autopilot.yml", _REPOSITORY_DISPATCH_AUTOMERGE)
        findings = aca.scan_repo(repo)
        assert len(findings) == 1
        assert "GitHub repository_dispatch trigger" in findings[0]["triggers"]


def test_this_repos_own_real_workflows_are_not_flagged():
    # a scanner that cries wolf on ordinary CI is worse than no scanner.
    # _require_script() is what actually keeps this a KIT-only assertion:
    # scripts/audit_ci_automation.py never lands in a bootstrapped repo (see
    # the module-level comment), so this test skips there instead of
    # asserting a consumer project's own CI is clean — which would be an
    # unsilenceable false failure for any consumer with a legitimate
    # scheduled auto-merge workflow.
    _require_script()
    findings = aca.scan_repo(_REPO_ROOT)
    assert findings == [], f"unexpected findings against this repo's own CI: {findings}"


def test_branch_protection_check_degrades_cleanly_without_the_cli():
    _require_script()
    original_which = aca._which
    aca._which = lambda cli: None  # simulate: neither gh nor glab installed
    try:
        gh_result = aca.check_branch_protection_github("owner/repo")
        gl_result = aca.check_branch_protection_gitlab("owner/repo")
    finally:
        aca._which = original_which
    assert gh_result == {"available": False, "reason": "gh CLI not installed"}
    assert gl_result == {"available": False, "reason": "glab CLI not installed"}


def test_http_status_extracts_code_from_stderr():
    _require_script()
    assert aca._http_status("gh: HTTP 403: Must have admin rights") == 403
    assert aca._http_status("gh: Branch not protected (HTTP 404)") == 404
    assert aca._http_status("connection timed out") is None


def test_repo_info_fetch_failure_skips_protection_check_without_guessing_branch():
    # an earlier version guessed default_branch="main" when this call
    # failed, then queried branches/main/protection — a 404 there (wrong
    # branch name) is indistinguishable from "branch not protected",
    # falsely clearing a repo whose real default branch is master/develop
    _require_script()

    def fake_run(args):
        if args[:2] == ["gh", "auth"]:
            return 0, "", ""
        if args[-1] == "repos/owner/repo":
            return 1, "", "gh: HTTP 403: API rate limit exceeded"
        raise AssertionError(f"unexpected _run call: {args}")

    original_which, original_run = aca._which, aca._run
    aca._which = lambda cli: "/usr/bin/gh"
    aca._run = fake_run
    try:
        result = aca.check_branch_protection_github("owner/repo")
    finally:
        aca._which, aca._run = original_which, original_run
    assert "repo_check_error" in result
    assert "branch_protected" not in result


def test_strict_exits_nonzero_on_the_actual_incident_shape():
    # the primary --strict trip condition: a static-scan finding. Every
    # other --strict test runs against an empty tempdir (findings always
    # []), so the one path this whole tool exists to catch — a real
    # dangerous workflow making --strict fail closed — had no dedicated
    # proof; `flagged = True` on a finding could be deleted and every other
    # test would still pass.
    _require_script()
    with tempfile.TemporaryDirectory() as repo:
        _write(repo, ".github/workflows/pr-autopilot.yml", _DANGEROUS_WORKFLOW)
        code, _ = _run_script(["--no-live", "--strict"], repo_root=repo)
    assert code == 1


def test_dangerous_finding_without_strict_still_exits_zero():
    # the "advisory by default" promise in the module docstring/usage text
    _require_script()
    with tempfile.TemporaryDirectory() as repo:
        _write(repo, ".github/workflows/pr-autopilot.yml", _DANGEROUS_WORKFLOW)
        code, _ = _run_script(["--no-live"], repo_root=repo)
    assert code == 0


def test_strict_flags_on_a_genuinely_unprotected_github_branch():
    # a clean tempdir root, not this repo's own — an exit-code assertion
    # here must depend only on the monkeypatched result, not on this
    # repo's real workflows staying clean
    _require_script()
    original = aca.check_branch_protection_github
    aca.check_branch_protection_github = lambda slug: {
        "available": True, "provider": "github", "branch_protected": False}
    try:
        with tempfile.TemporaryDirectory() as repo:
            code, _ = _run_script(
                ["--slug", "acme/widgets", "--provider", "github", "--strict"], repo_root=repo)
    finally:
        aca.check_branch_protection_github = original
    assert code == 1


def test_strict_does_not_flag_on_an_unverifiable_check():
    # "couldn't verify" (typically a non-admin CI token, the common case)
    # must not cry wolf under --strict
    _require_script()
    original = aca.check_branch_protection_github
    aca.check_branch_protection_github = lambda slug: {
        "available": True, "provider": "github",
        "branch_protection_check_error": "could not verify"}
    try:
        with tempfile.TemporaryDirectory() as repo:
            code, _ = _run_script(
                ["--slug", "acme/widgets", "--provider", "github", "--strict"], repo_root=repo)
    finally:
        aca.check_branch_protection_github = original
    assert code == 0


def test_strict_flags_on_gitlab_merge_without_pipeline_success():
    _require_script()
    original = aca.check_branch_protection_gitlab
    aca.check_branch_protection_gitlab = lambda slug: {
        "available": True, "provider": "gitlab",
        "only_allow_merge_if_pipeline_succeeds": False}
    try:
        with tempfile.TemporaryDirectory() as repo:
            code, _ = _run_script(
                ["--slug", "acme/widgets", "--provider", "gitlab", "--strict"], repo_root=repo)
    finally:
        aca.check_branch_protection_gitlab = original
    assert code == 1


def test_strict_flags_on_a_genuinely_unprotected_gitlab_branch():
    _require_script()
    original = aca.check_branch_protection_gitlab
    aca.check_branch_protection_gitlab = lambda slug: {
        "available": True, "provider": "gitlab", "branch_protected": False}
    try:
        with tempfile.TemporaryDirectory() as repo:
            code, _ = _run_script(
                ["--slug", "acme/widgets", "--provider", "gitlab", "--strict"], repo_root=repo)
    finally:
        aca.check_branch_protection_gitlab = original
    assert code == 1


def test_gitlab_branch_protection_success_via_exact_name_rule():
    _require_script()

    def fake_run(args):
        if args[:2] == ["glab", "auth"]:
            return 0, "", ""
        if "/protected_branches" in args[-1]:
            return 0, '[{"name": "main"}]', ""
        return 0, ('{"default_branch": "main", '
                    '"only_allow_merge_if_pipeline_succeeds": true}'), ""

    original_which, original_run = aca._which, aca._run
    aca._which = lambda cli: "/usr/bin/glab"
    aca._run = fake_run
    try:
        result = aca.check_branch_protection_gitlab("group/project")
    finally:
        aca._which, aca._run = original_which, original_run
    assert result["branch_protected"] is True
    assert result["only_allow_merge_if_pipeline_succeeds"] is True


def test_gitlab_branch_protection_success_via_wildcard_rule():
    # a default branch protected only via a WILDCARD rule (no rule
    # literally named "main") must still be reported protected — a by-name
    # lookup would 404 here
    _require_script()

    def fake_run(args):
        if args[:2] == ["glab", "auth"]:
            return 0, "", ""
        if "/protected_branches" in args[-1]:
            return 0, '[{"name": "ma*"}]', ""
        return 0, '{"default_branch": "main"}', ""

    original_which, original_run = aca._which, aca._run
    aca._which = lambda cli: "/usr/bin/glab"
    aca._run = fake_run
    try:
        result = aca.check_branch_protection_gitlab("group/project")
    finally:
        aca._which, aca._run = original_which, original_run
    assert result["branch_protected"] is True


def test_gitlab_wildcard_match_is_case_sensitive():
    # fnmatch.fnmatch calls os.path.normcase, which lowercases on Windows
    # but is a no-op on POSIX — so a plain "Main" vs "main" test would only
    # ever catch a fnmatch.fnmatch regression on Windows, and both this
    # repo's CI runners are Linux (.github/workflows/ci.yml, .gitlab-ci.yml
    # both run on Linux). A test that passes identically on the correct
    # code AND the bug, everywhere it actually runs, isn't a pin. FIXED by
    # forcing the Windows-shaped normalization here regardless of host OS:
    # fnmatch.fnmatchcase (what the code must use) never calls normcase at
    # all, so it stays case-sensitive even under this patch; fnmatch.fnmatch
    # would not — this discriminates on every platform, not just Windows.
    _require_script()

    def fake_run(args):
        if args[:2] == ["glab", "auth"]:
            return 0, "", ""
        if "/protected_branches" in args[-1]:
            return 0, '[{"name": "Main"}]', ""
        return 0, '{"default_branch": "main"}', ""

    original_which, original_run = aca._which, aca._run
    original_normcase = os.path.normcase
    aca._which = lambda cli: "/usr/bin/glab"
    aca._run = fake_run
    os.path.normcase = str.lower
    try:
        result = aca.check_branch_protection_gitlab("group/project")
    finally:
        aca._which, aca._run = original_which, original_run
        os.path.normcase = original_normcase
    assert result["branch_protected"] is False


def test_gitlab_protected_branches_request_paginates():
    # GitLab defaults to 20 results per page and `glab api` doesn't
    # auto-paginate; a project with more protected-branch rules than that
    # could have its default-branch rule fall off the first page — request
    # a large enough page explicitly rather than trusting the default
    _require_script()
    seen_urls = []

    def fake_run(args):
        if args[:2] == ["glab", "auth"]:
            return 0, "", ""
        if "/protected_branches" in args[-1]:
            seen_urls.append(args[-1])
            return 0, "[]", ""
        return 0, '{"default_branch": "main"}', ""

    original_which, original_run = aca._which, aca._run
    aca._which = lambda cli: "/usr/bin/glab"
    aca._run = fake_run
    try:
        aca.check_branch_protection_gitlab("group/project")
    finally:
        aca._which, aca._run = original_which, original_run
    assert seen_urls and "per_page=100" in seen_urls[0], (
        f"expected a per_page parameter on the protected_branches request, got {seen_urls}")


def test_gitlab_full_page_with_no_match_is_ambiguous_not_unprotected():
    # `?per_page=100` raises the truncation threshold, it doesn't remove
    # it — a project with MORE than 100 rules could still have its
    # default-branch rule on a page this tool never fetches. A full page
    # (exactly the page-size limit) with no match must stay ambiguous;
    # only an INCOMPLETE page with no match is a genuine "checked
    # everything, found nothing".
    _require_script()

    def fake_run(args):
        if args[:2] == ["glab", "auth"]:
            return 0, "", ""
        if "/protected_branches" in args[-1]:
            rules = [{"name": f"other-{i}"} for i in range(100)]
            return 0, json.dumps(rules), ""
        return 0, '{"default_branch": "main"}', ""

    original_which, original_run = aca._which, aca._run
    aca._which = lambda cli: "/usr/bin/glab"
    aca._run = fake_run
    try:
        result = aca.check_branch_protection_gitlab("group/project")
    finally:
        aca._which, aca._run = original_which, original_run
    assert "branch_protection_check_error" in result
    assert "branch_protected" not in result


def test_gitlab_branch_protection_unparseable_response_is_ambiguous():
    # a 200 whose body isn't a JSON array must not silently resolve to
    # "confirmed unprotected" — the one place this could otherwise happen
    _require_script()

    def fake_run(args):
        if args[:2] == ["glab", "auth"]:
            return 0, "", ""
        if "/protected_branches" in args[-1]:
            return 0, "not json at all", ""
        return 0, '{"default_branch": "main"}', ""

    original_which, original_run = aca._which, aca._run
    aca._which = lambda cli: "/usr/bin/glab"
    aca._run = fake_run
    try:
        result = aca.check_branch_protection_gitlab("group/project")
    finally:
        aca._which, aca._run = original_which, original_run
    assert "branch_protection_check_error" in result
    assert "branch_protected" not in result


def test_gitlab_branch_protection_empty_rule_list_means_unprotected():
    # the list endpoint returns 200 with [] when nothing is protected —
    # this is the ONLY legitimate "unprotected" signal for this endpoint,
    # unlike a 404 (which never legitimately means that here)
    _require_script()

    def fake_run(args):
        if args[:2] == ["glab", "auth"]:
            return 0, "", ""
        if "/protected_branches" in args[-1]:
            return 0, "[]", ""
        return 0, '{"default_branch": "main"}', ""

    original_which, original_run = aca._which, aca._run
    aca._which = lambda cli: "/usr/bin/glab"
    aca._run = fake_run
    try:
        result = aca.check_branch_protection_gitlab("group/project")
    finally:
        aca._which, aca._run = original_which, original_run
    assert result["branch_protected"] is False
    assert "branch_protection_check_error" not in result


def test_gitlab_branch_protection_list_failure_is_ambiguous_not_unprotected():
    # a non-zero exit from the LIST endpoint is never a legitimate
    # "unprotected" signal (that's only ever a 200 with an empty array) —
    # any failure here must be reported as ambiguous, unconditionally,
    # regardless of HTTP status
    _require_script()

    def fake_run(args):
        if args[:2] == ["glab", "auth"]:
            return 0, "", ""
        if "/protected_branches" in args[-1]:
            return 1, "", "glab: HTTP 404: 404 Project Not Found"
        return 0, '{"default_branch": "main"}', ""

    original_which, original_run = aca._which, aca._run
    aca._which = lambda cli: "/usr/bin/glab"
    aca._run = fake_run
    try:
        result = aca.check_branch_protection_gitlab("group/project")
    finally:
        aca._which, aca._run = original_which, original_run
    assert "branch_protection_check_error" in result
    assert "branch_protected" not in result


def test_gitlab_repo_check_error_on_initial_fetch_failure():
    # an earlier version had no `else` for this failure at all: a
    # 403/404/rate-limit/network failure printed as `{"available": true,
    # ...}` with nothing saying the call failed — indistinguishable from a
    # verified-clean result
    _require_script()

    def fake_run(args):
        if args[:2] == ["glab", "auth"]:
            return 0, "", ""
        return 1, "", "glab: HTTP 403: insufficient access"

    original_which, original_run = aca._which, aca._run
    aca._which = lambda cli: "/usr/bin/glab"
    aca._run = fake_run
    try:
        result = aca.check_branch_protection_gitlab("group/project")
    finally:
        aca._which, aca._run = original_which, original_run
    assert "repo_check_error" in result
    assert "branch_protected" not in result
    assert "only_allow_merge_if_pipeline_succeeds" not in result


def test_branch_protection_success_reports_required_checks_and_makes_two_api_calls():
    _require_script()
    calls = []

    def fake_run(args):
        calls.append(args)
        if args[:2] == ["gh", "auth"]:
            return 0, "", ""
        if args[-1] == "repos/owner/repo":
            return 0, '{"default_branch": "main", "allow_auto_merge": true}', ""
        if args[-1].endswith("/protection"):
            return 0, '{"required_status_checks": {"contexts": ["lint"]}}', ""
        raise AssertionError(f"unexpected _run call: {args}")

    original_which, original_run = aca._which, aca._run
    aca._which = lambda cli: "/usr/bin/gh"
    aca._run = fake_run
    try:
        result = aca.check_branch_protection_github("owner/repo")
    finally:
        aca._which, aca._run = original_which, original_run
    assert result["branch_protected"] is True
    assert result["auto_merge_enabled"] is True
    # printed verbatim for a human to read — never evaluated for "coverage"
    assert result["required_checks"] == ["lint"]
    # one call for repo info (also carries default_branch), one for
    # protection — not the earlier three (a redundant --jq default_branch
    # call in between)
    gh_api_calls = [c for c in calls if c[:2] == ["gh", "api"]]
    assert len(gh_api_calls) == 2, f"expected exactly 2 gh api calls, got {gh_api_calls}"


def test_branch_protection_403_is_not_treated_as_unprotected():
    # the actual cry-wolf/false-negative trap: branch-protection reads need
    # admin on the repo, which a CI job's default GITHUB_TOKEN doesn't have
    # — a 403 there must not be reported as "branch not protected"
    _require_script()

    def fake_run(args):
        if args[:2] == ["gh", "auth"]:
            return 0, "", ""
        if args[-1] == "repos/owner/repo":
            return 0, '{"default_branch": "main"}', ""
        if args[-1].endswith("/protection"):
            return 1, "", "gh: HTTP 403: Must have admin rights to Repository."
        raise AssertionError(f"unexpected _run call: {args}")

    original_which, original_run = aca._which, aca._run
    aca._which = lambda cli: "/usr/bin/gh"
    aca._run = fake_run
    try:
        result = aca.check_branch_protection_github("owner/repo")
    finally:
        aca._which, aca._run = original_which, original_run
    assert "branch_protection_check_error" in result
    assert "branch_protected" not in result


def test_branch_protection_404_and_no_ruleset_means_genuinely_unprotected():
    _require_script()

    def fake_run(args):
        if args[:2] == ["gh", "auth"]:
            return 0, "", ""
        if args[-1] == "repos/owner/repo":
            return 0, '{"default_branch": "main"}', ""
        if args[-1].endswith("/protection"):
            return 1, "", "gh: Branch not protected (HTTP 404)"
        if "/rules/branches/main" in args[-1]:
            return 0, "[]", ""
        raise AssertionError(f"unexpected _run call: {args}")

    original_which, original_run = aca._which, aca._run
    aca._which = lambda cli: "/usr/bin/gh"
    aca._run = fake_run
    try:
        result = aca.check_branch_protection_github("owner/repo")
    finally:
        aca._which, aca._run = original_which, original_run
    assert result["branch_protected"] is False
    assert "branch_protection_check_error" not in result


def test_branch_protection_404_but_a_ruleset_covers_it_is_still_protected():
    # a repo protected only via GitHub's newer ruleset mechanism (not
    # classic branch protection) 404s on the classic endpoint too — an
    # earlier version treated that 404 as unconditionally "unprotected",
    # misreporting a correctly protected repo
    _require_script()

    def fake_run(args):
        if args[:2] == ["gh", "auth"]:
            return 0, "", ""
        if args[-1] == "repos/owner/repo":
            return 0, '{"default_branch": "main"}', ""
        if args[-1].endswith("/protection"):
            return 1, "", "gh: Branch not protected (HTTP 404)"
        if "/rules/branches/main" in args[-1]:
            return 0, '[{"type": "pull_request"}]', ""
        raise AssertionError(f"unexpected _run call: {args}")

    original_which, original_run = aca._which, aca._run
    aca._which = lambda cli: "/usr/bin/gh"
    aca._run = fake_run
    try:
        result = aca.check_branch_protection_github("owner/repo")
    finally:
        aca._which, aca._run = original_which, original_run
    assert result["branch_protected"] is True


def test_branch_protection_404_and_ruleset_check_itself_fails_is_ambiguous():
    _require_script()

    def fake_run(args):
        if args[:2] == ["gh", "auth"]:
            return 0, "", ""
        if args[-1] == "repos/owner/repo":
            return 0, '{"default_branch": "main"}', ""
        if args[-1].endswith("/protection"):
            return 1, "", "gh: Branch not protected (HTTP 404)"
        if "/rules/branches/main" in args[-1]:
            return 1, "", "gh: HTTP 403: insufficient access"
        raise AssertionError(f"unexpected _run call: {args}")

    original_which, original_run = aca._which, aca._run
    aca._which = lambda cli: "/usr/bin/gh"
    aca._run = fake_run
    try:
        result = aca.check_branch_protection_github("owner/repo")
    finally:
        aca._which, aca._run = original_which, original_run
    assert "branch_protection_check_error" in result
    assert "branch_protected" not in result


def test_branch_protection_404_and_rulesets_response_not_an_array_is_ambiguous():
    # a 200 whose body isn't a JSON array (unexpected shape) must not
    # silently resolve to "confirmed unprotected" — an earlier version's
    # helper collapsed "couldn't parse as an array" into an empty list,
    # indistinguishable from a genuinely empty, meaningful answer
    _require_script()

    def fake_run(args):
        if args[:2] == ["gh", "auth"]:
            return 0, "", ""
        if args[-1] == "repos/owner/repo":
            return 0, '{"default_branch": "main"}', ""
        if args[-1].endswith("/protection"):
            return 1, "", "gh: Branch not protected (HTTP 404)"
        if "/rules/branches/main" in args[-1]:
            return 0, "null", ""
        raise AssertionError(f"unexpected _run call: {args}")

    original_which, original_run = aca._which, aca._run
    aca._which = lambda cli: "/usr/bin/gh"
    aca._run = fake_run
    try:
        result = aca.check_branch_protection_github("owner/repo")
    finally:
        aca._which, aca._run = original_which, original_run
    assert "branch_protection_check_error" in result
    assert "branch_protected" not in result


def test_template_hook_flags_the_same_dangerous_shape():
    _require_template()
    with tempfile.TemporaryDirectory() as repo:
        path = _write(repo, ".github/workflows/pr-autopilot.yml", _DANGEROUS_WORKFLOW)
        finding = tmpl.scan_file(path)
        assert finding is not None
        assert "GitHub schedule trigger" in finding["triggers"]


def test_template_fails_open_without_its_command_utils_sibling():
    # The real deployed failure mode this guards against: the template is
    # copied into a project's `.claude/hooks/` alongside `_command_utils.py`
    # (see its module docstring) — but if it's ever run somewhere that
    # sibling isn't present (e.g. copied alone, or `_command_utils.py`
    # itself is broken), the docstring promises "any error exits 0 with no
    # output". Proven here by actually running the file in isolation via
    # subprocess — the standalone-script shape it's designed for — with no
    # `_command_utils.py` next to it, not by asserting on its source code.
    _require_template()
    with tempfile.TemporaryDirectory() as isolated:
        path = _write(isolated, "ci_automation_audit.py",
                       open(_TEMPLATE_FILE, encoding="utf-8").read())
        result = subprocess.run([sys.executable, path], capture_output=True,
                                 text=True, timeout=20)
        assert result.returncode == 0, (
            f"expected fail-open (exit 0), got {result.returncode}: {result.stderr}")
        assert result.stdout == "" and result.stderr == "", (
            f"expected silent fail-open, got stdout={result.stdout!r} "
            f"stderr={result.stderr!r}")


def test_template_and_script_pattern_lists_have_not_drifted():
    # the template is a deliberate stand-alone COPY, not an import (see its
    # module docstring) — this is the closest thing to a parity test for it.
    # Compares (pattern, flags) pairs, not bare pattern strings: two regexes
    # with identical source but different flags (e.g. one case-insensitive,
    # one not) behave differently and bare-string comparison would miss that.
    _require_script()
    _require_template()
    script_triggers = {(p.pattern, p.flags) for _, p in aca._TRIGGER_PATTERNS}
    template_triggers = {(p.pattern, p.flags) for _, p in tmpl._TRIGGER_PATTERNS}
    script_actions = {(p.pattern, p.flags) for _, p in aca._AUTOMERGE_PATTERNS}
    template_actions = {(p.pattern, p.flags) for _, p in tmpl._AUTOMERGE_PATTERNS}
    assert script_triggers == template_triggers, (
        "templates/ci-audit/ci_automation_audit.py's trigger patterns have "
        "drifted from scripts/audit_ci_automation.py's — keep them in sync")
    assert script_actions == template_actions, (
        "templates/ci-audit/ci_automation_audit.py's action patterns have "
        "drifted from scripts/audit_ci_automation.py's — keep them in sync")


def test_safe_json_object_rejects_non_dict_json():
    _require_script()
    assert aca._safe_json_object("null") == {}
    assert aca._safe_json_object("[1, 2, 3]") == {}
    assert aca._safe_json_object("not json") == {}
    assert aca._safe_json_object('{"a": 1}') == {"a": 1}


def test_slug_without_provider_is_rejected():
    _require_script()
    code, out = _run_script(["--slug", "acme/widgets"])
    assert code != 0
    assert "--provider" in out


def test_slug_with_provider_does_not_error_on_argument_parsing():
    # --no-live avoids any real gh/glab call; this only proves argparse
    # accepts the combination and the script proceeds past arg parsing
    _require_script()
    code, _ = _run_script(["--slug", "acme/widgets", "--provider", "github", "--no-live"])
    assert code == 0


def test_detect_remotes_finds_github_and_gitlab_urls():
    # _detect_remotes had ZERO test coverage before this — it's the sole
    # input to --strict on the tool's default, documented invocation (no
    # --slug). A silent regression in either regex would turn the live
    # check into a no-op on every real run with no test ever catching it.
    _require_script()
    _require_git()
    with tempfile.TemporaryDirectory() as repo:
        _git(repo, "init", "-q")
        _add_remotes(repo, {
            "origin": "git@github.com:acme/widgets.git",
            "gitlab": "https://gitlab.com/acme/widgets-mirror.git",
        })
        remotes = aca._detect_remotes(repo)
    assert ("origin", "acme/widgets", "github") in remotes
    assert ("gitlab", "acme/widgets-mirror", "gitlab") in remotes
    assert len(remotes) == 2


def test_detect_remotes_ignores_unrelated_hosts():
    _require_script()
    _require_git()
    with tempfile.TemporaryDirectory() as repo:
        _git(repo, "init", "-q")
        _add_remotes(repo, {"origin": "https://bitbucket.org/acme/widgets.git"})
        remotes = aca._detect_remotes(repo)
    assert remotes == []


def test_detect_remotes_requires_a_host_boundary():
    # an earlier version's regex had no left boundary on the host, so
    # "github.com" also matched a host merely ENDING in that string — a
    # completely unrelated project's slug would then become the sole,
    # unambiguous input to --strict
    _require_script()
    _require_git()
    with tempfile.TemporaryDirectory() as repo:
        _git(repo, "init", "-q")
        _add_remotes(repo, {"origin": "https://mygithub.com/acme/widgets.git"})
        remotes = aca._detect_remotes(repo)
    assert remotes == []


def test_detect_remotes_dedupes_by_slug_and_provider():
    # `git remote` lists names alphabetically, not insertion order — with
    # "a-mirror" and "z-origin" both pointing at the same repo, "a-mirror"
    # is what git reports first, and that's the one the de-dupe keeps.
    _require_script()
    _require_git()
    with tempfile.TemporaryDirectory() as repo:
        _git(repo, "init", "-q")
        _add_remotes(repo, {
            "z-origin": "git@github.com:acme/widgets.git",
            "a-mirror": "https://github.com/acme/widgets.git",
        })
        remotes = aca._detect_remotes(repo)
    assert remotes == [("a-mirror", "acme/widgets", "github")]


def test_detect_remotes_returns_empty_outside_a_git_repo():
    _require_script()
    _require_git()
    with tempfile.TemporaryDirectory() as not_a_repo:
        assert aca._detect_remotes(not_a_repo) == []


def test_main_single_remote_governs_strict_regardless_of_its_name():
    # exactly one remote is unambiguous no matter what it's called
    _require_script()
    _require_git()
    original = aca.check_branch_protection_github
    aca.check_branch_protection_github = lambda slug: {
        "available": True, "provider": "github", "branch_protected": False}
    try:
        with tempfile.TemporaryDirectory() as repo:
            _git(repo, "init", "-q")
            _add_remotes(repo, {"upstream": "git@github.com:acme/widgets.git"})
            code, out = _run_script(["--strict"], repo_root=repo)
    finally:
        aca.check_branch_protection_github = original
    assert code == 1
    assert "informational only" not in out


def test_main_multiple_remotes_without_slug_govern_nothing():
    # the round-fix this test pins: a common local topology (origin = a
    # personal fork, upstream = the canonical repo) must NOT let the
    # fork's near-universally-unprotected branch trip --strict on a
    # correctly configured project. Ambiguity between multiple remotes is
    # resolved by trusting NEITHER automatically — same principle as
    # --slug requiring --provider.
    _require_script()
    _require_git()
    original = aca.check_branch_protection_github
    calls = {}

    def fake_check(slug):
        # the fork (origin) is unprotected; the canonical repo (upstream)
        # is correctly protected — neither may govern --strict here
        calls[slug] = True
        return {"available": True, "provider": "github",
                "branch_protected": slug != "someone/widgets-fork"}

    aca.check_branch_protection_github = fake_check
    try:
        with tempfile.TemporaryDirectory() as repo:
            _git(repo, "init", "-q")
            _add_remotes(repo, {
                "origin": "git@github.com:someone/widgets-fork.git",
                "upstream": "git@github.com:acme/widgets.git",
            })
            code, out = _run_script(["--strict"], repo_root=repo)
    finally:
        aca.check_branch_protection_github = original
    assert code == 0, "an unprotected fork must not trip --strict when ambiguous"
    assert "someone/widgets-fork" in calls and "acme/widgets" in calls
    assert "informational only" in out


def test_main_explicit_slug_disambiguates_among_multiple_remotes():
    # --slug/--provider is exactly the escape hatch for the ambiguous case
    _require_script()
    _require_git()
    original = aca.check_branch_protection_github
    aca.check_branch_protection_github = lambda slug: {
        "available": True, "provider": "github", "branch_protected": False}
    try:
        with tempfile.TemporaryDirectory() as repo:
            _git(repo, "init", "-q")
            _add_remotes(repo, {
                "origin": "git@github.com:someone/widgets-fork.git",
                "upstream": "git@github.com:acme/widgets.git",
            })
            code, _ = _run_script(
                ["--slug", "acme/widgets", "--provider", "github", "--strict"], repo_root=repo)
    finally:
        aca.check_branch_protection_github = original
    assert code == 1


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
    print("all tests passed" if not _failed else f"{_failed} test(s) failed")
    sys.exit(1 if _failed else 0)
