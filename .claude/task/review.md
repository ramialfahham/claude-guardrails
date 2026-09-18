# Review

diff_sha256: 2988078d48eeb9ed1b45eaf2a8239626543011bb55422494cd24bdd46ca8ec85

rounds: 3

Within the cap. Round-by-round findings and fixes are in `.claude/task/contract.md`'s
amendments (round 1: seven platform findings; round 2: six platform + one scope; round 3:
clean). Round 2's findings were all introduced by round 1's own fixes — no "present since
round 1" carry-overs.

## scope-auditor
VERDICT: PASS (round 3, final)
risks_checked:
- Scope: every changed file inside `scope_paths` (`.claude/tests/test_completion_gate.py` added by
  amendment for one stated reason — its non-dict test was silently weakened by the opt-in check).
- Owner decisions implemented exactly and nothing beyond: plugin shape, name `claude-project-kit`,
  hooks fire only in opted-in projects with `.claude/review_routing.json` as the marker. The
  builder's layout call (components stay under `.claude/`, manifest declares the paths) is
  recorded as a builder call with a phase-3 escape hatch. No phase-2/3 work started; the handover
  tells the next session not to set up the owner's website the old way.
- Opt-in short-circuit is the first thing every one of the 10 hooks does, before parsing or
  emitting anything; marker path identical in `_command_utils.OPT_IN_MARKER` and `preflight.sh`.
- `hooks.json` ↔ `settings.json` parity is whole-block equality after root-token substitution.
- Round-2 finding (design-doc table called the `setup-project` skill a "command") fixed; the
  observation was real, the label was wrong.

## platform-reviewer
VERDICT: PASS (round 3, final — opus, guard paths `*hooks/*`, `.claude/tests/*`)
risks_checked:
- No credential-shaped literal anywhere in the patch — all six `secret_scan.py` patterns run over
  the full `review_input.patch`; the fixture's AWS key is split at `"AKIA" + "IOSFODNN7EXAMPLE"`
  (round 2's finding: the contiguous literal would have made this kit's own gate deny this
  branch's commit).
- Revert coverage: each provocation traced to its emitting line; `commit_review_gate` covered on
  both paths (opted-in deny at `:232`, no-routing NOTE at `:302` — fixture branch `work` has no
  base ref). Builder verified by reverting `secret_scan`'s and `commit_review_gate`'s checks: the
  silent test fails on exactly that hook. Only `completion_gate` is undetectable by construction.
- Existing deny-path tests still reach the gate (their fixtures write `review_routing.json`);
  `test_fails_open_on_non_dict_event` reaches its non-dict path again via an opted-in temp dir.
- Fail-open orientation: `project_opted_in` returns False on any exception (hook does nothing);
  CI runs each test file under `set -e`, new runner exits 1 on failure (fail closed).
- Marker cleanup filenames match both hooks' sanitisers; `uuid4` session ids; `TemporaryDirectory`
  everywhere; git/bash absence skips; preflight PATH is an empty dir inside the fixture.
- Handover claims about `bootstrap.sh` verified: `hooks.json` and the new test ship to targets
  (harmless: Claude Code reads project hooks from `settings.json`; the test skips without the
  manifest); `keep_file review_routing.json` seeds the marker in bootstrapped projects.
- Owner-level flags, recorded in `active_work.md`, not decided: per-Bash-call process cost of
  loading six hooks everywhere; whether `.claude-plugin/*` should be a guard path.

Live: `claude --plugin-dir <kit> -p` (v2.1.223) in a repo with no `.claude/` — plugin listed in
`system/init`; commit `COMMITTED` without the marker, `REVIEW GATE` denial with it. Recorded with
commands and outputs in `docs/project-kit-design.md`.
