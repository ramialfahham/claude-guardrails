# Guard paths — opus-on-touch convention

These paths ARE this repo's own review/governance mechanism — the hooks that
gate every commit, the reviewer agents, the routing that decides which
reviewer runs, and the CI that backstops all of it. A defect here doesn't
just ship a bug; it can silently weaken or disable the thing that's supposed
to catch defects in the first place.

**Convention**: when a diff you're about to send for review touches any path
in the list below, spawn the required reviewer(s) — currently `cto-reviewer`,
and any future function-named reviewer routed to a guard path — with
`model: opus` instead of their frontmatter default (`sonnet`). `scope-auditor`
is exempted: it's required on every commit regardless of path, so escalating
it here would multiply cost for the highest-frequency reviewer for no
proportionate benefit.

**This is a procedural convention, not hook-enforced.** A `PreToolUse(Bash)`
hook — this repo's entire enforcement mechanism elsewhere — cannot see a
Task-tool subagent spawn, so there is no equivalent of `commit_review_gate.py`
for "which model did this reviewer actually run on." Follow it because it's
the right call on a high-stakes diff, not because anything will stop you if
you don't. `.claude/tests/test_routing_doc_parity.py` only guarantees the
list below and `review_routing.json` agree with each other — it can't verify
a reviewer was actually spawned at the promoted model.

## Guard paths

- scripts/*
- .claude/tests/*
- .github/workflows/*
- requirements*.txt
- *hooks/*
- .claude/agents/*
- .claude/commands/*
- .claude/settings.json
- .claude/review_routing.json
- .mcp.json
- .cursor/mcp.json

## Exempted from escalation

- scope-auditor (see "Convention" above)
