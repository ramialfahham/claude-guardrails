# Task contract

objective: Phase 2 of the `claude-project-kit` plan — a routing fragment per
  reviewer module (which paths route to it, or whether it's required on every
  commit regardless of path) and `scripts/compose_routing.py`, which merges a
  target project's `review_routing.json` with the fragments for whichever
  reviewers were selected, safely (union same-pattern entries, catch a hand-
  authoring duplicate-key mistake, never silently drop a reviewer).

scope_paths:
  - templates/reviewers/routing/**
  - scripts/compose_routing.py
  - .claude/tests/test_compose_routing.py
  - .claude/task/contract.md
  - .claude/task/review.md

decisions_reserved:
  - None new. This phase only adds data (routing fragments) and a merge script;
    it doesn't wire anything into an actual project yet (no interview exists —
    Phase 6). Naming/scope decisions already made in Phase 1's contract stand.

done_when:
  - `templates/reviewers/routing/<name>.routing.json` exists for all 5 Phase 1
    modules, each `{"always": bool, "paths": [<fnmatch pattern>, ...]}`. Four
    (`platform`, `data-engineer`, `analytics-engineer`, `frontend`) route by
    path, derived from that module's own "territory" description. One
    (`security`) is `"always": true` — sensitive-data handling isn't confined
    to specific paths the way the others are, so it can't be scoped by pattern
    the same way.
  - **Two distinct meanings of "always" are documented, not conflated**: Phase
    1's `applies_when: [always]` on `platform-reviewer` means "always INCLUDE
    this reviewer when scaffolding a project" — a selection-time decision. A
    fragment's `"always": true` means "always REQUIRE this reviewer's sign-off
    on every commit regardless of path" — a routing-time decision. They answer
    different questions; `platform-reviewer`'s own fragment is path-routed
    (`"always": false`), same as this repo's existing `cto-reviewer` is today.
  - `scripts/compose_routing.py` exposes a pure function
    `compose(base: dict, fragments: dict[str, dict]) -> dict` (testable without
    touching disk) plus a CLI (`--target PATH --reviewers name1,name2`).
    Composing: unions a pattern's reviewer list across fragments/base
    (de-duped, never silently overwritten); appends an `"always": true`
    fragment's reviewer name into the base's top-level `always` list (deduped);
    loads every JSON file (fragments AND the target base) through a decoder
    that REJECTS a literal duplicate key within one object — a hand-authoring
    mistake `json.load` would otherwise silently resolve to "last value wins".
  - `.claude/tests/test_compose_routing.py` (plain-Python, this repo's
    `test_*.py` convention) proves: two fragments legitimately routing the same
    pattern to different reviewers end up unioned, not one overwriting the
    other; a literal duplicate JSON key in a fixture file is rejected before
    trusting the loader; composing is idempotent (running it twice with the
    same inputs doesn't duplicate entries); the 5 shipped fragments all parse
    and match the `{"always": bool, "paths": [...]}` shape.
  - All existing `.claude/tests/test_*.py` still pass; JSON configs still
    parse; hooks still byte-compile; shell scripts still lint.
  - scope-auditor + cto-reviewer PASS on the staged diff.

amendments:
  - 2026-09-05 — contract created for Phase 2 of the approved plan
    (`C:\Users\Rami\.claude\plans\happy-stargazing-mccarthy.md`). Built on
    updated `main` (Phase 1 + 1b merged).
