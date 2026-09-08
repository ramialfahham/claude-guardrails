# No confidential-scope-doc / summarization step in the interview

**Status**: decided, cut (during Phase 6b planning). Source: Phase 6b's
`.claude/task/contract.md` amendments log (that phase's git history).

## Context

An earlier version of this plan's `setup-project` interview included a step
where the owner could paste project-specific context (client name, internal
system names, business rules) that the kit would summarize into `CLAUDE.md`,
keeping the full text in a separate `.claude/rules/` file — the idea being to
keep the most-read file (`CLAUDE.md`) clean while still giving Claude the
context it needs.

## Decision

Cut entirely, not deferred. No such step exists anywhere in the interview or
generation flow. Project-specific context is something the owner writes by
hand later, deliberately, once they've decided what's actually safe to
include — never something the setup wizard prompts for.

## Why

An automated setup step that invites pasting client names, internal system
names, or business rules into a new repo is a bad default regardless of where
the text ends up — the "summarize vs. keep full" question was solving the
wrong problem (WHERE the sensitive text lives), when the real problem was
whether an automated flow should be soliciting it AT ALL. Neither sibling
repo this kit's design draws from (`dbt-agent-kit`, `football-data-pipeline`)
had this pattern to build from either — checked directly before the decision
was made, not assumed.

## Consequences

- The interview (`.claude/skills/setup-project/SKILL.md`) never asks for or
  writes project-specific business context. Its one free-text field
  (`unmatched_stack_description`) is a narrow "what stack am I missing"
  escalation note, never treated as project context and never written to any
  file — only ever a pass-through prompt for a human to read.
- If a real need for structured project context re-emerges later, it needs
  its own fresh design conversation with the owner — this was a deliberate
  cut, not a placeholder.
