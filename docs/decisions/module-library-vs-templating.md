# Reviewer module library, not template parameter-substitution

**Status**: decided, shipped (Phase 1 of the master plan).

## Context

Generating a project-tailored reviewer set could work two ways: synthesize a
generic reviewer from the interview's answer flags (parameterized template —
"you said dbt, so add a dbt-checklist section"), or maintain a small library of
separately hand-authored reviewer modules and select/combine them.

## Decision

A library. `templates/reviewers/*.md`, each a real, standalone reviewer file
with its own frontmatter (`applies_when`, `model`, `tools`) and its own
hand-written review checklist — never assembled from fragments at generation
time. The interview (`scripts/select_reviewer_modules` in
`scripts/preview_project_setup.py`) only picks WHICH existing modules apply;
it never writes reviewer prose.

## Why

A reviewer synthesized purely from interview flags reproduces a failure this
kit's own sibling project already had and fixed once: one overloaded reviewer,
required on a large share of commits, rubber-stamping code well outside its
actual competence — until it was split into `platform-reviewer`/
`data-engineer-reviewer`/etc. as separate, focused modules. A parameterized
template is exactly the "one reviewer, many hats" shape that split was meant
to get away from. Naming discipline is enforced separately
(`scripts/lint_reviewer_name.py` rejects corporate-title names like
`cto-reviewer` for anything new), and the library grows the same way —
deliberately, one hand-authored module at a time
(`scripts/promote_reviewer.py`), never pre-guessed upfront for stacks nobody
has actually needed yet.

## Consequences

- An unmatched stack today gets a pass-through escalation note for a human to
  read (`preview_project_setup.py`'s `build_escalations`) — no reviewer is
  drafted or installed automatically. `templates/reviewers/_skeleton.md` is
  the scaffold a human starts from when writing one by hand; the interview
  doesn't reach for it itself. (A generation step that drafts from it
  automatically was scoped out of Phase 6b explicitly — see that phase's
  contract — not yet built.)
- The library is small today (5 modules) and grows by evidence, not
  speculation — a project's real review history is what justifies adding one.
