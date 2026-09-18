#!/usr/bin/env python
"""Dry-run preview for the `setup-project` interview — Phase 6a of
`claude-project-kit`.

Given structured interview answers (never free-text inference — see below),
computes and prints what a real project setup WOULD generate: which reviewer
modules from `templates/reviewers/` would be selected, what their composed
`review_routing.json` would look like, the guard-paths preview, each
module's model tier, and the naming-lint result on each selected module.

Writes NOTHING to any target project, ever. No code path in this file opens
a file in any write mode ("w", "a", "x", or "+") — this is a preview tool
only. Phase 6b (a separate, later contract) is where actual file generation
for a target project happens. (Running this file as Python does create the
interpreter's own `__pycache__/*.pyc` bytecode cache next to it, like any
Python script — gitignored, not a write to any project's tracked content;
"writes nothing" refers to project files, not interpreter bytecode.)

Deliberately does NOT try to infer anything from unstructured text (a scope
document, a repo tree, free-form prose). An earlier phase of this kit
(`scripts/audit_ci_automation.py`'s job-coverage-matching feature, since
deleted — see `.claude/task/contract.md`'s amendments log for that phase)
tried exactly that kind of inference and produced a long, non-converging
series of correctness bugs across many review rounds. Selection here is a
pure function of a small set of yes/no/enum answers; the ONE free-text
field (`unmatched_stack_description`) is never parsed or acted on — it only
becomes a plain escalation note for a human to read.

Usable as a library (`build_preview`) or a CLI:
  python scripts/preview_project_setup.py --dbt
  python scripts/preview_project_setup.py --data-eng --frontend --sensitive-data
  python scripts/preview_project_setup.py --ci-provider gitlab

`SetupAnswers.unmatched_stack_description` has NO CLI flag — deliberately.
The `.claude/skills/setup-project/SKILL.md` interview must never embed a
user's free-text answer into a shell command line (a real command-injection
finding on an earlier draft of that skill); removing the flag here makes
that structurally impossible rather than relying on the skill's own prose
to avoid it. Construct a `SetupAnswers` directly in Python if you need this
field for something other than the interview's own note-taking.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPTS_DIR)
_REVIEWERS_DIR = os.path.join(_REPO_ROOT, "templates", "reviewers")
_FRAGMENTS_DIR = os.path.join(_REVIEWERS_DIR, "routing")

sys.path.insert(0, _SCRIPTS_DIR)
import compose_routing  # noqa: E402
import lint_reviewer_name  # noqa: E402

# The guard-path-routed reviewer for a NEW project is always platform-reviewer
# (applies_when: [always], so it's selected for every project) — same name
# this kit's own self-governance copy now uses too (the old cto-reviewer.md
# legacy name was retired; see active_work.md history). scope-auditor is
# exempted for the same reason it's exempted in this kit's own guard-paths.md:
# it's the one reviewer required on every commit regardless of path, so
# escalating it would multiply cost for the highest-frequency reviewer.
_GUARD_PATH_REVIEWER = "platform-reviewer"
_EXEMPTED_REVIEWER = "scope-auditor"

# The composition base for a NEW project — deliberately NOT this kit's own
# shipped .claude/review_routing.json. A new project starts from just the
# universal "scope-auditor always runs" rule; everything else comes from the
# selected modules' own routing fragments.
_BASE_ROUTING: dict = {
    "always": ["scope-auditor"],
    "paths": {},
}

_APPLIES_WHEN_RE = re.compile(r"^applies_when:\s*\[([^\]]*)\]", re.MULTILINE)
_MODEL_RE = re.compile(r"^model:\s*(\S+)", re.MULTILINE)

_PROVIDER_DISPLAY_NAME = {"github": "GitHub", "gitlab": "GitLab"}  # str.title() gives
# "Gitlab"/"Github", not the real product names — shared here so every caller (the preview
# notes, the rendered starter README) gets consistent, correct capitalization.

_TAG_TO_ANSWER_FIELD = {
    "dbt": "dbt",
    "data-eng": "data_eng",
    "frontend": "frontend",
    "sensitive-data": "sensitive_data",
}


@dataclass(frozen=True)
class SetupAnswers:
    dbt: bool = False
    data_eng: bool = False
    frontend: bool = False
    sensitive_data: bool = False
    ci_provider: str = "none"  # "github" | "gitlab" | "none"
    tracker_provider: str = "none"  # "github" | "gitlab" | "none"
    process_tier: str = "standard"  # "solo" | "standard"
    unmatched_stack_description: str = ""  # "" means no unmatched-stack escalation


def selected_tags(answers: SetupAnswers) -> set[str]:
    """Pure: answers -> the set of `applies_when` tags this project has,
    plus 'always' (every project gets the always-on modules)."""
    tags = {"always"}
    for tag, field_name in _TAG_TO_ANSWER_FIELD.items():
        if getattr(answers, field_name):
            tags.add(tag)
    return tags


def _module_frontmatter(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        content = f.read()
    parts = content.split("---", 2)
    return parts[1] if len(parts) >= 3 else ""


class MalformedModuleError(ValueError):
    """A file in `templates/reviewers/` that `_files_from_dir` treats as a
    module candidate has no parseable `applies_when` frontmatter field. An
    earlier version silently mapped this to `tags: []` (module excluded
    from every project, indistinguishable from "correctly has no matching
    tag") — exactly the "fail quietly on a parse miss" pattern this file's
    own module docstring calls out as the cause of a deleted, non-converging
    Phase 5 feature. A genuine parse miss here must be loud, not silent."""


# templates/reviewers/README.md documents the library (see its own content)
# and is not a reviewer module, but lint_reviewer_name._files_from_dir has
# no way to tell — it only filters by ".md" extension and a leading "_".
# Excluded here BY NAME, deliberately, rather than relying on it having no
# `applies_when` field to parse (that used to be how it was excluded, which
# made a real parse failure on an actual module indistinguishable from this
# expected case).
_NON_MODULE_FILES = {"README"}


def load_module_tags(reviewers_dir: str = _REVIEWERS_DIR) -> dict[str, list[str]]:
    """{module_name: [applies_when tags]} for every real module in
    `reviewers_dir` (skips `_`-prefixed drafts/skeletons and `README`, same
    convention as `lint_reviewer_name._files_from_dir` plus the one
    non-module exception it can't itself detect). Best-effort regex, not a
    YAML parser — matches this repo's zero-dependency policy; every shipped
    module's frontmatter is hand-authored in the one-line `[tag]` shape this
    matches. Raises `MalformedModuleError` (loud) rather than mapping a
    parse miss to an empty tag list (silent, and indistinguishable from a
    module that legitimately matches nothing)."""
    result = {}
    for path in lint_reviewer_name._files_from_dir(reviewers_dir):
        name = os.path.basename(path)[: -len(".md")]
        if name in _NON_MODULE_FILES:
            continue
        frontmatter = _module_frontmatter(path)
        m = _APPLIES_WHEN_RE.search(frontmatter) if frontmatter else None
        if not m:
            raise MalformedModuleError(
                f"{name}.md has no parseable 'applies_when: [...]' frontmatter field")
        tags = [t.strip() for t in m.group(1).split(",") if t.strip()]
        if not tags:
            raise MalformedModuleError(f"{name}.md's applies_when field is empty")
        result[name] = tags
    return result


def select_reviewer_modules(answers: SetupAnswers,
                             reviewers_dir: str = _REVIEWERS_DIR) -> list[str]:
    """Deterministic: a module is included iff it has the 'always' tag, or
    any of its tags is in `selected_tags(answers)`. No scoring, no
    inference — every inclusion traces to one matching tag. Returns names
    sorted for a stable, diffable preview."""
    tags = selected_tags(answers)
    module_tags = load_module_tags(reviewers_dir)
    return sorted(
        name for name, mtags in module_tags.items()
        if "always" in mtags or tags.intersection(mtags)
    )


def build_routing_preview(module_names: list[str],
                           base_routing: dict = _BASE_ROUTING,
                           fragments_dir: str = _FRAGMENTS_DIR) -> dict:
    """The composed review_routing.json a new project would get, via the
    REAL compose_routing.compose() — this function adds no merge logic of
    its own, only loads each selected module's fragment file."""
    fragments = {}
    for name in module_names:
        frag_path = os.path.join(fragments_dir, f"{name}.routing.json")
        fragments[name] = compose_routing.load_json_strict(frag_path)
    return compose_routing.compose(base_routing, fragments)


class EmptyGuardPathsError(ValueError):
    """`platform-reviewer` is `applies_when: [always]`, so it is selected —
    and therefore routed to at least its own fragment's paths — for every
    possible answer set; a `routing_preview` that routes nothing to it is
    not a normal "small project" case, it means something upstream is
    broken (an empty/corrupted fragment file, or a caller that composed the
    wrong reviewer's routing). An earlier version silently degraded to
    `escalate_reviewer: None` here, producing a meaningless preview line
    ("escalate None to opus on 0 guard path(s)") instead of surfacing the
    real problem — the same "fail quietly on a miss" pattern
    `load_module_tags` was fixed to avoid; this function must hold the same
    standard."""


def build_guard_paths_preview(routing_preview: dict) -> dict:
    """The guard-paths.md a new project would get: derived DIRECTLY from
    the composed routing preview itself — the exact paths
    `_GUARD_PATH_REVIEWER` (`platform-reviewer`) is actually routed to —
    never a second, independently-sourced list. `templates/rules/
    guard-paths.md.tmpl` says this in as many words: "REPLACE with this
    project's actual guard paths — the routing entries pointing at
    whichever reviewer(s) own platform/CI/hooks/governance concerns."

    (This kit's OWN shipped `.claude/rules/guard-paths.md` currently
    disagrees with `templates/reviewers/routing/platform-reviewer.routing.json`
    on which paths are covered — a real, pre-existing drift between this
    kit's own dogfooded rule file and the reviewer-module library meant to
    succeed it. That's a defect in those two files, not in this function;
    fixing it means editing one of them, both outside this contract's
    scope_paths, so it's reported to the owner separately rather than
    addressed — or silently worked around — here.)"""
    guard_paths = sorted(
        pattern for pattern, reviewers in routing_preview.get("paths", {}).items()
        if _GUARD_PATH_REVIEWER in reviewers
    )
    if not guard_paths:
        raise EmptyGuardPathsError(
            f"no path in the given routing preview routes to "
            f"{_GUARD_PATH_REVIEWER!r} — it is applies_when: [always], so "
            "this should never legitimately be empty"
        )
    return {
        "guard_paths": guard_paths,
        "escalate_reviewer": _GUARD_PATH_REVIEWER,
        "exempted": _EXEMPTED_REVIEWER,
    }


def build_model_tiers(module_names: list[str],
                       reviewers_dir: str = _REVIEWERS_DIR) -> dict[str, str]:
    """{module_name: its ACTUAL `model:` frontmatter value} — read from the
    real file, never hardcoded, so a future frontmatter change surfaces
    here automatically."""
    result = {}
    for name in module_names:
        path = os.path.join(reviewers_dir, f"{name}.md")
        frontmatter = _module_frontmatter(path)
        m = _MODEL_RE.search(frontmatter)
        result[name] = m.group(1) if m else "(unknown)"
    return result


def build_naming_lint_report(module_names: list[str],
                              reviewers_dir: str = _REVIEWERS_DIR) -> dict:
    """{module_name: (denylist_hits, mismatch_or_None)} via the REAL
    lint_reviewer_name.check_file — never a reimplementation of the naming
    rule."""
    result = {}
    for name in module_names:
        path = os.path.join(reviewers_dir, f"{name}.md")
        _, hits, mismatch = lint_reviewer_name.check_file(path)
        result[name] = {"denylist_hits": hits, "mismatch": mismatch}
    return result


def build_escalations(answers: SetupAnswers) -> list[str]:
    """[] normally. One entry if `unmatched_stack_description` is set —
    this is a PASS-THROUGH note only: nothing is drafted, slugged, or
    lint-checked against it in this phase. Drafting from
    `templates/reviewers/_skeleton.md` is Phase 6b/generation work."""
    if not answers.unmatched_stack_description.strip():
        return []
    return [
        "Unmatched stack reported: "
        f"{answers.unmatched_stack_description.strip()!r} — this phase does not "
        "draft a reviewer for it. A future setup would start from "
        "templates/reviewers/_skeleton.md and require a human read-through "
        "before use."
    ]


def build_preview(answers: SetupAnswers) -> dict:
    """Assembles every preview section into one dict — the single source of
    truth both the tests and `format_preview`/the CLI render from. Raises
    ValueError (not a bare KeyError from a display-name lookup) for an
    unrecognised `ci_provider`/`tracker_provider`/`process_tier` — the CLI's
    own `choices=` already prevents this from argv, but a direct
    `SetupAnswers` caller (tests, another script) gets a clear message
    instead of an opaque crash deep in dict indexing."""
    for field_name, value, allowed in (
            ("ci_provider", answers.ci_provider, {"github", "gitlab", "none"}),
            ("tracker_provider", answers.tracker_provider, {"github", "gitlab", "none"}),
            ("process_tier", answers.process_tier, {"solo", "standard"})):
        if value not in allowed:
            raise ValueError(f"answers.{field_name}={value!r} is not one of {allowed}")
    module_names = select_reviewer_modules(answers)
    routing_preview = build_routing_preview(module_names)
    return {
        "answers": {
            "dbt": answers.dbt,
            "data_eng": answers.data_eng,
            "frontend": answers.frontend,
            "sensitive_data": answers.sensitive_data,
            "ci_provider": answers.ci_provider,
            "tracker_provider": answers.tracker_provider,
            "process_tier": answers.process_tier,
        },
        "selected_modules": module_names,
        "model_tiers": build_model_tiers(module_names),
        "naming_lint": build_naming_lint_report(module_names),
        "routing_preview": routing_preview,
        "guard_paths_preview": build_guard_paths_preview(routing_preview),
        "escalations": build_escalations(answers),
        "ci_provider_note": (
            "Generation will install templates/ci-audit/ci_automation_audit.py "
            "into .claude/hooks/ and wire it as a SessionStart hook — an "
            "advisory-only scan for a workflow that combines a schedule/"
            "dispatch trigger with an auto-merge action. Does not change "
            "which reviewer modules are selected (the shipped routing "
            "fragments already cover both GitHub and GitLab paths)."
            if answers.ci_provider != "none" else
            "No CI provider given — the CI-automation-audit hook needs one "
            "to install, so nothing is wired for this project."
        ),
        "tracker_provider_note": (
            f"Roadmap tracking will point at "
            f"{_PROVIDER_DISPLAY_NAME[answers.tracker_provider]} Issues in the "
            "starter README — the roadmap is never a markdown file in this project."
            if answers.tracker_provider != "none" else
            "No tracker given — the starter README will say to name one before "
            "tracking any backlog, rather than defaulting to a roadmap file."
        ),
        "process_tier_note": (
            "Solo tier: generation converts working-agreement.md to a lightweight "
            "version (no mandatory task contract for routine changes, no ADR "
            "requirement) if it's recognised (any released standard or Solo vintage) "
            "or missing — but an unrecognised (hand-customized) file REFUSES the "
            "entire generation, not just that one file, unless --force is passed."
            if answers.process_tier == "solo" else
            "Standard tier: generation leaves an already-standard "
            "working-agreement.md (any released vintage) as-is; it only writes to "
            "reverse a recognised prior Solo choice or fill in a missing file — "
            "never to overwrite a hand-customized file without --force."
        ),
    }


def format_preview(preview: dict) -> str:
    """Human-readable rendering of `build_preview`'s output. Pure string
    formatting — no I/O, nothing computed here that isn't already in the
    dict."""
    lines = []
    lines.append("DRY RUN — nothing was written. This is a preview only.")
    lines.append("")
    lines.append(f"Selected reviewer modules ({len(preview['selected_modules'])}):")
    for name in preview["selected_modules"]:
        tier = preview["model_tiers"].get(name, "(unknown)")
        lint = preview["naming_lint"].get(name, {})
        flag = ""
        if lint.get("denylist_hits"):
            flag = f"  [NAMING LINT FAIL: {lint['denylist_hits']}]"
        elif lint.get("mismatch"):
            flag = f"  [NAMING LINT FAIL: {lint['mismatch']}]"
        lines.append(f"  - {name}  (model: {tier}){flag}")
    lines.append("")
    lines.append(f"CI provider: {preview['answers']['ci_provider']} — "
                  f"{preview['ci_provider_note']}")
    lines.append("")
    lines.append(f"Tracker: {preview['answers']['tracker_provider']} — "
                  f"{preview['tracker_provider_note']}")
    lines.append("")
    lines.append(f"Process tier: {preview['answers']['process_tier']} — "
                  f"{preview['process_tier_note']}")
    lines.append("")
    lines.append("Composed review_routing.json preview:")
    lines.append(json.dumps(preview["routing_preview"], indent=2))
    lines.append("")
    gp = preview["guard_paths_preview"]
    lines.append(f"Guard-paths convention: escalate {gp['escalate_reviewer']!r} to "
                  f"opus on {len(gp['guard_paths'])} guard path(s); "
                  f"{gp['exempted']!r} exempted.")
    if preview["escalations"]:
        lines.append("")
        lines.append("Escalations:")
        for note in preview["escalations"]:
            lines.append(f"  - {note}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dbt", action="store_true")
    parser.add_argument("--data-eng", action="store_true")
    parser.add_argument("--frontend", action="store_true")
    parser.add_argument("--sensitive-data", action="store_true")
    parser.add_argument("--ci-provider", choices=["github", "gitlab", "none"], default="none")
    parser.add_argument("--tracker-provider", choices=["github", "gitlab", "none"], default="none")
    parser.add_argument("--process-tier", choices=["solo", "standard"], default="standard")
    # Deliberately NO --unmatched-stack flag — see the module docstring for
    # why. A caller that needs `unmatched_stack_description` for something
    # other than the CLI must construct a SetupAnswers directly in Python.
    args = parser.parse_args()

    answers = SetupAnswers(
        dbt=args.dbt,
        data_eng=args.data_eng,
        frontend=args.frontend,
        sensitive_data=args.sensitive_data,
        ci_provider=args.ci_provider,
        tracker_provider=args.tracker_provider,
        process_tier=args.process_tier,
    )
    print(format_preview(build_preview(answers)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
