#!/usr/bin/env python
"""Promote a drafted reviewer into the shared templates/reviewers/ library.

The library is meant to grow the way a real project's reviewer set grows: one
hand-authored module at a time, added only once it's proven itself on real
reviews — never pre-guessed, never auto-added. `templates/reviewers/_skeleton.md`
drafts a reviewer for a stack nothing else covers; this script is the deliberate,
manual step that turns a proven draft into a reusable module. It is NOT wired to
anything automatic (no review count, no usage threshold) — that is by design.

Usage:
  python scripts/promote_reviewer.py SOURCE_MD [--force]

Refuses (no file written) when:
  - the source is not readable UTF-8 text, or has no frontmatter block,
  - the source is still marked `draft: true` in its frontmatter,
  - a required frontmatter field is missing (name, description, tools, model,
    applies_when),
  - the name isn't a plain lowercase kebab-case token (no `/`, `..`, or other
    path-shaped content — the name becomes a filename, so it must be safe as
    one) or fails the naming lint (a corporate-title token),
  - a file already exists at the destination, unless --force is given.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lint_reviewer_name import check_name, _FRONTMATTER_NAME  # noqa: E402

REQUIRED_FIELDS = ["name", "description", "tools", "model", "applies_when"]
_REVIEWERS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "templates", "reviewers",
)

# The name becomes `<name>.md` on disk (promote()), so it must be safe as a bare
# filename: lowercase, alphanumeric, hyphen-separated, nothing that could act as
# a path (`/`, `\`, `..`, a leading `.`, an absolute-path shape).
_SAFE_NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class PromotionRefused(Exception):
    """Raised with a human-readable reason; never a bare assertion."""


def _frontmatter_block(text: str) -> str:
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise PromotionRefused("no YAML frontmatter block found (need two '---' lines)")
    return parts[1]


def _field(frontmatter: str, key: str) -> str | None:
    m = re.search(rf"^{re.escape(key)}:\s*(.+)$", frontmatter, re.MULTILINE)
    return m.group(1).strip() if m else None


def validate_source(text: str) -> dict[str, str]:
    """Return the required fields' values, or raise PromotionRefused."""
    fm = _frontmatter_block(text)

    draft = _field(fm, "draft")
    if draft and draft.strip().lower() == "true":
        raise PromotionRefused(
            "source is still marked `draft: true` — read it, edit it, remove the "
            "draft flag once you've reviewed it, then promote")

    values: dict[str, str] = {}
    missing = []
    for key in REQUIRED_FIELDS:
        if key == "name":
            # Reuse lint_reviewer_name's OWN compiled regex object (captures a
            # single `\S+` token) rather than the generic rest-of-line `_field`
            # — the two scripts must agree on what "the name" is, since this
            # one derives a filename from it and the other checks a filename
            # against it. Sharing the regex object (not a re-typed copy of the
            # pattern) means they can't drift apart.
            m = _FRONTMATTER_NAME.search(fm)
            val = m.group(1) if m else None
        else:
            val = _field(fm, key)
        if not val:
            missing.append(key)
        else:
            values[key] = val
    if missing:
        raise PromotionRefused(
            f"missing required frontmatter field(s): {missing} — a module without "
            "these can't be routed or reviewed like the rest of the library")

    name = values["name"]
    if not _SAFE_NAME.match(name):
        raise PromotionRefused(
            f"name {name!r} isn't a safe plain kebab-case name (lowercase letters, "
            "digits, single hyphens only) — it becomes a filename, so anything "
            "path-shaped (`/`, `..`, etc.) is refused")

    hits = check_name(name)
    if hits:
        raise PromotionRefused(
            f"name {name!r} contains corporate-title token(s) {hits} — "
            "rename it to describe what it actually checks")

    return values


def promote(source_path: str, force: bool = False, dest_dir: str = _REVIEWERS_DIR) -> str:
    """Promote `source_path` into `dest_dir`. Returns the destination path.
    Raises PromotionRefused on any check failure; writes nothing on refusal."""
    try:
        with open(source_path, encoding="utf-8") as f:
            text = f.read()
    except UnicodeDecodeError as e:
        raise PromotionRefused(f"source is not valid UTF-8 text: {e}") from e

    values = validate_source(text)
    dest_path = os.path.join(dest_dir, f"{values['name']}.md")

    if os.path.exists(dest_path) and not force:
        raise PromotionRefused(
            f"{dest_path} already exists — pass --force to replace it deliberately")

    os.makedirs(dest_dir, exist_ok=True)
    shutil.copyfile(source_path, dest_path)
    return dest_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="path to the drafted reviewer .md to promote")
    parser.add_argument("--force", action="store_true",
                         help="overwrite an existing module at the destination")
    args = parser.parse_args()

    try:
        dest = promote(args.source, force=args.force)
    except PromotionRefused as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 1
    except FileNotFoundError:
        print(f"REFUSED: no such file: {args.source}", file=sys.stderr)
        return 1

    print(f"promoted {args.source} -> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
