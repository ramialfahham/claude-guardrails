# Task contract

objective: Phase 5 of the `claude-project-kit` plan — a read-only, stdlib-only
  CI-automation auditor that detects the actual class of failure that
  happened for real: `football-data-pipeline`'s `pr-autopilot.yml` combined a
  schedule/dispatch trigger with an auto-merge action, trusting `mergeable_state`
  alone — which only reflects checks branch protection actually REQUIRES —
  so PRs merged while the real build job was still queued. No local git hook
  could ever have caught this (it's a server-side CI-provider behavior, not a
  git operation). This phase builds the tool that can: a static scan for the
  dangerous trigger+action combination, plus a best-effort live check (via
  `gh`/`glab`, when authenticated) for the directly-answerable facts: is the
  default branch protected, is auto-merge enabled (GitHub) or is merging
  allowed without a passing pipeline (GitLab). **Amended after round 7** (see
  amendments below): the live check does NOT attempt to judge whether the
  required-status-checks list "covers" the project's real CI jobs — that
  requires project-specific knowledge (which jobs are load-bearing) a
  generic tool can't correctly infer from parsing arbitrary workflow YAML,
  and attempting it produced an escalating, non-converging series of
  correctness bugs across 7 review rounds. The required-checks list is
  printed verbatim for a human to judge instead.

scope_paths:
  - scripts/audit_ci_automation.py
  - templates/ci-audit/ci_automation_audit.py
  - .claude/tests/test_audit_ci_automation.py
  - .claude/task/contract.md
  - .claude/task/review.md

decisions_reserved:
  - Not wiring this repo's own `.claude/settings.json` to run the audit as a
    `SessionStart` hook — that's a new, always-on mechanism (extra work on
    every session start), which is an owner-level "new mechanism" call per
    working-agreement.md §6, not something to add silently while building
    the tool. This phase builds and tests the tool + the hook TEMPLATE only;
    whether THIS repo (or any specific project) actually turns the hook on
    is left to the owner, same as the migrate-to-gitlab skill's own stated
    boundary ("branch protection is project configuration, not something a
    script flips").
  - stdlib-only static scan (regex/text matching on workflow YAML), no YAML
    parsing dependency — matches this repo's existing zero-dependency policy
    (already the explicit decision in the original plan). Accepts some false
    negatives against unusually-formatted YAML in exchange for adding
    nothing to install.
  - The live branch-protection check is best-effort and read-only: skips
    cleanly (never crashes, never blocks) when `gh`/`glab` isn't installed or
    authenticated, and never modifies branch protection or auto-merge
    settings itself — reporting only, matching the precedent already set
    this session for GitLab branch-protection changes (report, then the
    owner runs the fix, or asks the agent to with explicit permission).

done_when:
  - `scripts/audit_ci_automation.py`: scans `.github/workflows/*.yml` and
    `.gitlab-ci.yml` for a schedule/dispatch trigger co-occurring with an
    auto-merge/merge-API action in the SAME file, and flags it, naming both
    the matched trigger and the matched action.
  - Verified against a fixture workflow shaped like `football-data-pipeline`'s
    actual `pr-autopilot.yml` (schedule trigger + an auto-merge action) —
    confirmed flagged. Verified against THIS repo's own real
    `.github/workflows/ci.yml` and `.gitlab-ci.yml` (push/MR-only triggers,
    no merge action) — confirmed NOT flagged (a scanner that also cries wolf
    on every ordinary CI file is worse than no scanner).
  - Best-effort live check: when `gh`/`glab` is present and authenticated,
    reports whether the default branch is protected, whether auto-merge is
    enabled (GitHub) or merging is allowed without a passing pipeline
    (GitLab), and prints the required-status-checks list verbatim. Skips
    cleanly, reported as such, when the CLI is absent/unauthenticated.
    Does NOT attempt to judge whether that list covers the project's real
    CI jobs (amended after round 7 — see amendments).
  - `templates/ci-audit/ci_automation_audit.py`: the static-scan check only
    (the live check is a deliberate, manual-audit-tool concern, not
    appropriate for something that might run on every session start),
    shaped as a `SessionStart` hook using `emit_context` — never blocks.
    Inert: not wired into any project's `.claude/settings.json` by this
    phase (same "not wired yet, Phase 6/7 dependency" status as Phase 1's
    and Phase 4's template content).
  - `.claude/tests/test_audit_ci_automation.py` proves the scanner distinguishes
    the dangerous fixture from a safe one, and that the live-check path
    degrades gracefully (no crash) when the CLI is unavailable — using a
    fake/stubbed CLI lookup, not a real network call in the test suite.
  - All existing `.claude/tests/test_*.py` still pass; JSON configs still
    parse; hooks still byte-compile; shell scripts still lint.
  - scope-auditor + cto-reviewer PASS on the staged diff.

amendments:
  - 2026-09-06 — contract created for Phase 5 of the approved plan
    (`C:\Users\Rami\.claude\plans\happy-stargazing-mccarthy.md`). Built on
    updated `main` (Phase 4 merged).
  - 2026-09-06 — round 1 review: both scope-auditor and cto-reviewer (opus)
    FAILed. All 9 findings were real defects, fixed (none disputed):
    1. `main()` inferred provider from `"github" in args.slug` — never true
       for an ordinary slug, silently routing every manually-specified
       GitHub repo to the GitLab check. FIXED: `--provider` is now a
       required companion to `--slug`, no inference.
    2. `check_branch_protection_gitlab` passed the raw `owner/repo` slug to
       `glab api projects/{slug}` — GitLab's API needs the path
       URL-encoded or a numeric ID; the raw form 404s (confirmed by the
       live run below, which now returns real data). FIXED: encode with
       `urllib.parse.quote(slug, safe="")`.
    3. `json.loads(out).get(...)` call sites caught only
       `json.JSONDecodeError`; valid-but-non-object JSON (`null`, a bare
       array) raises `AttributeError` on `.get()`, uncaught. FIXED: new
       `_safe_json_object()` helper used at all three call sites.
    4. The template/script pattern-parity test compared bare `.pattern`
       strings, missing a `.flags` (e.g. case-sensitivity) drift between
       the two copies. FIXED: compares `(pattern, flags)` tuples.
    5. Cry-wolf gap: `_AUTOMERGE_PATTERNS` included a loose
       `\bauto[_-]?merge\b` keyword (any case, anywhere) that would fire on
       a comment merely disclaiming auto-merge — the same failure mode this
       tool's own contract calls "worse than no scanner." FIXED: removed
       the loose keyword, replaced with a tightened enable-flag-shaped
       pattern requiring an assignment context; added
       `test_dispatch_with_automerge_disclaimer_is_not_flagged` proving the
       disclaiming-comment case no longer fires.
    6. No pattern covered the Octokit/github-script (`pulls.merge(`) or
       GitLab API-client (`merge_requests.merge(`) call shapes. FIXED:
       added both, plus `test_octokit_pulls_merge_is_flagged`.
    7. The template's `main()` imported `_command_utils` OUTSIDE its own
       `try/except`, so a copy dropped without its sibling file would raise
       `ModuleNotFoundError` instead of failing open, contradicting the
       file's own docstring promise. FIXED: import moved inside the `try`.
    8. The template's docstring claimed "there is no parity test for this
       one" — false, `test_template_and_script_pattern_lists_have_not_drifted`
       already existed and both reviewers caught the stale claim
       independently. FIXED: docstring now names the real test.
    9. (scope-auditor) `--slug` help text still said "auto-detected from
       'origin' if omitted", stale since `_detect_remotes` checks all
       configured remotes, not just `origin`. FIXED: help text corrected;
       also added `test_slug_without_provider_is_rejected` and
       `test_slug_with_provider_does_not_error_on_argument_parsing` for the
       new `--provider` requirement, and `test_safe_json_object_rejects_non_dict_json`.
    Re-verified end-to-end after fixes: full local test suite (all
    `.claude/tests/test_*.py`, 15/15 new tests + all pre-existing suites)
    passes; live CLI run against this repo's own two remotes now correctly
    resolves both `rami.al-fahham/claude-guardrails` (gitlab, real API data
    returned) and `ramialfahham/claude-guardrails` (github, degrades
    cleanly — `gh` not authenticated) instead of the old silent
    mis-routing/404 behavior.
  - 2026-09-06 — round 2 review: scope-auditor PASSed; cto-reviewer (opus)
    FAILed with 5 findings, all real, fixed:
    1. **Headline defect**: `.claude/tests/test_audit_ci_automation.py`
       imported `scripts/audit_ci_automation.py` and
       `templates/ci-audit/ci_automation_audit.py` at module scope with no
       existence guard. `scripts/bootstrap.sh` copies `.claude/tests/` into
       every consumer repo but never `scripts/` or `templates/` — confirmed
       by actually running `bash scripts/bootstrap.sh` into a scratch
       directory and inspecting the result, not by reading the script.
       That means `ModuleNotFoundError` at import time, escaping this
       file's own `__main__` handler, in every project bootstrapped from
       this kit — the identical mechanism to the Phase 4 defect already
       recorded above, unnoticed on this file in round 1. FIXED: guarded
       both imports behind `os.path.isfile` checks
       (`_HAVE_SCRIPT`/`_HAVE_TEMPLATE`), added `_require_script()` /
       `_require_template()` raising `unittest.SkipTest` at the top of
       every test that touches either module, and taught the `__main__`
       runner to print `skip` instead of crashing on `SkipTest` (matching
       `test_bootstrap.py`'s established pattern). Verified by actually
       bootstrapping a scratch repo, copying the fixed test file into it,
       and confirming all 17 tests print `skip ...: ... not present (a
       bootstrapped repo, not the kit)` with exit 0 — not just that the
       code compiles.
    2. `test_this_repos_own_real_workflows_are_not_flagged` would, once the
       file is blind-copied, assert a *consumer* repo's own CI is clean —
       an unsilenceable false failure for any consumer with a legitimate
       scheduled workflow. Resolved as a consequence of fix 1 (the test
       skips entirely wherever `scripts/audit_ci_automation.py` is absent,
       i.e. everywhere except this kit); comment strengthened to say so
       explicitly.
    3. `templates/ci-audit/ci_automation_audit.py`'s `main()` closed its
       `try` block before the `os.path.relpath(...)`/`emit_context(...)`
       calls, so an encoding or pipe error there would exit non-zero with a
       traceback — contradicting the file's own "Fails OPEN: any error …
       exits 0 with no output" docstring promise. Round 1's fix (moving the
       import inside `try`) didn't close this gap. FIXED: the whole body
       moved inside the `try`.
    4. No test proved the fail-open behavior at all. FIXED:
       `test_template_fails_open_without_its_command_utils_sibling` copies
       the template into an isolated temp directory (no `_command_utils.py`
       sibling) and runs it via a real `subprocess`, asserting exit 0 and
       silent stdout/stderr — proven against the actual failure shape, not
       asserted on source code.
    5. `_TRIGGER_PATTERNS` had no entry for `repository_dispatch:` — an
       externally-poked GitHub trigger, the closest analogue to the real
       incident's own trigger shape and squarely inside the contract's
       "schedule/dispatch trigger" done_when. FIXED: added to both the
       script and template pattern lists (parity test still passes) plus
       `test_repository_dispatch_trigger_is_flagged`.
    Re-verified end-to-end: full local test suite (17/17 new tests + all
    pre-existing suites) passes; byte-compile and JSON validation clean;
    the bootstrapped-repo skip behavior verified by an actual bootstrap run,
    not just code review.
    **Separately flagged, out of this contract's scope_paths**: the same
    "blind-copied test imports an uncopied scripts/ module" defect exists,
    unfixed, in three PRE-EXISTING test files —
    `.claude/tests/test_reviewer_naming_lint.py`,
    `.claude/tests/test_compose_routing.py`,
    `.claude/tests/test_promote_reviewer.py` — confirmed by directly running
    `test_reviewer_naming_lint.py` inside a freshly bootstrapped scratch
    repo and observing the same `ModuleNotFoundError`. This means
    `.claude/tests/*` is broken today in every repo bootstrapped from this
    kit. Not fixed here: it's a systemic, pre-existing issue spanning three
    files this contract's `scope_paths` doesn't cover, not something to
    silently expand into mid-phase. Reported to the owner as its own
    follow-up.
  - 2026-09-06 — round 3 review: scope-auditor PASSed (confirmed the
    3-pre-existing-files scope boundary above is legitimate, not evasion).
    cto-reviewer (opus) FAILed with 2 findings in
    `check_branch_protection_github`, both real, fixed:
    1. **Cry-wolf via error conflation**: a non-zero exit from
       `gh api repos/{slug}/branches/{branch}/protection` was reported as
       `branch_protected: False` regardless of WHY it failed. GitHub
       returns 404 for a genuinely unprotected branch, but also 403
       whenever the caller lacks admin on the repo — and branch-protection
       reads are admin-only, so a CI job's default `GITHUB_TOKEN` hits this
       on every correctly-protected repo it doesn't admin. `_run` also
       discarded stderr, so the two cases weren't even distinguishable.
       Consequence: a non-admin caller on a protected repo was told it's
       unprotected (the "worse than no scanner" failure this tool exists to
       avoid), `uncovered_jobs` — "the exact gap in the actual incident" per
       this contract's own objective — was silently never computed, and
       `--strict` couldn't fail closed on that gap in CI use. Same defect
       class as round 1 finding #2 (GitLab 404) and #3 (`.get()` on
       non-object JSON): fixed pointwise on GitLab, never generalized to
       GitHub. FIXED: `_run` now returns `(code, stdout, stderr)`; a new
       `_http_status(stderr)` extracts the HTTP status `gh`/`glab` report
       on failure; only a genuine 404 sets `branch_protected: False`, any
       other failure (403, rate limit, network) sets a distinct
       `branch_protection_check_error` field and leaves `branch_protected`/
       `uncovered_jobs` OUT of the result entirely — their absence is now
       unambiguous, not conflated with "verified clean". Proven by
       `test_branch_protection_403_is_not_treated_as_unprotected`,
       `test_branch_protection_404_means_genuinely_unprotected`, and
       `test_branch_protection_success_reports_uncovered_jobs_and_makes_two_api_calls`,
       each driving `check_branch_protection_github` through a fake `_run`
       rather than asserting on source code.
    2. **Redundant call + a bad guess**: `default_branch` was fetched via a
       second `gh api ... --jq .default_branch` call, defaulting to the
       literal string `"main"` on any failure — wrong for any repo whose
       default branch is `master`/`develop`, and a wasted round-trip since
       the repo object fetched one call earlier already carries
       `default_branch`. FIXED: read `default_branch` from the first
       `repos/{slug}` response; the redundant call is gone (down to 2 `gh
       api` calls total, asserted by
       `test_branch_protection_success_reports_uncovered_jobs_and_makes_two_api_calls`'s
       call-count check).
    Re-verified end-to-end: full local test suite (21/21 tests) passes;
    byte-compile clean; live CLI run against this repo's own remotes still
    correct (GitLab returns real data, GitHub degrades cleanly — `gh` not
    authenticated in this environment, so the new classification logic
    isn't exercised live here, only via the fake-`_run` unit tests above).
  - 2026-09-06 — round 4 review: scope-auditor PASSed. cto-reviewer (opus)
    FAILed again with 3 findings, all in the same
    `check_branch_protection_github` area — the round-3 fix was pointwise,
    not generalized. This put the task at round 4, past this repo's own
    3-round cap (`.claude/hooks/commit_review_gate.py`); per the Phase 3
    precedent (escalating, not repeated, findings can justify continuing
    past the cap, but only with the owner's explicit sign-off), the owner
    was asked whether to keep fixing or narrow the live check to
    advisory-only. **CPO ANSWER: keep fixing (round 5).**
    Round 4 findings, all real, fixed:
    1. The round-3 fix reinstated the exact bug it removed, one call
       earlier: if the `repos/{slug}` fetch itself failed (403/rate-limit/
       network), `repo_info` silently became `{}` and
       `default_branch = repo_info.get("default_branch") or "main"` fell
       back to the literal guess again. Querying `branches/main/protection`
       on the WRONG guessed branch 404s with the same status GitHub uses
       for "branch not protected" — indistinguishable, so a correctly
       protected repo (real default branch `master`/`develop`) could still
       be reported `branch_protected: False`. FIXED: if the repo-object
       fetch fails, or its response has no `default_branch` field, the
       protection check is skipped entirely and a `repo_check_error` is
       reported instead of guessing — proven by
       `test_repo_info_fetch_failure_skips_protection_check_without_guessing_branch`.
    2. `--strict` (documented "for wiring into a CI job") failed OPEN on
       the single worst live-check state: `branch_protected: False` never
       set `flagged`, only `uncovered_jobs` did — so a genuinely
       unprotected default branch printed to stdout but exited 0. GitLab's
       result was entirely excluded from `--strict` too (this repo's own
       primary remote is GitLab). FIXED, as a deliberate, narrow
       inclusion — NOT "flag on anything live-check-related": `--strict`
       now also trips on `branch_protected is False` (GitHub) and
       `only_allow_merge_if_pipeline_succeeds is False` (GitLab, the direct
       analogue of the incident). It deliberately does NOT trip on
       `branch_protection_check_error`/`repo_check_error` ("couldn't
       verify", most often just meaning the CI token isn't a repo admin) —
       flagging on that would make `--strict` cry wolf on most ordinary CI
       runs, the opposite of the goal. Proven by
       `test_strict_flags_on_a_genuinely_unprotected_github_branch`,
       `test_strict_does_not_flag_on_an_unverifiable_check`, and
       `test_strict_flags_on_gitlab_merge_without_pipeline_success`.
       (Side effect of this fix: running the tool live against this repo's
       own GitLab project now correctly exits 1 under `--strict` — this
       repo's GitLab project does not require pipeline success before
       merging. A real, separate finding about this repo's own GitLab
       config, surfaced to the owner outside this contract, not something
       this phase's scope covers fixing.)
    3. The required-check-to-job match was bidirectional substring
       matching (`job in context OR context in job`); the second direction
       silently under-reported `uncovered_jobs` — a required context
       `"test"` would be reported as covering an unrelated job
       `"docs-test"` merely because "test" is a substring of it. FIXED:
       replaced with `_job_covers()`, keeping only the legitimate direction
       (a job name as a whole leading word of a matrix-style context like
       `"test (3.11)"`), dropping the substring-in-job-name direction
       entirely. Proven by
       `test_job_covers_matrix_context_but_not_an_unrelated_longer_job_name`.
    Re-verified end-to-end: full local test suite (26/26 tests) passes;
    byte-compile clean; live CLI run against this repo (`--strict`) now
    exits 1 — correctly, per finding #2's side effect above, not a
    regression.
  - 2026-09-06 — round 5 review: scope-auditor PASSed (also confirmed the
    round-4 CPO ANSWER was a real recorded owner sign-off, not a
    self-approval). cto-reviewer (opus) FAILed with 4 more findings — this
    was now round 6 territory. Given the pattern of each round's fix
    creating or exposing a new issue in the same area, the owner was asked
    again how to close this out: keep narrowly patching, take the reviewer's
    own suggested minimal fix (drop job-coverage from `--strict` entirely),
    or go further and fix the underlying design gaps properly.
    **CPO ANSWER: go further (the "full fix").**
    Round 5 findings, all real, fixed:
    1. **Headline defect**: `all_job_names` was the union of every job key
       from EVERY workflow file, including `.gitlab-ci.yml`, handed to the
       GitHub check as the set its required status checks must cover.
       GitHub's `contexts` can never contain a job that only exists in
       `.gitlab-ci.yml` — so on a repo with any provider-specific job (a
       GitLab-only `deploy`, a GitHub-only `build`), `uncovered_jobs` would
       be non-empty and `--strict` would exit 1 on a CORRECTLY configured
       repo. Masked on this repo only because its one GitHub job and one
       GitLab job happen to share the name `test`. FIXED: job discovery is
       now strictly per-provider — `check_branch_protection_github` only
       ever sees jobs from GitHub workflow files, `check_branch_protection_gitlab`
       only ever sees jobs from `.gitlab-ci.yml`. Proven by
       `test_main_keeps_github_and_gitlab_job_names_separate`, which builds
       a repo with one job of each kind and asserts the GitHub check never
       even receives the GitLab job.
    2. `_job_covers()`'s round-4 narrowing (prefix-only match) also
       rejected two real GitHub context shapes: a reusable/called workflow
       context (`"ci / test"` for job `test`) and a job whose required
       context comes from an explicit `name:` field rather than its key
       (`find_job_names` only ever extracted keys). Both would produce
       spurious `uncovered_jobs`. FIXED: `_job_covers` now does a
       whole-word regex match (`(?:^|[\s/])job(?:$|[\s(/])`) that accepts
       the exact, matrix, AND reusable-workflow shapes while still
       rejecting the substring false-positive round 4 removed; a new
       `find_github_jobs()` extracts (key, `name:` field) pairs, and a new
       `_uncovered_jobs()` checks BOTH identifiers per job so a job covered
       only via its `name:` isn't also flagged uncovered under its bare
       key. Proven by `test_job_covers_reusable_workflow_context`,
       `test_find_github_jobs_captures_name_field`, and
       `test_uncovered_jobs_checks_both_key_and_name_field`.
    3. `check_branch_protection_gitlab` had no `else` for a failed initial
       project-info fetch: a 403/404/rate-limit/network failure printed as
       `{"available": true, "provider": "gitlab", ...}` with no error
       field at all — indistinguishable from "verified clean". Third
       occurrence of the exact pointwise-fix pattern (rounds 3 and 4 fixed
       this on GitHub only). FIXED: mirrors the GitHub side exactly — a
       failed fetch reports `repo_check_error` and returns early. Proven by
       `test_gitlab_repo_check_error_on_initial_fetch_failure`.
    4. `check_branch_protection_gitlab` never actually checked branch
       protection despite its name and call site — `--strict` failed
       closed on an unprotected GitHub default branch but failed OPEN on a
       completely unprotected GitLab one, on a repo whose primary remote
       IS GitLab. FIXED: added a real check against GitLab's
       `GET /projects/:id/protected_branches/:name` endpoint (404 means
       genuinely unprotected, any other failure reports
       `branch_protection_check_error`, mirroring the GitHub 404/error
       split exactly), and wired `branch_protected is False` into
       `--strict` for GitLab too. GitLab Community Edition has no per-job
       required-check list tied to protected branches the way GitHub's
       `required_status_checks.contexts` is (that's a separate,
       Premium-tier "external status checks" feature) — `job_names_found`
       is still reported for a human to read, but no `uncovered_jobs` is
       fabricated for GitLab, since claiming that coverage guarantee would
       misrepresent what was actually checked. Proven by
       `test_gitlab_branch_protection_success`,
       `test_gitlab_branch_protection_404_means_unprotected`, and
       `test_strict_flags_on_a_genuinely_unprotected_gitlab_branch`.
    Also fixed, a secondary (uncounted) finding from the same round: the
    `--strict` tests ran against this repo's own real root, so their exit
    codes accidentally depended on this repo's static scan staying clean —
    decoupled by running them against an isolated empty tempdir.
    Re-verified end-to-end: full local test suite (33/33 tests) passes;
    byte-compile clean; live CLI run against this repo now reports
    `branch_protected: true` for its real GitLab project (previously never
    checked at all) alongside the pre-existing
    `only_allow_merge_if_pipeline_succeeds: false` finding — `--strict`
    still correctly exits 1, for the right documented reason.
  - 2026-09-06 — round 6 review: scope-auditor PASSed (confirmed the
    round-5 CPO ANSWER was a distinct, real owner sign-off — not reused
    from round 4's). cto-reviewer (opus) FAILed with 4 more findings — now
    round 7 territory. The headline finding was the SAME defect class as
    round 5's #1, one abstraction level up: round 5 fixed "don't mix
    GitHub and GitLab job names", but not "don't include jobs from a
    GitHub workflow that can't run on the PR head" (release/deploy/
    schedule/dispatch-only workflows) — those jobs can never appear in
    `required_status_checks.contexts` either, so `--strict` could still
    exit 1 on a correctly configured repo. Given the recurring pattern of
    each round's fix exposing a new issue in the same specific area
    (translating GitHub/GitLab API semantics into a fail-closed gate), the
    owner was asked again — this time with an explicit, named alternative
    (drop job-coverage from `--strict` entirely, the reviewer's own
    suggestion) versus continuing to chase full correctness.
    **CPO ANSWER: keep fixing (round 7).**
    Round 6 findings, all real, fixed:
    1. **Headline defect**: `deduped_github_jobs` included every job from
       every file under `.github/workflows/`, regardless of trigger.
       FIXED: a new `_runs_on_pull_request(text)` checks a workflow's `on:`
       block for `pull_request`/`merge_group` (inline, list, and mapping-
       block forms); `main()` now only feeds a GitHub workflow's jobs into
       coverage checking when that returns True. Proven by
       `test_runs_on_pull_request_detects_inline_and_block_forms` and
       `test_main_excludes_non_pull_request_workflow_jobs_from_coverage_check`
       (a repo with a `pull_request`-triggered `ci.yml` and a
       tag-triggered `release.yml` — only `ci.yml`'s job reaches the
       GitHub check).
    2. The live-check job-discovery loop re-read every workflow file with
       an UNGUARDED `open(path).read()`, while the identical read inside
       `scan_file` (used by the static scan) was already wrapped in
       `try/except OSError`. An unreadable file or a `.yml`-named directory
       would crash `main()` with a traceback, contradicting the tool's own
       docstring ("never crashes"). FIXED: wrapped in the same
       `try/except OSError: continue`. Proven by
       `test_live_check_skips_an_unreadable_workflow_file` (a real
       directory named like a workflow file).
    3. Round 5's `_job_covers()` widening (to catch reusable-workflow
       contexts) also accepted a job name in the CALLER (workflow-name)
       position of a `"<caller> / <callee>"` context — `_job_covers("test",
       "test / build")` was `True`, treating an unrelated workflow that
       merely shares the job's name as coverage. That's the exact
       under-reporting direction round 4 deliberately removed, reintroduced
       through the widening, and it fails OPEN on the one thing
       `uncovered_jobs` exists to catch. FIXED: `_job_covers` now checks
       only the CALLEE (rightmost) segment of a `/`-separated context.
       `test_job_covers_reusable_workflow_context`'s assertion was wrong
       and is corrected to expect `False` for the caller-position case.
    4. `check_branch_protection_gitlab`'s `GET /projects/:id/protected_branches/:name`
       looks up a rule by exact name — a default branch protected only via
       a WILDCARD rule (`main*`, `re*`, `*`) has no rule literally named
       `main`, 404s, and was reported `branch_protected: False`. Same
       404-conflation class round 3 fixed on GitHub, recreated on this new
       GitLab endpoint. FIXED: switched to the LIST endpoint
       (`GET /projects/:id/protected_branches`) plus `fnmatch` against
       every returned rule name. This also simplified the error handling:
       unlike the by-name lookup, GitLab's list endpoint returns 200 with
       an empty array when nothing is protected, so a non-zero exit from
       it is NEVER a legitimate "unprotected" signal — any failure now
       unconditionally reports `branch_protection_check_error`, with no
       404-is-different special case needed at all. Proven by
       `test_gitlab_branch_protection_success_via_exact_name_rule`,
       `test_gitlab_branch_protection_success_via_wildcard_rule`,
       `test_gitlab_branch_protection_empty_rule_list_means_unprotected`,
       and `test_gitlab_branch_protection_list_failure_is_ambiguous_not_unprotected`.
    Re-verified end-to-end: full local test suite (37/37 tests) passes;
    byte-compile clean; live CLI run against this repo still correctly
    reports `branch_protected: true` (via the new wildcard-safe list
    endpoint) and `--strict` still exits 1 for the pre-existing, correct
    `only_allow_merge_if_pipeline_succeeds: false` reason.
  - 2026-09-06 — round 7 review: cto-reviewer (opus) FAILed with EXACTLY 5
    findings (reconciled explicitly here after a later review round
    correctly questioned whether this entry's original prose undercounted
    them): (1) `_job_covers` splitting on any `/` instead of the literal
    `" / "` reusable-workflow separator, colliding with matrix-context
    syntax like `"build (linux/amd64)"`; (2) `_runs_on_pull_request`
    treating a trailing `on:  # comment` as the inline trigger value and
    never reading the indented block, silently dropping that workflow's
    jobs; (3) the same function's block-matching searching for the bare
    words `pull_request`/`merge_group` anywhere in the block, including
    inside a `workflow_dispatch` input's description text; (4) the GitLab
    protected-branches LIST call having no pagination; (5) `fnmatch.fnmatch`
    case-normalizing via `os.path.normcase`, giving OS-dependent verdicts.
    Findings 1-3 were in the job-coverage-matching machinery this round's
    cut later deleted entirely — they left with it. Findings 4 and 5 were
    in the GitLab branch-protection code the cut RETAINED, and were NOT
    fixed before the cut conversation started — they survived, unfixed,
    for two more review rounds until a later round's cto-reviewer found
    them again (see below) and they finally got applied. This entry's
    original prose said "5 more findings, all in the job-coverage-matching
    area" — that was wrong for findings 4 and 5, and is corrected here.
    The reviewer's own writeup also noted that some of round 7's own fixes
    had "moved, not removed" bugs from earlier rounds. This was the third
    round-cap escalation in a row on the same feature area. Rather than ask
    the owner to approve a round 8, the owner instead asked the more
    fundamental question: does job-coverage matching belong in this tool at
    all, and is a stdlib-only regex approach to YAML even the right tool?
    A first pass (mine) proposed adding a YAML-parsing dependency (PyYAML)
    to fix the recurring syntax-edge-case bugs. The owner correctly
    rejected this as unverified, un-authoritative reasoning and asked for
    an independent second opinion instead — a fresh subagent, with no
    prior involvement, given the full bug history from this file and asked
    for its own opinionated recommendation.
    That independent review's finding: of the ~11 defects across rounds
    4-6, only ~2 were genuine YAML-syntax bugs a real parser would fix; the
    other ~9 were API-semantics/matching-policy judgment calls (GitLab
    wildcard rules, 403-vs-404 conflation, caller/callee position, provider
    mixing, `--strict` polarity) that a YAML parser does not address at
    all. It also identified a NEW landmine in the PyYAML proposal itself:
    in YAML 1.1, a bare `on:` key parses as the boolean `True`, which would
    have broken `_runs_on_pull_request` in yet another way. Its verdict:
    the feature asks a question a generic tool cannot correctly answer —
    "does the required-checks list cover every job that matters" presumes
    every job SHOULD be required, which is a project-specific judgment
    (conditional jobs, path-filtered jobs, deploy-only jobs, matrix jobs
    all legitimately may not need to be required) that cannot be correctly
    inferred from parsing arbitrary YAML. Recommendation: delete the
    job-coverage-matching feature entirely; keep the static scan (stable
    for all 7 rounds) and the directly-answerable API facts (branch
    protected y/n, auto-merge enabled y/n, GitLab's
    only_allow_merge_if_pipeline_succeeds y/n); print the required-checks
    list verbatim for a human to judge instead of evaluating it.
    **CPO ANSWER: make the cut.** (The owner also gave direct, pointed
    feedback in this session about the review pattern itself — recorded in
    the global memory store as `technical-authority-vs-avoidance.md` —
    which is the reason this decision went through an independent second
    opinion rather than another self-directed fix-and-re-review cycle.)
    Cut from `scripts/audit_ci_automation.py` (561 → 407 lines):
    `_GITLAB_RESERVED_KEYS`, `find_job_names`, `find_github_jobs`,
    `_runs_on_pull_request`, `_job_covers`, `_uncovered_jobs`, the
    per-provider job-discovery loop in `main()`, and `uncovered_jobs` from
    both the printed result and `--strict`'s flagging logic.
    `check_branch_protection_github`/`_gitlab` no longer take a jobs
    parameter at all. `required_checks` (GitHub) is still printed verbatim.
    Cut from `.claude/tests/test_audit_ci_automation.py` (37 → 29 tests):
    every job-coverage-specific test (`test_find_job_names_*`,
    `test_find_github_jobs_*`, `test_job_covers_*`,
    `test_uncovered_jobs_*`, `test_runs_on_pull_request_*`,
    `test_main_keeps_github_and_gitlab_job_names_separate`,
    `test_main_excludes_non_pull_request_workflow_jobs_from_coverage_check`,
    `test_live_check_skips_an_unreadable_workflow_file` — the last of
    these tested a guard in the job-discovery loop, which no longer
    exists). Remaining tests that called the two check functions with a
    now-removed jobs argument were updated to the new single-argument
    signature; `test_branch_protection_success_reports_uncovered_jobs_and_makes_two_api_calls`
    renamed to `..._reports_required_checks_and_makes_two_api_calls` and
    now asserts the printed list instead of a computed coverage verdict.
    `templates/ci-audit/ci_automation_audit.py` required NO changes — it
    was always static-scan-only and never had job-coverage logic.
    Re-verified end-to-end: full local test suite (29/29 tests) passes;
    byte-compile clean; live CLI run against this repo unchanged in its
    real findings (`branch_protected: true`,
    `only_allow_merge_if_pipeline_succeeds: false`, `--strict` still
    exits 1 for the same correct reason) — confirms the cut removed
    complexity, not correctness.
  - 2026-09-06 — review of the cut: scope-auditor PASSed (confirmed the
    cut was a real, recorded owner decision and the removal was clean, no
    stale references). cto-reviewer (opus) FAILed with 2 findings — both
    in code the cut RETAINED, not the deleted job-coverage area (worth
    noting explicitly: this is not a re-entry into the pattern that caused
    the 7-round loop). Both real, fixed:
    1. **Zero test coverage on `--strict`'s primary trigger**: every
       `--strict` test ran against an empty `tempfile.TemporaryDirectory()`,
       so `findings` was always `[]` in all of them — the line that makes
       `--strict` exit 1 when the STATIC SCAN finds the actual incident
       shape (`flagged = True` on a finding) could be deleted and all 29
       tests would still pass. Same standard this repo has applied since
       Phase 3 ("a pin that never fired isn't a pin"). FIXED:
       `test_strict_exits_nonzero_on_the_actual_incident_shape` writes a
       real dangerous workflow to a tempdir and asserts `--strict` exits 1;
       `test_dangerous_finding_without_strict_still_exits_zero` proves the
       "advisory by default" promise in the module docstring the other
       direction (finding present, no `--strict`, still exits 0).
    2. **GitHub rulesets false negative**: `GET repos/{slug}/branches/{branch}/protection`
       reports CLASSIC branch protection only. A branch protected solely
       via GitHub's newer ruleset mechanism (the current default
       recommendation for new orgs) has no classic rule, so this endpoint
       404s — and the code treated any 404 as "genuinely unprotected",
       same as classic-protection-absent. That misreports a correctly
       ruleset-protected repo as unprotected, tripping `--strict` on a
       correctly configured repo. Same defect class as round 6's GitLab
       wildcard-rule finding (a protection mechanism the queried endpoint
       can't see, misreported as absent), recreated on GitHub, inside
       retained "print a single API fact" code — not the deleted
       job-coverage-judgment logic. FIXED: on a classic-protection 404,
       also queries `GET repos/{slug}/rules/branches/{branch}` (reports
       rulesets actually in effect for that branch, not admin-gated); a
       non-empty rules list means protected, an empty one means genuinely
       unprotected, and a failure of THIS check reports
       `branch_protection_check_error` rather than assuming unprotected —
       same "ambiguous stays ambiguous" discipline as every other check in
       this file. Proven by
       `test_branch_protection_404_and_no_ruleset_means_genuinely_unprotected`,
       `test_branch_protection_404_but_a_ruleset_covers_it_is_still_protected`,
       and `test_branch_protection_404_and_ruleset_check_itself_fails_is_ambiguous`.
    Noted by cto-reviewer as out-of-scope, not blocking: `.claude/hooks/__pycache__/*.pyc`
    is tracked despite `.gitignore` (pre-existing, unrelated to this diff —
    the long-deferred cleanup item already on this repo's own handover
    notes); `--provider` without `--slug` is silently ignored (cosmetic);
    GitHub's `required_checks` isn't cross-checked against `--strict` the
    way GitLab's pipeline-success flag is — a real asymmetry, but squarely
    inside the owner-approved "print, don't judge" cut, not re-litigated.
    Re-verified end-to-end: full local test suite (33/33 tests) passes;
    byte-compile clean; live CLI run against this repo unchanged in its
    real findings.
  - 2026-09-06 — review of the rulesets fix: scope-auditor PASSed.
    cto-reviewer (opus) FAILed with 3 findings, all in the GitLab
    branch-protection check — the reviewer explicitly noted the first two
    were the SAME defects already recorded at this file's own round-7 entry
    ("`fnmatch` gave different answers on Windows vs Linux"; GitLab list
    pagination) which never actually got applied: round 7's fix cycle was
    interrupted by the "does this belong in the kit" conversation and the
    eventual cut, and while the cut correctly removed the job-coverage code
    those two round-7 findings named, it left the GitLab branch-protection
    code — which the cut RETAINED — carrying the same two unfixed bugs
    forward. A real miss: when cutting a feature, still need to check
    whether earlier findings on RETAINED code paths were left dangling.
    All 3 findings, fixed:
    1. **fnmatch case-sensitivity** (the round-7 finding, now actually
       applied): `fnmatch.fnmatch` case- and separator-normalizes via
       `os.path.normcase` — identity on POSIX, lowercasing on Windows — so
       the same GitLab project's `branch_protected` verdict (and `--strict`
       exit code) differed by the OS the audit happened to run on.
       Confirmed empirically on this machine before fixing:
       `fnmatch.fnmatch('main', 'Main')` is `True` here,
       `fnmatch.fnmatchcase('main', 'Main')` is `False` — the fix is real,
       not cosmetic. FIXED: switched to `fnmatch.fnmatchcase`. Proven by
       `test_gitlab_wildcard_match_is_case_sensitive`, which would fail
       under the old `fnmatch.fnmatch` on this machine (verified directly,
       not just asserted).
    2. **GitLab list-endpoint pagination** (the other round-7 finding, now
       actually applied): the protected-branches LIST call had no
       `per_page`, so GitLab's default page size (20) could silently
       truncate the response — a project with more protection rules than
       that could have its default-branch rule fall off the first page,
       misreporting a protected project as unprotected and tripping
       `--strict` on a correctly configured repo. FIXED: added
       `?per_page=100` (GitLab's max) to the request. Proven by
       `test_gitlab_protected_branches_request_paginates`, which asserts
       the actual URL requested, not just the outcome.
    3. **A genuinely new finding**: `_safe_json_array` collapsed "this
       response isn't a JSON array at all" into the same `[]` as "this is
       a genuinely empty array" — so an unparseable 200 response (wrong
       shape, unexpected wrapper object) silently became "confirmed
       unprotected" instead of "couldn't verify", the one place in this
       file where an unparseable answer resolved to a confirmed gap
       instead of staying ambiguous (contradicting every other check in
       this file, all built around "ambiguous stays ambiguous"). The same
       collapse existed in the new GitHub rulesets check too (same helper).
       FIXED: replaced `_safe_json_array` with `_parsed_json_array`, which
       returns `None` (not `[]`) when the response doesn't parse as an
       array, so callers can distinguish and report
       `branch_protection_check_error` instead of assuming unprotected.
       Applied at both call sites (GitHub rulesets, GitLab protected-
       branches list). Proven by
       `test_branch_protection_404_and_rulesets_response_not_an_array_is_ambiguous`
       and `test_gitlab_branch_protection_unparseable_response_is_ambiguous`.
    Re-verified end-to-end: full local test suite (37/37 tests) passes;
    byte-compile clean; live CLI run against this repo unchanged in its
    real findings (this repo's real GitLab protection rule is presumably
    lowercase, so the case-sensitivity fix doesn't change its own result).
  - 2026-09-06 — review of the fnmatch/pagination fix: scope-auditor
    PASSed and confirmed no other pre-cut findings on retained code were
    left dangling. cto-reviewer (opus) FAILed with 3 more findings, all
    real, fixed:
    1. **The case-sensitivity test's own pin was vacuous where it
       actually runs.** `test_gitlab_wildcard_match_is_case_sensitive`
       used rule `"Main"` vs branch `"main"` and asserted `branch_protected
       is False` — but `os.path.normcase` (what `fnmatch.fnmatch` calls) is
       a no-op on POSIX, so `fnmatch.fnmatch('main', 'Main')` is ALREADY
       `False` on Linux. Confirmed empirically before fixing (see the
       Bash output in this session: `fnmatch.fnmatch` under a simulated
       POSIX `normcase` returns `False`). Both this repo's CI runners are
       Linux (`.github/workflows/ci.yml`, `.gitlab-ci.yml`), so the test
       passed identically whether the code used `fnmatch.fnmatch` or
       `fnmatch.fnmatchcase` — the ONE guard against silently reverting the
       fix was green under both the bug and the correct code, everywhere
       it's actually executed. This repo's own Phase 3 standard, quoted in
       this very file: "a pin that never fired isn't a pin." FIXED: the
       test now monkeypatches `os.path.normcase = str.lower` for its
       duration — forcing the Windows-shaped normalization regardless of
       host OS — so `fnmatch.fnmatchcase` (which never calls `normcase` at
       all) stays correctly case-sensitive under the patch while
       `fnmatch.fnmatch` would not. Verified empirically both ways before
       committing to this design (see Bash output in this session).
    2. **`?per_page=100` raised the truncation threshold, it didn't remove
       it.** A project with MORE than 100 protected-branch rules still gets
       a truncated single page; if none of the returned names match, the
       code was concluding `branch_protected: False` — a CONFIRMED gap —
       when the true answer might be on a page never fetched. Recreated the
       exact ambiguity-collapse class this file has fixed repeatedly.
       FIXED: a full page (`len(rules) >= 100`, the page-size limit) with
       no match now reports `branch_protection_check_error` instead of
       `branch_protected: False`; only an INCOMPLETE page with no match is
       treated as a genuine "checked everything, found nothing." Proven by
       `test_gitlab_full_page_with_no_match_is_ambiguous_not_unprotected`.
    3. **Documentation accuracy**: the round-7 amendment entry above
       (originally written before the cut) said "5 more findings, all in
       the job-coverage-matching area" — wrong for 2 of the 5 (pagination
       and `fnmatch`, both in retained branch-protection code, not the
       deleted job-coverage machinery). Corrected in place with an explicit
       enumeration of all 5 findings and which of them the cut actually
       resolved vs. which survived unfixed until this and the prior review
       round caught them.
    Re-verified end-to-end: full local test suite (38/38 tests) passes;
    byte-compile clean; live CLI run against this repo unchanged in its
    real findings.
  - 2026-09-06 — review of the truncation-ambiguity fix: scope-auditor
    PASSed. cto-reviewer (opus) FAILed with a headline structural finding
    plus 2 secondary ones — this time explicitly asked to step back from
    fixing individual findings and check for a systemic problem still
    being papered over, given the file's own history of pointwise fixes
    recurring. It found one, and it was real:
    1. **Headline**: `_detect_remotes` had ZERO test coverage — the sole
       input to `--strict` on this tool's default, documented invocation
       (no `--slug`) — and `main()` OR'd every detected remote's verdict
       into `flagged`. In a fork checkout (`origin` = a personal fork,
       `upstream` = the canonical repo — an extremely common topology), the
       fork's near-universally-unprotected default branch would trip
       `--strict` on a project that isn't actually misconfigured. Same
       "cry wolf on a correct repo" class fixed pointwise in rounds 4, 5,
       6 and the ruleset/pagination rounds, now found in the one function
       nobody had ever tested. FIXED, and the fix was revised once during
       implementation: the first draft tried "trust the remote named
       'origin' when there are several" — but this repo's OWN two remotes
       are the exact counterexample (`origin` here is the less-relevant,
       unauthenticated one; `gitlab` is the actual active remote from this
       session's own GitLab migration), so preferring `origin` by name
       would have been a second wrong guess replacing the first. Final
       design: with exactly one detected remote it unambiguously governs
       `--strict`; with more than one, NONE of them does automatically —
       all are still printed (marked "informational only, does not affect
       --strict") — and `--slug`/`--provider` is the required disambiguator,
       the same principle already established for that flag pair. Verified
       live against this repo itself: `python scripts/audit_ci_automation.py
       --strict` (no `--slug`, two real remotes) now exits 0 with both
       remotes printed as informational, where it would previously have
       exited 1 based on whichever remote's check happened to run;
       `--slug rami.al-fahham/claude-guardrails --provider gitlab --strict`
       still correctly exits 1 for the real, pre-existing
       `only_allow_merge_if_pipeline_succeeds: false` reason. Proven by 4
       new direct tests against `_detect_remotes` using a REAL git repo
       (`git init` + `git remote add`, not mocked — the function shells out
       to real `git`) plus 3 new `main()`-level tests for the
       single-remote/multiple-remote/explicit-`--slug` cases.
    2. GitHub's rulesets call (paginated, like GitLab's protected-branches
       list) had neither `per_page` nor a truncation guard, while the
       structurally similar GitLab call had just gotten both — "fix
       applied to one of two similar call sites" being exactly the pattern
       that produced the rounds 3→4→5 loop. Investigated rather than
       reflexively copying the GitLab fix: GitHub's endpoint reports rules
       ALREADY MATCHED to the specific branch server-side (unlike GitLab's
       "return every rule, match client-side"), so an empty first page
       reliably means zero total rules regardless of page size — no
       truncation-ambiguity case exists here the way it does for GitLab.
       Added `?per_page=100` anyway for hygiene/consistency and documented
       IN THE CODE why no additional guard is needed, rather than leaving
       the asymmetry unexplained.
    3. The rulesets check-failure error message discarded stderr and
       therefore never included an HTTP status, unlike every other
       `*_check_error` string in the file. FIXED: now captures and
       includes it.
    Re-verified end-to-end: full local test suite (44/44 tests) passes;
    byte-compile clean.
  - 2026-09-06 — review of the primary-remote fix: scope-auditor PASSed.
    cto-reviewer (opus) FAILed with 3 findings, all real, fixed:
    1. **Reinvented a pattern this repo already has, on a factually wrong
       justification**: the new `_init_repo_with_remotes` test helper used
       `tempfile.mkdtemp()` + `shutil.rmtree(ignore_errors=True)`, with a
       comment claiming a context manager "can't give a concrete path
       up front" — false, and this repo's own
       `.claude/tests/test_commit_review_gate.py` and `test_secret_scan.py`
       already `git init` inside `with tempfile.TemporaryDirectory()`.
       Real consequences: `ignore_errors=True` silently swallowed cleanup
       failures; `check=True` raising on a git failure would leak the
       tempdir AND abort the whole test file (the `__main__` runner only
       catches `SkipTest`/`AssertionError`); no `timeout=` unlike this
       repo's own `_git` helper (which has one). FIXED: replaced with a
       `_git(repo, *args)` helper copied from the established pattern
       (`cwd=`, `check=True`, `capture_output=True`, `timeout=30`) plus an
       `_add_remotes(repo, remotes)` helper, both used inside
       `with tempfile.TemporaryDirectory()` in every affected test.
    2. **Doc-sync**: the module Usage block and the `--slug`/`--strict`
       `--help` text still said only "exit 1 if anything is flagged" with
       no mention that the live check is now informational-only whenever
       more than one remote is detected — on a dual-remote checkout (this
       repo's own topology), `--strict`'s live half is permanently inert
       on the documented default invocation, and the CLI's own
       documentation didn't say so. Same stale-help-text defect class as
       round 1 finding #9. FIXED: both the module docstring and the
       `--slug`/`--strict` argparse help strings now state the rule and
       point at `--slug` as the escape hatch. Verified via
       `python scripts/audit_ci_automation.py --help`.
    3. **Unanchored host match**: `re.search(r"github\.com[:/]...")` (and
       the GitLab equivalent) had no left boundary on the host, so a host
       merely ENDING in that string (e.g. `mygithub.com`) would match —
       and if that were the repo's only detected remote, an unrelated
       project's slug would become the sole, unambiguous input to
       `--strict`, misreporting a correctly configured repo based on
       someone else's settings. FIXED: anchored with `(?:^|[@/])` before
       the host on both regexes. Proven by
       `test_detect_remotes_requires_a_host_boundary`.
    Re-verified end-to-end: full local test suite (45/45 tests) passes;
    byte-compile clean; live CLI run against this repo unchanged in
    behavior (still correctly prints both remotes as informational-only
    and exits 0 without `--slug`); `--help` output now documents the
    multi-remote rule.
