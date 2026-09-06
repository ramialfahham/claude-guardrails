#!/usr/bin/env python
"""Read-only CI-provider automation auditor.

Exists because of a real incident, not a hypothetical one: a project's own
GitHub Actions workflow (a scheduled/dispatchable job) auto-merged pull
requests by trusting `mergeable_state` alone — which only reflects checks
branch protection actually REQUIRES. The real build job wasn't in that
required list, so PRs merged while the build was still queued. No local git
hook could ever catch this: it's a server-side CI-provider behavior, not a
`git` operation any `PreToolUse(Bash)` hook (this repo's entire enforcement
mechanism elsewhere) can see.

Two checks, both read-only and advisory — this script NEVER modifies
anything, never fails a CI job it isn't explicitly asked to fail:

1. STATIC scan of `.github/workflows/*.yml` and `.gitlab-ci.yml`: does any
   single file combine a schedule/dispatch-style trigger with something that
   looks like an auto-merge action or a merge-API call? That combination —
   not either alone — is the actual danger shape. stdlib regex/text
   matching only, no YAML-parsing dependency (matches this repo's
   zero-dependency policy; accepts some false negatives on unusual
   formatting in exchange for adding nothing to install).

2. Best-effort LIVE check via `gh`/`glab` (only if installed and
   authenticated — skips cleanly otherwise, never crashes): is the default
   branch protected, is auto-merge enabled (GitHub) or is merging allowed
   without a passing pipeline (GitLab), and — printed verbatim, not
   evaluated — what does the required-status-checks list actually contain?
   Deliberately does NOT try to decide whether that list "covers" the
   project's real CI jobs: which jobs are load-bearing is a project-specific
   judgment call, not something inferable from parsing arbitrary workflow
   YAML with text patterns. An earlier version attempted that inference and
   produced a long, escalating series of correctness bugs across several
   rounds of review (trigger-detection edge cases, matrix/reusable-workflow
   syntax collisions, provider mixing) without converging — removed rather
   than continuing to chase; see `.claude/task/contract.md`'s amendments log
   for the full history. A human reading the printed `required_checks` list
   can make that judgment; this tool no longer tries to make it for them.

Usage:
  python scripts/audit_ci_automation.py [--repo-root PATH]
                                         [--slug OWNER/REPO --provider {github,gitlab}]
                                         [--no-live] [--strict]
--slug requires --provider alongside it — a bare `owner/repo` slug carries no
hostname, so the provider can't be inferred from it (a real bug an earlier
version of this script had: guessing from whether the literal substring
"github" appeared in the slug, which is never true for an ordinary slug like
"acme/widgets", silently routing every manually-specified GitHub repo to the
GitLab check instead).
--strict exits 1 if anything is flagged (for wiring into a CI job); without
it, the script always exits 0 — it's advisory by default. The STATIC scan
always governs --strict. The LIVE check governs it ONLY when exactly one
GitHub/GitLab remote is in play (either via --slug, or auto-detection
finding just one) — with more than one detected remote (e.g. a fork
checkout with both 'origin' and 'upstream', or this repo's own two
remotes), every live-check result prints as informational only and NONE
of them can trip --strict, because there's no reliable way to guess which
remote is "the real one" to judge (this repo's own remotes are a
counterexample to any name-based guess, including preferring 'origin').
Pass --slug/--provider to pick one explicitly if you need --strict to
cover the live check on a multi-remote checkout.
"""

from __future__ import annotations

import argparse
import fnmatch
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse

_TRIGGER_PATTERNS = [
    ("GitHub schedule trigger", re.compile(r"^\s*schedule\s*:", re.MULTILINE)),
    ("GitHub workflow_dispatch trigger", re.compile(r"\bworkflow_dispatch\s*:")),
    ("GitHub repository_dispatch trigger", re.compile(r"\brepository_dispatch\s*:")),
    ("GitLab schedule pipeline source",
     re.compile(r'\$CI_PIPELINE_SOURCE\s*==\s*"schedule"')),
]

# Deliberately specific, not a loose keyword scan. An earlier version also
# matched a bare `\bauto[_-]?merge\b` anywhere (any case) — which fired on a
# comment saying "we deliberately do NOT auto-merge", combined with the very
# common `workflow_dispatch` trigger. That is the exact cry-wolf failure this
# tool's own contract calls "worse than no scanner": every pattern here names
# a concrete mechanism (a CLI invocation, a known action, an API call shape,
# or an explicit enable-flag assignment), not a word that can appear in prose.
_AUTOMERGE_PATTERNS = [
    ("`gh pr merge`", re.compile(r"gh\s+pr\s+merge\b")),
    ("`glab mr merge`/`accept`", re.compile(r"glab\s+mr\s+(merge|accept)\b")),
    ("a known GitHub auto-merge action",
     re.compile(r"(enable-pull-request-automerge|pascalgn/automerge-action)")),
    ("a merge-API endpoint call",
     re.compile(r"/(pulls|merge_requests)/[^\s\"']*/merge\b")),
    ("an Octokit/github-script pulls.merge() call",
     re.compile(r"\.(rest\.)?pulls\.merge\s*\(")),
    ("a GitLab merge_requests.merge() API call",
     re.compile(r"\.merge_requests\.merge\s*\(")),
    ("an explicit auto-merge enable flag",
     re.compile(r'\bauto[_-]?merge\b\s*[:=]\s*"?(true|enabled?)"?', re.IGNORECASE)),
]


def _iter_workflow_files(root: str) -> list[str]:
    files = sorted(glob.glob(os.path.join(root, ".github", "workflows", "*.yml")))
    files += sorted(glob.glob(os.path.join(root, ".github", "workflows", "*.yaml")))
    gitlab_ci = os.path.join(root, ".gitlab-ci.yml")
    if os.path.isfile(gitlab_ci):
        files.append(gitlab_ci)
    return files


def _matches(patterns, text: str) -> list[str]:
    return [name for name, pattern in patterns if pattern.search(text)]


def scan_file(path: str) -> dict | None:
    """A finding dict if `path` combines a schedule/dispatch trigger with an
    auto-merge action in the SAME file, else None. Either alone is normal;
    the combination is the actual danger shape from the real incident."""
    try:
        text = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return None
    triggers = _matches(_TRIGGER_PATTERNS, text)
    actions = _matches(_AUTOMERGE_PATTERNS, text)
    if triggers and actions:
        return {"file": path, "triggers": triggers, "actions": actions}
    return None


def scan_repo(root: str) -> list[dict]:
    return [f for f in (scan_file(p) for p in _iter_workflow_files(root)) if f]


def _which(cli: str) -> str | None:
    return shutil.which(cli)


def _run(args: list[str]) -> tuple[int, str, str]:
    """Returns (returncode, stdout, stderr) — stderr matters for the
    branch-protection check below, which must tell "genuinely unprotected"
    (gh/glab api returns 404) apart from "couldn't tell" (403 permission
    denied, rate limit, network error) rather than collapsing every non-zero
    exit to the same false "not protected"."""
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=20)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:  # noqa: BLE001 — this path must never raise
        return 1, "", str(e)


_HTTP_STATUS_RE = re.compile(r"HTTP (\d{3})")


def _http_status(stderr: str) -> int | None:
    """Best-effort extraction of the HTTP status `gh`/`glab api` reported in
    stderr on a non-zero exit (both CLIs print e.g. "HTTP 404" on API
    errors) — None if the message doesn't contain one (network error,
    timeout, CLI-level argument error)."""
    m = _HTTP_STATUS_RE.search(stderr)
    return int(m.group(1)) if m else None


def _safe_json_object(text: str) -> dict:
    """`json.loads(text)` if it parses to a JSON OBJECT, else `{}` — never
    raises. An earlier version called `.get()` directly on `json.loads(...)`
    result, guarded only by `except json.JSONDecodeError`; valid JSON that
    isn't an object (`null`, a bare list, a paginated array) parses fine and
    then raises AttributeError on `.get()`, which escaped to the caller."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _parsed_json_array(text: str) -> list | None:
    """`json.loads(text)` if it parses to a JSON ARRAY, else `None` — never
    raises. Unlike `_safe_json_object`'s "just give me something usable"
    contract, this distinguishes a genuinely empty array (a real, meaningful
    answer: "the list is empty") from "this didn't parse as an array at
    all" (`None`) — an earlier version collapsed both to `[]`, so an
    unparseable exit-0 response silently became "confirmed empty" instead
    of "couldn't verify", the one place in this file that let an
    unparseable answer resolve to a confirmed gap instead of staying
    ambiguous."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, list) else None


def check_branch_protection_github(slug: str) -> dict:
    """Best-effort. Returns a dict with 'available': False if gh isn't
    installed/authenticated — never raises, never blocks. Reports the
    required-status-checks list verbatim; does NOT judge whether it
    "covers" the project's real CI jobs — that's a project-specific
    judgment call a generic tool can't correctly infer from workflow YAML
    (see the module docstring)."""
    if not _which("gh"):
        return {"available": False, "reason": "gh CLI not installed"}
    code, _, _ = _run(["gh", "auth", "status"])
    if code != 0:
        return {"available": False, "reason": "gh CLI not authenticated"}

    result: dict = {"available": True, "provider": "github"}
    code, out, err = _run(["gh", "api", f"repos/{slug}"])
    if code != 0:
        # Can't fetch the repo object at all (403, rate limit, network,
        # bad slug) — there's no real `default_branch` to check protection
        # against. An earlier version guessed "main" here, which risks
        # querying the WRONG branch: that 404s with the same status as
        # "branch not protected", which would falsely clear a genuinely
        # protected repo whose real default branch is master/develop/trunk.
        # Skip the protection check entirely rather than guess.
        result["repo_check_error"] = (
            f"could not fetch repo info (gh api exited {code}"
            + (f", HTTP {_http_status(err)}" if _http_status(err) else "") + ")"
        )
        return result
    repo_info = _safe_json_object(out)
    result["auto_merge_enabled"] = repo_info.get("allow_auto_merge")
    default_branch = repo_info.get("default_branch")
    if not default_branch:
        result["repo_check_error"] = "repo info response had no default_branch field"
        return result

    code, out, err = _run(["gh", "api", f"repos/{slug}/branches/{default_branch}/protection"])
    if code == 0:
        result["branch_protected"] = True
        contexts = (_safe_json_object(out).get("required_status_checks") or {}).get(
            "contexts") or []
        result["required_checks"] = contexts
    elif _http_status(err) == 404:
        # A 404 here means "no CLASSIC branch protection rule" — it does
        # NOT mean unprotected: GitHub's newer ruleset mechanism can also
        # protect this branch, and a ruleset-protected branch has no
        # classic protection rule at all, so it 404s here too. Check
        # rulesets before concluding unprotected, using the endpoint that
        # reports rules actually in effect for this branch name (and,
        # unlike the classic endpoint, isn't admin-gated). `?per_page=100`
        # for consistency with the GitLab list call below — though unlike
        # that one, truncation can't manufacture a false "unprotected"
        # here: this reports rules FOR this specific branch (GitHub does
        # the pattern-matching server-side), so a non-empty result is
        # trustworthy regardless of page size, and an empty first page
        # only happens when the true total is zero (pagination can't skip
        # straight to page 2's content) — there's no "the real match might
        # be on a page we didn't fetch" case the way GitLab's
        # match-a-wildcard-pattern-against-every-rule check has.
        code2, out2, err2 = _run(
            ["gh", "api", f"repos/{slug}/rules/branches/{default_branch}?per_page=100"])
        rules = _parsed_json_array(out2) if code2 == 0 else None
        if rules is not None:
            result["branch_protected"] = bool(rules)
        else:
            result["branch_protection_check_error"] = (
                f"could not verify (no classic protection rule, and the rulesets "
                f"check itself failed or returned an unexpected shape: gh api "
                f"exited {code2}"
                + (f", HTTP {_http_status(err2)}" if _http_status(err2) else "")
                + ") — not treated as unprotected"
            )
    else:
        # Any other failure (403 — branch-protection reads require admin
        # on the repo, and the default GITHUB_TOKEN in a CI job is not
        # admin; rate limit; network error) must NOT be reported as
        # "not protected" — that's a false negative on the exact thing
        # this tool exists to catch. Leaving `branch_protected` OUT of the
        # result (rather than False) keeps "couldn't verify" visibly
        # distinct from "verified and clean".
        result["branch_protection_check_error"] = (
            f"could not verify (gh api exited {code}"
            + (f", HTTP {_http_status(err)}" if _http_status(err) else "") + ") — "
            "reading branch protection requires admin access to the repo; "
            "not treated as unprotected"
        )
    return result


def check_branch_protection_gitlab(slug: str) -> dict:
    """Best-effort GitLab equivalent. GitLab has no single 'auto-merge
    enabled' boolean the way GitHub does — reports what's actually
    inspectable (merge-on-pipeline-success, and whether the default branch
    is protected) rather than a claim GitLab doesn't make available."""
    if not _which("glab"):
        return {"available": False, "reason": "glab CLI not installed"}
    code, _, _ = _run(["glab", "auth", "status"])
    if code != 0:
        return {"available": False, "reason": "glab CLI not authenticated"}

    result: dict = {"available": True, "provider": "gitlab"}
    # GitLab's GET /projects/:id needs a numeric ID or a URL-ENCODED path —
    # `projects/group/project` 404s (the slash is read as a path separator,
    # not part of the ID). An earlier version passed the raw slug and this
    # call silently 404'd every time, always returning no data.
    encoded_slug = urllib.parse.quote(slug, safe="")
    code, out, err = _run(["glab", "api", f"projects/{encoded_slug}"])
    if code != 0:
        # Mirrors the GitHub check: a failed fetch must be reported as
        # "couldn't verify", never silently omitted — an earlier version
        # had no `else` here at all, so a 403/404/rate-limit/network
        # failure printed as `{"available": true, ...}` with nothing
        # saying the call failed, indistinguishable from "verified clean".
        result["repo_check_error"] = (
            f"could not fetch project info (glab api exited {code}"
            + (f", HTTP {_http_status(err)}" if _http_status(err) else "") + ")"
        )
        return result
    project_info = _safe_json_object(out)
    result["only_allow_merge_if_pipeline_succeeds"] = project_info.get(
        "only_allow_merge_if_pipeline_succeeds")
    default_branch = project_info.get("default_branch")
    if not default_branch:
        result["repo_check_error"] = "project info response had no default_branch field"
        return result

    # The LIST endpoint, not GET .../protected_branches/:name — a project
    # can protect its default branch via a WILDCARD rule (`main*`, `re*`,
    # `*`) that has no rule literally named `main`; querying by exact name
    # 404s on such a project and would misreport it as unprotected. The
    # list endpoint returns every rule (name possibly a wildcard pattern),
    # matched here with fnmatch — and, unlike the by-name lookup, GitLab
    # returns 200 with an empty array when nothing is protected, so a
    # non-zero exit from THIS endpoint is never a legitimate "unprotected"
    # signal — it always means the check itself failed (auth, permissions,
    # rate limit, project not found). `?per_page=100` (GitLab's max page
    # size) raises the truncation threshold from GitLab's default of 20,
    # but doesn't remove it — a project with over 100 rules can still have
    # its default-branch rule fall off this one page.
    _PAGE_SIZE = 100
    code, out, err = _run(
        ["glab", "api", f"projects/{encoded_slug}/protected_branches?per_page={_PAGE_SIZE}"])
    rules = _parsed_json_array(out) if code == 0 else None
    if rules is not None:
        rule_names = [r.get("name") for r in rules if isinstance(r, dict) and r.get("name")]
        # fnmatchCASE, not fnmatch: fnmatch case- and separator-normalizes
        # through os.path.normcase, which is a no-op on POSIX but lowercases
        # on Windows — the same project's protection verdict would differ
        # by the OS the audit happens to run on. Git ref names are
        # case-sensitive; the match must be too.
        matched = any(fnmatch.fnmatchcase(default_branch, pattern) for pattern in rule_names)
        if not matched and len(rules) >= _PAGE_SIZE:
            # A FULL page with no match doesn't mean "confirmed
            # unprotected" — there may be a next page this best-effort tool
            # didn't fetch, and the default-branch rule could be on it.
            # Only an INCOMPLETE page (fewer rules than the page size) with
            # no match is a genuine "checked everything, found nothing".
            result["branch_protection_check_error"] = (
                f"could not verify — {len(rules)} protected-branch rules "
                f"returned (the page-size limit), so the list may be "
                "truncated; not treated as unprotected"
            )
        else:
            result["branch_protected"] = matched
    else:
        result["branch_protection_check_error"] = (
            f"could not verify (glab api exited {code}"
            + (f", HTTP {_http_status(err)}" if _http_status(err) else "")
            + ("" if code != 0 else ", response was not a JSON array") + ")"
        )
    return result


def _detect_remotes(root: str) -> list[tuple[str, str, str]]:
    """(remote_name, slug, provider) for every configured remote that
    points at github.com or gitlab.com — not just 'origin'. A repo can have
    (and this one does) an unauthenticated/suspended 'origin' and a real,
    active remote under a different name; checking only 'origin' would
    silently skip the remote that actually matters. All are returned for a
    human to read — but `main()` deliberately does NOT let every one of
    them govern `--strict`'s exit code, and does NOT guess which one is
    "the real one" by name either (see there for why: this repo's own
    remotes are the counterexample to "trust origin")."""
    code, out, _ = _run(["git", "-C", root, "remote"])
    if code != 0:
        return []
    found = []
    for name in out.split():
        code, url_out, _ = _run(["git", "-C", root, "remote", "get-url", name])
        if code != 0:
            continue
        url = url_out.strip()
        # `(?:^|[@/])` anchors the LEFT side of the host: without it,
        # `github\.com` also matches a host that merely ENDS in that
        # string (e.g. `mygitlab.com`) — and if that's the repo's only
        # remote, its slug becomes the sole, unambiguous input to
        # `--strict`, so an unrelated project's settings could fail a
        # correctly configured repo.
        m = re.search(r"(?:^|[@/])github\.com[:/]([\w.-]+/[\w.-]+?)(?:\.git)?$", url)
        if m:
            found.append((name, m.group(1), "github"))
            continue
        m = re.search(r"(?:^|[@/])gitlab\.com[:/]([\w./-]+?)(?:\.git)?$", url)
        if m:
            found.append((name, m.group(1), "gitlab"))
    # de-dupe by slug+provider (two remote NAMES can point at the same
    # repo) — keeps the first-seen name for that repo.
    seen = set()
    unique = []
    for remote_name, slug, provider in found:
        key = (slug, provider)
        if key not in seen:
            seen.add(key)
            unique.append((remote_name, slug, provider))
    return unique


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--slug", help="owner/repo — auto-detected from configured "
                                         "remotes if omitted; requires --provider; "
                                         "pass this to let --strict cover the live "
                                         "check when more than one remote is detected")
    parser.add_argument("--provider", choices=["github", "gitlab"],
                         help="required alongside --slug — a bare slug carries no "
                              "hostname to infer this from")
    parser.add_argument("--no-live", action="store_true",
                         help="skip the gh/glab live check, static scan only")
    parser.add_argument("--strict", action="store_true",
                         help="exit 1 if anything is flagged (default: always exit 0); "
                              "the live check only counts toward this with exactly one "
                              "unambiguous remote in play — see --slug")
    args = parser.parse_args()
    if args.slug and not args.provider:
        parser.error("--slug requires --provider (github or gitlab) — it can't be "
                      "inferred from a bare owner/repo slug")

    root = os.path.abspath(args.repo_root)
    findings = scan_repo(root)

    flagged = False
    if findings:
        flagged = True
        print("STATIC SCAN — dangerous trigger+action combination found:")
        for f in findings:
            print(f"  {f['file']}")
            print(f"    trigger(s): {', '.join(f['triggers'])}")
            print(f"    action(s):  {', '.join(f['actions'])}")
    else:
        print("STATIC SCAN — clean: no file combines a schedule/dispatch "
              "trigger with an auto-merge action.")

    if not args.no_live:
        if args.slug:
            remotes = [("--slug", args.slug, args.provider)]
        else:
            remotes = _detect_remotes(root)

        # Which ONE remote, if any, is allowed to govern --strict.
        # Deliberately not "every detected remote ORed together": a
        # common local topology is `origin` = a personal fork,
        # `upstream` = the canonical repo — the fork's default branch is
        # almost never protected, and letting that trip --strict would
        # fail a correctly configured project for a reason that has
        # nothing to do with it. With exactly one remote there's no
        # ambiguity. With several, this deliberately does NOT guess which
        # one is "the real one" by name (e.g. preferring 'origin') — this
        # repo's OWN remotes are the counterexample: 'origin' here is the
        # unauthenticated/less-relevant one, a differently-named remote is
        # the active one. Same principle as `--slug` requiring
        # `--provider`: don't infer an answer that's genuinely ambiguous —
        # require the caller to pick one explicitly.
        if len(remotes) == 1:
            primary_name = remotes[0][0]
        else:
            primary_name = None
            if remotes:
                print("\nLIVE CHECK — multiple remotes detected; none will govern "
                      "--strict without --slug/--provider to pick one explicitly.")

        if not remotes:
            print("\nLIVE CHECK — skipped: no GitHub/GitLab remote detected.")
        for remote_name, slug, provider in remotes:
            is_primary = remote_name == primary_name
            note = "" if is_primary else " — informational only, does not affect --strict"
            if provider == "github":
                result = check_branch_protection_github(slug)
                print(f"\nLIVE CHECK ({remote_name}: {slug}, github){note}:",
                      json.dumps(result, indent=2))
                # A CONFIRMED gap trips --strict: a genuinely unprotected
                # default branch (branch_protected is False, not merely
                # absent). Deliberately NOT flagging on
                # branch_protection_check_error / repo_check_error — those
                # mean "couldn't verify" (most often a non-admin token, the
                # normal case for CI), and --strict crying wolf on every
                # such run would train exactly the behavior this tool
                # exists to prevent.
                if is_primary and result.get("branch_protected") is False:
                    flagged = True
            elif provider == "gitlab":
                result = check_branch_protection_gitlab(slug)
                print(f"\nLIVE CHECK ({remote_name}: {slug}, gitlab){note}:",
                      json.dumps(result, indent=2))
                # Same two confirmed-gap conditions as the GitHub side: a
                # genuinely unprotected default branch, or a project that
                # allows merging even though its pipeline hasn't succeeded
                # (the direct GitLab analogue of the incident). Same
                # deliberate exclusion of *_check_error too.
                if is_primary and (
                        result.get("branch_protected") is False
                        or result.get("only_allow_merge_if_pipeline_succeeds") is False):
                    flagged = True

    return 1 if (flagged and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
