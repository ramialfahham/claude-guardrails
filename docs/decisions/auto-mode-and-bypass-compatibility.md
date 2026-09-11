# This kit's `PreToolUse` enforcement is unaffected by permission mode

**Status**: verified, documented. Source: Anthropic's official Claude Code
documentation, fetched and read directly (not inferred from memory) —
`code.claude.com/docs/en/hooks`, `code.claude.com/docs/en/permissions`,
`code.claude.com/docs/en/permission-modes`, September 2026.

## Context

Auto mode — a classifier model that reviews actions instead of prompting the
user — is now the *default* starting permission mode on Pro, Max, and Team
plans. This kit's actual enforcement is two `PreToolUse(Bash)` hooks,
`commit_review_gate.py` and `branch_discipline.py`. (`completion_gate.py`, a
third hook added alongside this document, is ALSO a `PreToolUse` hook — see
its own scope note below for why it is still not an enforcement mechanism
despite sharing the event.) Those two enforcing hooks were built and shipped
across Phases 1-7 without ever checking whether they still function
correctly once a session is running in auto mode instead of the traditional
"ask before every action" mode.

## What the docs actually say

Verified via direct quotes, not assumption:

> "PreToolUse hooks run before the permission prompt, for every tool except
> `EndConversation`. The hook output can deny the tool call, force a prompt,
> or skip the prompt to let the call proceed."
> — `docs/en/permissions`, "Extend permissions with hooks"

> "A blocking hook also takes precedence over allow rules. A hook that exits
> with code 2 stops the tool call before permission rules are evaluated, so
> the block applies even when an allow rule would otherwise let the call
> proceed."
> — `docs/en/permissions`

On the auto-mode classifier specifically — this is the load-bearing quote,
given here with its full surrounding sentence rather than an isolated
fragment, since a shorter excerpt could read as ambiguous about what it's
actually describing:

> "A hook's `"ask"` also forces a permission prompt in auto mode: the
> classifier can still deny the tool call, but it can't approve the call
> silently. Before v2.1.211, the classifier could approve a Bash command
> running outside the sandbox without showing the prompt the hook requested;
> the classifier still applied its own safety rules to that command, and a
> hook `"deny"` was always honored."
> — `docs/en/hooks`, PreToolUse decision-control section

Read in full, this states plainly that a `PreToolUse` hook's `"deny"` is
honored regardless of what the auto-mode classifier would otherwise decide
— both before and after the v2.1.211 fix described, the sentence's own
structure separates the historical `"ask"` bug (fixed) from the `"deny"`
guarantee (stated as holding throughout, not scoped to the fix).

## Conclusion — scoped precisely to what's enforcing

A `PreToolUse` hook's `deny` decision is evaluated **before**, and takes
precedence over, both permission rules and the auto-mode classifier. This
kit's two enforcing hooks (`commit_review_gate.py`, `branch_discipline.py`)
decide `deny` vs. `allow` purely from repository/diff state (routing
config, `review.md`, staged paths, branch name) — neither reads or branches
on `permission_mode` anywhere in its source. So this kit's actual
enforcement fires identically whether a session is in Manual mode or auto
mode. No code change was needed to close this gap — only verifying and
recording it.

**`completion_gate.py` is out of scope for this specific guarantee, by
design, even though it is the same `PreToolUse` event as the two enforcing
hooks.** It never sets `permissionDecision` at all — allow, deny, ask, or
defer — it only calls `hookSpecificOutput.additionalContext`, which
Anthropic's own PreToolUse decision-control reference describes plainly:
"String added to Claude's context alongside the tool result... See Add
context for Claude" (`docs/en/hooks`, "PreToolUse decision control" table).
Since it never makes a permission decision of any kind, the auto-mode
classifier has nothing to override for this hook — the
deny-survives-the-classifier guarantee above is about a different field
this hook never sets. (An earlier version of this hook used the `Stop`
event instead; that design was scrapped after discovering `Stop`'s
`additionalContext` is not actually passive — see `completion_gate.py`'s own
docstring for the full citation and reasoning. `PreToolUse`'s
`additionalContext`, by contrast, is genuinely non-blocking, which is why
this hook lives on this event now.)

`.claude/tests/test_hooks_import.py`'s
`test_gate_hooks_never_branch_on_permission_mode` is a **tripwire**, not the
reason this claim holds. Whether a hook's `deny` survives auto mode is
determined by Claude Code's own evaluation order (documented above), not by
whether the hook's source happens to mention `permission_mode`. The test
exists so that if one of these hooks is ever changed to branch on
`permission_mode` for some reason, that change forces a re-read of this
document rather than silently drifting from what it claims — it is a
regression guard on this document's continued accuracy, not the mechanism
that makes the document true today.

## What is NOT confirmed — stated honestly, not glossed over

The docs make no equivalent explicit statement for `bypassPermissions` mode.
The closest related sentence — "Deny rules block in every mode, including
`bypassPermissions`" — is about **permission deny *rules*** (`permissions.deny`
config entries), a different mechanism from a **hook's** `permissionDecision:
"deny"`. The general architecture (hooks run before the permission system,
independent of mode) strongly suggests the same holds for `bypassPermissions`,
but that is an inference, not a documented guarantee. `bypassPermissions` is
explicitly described elsewhere as intended "only in isolated environments
like containers, VMs, or dev containers... where Claude Code cannot damage
your host system" — so this gap is lower-stakes than it might sound, but it
is a real, named gap, not a confirmed guarantee this document is choosing to
overstate.

## Consequences

- This kit's two enforcing hooks do not need a "does this still work under
  auto mode" redesign — they already work, by construction, because they
  never depended on the permission-prompt layer in the first place.
- If a future hook in this kit that DOES enforce (denies/blocks) ever needs
  to read `permission_mode` for some reason, that is exactly the moment to
  re-verify this document's claim against Anthropic's then-current docs, not
  assume it still holds — the regression test named above exists
  specifically to force that re-verification rather than let it drift
  silently.
- `bypassPermissions` compatibility is not asserted here; if this kit is ever
  used in a context that relies on `bypassPermissions` mode specifically
  (a container/VM with no interactive session), that assumption should be
  checked directly rather than assumed from this document.
