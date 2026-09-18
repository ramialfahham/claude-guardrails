#!/usr/bin/env python
"""Actual generation for the `setup-project` interview — Phase 6b of
`claude-project-kit`.

Given a TARGET project that has already been bootstrapped
(`scripts/bootstrap.sh TARGET`) and structured interview answers, actually
writes the tailored governance setup Phase 6a's `preview_project_setup.py`
only ever previewed: copies the selected reviewer modules into
`TARGET/.claude/agents/`, removes any leftover `cto-reviewer.md` from a
project bootstrapped before this kit retired that legacy name (superseded by
`platform-reviewer`, which is `applies_when: [always]` and therefore always
selected — a fresh bootstrap ships that name directly and never creates the
legacy file at all), composes and writes a real
`TARGET/.claude/review_routing.json`, renders `TARGET/.claude/rules/guard-paths.md`
from the template, writes a starter `TARGET/README.md` if none exists (with a
tracker-guidance line reflecting `answers.tracker_provider` — the roadmap is
never a markdown file in this kit's convention), and reconciles
`TARGET/.claude/working-agreement.md` with `answers.process_tier` —
asymmetrically, not a blind overwrite either way. `"solo"` converts whatever
is currently there (subject to a hand-customization check) to the
lightweight template. `"standard"` only ever writes back to reverse a
RECOGNISED prior Solo choice (current content's sha256 is listed as `"solo"`
in `templates/known-working-agreement-digests.json` — any released Solo
vintage, not just the current template) or to fill in a genuinely missing
file, or when `force=True`; an existing file that's already some vintage of
standard is otherwise deliberately left untouched, never opportunistically
"modernized" to this checkout's current text.

That asymmetry, and the digest-list recognition mechanism itself, are both
the product of review catching real defects across several rounds — several
of them past this repo's 3-round cap, explicitly owner-authorized (see
`.claude/task/contract.md`'s amendments log for the full account, not
repeated here or given a specific count that would only go stale): an
earlier version tried recognizing a target's ACTUAL historical bootstrap
default via `.claude/.kit-version` + a `git show` against this kit's own
history, which seemed more precise but broke on this kit's own documented
upgrade path (`bootstrap.sh` restamps `.kit-version` on every re-run while
`working-agreement.md` itself is `keep_file`-protected, so the two drift out
of sync) — the boring, static, shipped-list alternative recognizes every
released default correctly regardless of git history, clone depth, or
bootstrap timing.

Reuses `preview_project_setup.py`'s selection/composition functions directly
(never reimplemented) and `compose_routing.py`'s `compose()`/`_write_atomic()`
directly. Validates everything (target is bootstrapped; every selected module
passes the naming lint) before any write — raises `GenerationRefused` and
writes nothing on any check failure, the same shape as `promote_reviewer.py`'s
`PromotionRefused`.

Each individual file write is atomic (temp file + `os.replace`, via
`compose_routing._write_atomic`), but the SEQUENCE of writes across steps is
not one transaction — a crash mid-sequence leaves partial state. Every step is
independently idempotent (re-running `generate()` with the same answers
converges to the same end state), so the documented recovery from a partial
failure is "run it again," not a rollback mechanism.

Also provides `smoke_test(target)`: proves the target's OWN just-generated
`commit_review_gate.py` actually fires, by running it as a real subprocess
with a simulated PreToolUse(Bash) event — the same technique
`.claude/tests/test_commit_review_gate.py`'s `_run_main_in` helper already
uses. A plain `git commit` subprocess call would NOT be blocked by anything
at the git layer regardless of the target's review state — this repo's commit
gate is a Claude-Code-session-level PreToolUse hook, not a git hook — so
"make a real commit and see if it's blocked" cannot prove what it claims to;
running the real hook script against a simulated event is what actually
proves it fires. No commit is ever made by the smoke test.

Usable as a library (`generate`, `smoke_test`) or a CLI:
  python scripts/generate_project_setup.py --target ../some-project --dbt
  python scripts/generate_project_setup.py --target ../some-project --frontend

`SetupAnswers.unmatched_stack_description` has NO CLI flag here either — it
isn't used by generation at all, only by the interview's advisory escalation
note (see `preview_project_setup.py`).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPTS_DIR)
_REVIEWERS_DIR = os.path.join(_REPO_ROOT, "templates", "reviewers")
_FRAGMENTS_DIR = os.path.join(_REVIEWERS_DIR, "routing")
_GUARD_PATHS_TMPL = os.path.join(_REPO_ROOT, "templates", "rules", "guard-paths.md.tmpl")
_README_TMPL = os.path.join(_REPO_ROOT, "templates", "starter-README.md.tmpl")
_KIT_WORKING_AGREEMENT = os.path.join(_REPO_ROOT, ".claude", "working-agreement.md")
_SOLO_WORKING_AGREEMENT_TMPL = os.path.join(
    _REPO_ROOT, "templates", "working-agreement-solo.md.tmpl")
_WORKING_AGREEMENT_DIGESTS_FILE = os.path.join(
    _REPO_ROOT, "templates", "known-working-agreement-digests.json")

sys.path.insert(0, _SCRIPTS_DIR)
import compose_routing  # noqa: E402
from preview_project_setup import (  # noqa: E402
    _PROVIDER_DISPLAY_NAME,
    SetupAnswers,
    build_guard_paths_preview,
    build_naming_lint_report,
    build_routing_preview,
    select_reviewer_modules,
)

# Tags every routing.json this tool writes, so a LATER generate() call can
# tell "my own prior output" apart from a hand-authored/bootstrap-default
# file — compose_routing.compose() only ever touches 'always'/'paths', so
# this key passes through into every composed result unchanged. On its own
# this only proves AUTHORSHIP, not that the file is still UNCHANGED since —
# _generated_sha256 (added at write time, see generate()) is what actually
# lets _routing_needs_force() tell "still exactly what I wrote" apart from
# "hand-edited since" (e.g. the routing tweak bootstrap.sh's own closing
# instructions explicitly tell the owner to make).
_GENERATED_BY_MARKER = "claude-project-kit/generate_project_setup.py"


def _canonical_json(body: dict) -> str:
    """Deterministic serialization for hashing: sorted keys (recursively),
    so re-parsing a written file and re-serializing it reproduces the exact
    same bytes regardless of on-disk key order or formatting — a hash
    computed this way only changes when the actual DATA changes."""
    return json.dumps(body, indent=2, sort_keys=True)


def _routing_content_hash(routing: dict) -> str:
    """sha256 over `routing` with `_generated_sha256` itself excluded (can't
    hash a dict that contains its own hash) — everything else, including
    `_generated_by`, is covered, so renaming the marker or changing any
    routing content both correctly change the hash."""
    body = {k: v for k, v in routing.items() if k != "_generated_sha256"}
    return hashlib.sha256(_canonical_json(body).encode("utf-8")).hexdigest()

# The base a NEW project's routing is composed onto — distinct from
# preview_project_setup._BASE_ROUTING, which never needed artifact_only
# handling for a read-only preview. Without artifact_only/artifact_only_never,
# every commit in a freshly generated project (including trivial task/handover
# file edits) would require full review, unlike this kit's own dogfooded
# .claude/review_routing.json, which already carries them.
_GENERATION_BASE: dict = {
    "always": ["scope-auditor"],
    "paths": {},
    "artifact_only": [".claude/task/*", ".claude/active_work.md"],
    "artifact_only_never": [".claude/task/contract.md"],
    "_generated_by": _GENERATED_BY_MARKER,
}

# This kit's OWN shipped review_routing.json — what bootstrap.sh's keep_file
# copies into a fresh target before generation ever runs. Read (never
# written) by _routing_needs_force() to recognise "still the untouched
# bootstrap placeholder" as safe to overwrite.
_KIT_ROUTING_FILE = os.path.join(_REPO_ROOT, ".claude", "review_routing.json")

# guard-paths.md has no bootstrap-shipped default at all (bootstrap.sh never
# creates .claude/rules/), so its own presence is the only signal generate()
# has. The marker line embeds a content hash of the body that follows it
# (see _render_guard_paths) — presence alone would only prove authorship,
# the same gap _routing_content_hash exists to close for review_routing.json.
_GUARD_PATHS_MARKER_PREFIX = f"<!-- generated by {_GENERATED_BY_MARKER}; sha256:"
_GUARD_PATHS_MARKER_SUFFIX = "; safe to regenerate if unchanged -->"
_GUARD_PATHS_MARKER_RE = re.compile(
    re.escape(_GUARD_PATHS_MARKER_PREFIX) + r"([0-9a-f]{64})"
    + re.escape(_GUARD_PATHS_MARKER_SUFFIX) + r"\n\n")

# A pre-rename bootstrap shipped this file into every project unconditionally,
# regardless of stack — the exact "one overloaded generic reviewer" problem
# the module library exists to fix. bootstrap.sh no longer ever creates it
# (the kit's own copy is platform-reviewer.md now), so this only ever matches
# a leftover from a project bootstrapped before that rename; generation
# removes only this one known filename, never a glob.
_LEGACY_REVIEWER_FILE = "cto-reviewer.md"


def _routing_needs_force(target: str, kit_routing_file: str = _KIT_ROUTING_FILE) -> bool:
    """True if target's existing review_routing.json looks hand-customized
    SINCE it was last generated — so generate() must not silently clobber
    it. False (safe to overwrite) if the file is absent, is byte-for-byte
    this tool's own last output (content hash matches its own recorded
    `_generated_sha256` — re-running generate(), even with different
    answers, is meant to be possible without --force), or is byte-for-byte
    the same JSON structure bootstrap.sh would have copied in untouched.
    True (needs --force) if it carries the `_generated_by` marker but its
    content has since diverged from the recorded hash — e.g. the routing
    tweak bootstrap.sh's own closing instructions explicitly tell the owner
    to make. A marker that merely proves AUTHORSHIP, with no hash check,
    would silently discard exactly that edit on the next generate() call —
    the real-world case the marker exists to protect, not just the narrower
    bootstrap-to-first-generate window."""
    path = os.path.join(target, ".claude", "review_routing.json")
    if not os.path.isfile(path):
        return False
    try:
        with open(path, encoding="utf-8") as f:
            current = json.load(f)
    except json.JSONDecodeError:
        return True  # unparseable — be conservative, don't silently clobber
    if current.get("_generated_by") == _GENERATED_BY_MARKER:
        stored_hash = current.get("_generated_sha256")
        return stored_hash != _routing_content_hash(current)
    try:
        with open(kit_routing_file, encoding="utf-8") as f:
            kit_default = json.load(f)
    except (OSError, json.JSONDecodeError):
        return True
    return current != kit_default


def _guard_paths_needs_force(target: str) -> bool:
    """Same reasoning as _routing_needs_force, applied to guard-paths.md's
    marker-comment-embedded hash (see _render_guard_paths) instead of a JSON
    field: no marker at all -> not this tool's output, protect it; marker
    present but the body's hash doesn't match the one recorded in it -> the
    body was hand-edited since generation, protect it; marker present and
    the hash matches -> byte-for-byte this tool's own last output, safe."""
    path = os.path.join(target, ".claude", "rules", "guard-paths.md")
    if not os.path.isfile(path):
        return False
    with open(path, encoding="utf-8") as f:
        content = f.read()
    m = _GUARD_PATHS_MARKER_RE.match(content)
    if not m:
        return True
    body = content[m.end():]
    return m.group(1) != hashlib.sha256(body.encode("utf-8")).hexdigest()


def _load_known_working_agreement_digests(
        digests_file: str = _WORKING_AGREEMENT_DIGESTS_FILE) -> dict[str, str]:
    """sha256 hexdigest -> tier ("standard"/"solo"), for every RELEASED
    working-agreement.md default this kit has ever shipped — a static,
    shipped list (templates/known-working-agreement-digests.json), not a
    git-history reconstruction. Round 3's review found the git-subprocess
    approach had a real coupling bug: bootstrap.sh overwrites
    `.claude/.kit-version` on every re-run while `working-agreement.md`
    itself is `keep_file`-protected, so the stamped SHA silently stops
    matching what's on disk the moment anyone follows this kit's own
    documented upgrade path (re-run bootstrap.sh, then re-run
    /setup-project) — reinstating the exact lockout the mechanism existed to
    prevent. A flat, append-only digest list has no such coupling: it's
    correct regardless of git history, clone depth, or bootstrap timing.

    Raises GenerationRefused (not a bare exception) if this kit's own shipped
    digests file is missing, isn't valid JSON, or doesn't have the expected
    {"digests": {...}} shape — every other content problem in this file
    raises the same way; a shipped file this broken should stop generation
    outright, not silently treat every working-agreement.md as unrecognised
    (which would just make hand-customization refusals over-fire) or crash
    with an unrelated traceback."""
    try:
        with open(digests_file, encoding="utf-8") as f:
            data = json.load(f)
        digests = data["digests"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as e:
        raise GenerationRefused(
            f"{digests_file} is missing or malformed ({e!r}) — this kit's own "
            "shipped digest list is broken; nothing written") from e
    if not isinstance(digests, dict) or not all(
            isinstance(k, str) and v in ("standard", "solo")
            for k, v in digests.items()):
        raise GenerationRefused(
            f"{digests_file}'s \"digests\" value isn't a flat map of string keys "
            "to 'standard'/'solo' — this kit's own shipped digest list is "
            "broken; nothing written")
    return digests


def _working_agreement_tier(
        content: str, digests: dict[str, str] | None = None) -> str | None:
    """"standard"/"solo" if `content`'s sha256 is a known released default,
    else None (unrecognised — hand-customized, or a default not yet listed)."""
    if digests is None:
        digests = _load_known_working_agreement_digests()
    return digests.get(hashlib.sha256(content.encode("utf-8")).hexdigest())


def _working_agreement_needs_force(
        target: str, digests: dict[str, str] | None = None) -> bool:
    """True if target's .claude/working-agreement.md looks hand-customized —
    i.e. its digest isn't in the known-digests list. False (safe to converge
    to Solo) if the file is absent or its digest is recognised, whatever
    tier/vintage. Only ever gates the Solo write path (see generate()) —
    Standard never needs this check, since it only ever writes from a state
    that's inherently safe (missing, or a recognised prior Solo choice) or
    when the owner explicitly passes force=True on an unrecognised file.
    `digests` is injectable (tests exercise a historical entry without
    needing it in the kit's own real, current digest list)."""
    path = os.path.join(target, ".claude", "working-agreement.md")
    if not os.path.isfile(path):
        return False
    with open(path, encoding="utf-8") as f:
        current = f.read()
    return _working_agreement_tier(current, digests=digests) is None


class GenerationRefused(Exception):
    """Raised with a human-readable reason; nothing is written before this
    can be raised — every check in generate() runs before the first write."""


class SmokeTestRefused(Exception):
    """Raised with a human-readable reason. Distinct from GenerationRefused
    so a caller can tell "setup wasn't written" apart from "setup was
    written, but the post-write verification didn't pass/couldn't run"."""


def _require_bootstrapped(target: str) -> None:
    if not os.path.isfile(os.path.join(target, ".claude", "settings.json")):
        raise GenerationRefused(
            f"{target!r} doesn't look bootstrapped (.claude/settings.json "
            f"missing) — run scripts/bootstrap.sh {target} first; generation "
            "is additive on top of bootstrap, not a replacement for it")


def _render_guard_paths(tmpl_path: str, guard_preview: dict) -> str:
    """Fill templates/rules/guard-paths.md.tmpl's <REPLACE: ...> markers and
    placeholder list from `build_guard_paths_preview`'s own output — never a
    second, independently-typed copy of the guard-paths list."""
    with open(tmpl_path, encoding="utf-8") as f:
        text = f.read()

    escalate = f"`{guard_preview['escalate_reviewer']}`"
    exempted = f"`{guard_preview['exempted']}`"

    text = re.sub(
        r"<REPLACE: the\s+guard-path-routed reviewer name\(s\) for this project,.*?>",
        escalate, text, count=1, flags=re.DOTALL)
    text = re.sub(
        r"<REPLACE: any\s+always-required reviewer that should stay exempt,.*?>",
        exempted, text, count=1, flags=re.DOTALL)

    guard_list = "\n".join(f"- `{p}`" for p in guard_preview["guard_paths"])
    text = re.sub(
        r"<!-- REPLACE.*?-->\n- <path pattern 1>\n- <path pattern 2>",
        guard_list, text, count=1, flags=re.DOTALL)

    text = text.replace("- <always-required reviewer name(s)>", f"- {exempted}", 1)

    if "<REPLACE" in text or "<path pattern" in text or "<always-required" in text:
        raise GenerationRefused(
            "templates/rules/guard-paths.md.tmpl has drifted from what this "
            "renderer expects — a placeholder marker was left unfilled; fix "
            "_render_guard_paths to match the template's current text")
    body_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    marker = _GUARD_PATHS_MARKER_PREFIX + body_hash + _GUARD_PATHS_MARKER_SUFFIX
    return marker + "\n\n" + text


def _render_readme(tmpl_path: str, target: str, module_names: list[str],
                    tracker_provider: str = "none") -> str:
    """Fill templates/starter-README.md.tmpl's placeholders. Only called when
    target/README.md doesn't already exist (see generate())."""
    with open(tmpl_path, encoding="utf-8") as f:
        text = f.read()

    project_name = os.path.basename(os.path.normpath(os.path.abspath(target)))
    text = text.replace("<REPLACE: project name>", project_name, 1)

    reviewer_list = "\n".join(f"- `{name}`" for name in module_names)
    text = re.sub(
        r"<!-- REPLACE with the bulleted list of installed reviewer modules -->\n"
        r"- <module name>",
        reviewer_list, text, count=1)

    tracker_guidance = (
        f"Track what's ahead in {_PROVIDER_DISPLAY_NAME[tracker_provider]} Issues "
        "(milestones/epics) — never a ROADMAP.md/BACKLOG.md file."
        if tracker_provider != "none" else
        "Track what's ahead in this project's issue tracker once it has one — never a "
        "ROADMAP.md/BACKLOG.md file."
    )
    text = re.sub(
        r"<!-- REPLACE with the tracker guidance line -->\n<tracker guidance>",
        tracker_guidance, text, count=1)

    if "<REPLACE" in text or "<module name>" in text or "<tracker guidance>" in text:
        raise GenerationRefused(
            "templates/starter-README.md.tmpl has drifted from what this "
            "renderer expects — a placeholder marker was left unfilled; fix "
            "_render_readme to match the template's current text")
    return text


def generate(target: str, answers: SetupAnswers,
             reviewers_dir: str = _REVIEWERS_DIR,
             fragments_dir: str = _FRAGMENTS_DIR,
             guard_paths_tmpl: str = _GUARD_PATHS_TMPL,
             readme_tmpl: str = _README_TMPL,
             kit_routing_file: str = _KIT_ROUTING_FILE,
             working_agreement_digests: dict[str, str] | None = None,
             force: bool = False) -> dict:
    """Write the tailored governance setup into `target`. Raises
    GenerationRefused with NOTHING written if any of: `target` isn't
    bootstrapped; a selected module fails the naming lint; `answers.process_tier`
    or `answers.tracker_provider` isn't a recognised value; `target`'s
    `review_routing.json` or `guard-paths.md` already look hand-customized
    and `force` isn't set; `answers.process_tier == "solo"` and
    `working-agreement.md` already looks hand-customized (its digest isn't in
    `templates/known-working-agreement-digests.json`) and `force` isn't set
    (Standard never needs this check — see the module docstring's asymmetry
    note: it only ever converts FROM a recognised Solo state, or writes when
    `force=True`, never clobbers an unrecognised file on its own); either
    template has drifted from what this file's renderers expect. Every one
    of those checks — including rendering both templates — runs before the
    first write, so a refusal never leaves a half-generated target. Returns
    a summary dict for a caller (the CLI, the skill) to print verbatim
    rather than re-narrate.

    `force=True` overwrites an already-customized review_routing.json/
    guard-paths.md deliberately — the same escape hatch bootstrap.sh's own
    `keep_file`/`--force` convention uses for project-owned config.
    `working-agreement.md` is narrower: `force` only overrides it when the
    current file is UNRECOGNISED (round 4's review caught an earlier version
    letting `force` overwrite ANY current content, including a recognised
    older-standard file — the exact silent-rewrite round 2 already flagged,
    re-entered via this flag) — a recognised standard or Solo file, of any
    vintage, is always left alone by Standard tier regardless of `force`.
    Not needed to simply re-run generate() with different answers, including
    a different process_tier: this tool's own prior output is recognised
    (via the `_generated_by` marker / the guard-paths.md marker line /
    working-agreement.md's own digest list) as safe to regenerate without
    it. `working_agreement_digests` is injectable (tests exercise a
    historical digest without it needing to be in this kit's own real,
    current `templates/known-working-agreement-digests.json`)."""
    _require_bootstrapped(target)

    module_names = select_reviewer_modules(answers, reviewers_dir)
    lint_report = build_naming_lint_report(module_names, reviewers_dir)
    bad = {name: report for name, report in lint_report.items()
           if report["denylist_hits"] or report["mismatch"]}
    if bad:
        raise GenerationRefused(
            f"naming lint failed for selected module(s), nothing written: {bad}")

    if not force and _routing_needs_force(target, kit_routing_file):
        raise GenerationRefused(
            f"{target}/.claude/review_routing.json already looks "
            "hand-customized (neither this tool's own prior output nor the "
            "untouched bootstrap default) — pass force=True to overwrite it "
            "deliberately")
    if not force and _guard_paths_needs_force(target):
        raise GenerationRefused(
            f"{target}/.claude/rules/guard-paths.md already exists and "
            "wasn't generated by this tool — pass force=True to overwrite "
            "it deliberately")
    if answers.process_tier not in ("solo", "standard"):
        raise GenerationRefused(
            f"answers.process_tier={answers.process_tier!r} is not 'solo' or "
            "'standard' — nothing written")
    if answers.tracker_provider not in _PROVIDER_DISPLAY_NAME and answers.tracker_provider != "none":
        raise GenerationRefused(
            f"answers.tracker_provider={answers.tracker_provider!r} is not "
            "'github', 'gitlab', or 'none' — nothing written")
    if (answers.process_tier == "solo" and not force
            and _working_agreement_needs_force(target, digests=working_agreement_digests)):
        raise GenerationRefused(
            f"{target}/.claude/working-agreement.md already looks "
            "hand-customized (not a state this tool recognises as its own) "
            "— pass force=True to overwrite it deliberately")

    # Render both templates NOW, before any write — a template-drift
    # GenerationRefused must never fire after a write has already happened.
    routing_preview = build_routing_preview(
        module_names, base_routing=_GENERATION_BASE, fragments_dir=fragments_dir)
    # Stamp the content hash AFTER composing but BEFORE guard_paths_preview
    # is derived from it — guard_paths_preview only reads "paths", so the
    # extra key doesn't affect it, and this way the written file's own
    # _generated_sha256 always matches what _routing_content_hash recomputes
    # from that exact file later.
    routing_preview["_generated_sha256"] = _routing_content_hash(routing_preview)
    guard_preview = build_guard_paths_preview(routing_preview)
    guard_md = _render_guard_paths(guard_paths_tmpl, guard_preview)  # may raise
    readme_path = os.path.join(target, "README.md")
    readme_needed = not os.path.isfile(readme_path)
    readme_text = (  # may raise
        _render_readme(readme_tmpl, target, module_names, answers.tracker_provider)
        if readme_needed else None)
    with open(_SOLO_WORKING_AGREEMENT_TMPL, encoding="utf-8") as f:
        solo_working_agreement = f.read()
    wa_path = os.path.join(target, ".claude", "working-agreement.md")
    current_working_agreement = None
    if os.path.isfile(wa_path):
        with open(wa_path, encoding="utf-8") as f:
            current_working_agreement = f.read()
    current_tier = (None if current_working_agreement is None
                     else _working_agreement_tier(
                         current_working_agreement, digests=working_agreement_digests))
    if answers.process_tier == "solo":
        write_working_agreement = current_working_agreement != solo_working_agreement
        desired_working_agreement = solo_working_agreement
        working_agreement_reason = (
            "solo: filled in a missing file with the lightweight template"
            if write_working_agreement and current_working_agreement is None else
            "solo: converted to the lightweight template"
            if write_working_agreement else
            "solo: already the solo template, nothing to do")
    else:
        # Standard NEVER opportunistically "modernizes" an existing file to
        # this checkout's current text — that would silently overwrite a
        # target's project-owned working-agreement.md (keep_file-protected
        # by bootstrap.sh) just because it happens to predate a kit release,
        # which is exactly what round 2's review caught this doing. Standard
        # only writes to reverse a RECOGNISED prior Solo choice (current
        # file's digest is listed as "solo" — any released Solo vintage, not
        # just the current template) or to fill in a missing file; anything
        # else RECOGNISED as already-standard, whatever vintage, is left
        # alone even under `force` — round 4's review caught an earlier
        # version of this line letting `force` overwrite ANY current
        # content, including a recognised older-standard file, which is
        # round 2's silent-rewrite defect re-entered via that flag instead
        # of via the digest-recognition gap. `force` only ever overrides an
        # UNRECOGNISED (hand-customized) file — the escape hatch review
        # round 3 found documented but not actually honoured.
        with open(_KIT_WORKING_AGREEMENT, encoding="utf-8") as f:
            desired_working_agreement = f.read()
        # Each branch decides BOTH write_working_agreement and its own reason
        # together, so the two can never disagree (round 6's review found an
        # earlier version deriving the reason from a SEPARATE re-check of the
        # same conditions, which a not-yet-possible fourth tier value could
        # have silently mismatched against the boolean it was supposed to
        # explain — `_load_known_working_agreement_digests` now also
        # validates every digest value is exactly "standard"/"solo", so
        # `current_tier` itself can never be anything else, but deriving the
        # reason from the same decision closes the class structurally rather
        # than relying on that validation alone).
        if current_working_agreement is None:
            write_working_agreement = True
            working_agreement_reason = "standard: filled in a missing file"
        elif current_tier == "solo":
            write_working_agreement = True
            working_agreement_reason = "standard: reversed a recognised prior Solo choice"
        elif current_tier == "standard":
            write_working_agreement = False
            working_agreement_reason = (
                "standard: already a recognised standard file (this vintage or an "
                "earlier one), left as-is regardless of force")
        elif force:
            write_working_agreement = True
            working_agreement_reason = (
                "standard: file is unrecognised (hand-customized) — force-overwrote it")
        else:
            write_working_agreement = False
            working_agreement_reason = (
                "standard: file is unrecognised (hand-customized) and force wasn't "
                "given — left as-is")

    # Nothing above this point has written anything. From here on, only
    # operations that (by construction) cannot themselves fail on content.
    summary: dict = {
        "target": target,
        "modules_installed": [],
        "legacy_reviewer_removed": False,
        "readme_written": False,
        "working_agreement_written": False,
        "working_agreement_reason": working_agreement_reason,
    }

    agents_dir = os.path.join(target, ".claude", "agents")
    os.makedirs(agents_dir, exist_ok=True)
    for name in module_names:
        shutil.copyfile(
            os.path.join(reviewers_dir, f"{name}.md"),
            os.path.join(agents_dir, f"{name}.md"))
        summary["modules_installed"].append(name)

    legacy_path = os.path.join(agents_dir, _LEGACY_REVIEWER_FILE)
    if os.path.isfile(legacy_path):
        os.remove(legacy_path)
        summary["legacy_reviewer_removed"] = True

    routing_path = os.path.join(target, ".claude", "review_routing.json")
    # Deliberately overwrites bootstrap.sh's keep_file-preserved copy (this
    # kit's own shipped review_routing.json) — this is the one moment a
    # project-specific config is meant to replace it. Safe here specifically
    # because the force-check above already ran.
    compose_routing._write_atomic(
        routing_path, json.dumps(routing_preview, indent=2) + "\n")
    summary["review_routing_written"] = routing_path

    rules_dir = os.path.join(target, ".claude", "rules")
    os.makedirs(rules_dir, exist_ok=True)
    guard_path = os.path.join(rules_dir, "guard-paths.md")
    compose_routing._write_atomic(guard_path, guard_md)
    summary["guard_paths_written"] = guard_path

    if readme_needed:
        compose_routing._write_atomic(readme_path, readme_text)
        summary["readme_written"] = True

    if write_working_agreement:
        compose_routing._write_atomic(wa_path, desired_working_agreement)
        summary["working_agreement_written"] = True

    return summary


def _simulate_commit_hook(target: str) -> dict:
    """Run TARGET's own .claude/hooks/commit_review_gate.py as a real
    subprocess with a simulated PreToolUse(Bash) event for `git commit` — the
    same event shape .claude/settings.json's real hook wiring sends, and the
    same technique test_commit_review_gate.py's own _run_main_in helper uses.
    {"denied": bool, "reason": str|None}. Empty stdout (or stdout with no
    "permissionDecisionReason" key) means the hook allowed the call."""
    hook_path = os.path.join(target, ".claude", "hooks", "commit_review_gate.py")
    event = json.dumps({"tool_input": {"command": "git commit -m smoke-test"}})
    env = dict(os.environ, CLAUDE_PROJECT_DIR=target)
    proc = subprocess.run(
        [sys.executable, hook_path], input=event, text=True,
        capture_output=True, cwd=target, env=env, timeout=30)
    reason = None
    out = proc.stdout.strip()
    if out:
        try:
            reason = json.loads(out.splitlines()[-1]).get(
                "hookSpecificOutput", {}).get("permissionDecisionReason")
        except json.JSONDecodeError:
            pass
    return {"denied": reason is not None, "reason": reason}


def _diff_hash(target: str) -> str:
    hook_path = os.path.join(target, ".claude", "hooks", "commit_review_gate.py")
    env = dict(os.environ, CLAUDE_PROJECT_DIR=target)
    proc = subprocess.run(
        [sys.executable, hook_path, "--diff-hash"], capture_output=True,
        text=True, cwd=target, env=env, timeout=30, check=True)
    return proc.stdout.strip()


def smoke_test(target: str) -> dict:
    """Prove the target's just-generated review gate actually fires: stage a
    trivial dummy file, confirm the simulated commit is DENIED with no
    review.md present, write a minimal valid review.md for target's actual
    required reviewers, confirm the simulated commit is now ALLOWED, then
    unstage and delete both the dummy file and review.md. No commit is ever
    made, so no destructive git operation is needed either way.

    Refuses (SmokeTestRefused, no git operation performed) if either path
    this function itself writes (`.claude/_smoke_test_tmp`,
    `.claude/task/review.md`) already exists in the target. That is the
    actual risk here — this function only ever `git add`/`git reset` those
    two EXACT paths, never `-A`/`.`, so it cannot disturb any other
    pre-existing uncommitted change (including, expectedly, the very files
    `generate()` just wrote and the caller hasn't committed yet — requiring
    a fully clean tree would make the smoke test refuse immediately after
    every real `generate()` call, which defeats chaining them). A
    pre-existing real `review.md` is a plausible, meaningful file in an
    active project; overwriting and then deleting it would be a genuinely
    bad, hard-to-recover mistake, so THAT is what this checks for."""
    hook_path = os.path.join(target, ".claude", "hooks", "commit_review_gate.py")
    if not os.path.isfile(hook_path):
        raise SmokeTestRefused(
            f"{target!r} has no .claude/hooks/commit_review_gate.py — "
            "bootstrap and generate must both run before the smoke test")

    dummy_path = os.path.join(target, ".claude", "_smoke_test_tmp")
    review_dir = os.path.join(target, ".claude", "task")
    review_path = os.path.join(review_dir, "review.md")
    for path, label in ((dummy_path, ".claude/_smoke_test_tmp"),
                         (review_path, ".claude/task/review.md")):
        if os.path.exists(path):
            raise SmokeTestRefused(
                f"{label} already exists in the target — refusing to "
                "overwrite it for the smoke test. If this is left over from "
                f"an interrupted previous run: `git -C {target} reset -- "
                f"{label}` then remove the file by hand, then retry.")
    try:
        with open(dummy_path, "w", encoding="utf-8") as f:
            f.write("smoke test placeholder — not meant to be committed\n")
        subprocess.run(["git", "add", dummy_path], cwd=target,
                        check=True, capture_output=True, timeout=30)

        blocked = _simulate_commit_hook(target)
        if not blocked["denied"]:
            raise SmokeTestRefused(
                "expected the generated commit_review_gate.py to DENY a "
                "commit with no review.md present, but it did not")

        with open(os.path.join(target, ".claude", "review_routing.json"),
                   encoding="utf-8") as f:
            routing = json.load(f)
        # NOT just routing["always"] — commit_review_gate._required_reviewers
        # unions 'always' with every reviewer named in ANY 'paths' pattern
        # matching the CUMULATIVE branch diff (everything committed since the
        # base branch, plus what's staged). If the target already committed
        # its generated .claude/ on a feature branch (bootstrap.sh's own
        # instructed next step), that cumulative diff includes
        # .claude/hooks/*, .claude/agents/*, etc. — which platform-reviewer's
        # own routing fragment matches — making it REQUIRED even though the
        # smoke test's own dummy file doesn't match any path pattern itself.
        # Recomputing the gate's exact cumulative-path-matching logic here
        # would duplicate it (and risk drifting from the real thing); taking
        # every reviewer named ANYWHERE in 'paths' is a safe superset instead
        # — the gate only requires a non-FAIL verdict from each REQUIRED
        # reviewer, so a few extra PASS sections for reviewers that turn out
        # not to be required this time are harmless.
        required = sorted(
            set(routing.get("always") or [])
            | {r for reviewers in (routing.get("paths") or {}).values()
               for r in reviewers})

        diff_hash = _diff_hash(target)
        lines = [f"diff_sha256: {diff_hash}", ""]
        for reviewer in required:
            lines += [f"## {reviewer}", "VERDICT: PASS", "risks_checked:",
                       "- smoke test", ""]
        os.makedirs(review_dir, exist_ok=True)
        with open(review_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        subprocess.run(["git", "add", review_path], cwd=target,
                        check=True, capture_output=True, timeout=30)

        allowed = _simulate_commit_hook(target)
        if allowed["denied"]:
            raise SmokeTestRefused(
                "expected the generated commit_review_gate.py to ALLOW a "
                f"commit with a valid review.md present, but it denied: "
                f"{allowed['reason']}")

        return {"blocked_without_review": True, "allowed_with_review": True}
    finally:
        # A cleanup failure here must not mask whatever exception is already
        # propagating (never raise from a finally on top of that), but must
        # also not vanish silently — surface it on stderr so a caller (the
        # CLI, the skill) can tell the user their index may still have
        # .claude/_smoke_test_tmp/.claude/task/review.md staged.
        reset = subprocess.run(
            ["git", "reset", "--", dummy_path, review_path], cwd=target,
            capture_output=True, text=True, timeout=30)
        if reset.returncode != 0:
            print(f"warning: smoke test cleanup's 'git reset' failed in "
                  f"{target!r}: {reset.stderr.strip()}", file=sys.stderr)
        for path in (dummy_path, review_path):
            if os.path.isfile(path):
                os.remove(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", required=True,
                         help="path to the already-bootstrapped target project")
    parser.add_argument("--dbt", action="store_true")
    parser.add_argument("--data-eng", action="store_true")
    parser.add_argument("--frontend", action="store_true")
    parser.add_argument("--sensitive-data", action="store_true")
    parser.add_argument("--ci-provider", choices=["github", "gitlab", "none"], default="none")
    parser.add_argument("--tracker-provider", choices=["github", "gitlab", "none"], default="none")
    parser.add_argument("--process-tier", choices=["solo", "standard"], default="standard")
    parser.add_argument("--force", action="store_true",
                         help="overwrite an already-customized "
                              "review_routing.json/guard-paths.md/"
                              "working-agreement.md deliberately (not needed "
                              "to just re-run with different answers — this "
                              "tool's own prior output is recognised as safe "
                              "to regenerate)")
    # Deliberately NO --unmatched-stack flag — see the module docstring. Also
    # deliberately no flag to skip the smoke test — the contract's done_when
    # describes generation and the smoke test as one operation; a caller
    # that wants generate() without smoke_test() has both as separate,
    # directly importable library functions instead of a CLI escape hatch
    # that isn't part of what this contract's CLI surface is specified as.
    args = parser.parse_args()

    answers = SetupAnswers(
        dbt=args.dbt, data_eng=args.data_eng, frontend=args.frontend,
        sensitive_data=args.sensitive_data, ci_provider=args.ci_provider,
        tracker_provider=args.tracker_provider, process_tier=args.process_tier,
    )
    try:
        summary = generate(args.target, answers, force=args.force)
    except GenerationRefused as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 1

    print(f"generated into {args.target}:")
    print(f"  modules installed: {summary['modules_installed']}")
    print(f"  legacy cto-reviewer.md removed: {summary['legacy_reviewer_removed']}")
    print(f"  review_routing.json written: {summary['review_routing_written']}")
    print(f"  guard-paths.md written: {summary['guard_paths_written']}")
    print(f"  README.md written: {summary['readme_written']}")
    print(f"  working-agreement.md written: {summary['working_agreement_written']} "
          f"({summary['working_agreement_reason']})")

    try:
        smoke = smoke_test(args.target)
    except SmokeTestRefused as e:
        print(f"REFUSED (smoke test): {e}", file=sys.stderr)
        return 1

    print(f"smoke test: blocked without review = {smoke['blocked_without_review']}, "
          f"allowed with review = {smoke['allowed_with_review']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
