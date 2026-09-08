# Opus-on-guard-paths is a documented convention, not hook-enforced

**Status**: decided, shipped (Phase 4 of the master plan). Full text:
`.claude/rules/guard-paths.md`.

## Context

A diff that touches this kit's own governance machinery (hooks, reviewer
agents, routing config, CI) deserves more scrutiny than an ordinary change —
a defect there can silently weaken the thing meant to catch defects elsewhere.
The question: enforce that mechanically, or rely on the orchestrating agent to
follow a stated rule.

## Decision

A documented convention (`.claude/rules/guard-paths.md`, copied into every
generated project's `.claude/rules/guard-paths.md` by
`scripts/generate_project_setup.py`): when a diff touches a listed guard path,
spawn the required reviewer(s) at `model: opus` instead of their frontmatter
default. `scope-auditor` is exempted, since it already runs on every commit
regardless of path — escalating it would multiply cost for the
highest-frequency reviewer for no proportionate benefit.

## Why not a hook

A `PreToolUse(Bash)` hook — this repo's entire enforcement mechanism
everywhere else — cannot see a Task-tool subagent spawn, so there is no
equivalent of `commit_review_gate.py` for "which model did this reviewer
actually run on." `.claude/tests/test_routing_doc_parity.py` guarantees the
guard-path list and `review_routing.json` agree with each other, which is a
real, mechanically-checked guarantee — but it can't verify a reviewer was
actually spawned at the promoted model. That gap is accepted, not hidden: the
convention's own text says so directly.

## Consequences

- Following the convention on a high-stakes diff is a judgment call the
  orchestrating agent has to make correctly, every time — there's no gate
  that blocks a commit for skipping it.
- If this is ever observed leaking in practice (opus not actually used on a
  guard-path diff), a real enforcement mechanism (e.g. a `PreToolUse(Task)`
  hook, if the harness ever exposes one) is the fallback — not yet built,
  since the convention hasn't been observed failing.
