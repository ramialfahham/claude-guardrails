#!/usr/bin/env python
"""Reject reviewer names that borrow a corporate job title instead of describing
what the reviewer actually checks (e.g. `cto-reviewer` for a role that never
reviews anything as a CTO in practice — a real project's own reviewers should be
named `platform-reviewer`, `data-engineer-reviewer`, etc.).

Matches whole `-`/`_`/whitespace-separated tokens against a denylist, not
substrings, so a name like `leaderboard-reviewer` is not flagged for containing
"lead". Deliberately does NOT attempt to catch a concatenated, no-separator name
(`ctoreviewer`) — a substring scan for that would also flag real words that
happen to contain a denylisted token, which is worse than the gap it closes;
this library's own naming convention is always `-`-separated, so that form
never actually gets produced here.

Checking a directory of `.md` files (`--dir`) validates BOTH the filename and
the file's own `name:` frontmatter field, and flags a mismatch between them —
a file could otherwise be named innocuously while its frontmatter `name:` (the
value Claude Code actually registers as the agent's name) carries the bad name.

Usable as a library (`check_name`, `check_file`) or a CLI:
  python scripts/lint_reviewer_name.py NAME [NAME ...]
  python scripts/lint_reviewer_name.py --dir templates/reviewers
"""

from __future__ import annotations

import argparse
import os
import re
import sys

DENYLIST = {
    "cto", "cpo", "ceo", "coo", "cio", "ciso",
    "vp", "evp", "svp",
    "director", "head", "chief", "president", "founder", "owner",
    "manager", "lead", "boss", "exec", "executive",
}

_TOKEN_SPLIT = re.compile(r"[-_\s]+")
_FRONTMATTER_NAME = re.compile(r"^name:\s*(\S+)", re.MULTILINE)


def check_name(name: str) -> list[str]:
    """Return the denylisted tokens found in `name` (whole-token match only)."""
    tokens = [t for t in _TOKEN_SPLIT.split(name.lower()) if t]
    return [t for t in tokens if t in DENYLIST]


def _frontmatter_name(path: str) -> str | None:
    """The `name:` value in a reviewer .md's YAML frontmatter, or None."""
    with open(path, encoding="utf-8") as f:
        content = f.read()
    parts = content.split("---", 2)
    if len(parts) < 3:
        return None
    m = _FRONTMATTER_NAME.search(parts[1])
    return m.group(1) if m else None


def check_file(path: str) -> tuple[str, list[str], str | None]:
    """Check one reviewer .md: (stem, denylisted tokens found in either the
    filename or the frontmatter name, a mismatch note if they disagree)."""
    stem = os.path.basename(path)
    if stem.endswith(".md"):
        stem = stem[: -len(".md")]
    fm_name = _frontmatter_name(path)
    hits = set(check_name(stem))
    if fm_name:
        hits.update(check_name(fm_name))
    mismatch = None
    if fm_name and fm_name != stem:
        mismatch = f"filename '{stem}' != frontmatter name '{fm_name}'"
    return stem, sorted(hits), mismatch


def _files_from_dir(directory: str) -> list[str]:
    return [
        os.path.join(directory, fname)
        for fname in sorted(os.listdir(directory))
        if fname.endswith(".md") and not fname.startswith("_")
    ]


def _names_from_dir(directory: str) -> list[str]:
    """Filenames only (no frontmatter check) — kept for callers that just want
    the module list, e.g. future routing composition."""
    return [os.path.basename(p)[: -len(".md")] for p in _files_from_dir(directory)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("names", nargs="*", help="reviewer names to check")
    parser.add_argument("--dir", help="check every *.md file in this directory — "
                                        "filename AND frontmatter name, plus any "
                                        "mismatch between them (skips files "
                                        "starting with '_' — drafts/skeletons)")
    args = parser.parse_args()

    if not args.names and not args.dir:
        parser.error("give at least one NAME or --dir")

    failed = False
    for name in args.names:
        hits = check_name(name)
        if hits:
            failed = True
            print(f"REJECT {name}: corporate-title token(s) {hits} — "
                  f"name it after what it actually checks instead")
        else:
            print(f"ok     {name}")

    if args.dir:
        for path in _files_from_dir(args.dir):
            stem, hits, mismatch = check_file(path)
            if hits:
                failed = True
                print(f"REJECT {stem}: corporate-title token(s) {hits} — "
                      f"name it after what it actually checks instead")
            elif mismatch:
                failed = True
                print(f"REJECT {stem}: {mismatch} — keep them identical")
            else:
                print(f"ok     {stem}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
