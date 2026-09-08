# Active work

## `claude-project-kit` — Phase 6a merged. Phase 6b MR open (!14).

Full plan: `C:\Users\Rami\.claude\plans\happy-stargazing-mccarthy.md`. 7 phases +
1b, one task contract each.

**Merged**: Phase 1 (MR !2), Phase 1b (MR !3), Phase 2 (MR !4), Phase 3 (MR !6),
Phase 4 (model-routing convention), Phase 5 (CI-provider automation audit),
Phase 6a (setup-project dry-run interview + preview, MR !12 + handover MR !13)
— all on `main`.

**Open, unmerged**: `!14` — Phase 6b, described below.

### Phase 6b — actual generation for setup-project: MR !14 open, CI green, needs owner merge

`scripts/generate_project_setup.py` — wires Phase 6a's dry-run preview into
real writes. Given a bootstrapped target project and structured interview
answers: copies selected reviewer modules into `.claude/agents/`, removes
the bootstrap-default `cto-reviewer.md`, composes and writes a real
`.claude/review_routing.json`, renders `.claude/rules/guard-paths.md` from
the template, writes a starter `README.md` if none exists, and runs a
`smoke_test()` proving the target's own generated `commit_review_gate.py`
actually fires. `.claude/skills/setup-project/SKILL.md` extended (steps
7-11) to drive it, gated behind an explicit second confirmation separate
from the existing "does this reviewer set look right" step.

**Two owner decisions locked before implementation, via a plan-mode
session** (both recorded verbatim in `.claude/task/contract.md`):
- **No confidential-scope-doc / summarization feature.** The original
  Phase 6 plan's idea (owner pastes project context, the kit summarizes it
  into `CLAUDE.md` with full detail kept in a separate `.claude/rules/`
  file) is cut ENTIRELY, not deferred. Owner's reasoning: an automated
  setup step that invites pasting client names, internal system names, or
  business rules into a new repo is a bad default regardless of where the
  text ends up. Neither sibling repo (`dbt-agent-kit`, `football-data-pipeline`)
  had this pattern to build from either — verified directly before the
  decision was made. **Don't resurrect this without a fresh, explicit
  owner conversation** — it was cut on purpose, not skipped for time.
- **The legacy `cto-reviewer.md` is removed from generated projects.**
  `bootstrap.sh` ships it into every project unconditionally regardless of
  stack — the exact "one overloaded generic reviewer" problem the whole
  module-library effort exists to fix. `platform-reviewer` (always
  selected, since it's `applies_when: [always]`) is its direct successor.
  Generation deletes only that one known filename, never a glob.

**This phase went through 4 review rounds — know this before touching the
file again.** Full blow-by-blow is in `.claude/task/contract.md`'s
amendments log; the headline pattern worth knowing without reading all of
it:

- **The smoke test cannot be "make a real commit and see if it's
  blocked."** `commit_review_gate.py`'s enforcement is a Claude-Code-
  session-level `PreToolUse(Bash)` hook, not a git hook — it only
  intercepts Bash TOOL calls made by a live agent session in its OWN
  project directory, never a plain `subprocess.run(["git","commit"])` from
  arbitrary code, and never a different directory a command happens to
  `cd`/`-C` into. (This was independently rediscovered and confirmed live
  mid-session: a literal `git -C <scratch-target> commit` run via the Bash
  tool got blocked by THIS repo's own gate, unrelated to the target,
  because this session's own diff was staged and unreviewed at the time —
  a real demonstration of the same mechanism.) The smoke test instead runs
  the target's own copied `commit_review_gate.py` as a real subprocess with
  a simulated PreToolUse JSON event on stdin — the same technique
  `test_commit_review_gate.py`'s own `_run_main_in` helper already uses.
  No commit is ever made.
- **Round 1** fixed 6 issues in the first draft, the two worth remembering:
  the smoke test's required-reviewer computation was `always`-only, but the
  real gate unions `always` with every reviewer whose `paths` pattern
  matches the CUMULATIVE branch diff — once a target commits its generated
  `.claude/` on a feature branch (bootstrap.sh's own instructed next step),
  that diff includes `.claude/hooks/*`/`.claude/agents/*`, making
  `platform-reviewer` required; an under-computed review.md made a
  correctly-working gate report as broken. Fixed with a safe superset
  instead of reimplementing the gate's matching logic. Also:
  `GenerationRefused`'s "nothing written" guarantee was violated because
  template rendering happened AFTER some writes — fixed by moving all
  validation and rendering before the first mutation.
- **Round 2** found that writing `guard-paths.md` un-skips
  `.claude/tests/test_routing_doc_parity.py` (shipped into every target by
  `bootstrap.sh`), which then failed in every generated project — it was
  hardcoded to look for `"cto-reviewer"` and compared raw list-item text
  against backtick-wrapped output. Fixed by generalizing that test to read
  the escalate-reviewer name from the doc's own "Convention" paragraph
  instead of hardcoding it (added to this contract's `scope_paths` as a
  recorded amendment — it's a SHARED file, also this kit's own dogfooded
  parity check). Also found the original `_generated_by` marker (added to
  protect hand-customized `review_routing.json`/`guard-paths.md` from being
  silently overwritten on a later re-run) only proved AUTHORSHIP, not that
  content was unchanged since — exactly the edit `bootstrap.sh`'s own
  closing instructions tell the owner to make would have been silently
  discarded. Fixed with real content-hash verification
  (`_generated_sha256` for routing.json, an embedded hash in
  guard-paths.md's marker comment) plus a `--force` CLI flag mirroring
  `bootstrap.sh`'s own `keep_file`/`--force` convention.
- **Round 3** (this repo's cap) found the new `--force` flag itself wasn't
  listed in the contract's own exhaustive CLI-flag documentation — the same
  standard applied to a since-removed `--skip-smoke-test` flag in round 1.
  Purely a docs-sync gap, fixed in one line.
- **Round 4** required fresh owner sign-off (recorded verbatim in
  contract.md) since it's past the cap. cto-reviewer correctly recognized
  nothing code-level had changed since its round-3 PASS and scoped its
  effort accordingly rather than re-running a full audit for no reason —
  worth remembering as the right instinct for a documentation-only round.
  scope-auditor ESCALATEd (not FAILed) only on whether the round-4
  authorization's CPO ANSWER was genuinely verbatim, correctly noting it
  has no access to the actual conversation to check — resolved directly by
  the builder, who does have that transcript. **Lesson**: a reviewer
  ESCALATEing on its own verification limits (as opposed to a substantive
  finding) doesn't need a fresh owner decision — it needs the builder to
  supply the information the subagent structurally can't reach.

**Next**: get `!14` merged, then decide on Phase 7 (distribution + portfolio
docs — `bootstrap.sh` gains a `templates/` sync + update mechanism reusing
`dbt-agent-kit`'s `sync-base.sh`/`.base-version` pattern, plus `README.md`,
`docs/project-kit-design.md`, short `docs/decisions/*.md` ADRs) — not yet
contracted.

**Owner decisions still open**: rename this repo to `claude-project-kit`
(deferred); rename `.claude/agents/cto-reviewer.md` itself (deferred, though
note it's now ALSO the name generation actively removes from every new
project — the rename question is entirely about this kit's own
self-governance file at this point, not about downstream projects anymore);
whether/how to wire `templates/ci-audit/ci_automation_audit.py` as an actual
`SessionStart` hook in any project (still inert everywhere, by design);
whether `templates/*` should be its own guard path in
`review_routing.json`/`guard-paths.md` (flagged at the end of Phase 5, still
not decided); the pre-existing drift between THIS kit's own hand-maintained
`.claude/rules/guard-paths.md` and `templates/reviewers/routing/
platform-reviewer.routing.json` (flagged during Phase 6a, still unresolved
in this kit's own copy — Phase 6b's generation logic avoids introducing this
SAME class of drift into new projects by deriving guard-paths.md fresh from
the composed routing every time, but doesn't fix the kit's own existing copy).

**Minor cleanup still NOT done** (deferred across several sessions now,
already caused one real rebase-blocking incident): `.claude/hooks/__pycache__/*.pyc`
tracked in git from before `.gitignore` existed — `git rm -r --cached
.claude/hooks/__pycache__` as its own tiny standalone commit. Just do it next
time.

## Earlier, unrelated to the above

GitLab CI migration (`.gitlab-ci.yml`) — done and merged. Not open work.

`football-data-pipeline`'s past auto-merge incident is resolved in that repo
already — not open work here. It's what motivated Phase 5.
