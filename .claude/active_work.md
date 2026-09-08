# Active work

## `claude-project-kit` — all 7 phases (+1b) merged. Plan complete.

Full plan: `C:\Users\Rami\.claude\plans\happy-stargazing-mccarthy.md`.

**Merged**: Phase 1 (MR !2), Phase 1b (MR !3), Phase 2 (MR !4), Phase 3 (MR !6),
Phase 4 (model-routing convention), Phase 5 (CI-provider automation audit),
Phase 6a (setup-project dry-run interview + preview, MR !12 + handover MR !13),
Phase 6b (actual generation, MR !14 + handover MR !15), Phase 7 (distribution +
portfolio docs, MR !16) — all on `main`. **No phase is open or unmerged.**

### Where things stand today

A project gets set up two ways:
- **Static**: `scripts/bootstrap.sh /path/to/project` — copies the guard code
  in. Safe to re-run (kit code refreshes, project-owned config is preserved
  unless `--force`); now also stamps `.claude/.kit-version` with this kit's
  own commit SHA on every run (Phase 7), so a project owner can tell what
  version they're on.
- **Tailored**: from a `claude-guardrails` checkout, run the `/setup-project`
  skill — interviews the project's stack, previews a reviewer set, then (after
  an explicit second confirmation) generates it: copies the matching reviewer
  modules, removes the bootstrap-default `cto-reviewer.md`, composes
  `review_routing.json`, renders `guard-paths.md`, writes a starter README,
  and runs a smoke test proving the new gate actually fires.

`docs/project-kit-design.md` is the architecture overview now (how
`scripts/`/`templates/`/`.claude/` fit together, the review-gate mechanics);
`docs/decisions/*.md` are short ADRs for the real design calls made across
every phase, each pointing at its actual source rather than re-narrating it;
`README.md` was brought current in Phase 7 (it had drifted — still described
only the original two reviewers with no mention of the module library or the
interview).

### Phase 7 — what to know before touching `scripts/bootstrap.sh`'s version-stamp block again

Went through 3 review rounds, and the version-stamp logic (a small addition —
stamp `.claude/.kit-version` with `git -C "$KIT_ROOT" rev-parse HEAD`) turned
into real iteration, not polish, because of environment-specific path-format
bugs caught LIVE (by manual scratch-repo verification, not just by review
prose) on this exact dev box:

1. A bare `rev-parse HEAD` (no `--verify`) echoes the literal string `HEAD`
   to stdout on an unborn-HEAD repo before failing on stderr —
   `2>/dev/null` doesn't catch that. Fixed with `--verify`.
2. `git -C "$KIT_ROOT"` walks UP to find an enclosing repo, so a non-git
   `KIT_ROOT` sitting inside an unrelated repo would stamp THAT repo's SHA.
   First fix: compare `rev-parse --show-toplevel`'s output against
   `$KIT_ROOT` as path text.
3. That comparison broke the NORMAL case on this exact box: git printed
   `D:/Projects/claude-guardrails` (drive-letter form) while `$KIT_ROOT`
   (via `pwd -P`) is `/d/Projects/claude-guardrails` (MSYS form) — same
   real directory, different string. Fixed by normalizing both sides
   through the same `abspath()` function.
4. That normalization ALSO broke, because Git Bash mount-aliases `%TEMP%`
   (`AppData\Local\Temp`) to `/tmp` — re-running `abspath()` on an
   already-canonical path isn't even idempotent there.
5. **Final fix**: stopped comparing path TEXT entirely. `[ -e
   "$KIT_ROOT/.git" ]` — a plain filesystem existence check — closes the
   whole bug class structurally instead of patching around it further.
   Correctly matches a worktree too (its `.git` is a file, not a
   directory — `-e` matches either).

**Lesson for next time a path needs comparing in a bash script that might
run under Git Bash on Windows**: don't compare path TEXT across tools (bash's
own `pwd -P` and git's own path-printing commands can format the SAME real
directory differently, and "normalize then compare" isn't reliably fixable
because normalization itself isn't always idempotent across a mount-aliased
tree like `%TEMP%`/`/tmp`). Prefer a existence/identity check that never
needs the two sides to agree on a string.

A second, separate finding from the same phase: `.claude/tests/test_bootstrap.py`'s
first version of the version-stamp tests was **tautological** —
`if os.path.isfile(stamp): assert ...` gates the check on the very file the
check exists to verify, so a regression that silently stopped the stamp from
being written would make the test SKIP, not FAIL, and CI treats a skip as
green. Fixed with `_kit_owed_a_stamp()`, which determines independently
(mirroring `bootstrap.sh`'s own gates, not the stamp file's existence)
whether one should exist, then hard-asserts when it should.

Three narrow items were flagged in round 3's review and deliberately left
unfixed (recorded in `.claude/task/contract.md`'s amendments, not silently
dropped): a corrupted (not merely absent) `.git` nested in an unrelated repo
could still mis-stamp; the skip message doesn't distinguish "unborn HEAD"
from "git unavailable" from "ownership refusal"; two doc sentences say
"every run" without the "when git history is available" qualifier. None
worth a further round — see the amendments log for the reviewer's own
reasoning on each.

**Owner decision locked this phase**: a minimal version stamp, not a port of
`dbt-agent-kit`'s full `sync-base.sh`/coverage-guard/CI-drift-check
machinery — that machinery exists to preserve a *derivative* kit's own local
overlay (routing/working-agreement additions), which a plain project
generated by this kit's own tooling doesn't have. Updating a plain project is
just re-running `bootstrap.sh` + `generate_project_setup.py` with the same
interview flags (the kit doesn't persist which flags were originally used —
documented honestly as a known limitation in the README/ADR, not silently
glossed over). If derivative kits become a repeated pattern, a real sync
mechanism earns its complexity then, not preemptively.

### Owner decisions still open (none blocking, none scheduled)

- Rename this repo to `claude-project-kit` (deferred since Phase 1's
  planning — `dbt-agent-kit/scripts/sync-base.sh` hardcodes this repo's
  GitHub URL as its sync source, so a rename needs that fixed in the same
  pass).
- Rename `.claude/agents/cto-reviewer.md` itself (deferred; note it's now
  ALSO the file generation actively removes from every new project, so this
  is entirely about this kit's own self-governance file at this point).
- Whether/how to wire `templates/ci-audit/ci_automation_audit.py` as an
  actual `SessionStart` hook anywhere (still inert everywhere, by design).
- Whether `templates/*` should be its own guard path in
  `review_routing.json`/`guard-paths.md` (flagged at the end of Phase 5,
  still not decided).
- The pre-existing drift between THIS kit's own hand-maintained
  `.claude/rules/guard-paths.md` and
  `templates/reviewers/routing/platform-reviewer.routing.json` (flagged
  during Phase 6a; Phase 6b's generation logic avoids introducing this same
  drift into NEW projects by deriving `guard-paths.md` fresh from the
  composed routing every time, but doesn't fix the kit's own existing copy).

### Minor cleanup still NOT done (deferred across many sessions now)

`.claude/hooks/__pycache__/*.pyc` tracked in git from before `.gitignore`
existed — `git rm -r --cached .claude/hooks/__pycache__` as its own tiny
standalone commit. Already caused one real rebase-blocking incident. Just do
it next time someone's touching hooks anyway.

## Earlier, unrelated to the above

GitLab CI migration (`.gitlab-ci.yml`) — done and merged. Not open work.

`football-data-pipeline`'s past auto-merge incident is resolved in that repo
already — not open work here. It's what motivated Phase 5.
