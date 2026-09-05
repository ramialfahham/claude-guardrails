# Review

diff_sha256: 5a28e35d4008baf23daa7fef04a49f604610b9d0b1166b5e97d72b2ed32936b5

## scope-auditor
VERDICT: PASS
risks_checked:
- Union behavior on same-path routing — a path pattern legitimately routed by
  two different fragments ends up with both reviewers listed, never one
  overwriting the other (`if name not in bucket: bucket.append(name)`),
  confirmed by `test_compose_unions_same_pattern_across_reviewers`.
- Duplicate JSON key rejection — a hand-authored fragment/target with a literal
  repeated key is rejected via the strict loader (`object_pairs_hook`) before
  being trusted, confirmed by `test_duplicate_key_in_json_is_rejected`.
- Two meanings of "always" — `platform-reviewer` (`applies_when: [always]`,
  scaffold-time) has a routing fragment `"always": false` with paths (only
  required when its territory is touched); `security-reviewer` (conditionally
  included) has `"always": true` (unconfined to a path once included). Both
  documented explicitly in `templates/reviewers/routing/README.md`, matching
  the contract. No owner-level decision made silently; all files in scope_paths.

## cto-reviewer
VERDICT: PASS
risks_checked:
- Type-confusion fix (prior FAIL) — `_validate_fragment_shape` rejects a
  fragment's `paths` if it isn't a list of strings (would otherwise iterate a
  string character-by-character); `_validate_base_shape` is a SEPARATE check
  for the base's different shape (`paths` is a `{pattern: [reviewer,...]}` map,
  not a list) — confirmed each correctly distinguishes the two shapes rather
  than one wrongly accepting the other's.
- Atomic-write fix (prior FAIL) — `_write_atomic` writes to a temp file then
  `os.replace()`s onto the target (atomic on both POSIX and Windows), cleaning
  up the temp file on any exception; verified with a test that forces a real
  `os.replace` failure and confirms no temp file is left behind, not just the
  trivial success-path case.
- Exception-boundary fix (prior FAIL) — `compose(base, fragments)` now sits
  inside the same try/except as the file loads, catching the new
  `MalformedRoutingError` too; `test_cli_refuses_malformed_fragment_and_leaves_target_untouched`
  runs the real CLI as a subprocess and confirms a clean `REFUSED:` message,
  non-zero exit, and the target file byte-for-byte untouched.
- Minor note from before (data-engineer-reviewer fragment missing a "raw
  landing" pattern) addressed — `raw/*` and `landing/*` added.
- Fragment patterns cross-checked against each reviewer's own "territory"
  description — all consistent, none overly broad.

Prior round FAILed on three real defects (silent type-confusion on a
malformed `paths` field, a non-atomic write that could corrupt an existing
routing config on a mid-write crash, and a raw traceback instead of a clean
refusal on malformed input). All three fixed and re-verified fresh against the
current code — including one round where a stale pre-fix review had to be
discarded and re-run, since it happened to complete after the patch snapshot
but before the actual fix.
