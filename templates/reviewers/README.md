# Reviewer module library

Hand-authored reviewer agents a project's setup can select and copy into
`.claude/agents/`, instead of every project inventing (or worse, not having) a
reviewer that actually matches its stack.

## Why modules, not a template you fill in

A reviewer synthesized purely from a few interview answers ends up generic —
and a generic reviewer rubber-stamps code outside its real competence. That
already happened once, for real: `football-data-pipeline`'s own
`review_routing.json` decision log records its `cto-reviewer` being required
on 28% of commits (including markup and analytics content it had no way to
judge well) until it was split into named specialists, which dropped that to
12%/24%. Each module here is hand-authored with a specific hunt list, the way
that split's replacements were — not generated from flags.

## Naming rule

Every module name describes what it actually checks, never a job title.
`scripts/lint_reviewer_name.py` enforces this as code (denylist: cto, cpo,
ceo, coo, cio, ciso, vp, evp, svp, director, head, chief, president, founder,
owner, manager, lead, boss, exec, executive — matched as whole tokens, so
`leaderboard-reviewer` is not flagged for containing "lead").

This kit's own self-governance reviewer used to be a documented exception —
`.claude/agents/cto-reviewer.md` — until it was retired in favor of shipping
`platform-reviewer.md` directly, so there is currently no live exception; a
future one would need the same kind of explicit callout, not silent reuse.

## `applies_when` tags

Each module's frontmatter carries an `applies_when` list of short tags. A
later setup step matches these against interview answers to decide which
modules to include. Current vocabulary:

| tag | meaning |
|---|---|
| `always` | every project gets this one |
| `dbt` | project uses dbt |
| `data-eng` | project has hand-written ingestion/ETL code |
| `frontend` | project has a UI |
| `sensitive-data` | project touches PII, credentials, or other sensitive data |

## Unmatched stacks

`_skeleton.md` (the leading underscore keeps it out of the naming lint and out
of any directory listing that only wants real modules) is a fallback: draft a
new reviewer from it for a stack nothing else here covers, and read it before
trusting it — an AI-drafted reviewer brief is not vetted the way the modules
above are.
