#!/usr/bin/env python
"""SessionStart hook TEMPLATE — advisory-only static CI-automation scan.

`scripts/generate_project_setup.py` copies this into a project's
`.claude/hooks/` and wires it as a `SessionStart` hook whenever the
`/setup-project` interview is given a CI provider (GitHub or GitLab) — see
that script's `_prepare_ci_audit_hook_settings`. If a project skips the
interview (plain `bootstrap.sh` only) or answers "not decided yet" for CI
provider, this file is never copied and stays purely template content, same
as the rest of `templates/`. Once wired, it prints a non-blocking context
note at the start of a session if any `.github/workflows/*.yml` or
`.gitlab-ci.yml` file combines a schedule/dispatch trigger with an
auto-merge action — the actual shape of a real incident (see
`scripts/audit_ci_automation.py` in `claude-project-kit` for the full
writeup and the heavier, deliberately-run tool this is a lightweight
cousin of).

Deliberately STATIC-SCAN ONLY — no `gh`/`glab` live API calls here. A
`SessionStart` hook runs on every session; a live check needs auth and a
network round-trip, which belongs in a tool you run on purpose
(`scripts/audit_ci_automation.py`), not something that fires silently every
time a session opens.

The trigger/action pattern lists below are a DELIBERATE COPY of
`scripts/audit_ci_automation.py`'s (not an import — this file must stand
alone once copied into a different repo). Keep them in sync by hand;
`.claude/tests/test_audit_ci_automation.py`'s
`test_template_and_script_pattern_lists_have_not_drifted` is the parity
test that catches drift between the two copies.

Fails OPEN: any error, including this file's own `_command_utils` import
failing (e.g. copied without its sibling), exits 0 with no output, same as
every hook here.
"""

from __future__ import annotations

import glob
import os
import re
import sys

_TRIGGER_PATTERNS = [
    ("GitHub schedule trigger", re.compile(r"^\s*schedule\s*:", re.MULTILINE)),
    ("GitHub workflow_dispatch trigger", re.compile(r"\bworkflow_dispatch\s*:")),
    ("GitHub repository_dispatch trigger", re.compile(r"\brepository_dispatch\s*:")),
    ("GitLab schedule pipeline source",
     re.compile(r'\$CI_PIPELINE_SOURCE\s*==\s*"schedule"')),
]

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


def _repo_root() -> str:
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


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
    try:
        text = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return None
    triggers = _matches(_TRIGGER_PATTERNS, text)
    actions = _matches(_AUTOMERGE_PATTERNS, text)
    if triggers and actions:
        return {"file": path, "triggers": triggers, "actions": actions}
    return None


def main() -> int:
    try:
        # Imported here, not at module level: this file needs `_command_utils`
        # only once it's actually sitting next to it in a project's
        # `.claude/hooks/` (see module docstring). Deferring the import means
        # the pure scanning functions above stay importable and testable on
        # their own, without needing that sibling file to be resolvable
        # first — and keeping it inside this `try` means a copy dropped
        # somewhere without its sibling fails open instead of raising.
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from _command_utils import emit_context

        root = _repo_root()
        findings = [f for f in (scan_file(p) for p in _iter_workflow_files(root)) if f]

        if findings:
            names = ", ".join(os.path.relpath(f["file"], root) for f in findings)
            emit_context(
                "SessionStart",
                f"CI-AUTOMATION AUDIT: {names} combine a schedule/dispatch trigger "
                "with what looks like an auto-merge action — the shape that once "
                "let PRs merge before their build finished. Run "
                "`python scripts/audit_ci_automation.py` for the full picture "
                "(including a live branch-protection check) before trusting it."
            )
    except Exception:
        pass  # fail open — including a bad relpath or a broken emit_context
    return 0


if __name__ == "__main__":
    sys.exit(main())
