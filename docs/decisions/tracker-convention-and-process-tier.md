# The roadmap lives in the issue tracker; process weight has two tiers

**Status**: decided, shipped. Full text: `.claude/working-agreement.md` §2,
`templates/working-agreement-solo.md.tmpl`, `.claude/skills/setup-project/SKILL.md`.

## Context

The owner had observed, across other projects, the same drift pattern twice: multiple
competing roadmap/backlog markdown files contradicting each other, and a working agreement
whose process weight didn't scale down for a small project — the same full ceremony applied
regardless of size. `football-data-pipeline` (a separate, real project) had already hit and
fixed the first problem directly: four competing roadmap-ish documents were deleted in favor
of one rule — the roadmap is the tracker's milestones and issues, never a file.

## Decision

**Tracker convention**: `.claude/working-agreement.md` §2 now states a hard rule — never
create a `ROADMAP.md`/`BACKLOG.md` file; the project's issue tracker (GitHub/GitLab Issues,
milestones/epics) is the single source of truth for what's ahead. `task/CONTRACT_TEMPLATE.md`
gained a `tracking_issue` field so each task links back to its tracker item. `/setup-project`'s
interview gained a tracker question (GitHub Issues / GitLab Issues / none), mirroring the
existing CI-provider question's shape exactly — tracker-agnostic, not hardcoded to whichever
tracker this kit's own repo happens to use.

**Process tier**: `/setup-project`'s interview gained a second question — Solo/small vs.
Standard — that decides which `working-agreement.md` a generated project gets.
Standard is this kit's own current `.claude/working-agreement.md` (full five-step protocol,
a task contract before non-trivial work, ADRs for real design decisions); Solo/small is a
shorter version (`templates/working-agreement-solo.md.tmpl`) that drops the
mandatory task-contract-for-routine-changes and ADR requirements, while keeping branch
discipline and the review gate — those are hook-enforced and cheap regardless of project
size, so there was no reason to relax them.

`generate()` reconciles the file with whichever tier is picked, but asymmetrically, not a
blind overwrite either way: Solo converts whatever's currently there (subject to a
hand-customization check); Standard only ever writes to reverse a recognised prior Solo
choice, fill in a missing file, or (with `--force`) replace an unrecognised file — it never
rewrites an already-standard file just because it predates the current kit release.
Recognition (both "is this hand-customized?" and "was this a prior Solo choice?") is a static,
shipped digest list — `templates/known-working-agreement-digests.json`, sha256 of every
released default for both tiers, appended whenever either template changes, checked by a
parity test the same shape as `test_routing_doc_parity.py` — not a marker-comment convention
like `guard-paths.md`'s (a working agreement is prose meant to be read, not something that
looks machine-rendered) and not a git-history reconstruction, which an earlier design
attempted and review found to be a real trap: see "Why a static list, not git history" below.

This kit's own repo (`claude-project-kit`) stays at Standard/full-weight unconditionally —
it's the thing other repos build on, so it holds the higher bar (`CLAUDE.md` already says
this for the reviewer set; the same reasoning applies here).

## Why a static list, not git history

`bootstrap.sh` runs before the interview even exists, so it always ships the Standard default
unchanged via its existing `keep_file` convention. The first design for "does this target's
current file count as a recognised default" tried to reconstruct history at runtime — read
`.claude/.kit-version` (the kit commit SHA `bootstrap.sh` stamps) and `git show
<sha>:.claude/working-agreement.md` against the kit's own history. Review found this had a
real, structural flaw: `bootstrap.sh` restamps `.kit-version` on *every* re-run while
`working-agreement.md` itself is `keep_file`-protected, so the two drift out of sync the
moment anyone follows this kit's own documented upgrade path (re-run `bootstrap.sh`, then
re-run `/setup-project`) — completely routine usage, not an edge case.

The mechanism went through several review rounds — past this repo's 3-round cap, with the
owner explicitly authorizing a full rebuild once that pattern (clever mechanism, real
structural gap) repeated rather than another patch. The static digest list has none of that
coupling: correctness doesn't depend on git history, clone depth, or bootstrap/generate
timing being in any particular order. Full round-by-round detail — including the specific
defects each round caught — lives in this branch's `.claude/task/contract.md` amendments log,
not here: a live count or narrative of review rounds in a permanent reference doc is itself
the kind of thing that goes stale, so this file deliberately doesn't keep one.

## Consequences

- A plain `bootstrap.sh` run (no `/setup-project`) always gets Standard — a project that
  never runs the interview isn't silently downgraded.
- The tracker question currently only changes one line in the starter README's guidance
  text — the same "recorded now, more uses later" shape the CI-provider question already
  has, not a half-built mechanism pretending to be complete.
- If Solo tier turns out to need more differences than working-agreement.md wording (e.g. a
  different review-round cap), that's a separate decision for whenever it's actually
  observed being needed — not pre-built speculatively here.
- Editing either template now requires a manual step (append its new digest) that's easy to
  forget — mitigated, not eliminated, by a parity test that fails the build loudly if
  forgotten, the same tradeoff `review_routing.json`/`guard-paths.md` already accept.
