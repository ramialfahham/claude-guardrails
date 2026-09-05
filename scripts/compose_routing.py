#!/usr/bin/env python
"""Merge reviewer routing fragments (templates/reviewers/routing/*.routing.json)
into a project's own .claude/review_routing.json.

Two fragments legitimately routing the SAME path pattern to different
reviewers is normal (a path can need more than one reviewer) and gets unioned,
never silently overwritten. What's rejected is a literal duplicate JSON key
within one object in either a fragment or the target file — `json.load` would
otherwise silently keep only the last value, hiding a hand-authoring mistake.

Usable as a library (`compose`) or a CLI:
  python scripts/compose_routing.py --target .claude/review_routing.json \
      --reviewers platform-reviewer,data-engineer-reviewer
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys

_ROUTING_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "templates", "reviewers", "routing",
)


class DuplicateKeyError(ValueError):
    """A JSON object literal repeated the same key — almost certainly a typo,
    since plain json.load would silently keep only the last value."""


class MalformedRoutingError(ValueError):
    """A fragment or target has the wrong shape (e.g. `paths` isn't a list) —
    refuse loudly rather than silently mis-composing it."""


def _no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    seen: dict = {}
    for key, value in pairs:
        if key in seen:
            raise DuplicateKeyError(f"duplicate key {key!r} in JSON object")
        seen[key] = value
    return seen


def load_json_strict(path: str) -> dict:
    """json.load, but a repeated key in any object anywhere in the document
    raises instead of silently keeping only the last value."""
    with open(path, encoding="utf-8") as f:
        return json.load(f, object_pairs_hook=_no_duplicate_keys)


def _validate_fragment_shape(name: str, frag: dict) -> None:
    """Refuse a malformed FRAGMENT before compose() ever touches it — a
    hand-authored `"paths": "scripts/*"` (string, not a list) would otherwise
    iterate character-by-character and silently inject garbage keys."""
    paths = frag.get("paths", [])
    if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
        raise MalformedRoutingError(
            f"{name}: 'paths' must be a list of strings, got {paths!r}")
    always = frag.get("always", False)
    if not isinstance(always, bool):
        raise MalformedRoutingError(f"{name}: 'always' must be a bool, got {always!r}")


def _validate_base_shape(base: dict) -> None:
    """Refuse a malformed BASE (a review_routing.json-shaped dict) — its
    `paths` is a {pattern: [reviewer, ...]} MAP, unlike a fragment's `paths`
    (a plain list of patterns), so this needs its own check."""
    paths = base.get("paths", {})
    if not isinstance(paths, dict) or not all(
        isinstance(k, str) and isinstance(v, list) and all(isinstance(x, str) for x in v)
        for k, v in paths.items()
    ):
        raise MalformedRoutingError(
            f"<base>: 'paths' must be a {{pattern: [reviewer, ...]}} map, got {paths!r}")
    always = base.get("always", [])
    if not isinstance(always, list) or not all(isinstance(a, str) for a in always):
        raise MalformedRoutingError(f"<base>: 'always' must be a list of strings, got {always!r}")


def compose(base: dict, fragments: dict[str, dict]) -> dict:
    """Merge `fragments` (reviewer name -> {"always": bool, "paths": [...]})
    into `base` (a review_routing.json-shaped dict). Returns a NEW dict; does
    not mutate `base`. Idempotent: composing the same fragments again over an
    already-composed result adds nothing further. Raises MalformedRoutingError
    if `base` or any fragment has the wrong shape, before writing anything."""
    _validate_base_shape(base)
    for name, frag in fragments.items():
        _validate_fragment_shape(name, frag)

    result = copy.deepcopy(base)
    result.setdefault("always", [])
    result.setdefault("paths", {})

    for name, frag in fragments.items():
        if frag.get("always"):
            if name not in result["always"]:
                result["always"].append(name)
        for pattern in frag.get("paths", []):
            bucket = result["paths"].setdefault(pattern, [])
            if name not in bucket:
                bucket.append(name)

    return result


def _write_atomic(path: str, content: str) -> None:
    """Write via a temp file + os.replace so a crash mid-write can't leave the
    target truncated or corrupted — a partially-written review_routing.json
    would silently disable review gating."""
    tmp_path = f"{path}.tmp-{os.getpid()}"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True,
                         help="path to the project's review_routing.json")
    parser.add_argument("--reviewers", required=True,
                         help="comma-separated reviewer names to compose in")
    parser.add_argument("--fragments-dir", default=_ROUTING_DIR,
                         help="directory of <name>.routing.json fragments "
                              f"(default: {_ROUTING_DIR})")
    parser.add_argument("--dry-run", action="store_true",
                         help="print the composed result instead of writing it")
    args = parser.parse_args()

    try:
        base = load_json_strict(args.target)

        names = [n.strip() for n in args.reviewers.split(",") if n.strip()]
        fragments = {}
        for name in names:
            frag_path = os.path.join(args.fragments_dir, f"{name}.routing.json")
            fragments[name] = load_json_strict(frag_path)

        composed = compose(base, fragments)
    except (DuplicateKeyError, MalformedRoutingError, json.JSONDecodeError,
            FileNotFoundError) as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(json.dumps(composed, indent=2))
    else:
        _write_atomic(args.target, json.dumps(composed, indent=2) + "\n")
        print(f"composed {len(names)} reviewer(s) into {args.target}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
