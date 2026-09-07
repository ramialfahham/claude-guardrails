# Active work

## `claude-project-kit` — Phase 5 merged. Phase 6a MR open (!12).

Full plan: `C:\Users\Rami\.claude\plans\happy-stargazing-mccarthy.md`. 7 phases +
1b, one task contract each.

**Merged**: Phase 1 (MR !2), Phase 1b (MR !3), Phase 2 (MR !4), Phase 3 (MR !6),
Phase 4 (model-routing convention), Phase 5 (CI-provider automation audit) — all
on `main`.

**Open, unmerged**: `!12` — Phase 6a, described below.

### Phase 6a — setup-project dry-run interview + preview: MR !12 open, CI green, needs owner merge

`scripts/preview_project_setup.py` (pure functions over a `SetupAnswers`
dataclass — no code path writes to disk, verified both by direct read of the
file and by a runtime sha256 content-hash snapshot test around a real
subprocess run) + `.claude/skills/setup-project/SKILL.md` (the
`AskUserQuestion`-driven interview that shells out to it and prints its
stdout verbatim) + `.claude/tests/test_preview_project_setup.py` (23 tests).
**Dry run only — writes nothing to any target project, no matter what's
answered.** Generating actual files (copying reviewer modules, composing a
real `review_routing.json`, a rendered `guard-paths.md`, a starter README,
and a post-setup smoke test) is Phase 6b — a separate, later contract, not
started.

**This phase went through 9 review rounds — know this before touching the
file again.** Full blow-by-blow is in `.claude/task/contract.md`'s
amendments log; the headline pattern worth knowing without reading all of
it:

- Rounds 1-4 fixed structural issues in `preview_project_setup.py` itself:
  an unguarded top-level test import that would crash a bootstrapped repo
  (fixed with the `_HAVE_SCRIPT`/`_require_script()` skip pattern — copy
  this pattern for any future test that imports a kit-only script);
  `build_guard_paths_preview` reading from two disagreeing sources instead
  of deriving from the composed routing; `load_module_tags` silently
  mis-excluding `README.md` instead of raising loudly; and — the one to
  remember — an early `--unmatched-stack` CLI flag that took arbitrary user
  free text as a shell argument. Round 3 tried to fix that in prose only;
  round 4 found the prose fix incomplete and deleted the flag from the CLI
  entirely. **There is no `--unmatched-stack` flag and there should never be
  one** — the free-text description is handled in the skill's own prose,
  never passed to any command.
- Rounds 5-8 were almost entirely about the *interview skill's* wording and
  mechanism, not the script: `AskUserQuestion`'s real schema (2-4 options,
  ≤12-char headers, required label+description per option) was verified
  programmatically each time after an earlier by-eye miscount slipped
  through. Round 8's finding is the one most likely to recur in future
  interview-skill work: an option added purely to satisfy the tool's
  2-option minimum ("Yes, something else needs a dedicated reviewer") had
  no free-text attached, and the skill's instructions said to get one via
  "a follow-up" without specifying its shape — which would have led a model
  to reach for a second `AskUserQuestion` and *invent* fake options to
  collect free text. **Lesson for any future `AskUserQuestion`-driven
  skill**: every follow-up needs its mechanism named explicitly (plain
  chat text vs. another tool call) — "a follow-up" is not a specification.
- **Round-cap discipline, tightened this phase**: this repo's convention is
  explicit owner sign-off past 3 review rounds. Earlier phases (Phase 5)
  extended that authorization loosely across multiple rounds on the
  builder's own judgment, then disclosed it after the fact. This phase
  fixed that: rounds 7, 8, and 9 each got their own fresh `AskUserQuestion`
  to the owner, with the exact verbatim answer recorded in
  `.claude/task/contract.md` before dispatching that round. **Follow this
  going forward — one fresh recorded answer per round past the cap, never
  a cross-reference to an earlier round's authorization.**
- Final state (round 9, both PASS): `.claude/skills/setup-project/SKILL.md`'s
  unmatched-stack question now has all three answer paths ("No", "Other"
  with free text, plain "Yes" with none) fully specified, including an
  explicit plain-text (not `AskUserQuestion`) follow-up for the third case.

**Next**: get `!12` merged, then decide whether to start Phase 6b (actual
generation logic — not yet contracted, needs its own confirmed contract per
this repo's Explore → Plan → Confirm → Implement → Verify discipline).

**Owner decisions still open**: rename this repo to `claude-project-kit`
(deferred); rename `.claude/agents/cto-reviewer.md` itself (deferred);
whether/how to wire `templates/ci-audit/ci_automation_audit.py` as an actual
`SessionStart` hook in any project (it's inert everywhere today, by design —
Phase 5's contract explicitly reserved this decision); whether `templates/*`
should be its own guard path in `review_routing.json`/`guard-paths.md`
(flagged at the end of Phase 5, still not decided).

**Minor cleanup still NOT done** (deferred across several sessions now,
already caused one real rebase-blocking incident): `.claude/hooks/__pycache__/*.pyc`
tracked in git from before `.gitignore` existed — `git rm -r --cached
.claude/hooks/__pycache__` as its own tiny standalone commit. Just do it next
time.

## Earlier, unrelated to the above

GitLab CI migration (`.gitlab-ci.yml`) — done and merged. Not open work.

`football-data-pipeline`'s past auto-merge incident is resolved in that repo
already — not open work here. It's what motivated Phase 5.
