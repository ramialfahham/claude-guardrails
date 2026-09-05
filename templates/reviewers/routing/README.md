# Routing fragments

One `<name>.routing.json` per reviewer module in `templates/reviewers/`, shape:

```json
{
  "always": false,
  "paths": ["scripts/*", "*hooks/*"]
}
```

`scripts/compose_routing.py` merges the fragments for whichever reviewers a
project selected into that project's `.claude/review_routing.json`.

## Two different meanings of "always" — don't conflate them

- A reviewer's own frontmatter `applies_when: [always]` (in
  `templates/reviewers/*.md`) means **always INCLUDE this reviewer when
  scaffolding a project** — a selection-time decision, made once, before any
  code exists.
- A fragment's `"always": true` here means **always REQUIRE this reviewer's
  sign-off on every commit, regardless of which files changed** — a
  routing-time decision, checked on every commit.

`platform-reviewer` is `applies_when: [always]` (every project gets it) but its
fragment is `"always": false` (it's still only required when the diff actually
touches its territory — scripts, hooks, CI, etc. — same as this repo's own
`cto-reviewer` today). `security-reviewer` is the opposite: only included when
a project says it touches sensitive data, but once included, `"always": true`
— sensitive-data handling isn't confined to a directory the way ingestion code
or dbt models are, so it can't be scoped by path the way the others can.

