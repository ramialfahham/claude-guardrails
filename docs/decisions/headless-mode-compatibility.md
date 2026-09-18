# Headless mode (`claude -p`): the gate holds, the human checkpoints don't apply

**Status**: verified, documented. Doc-only — no hook, script, template, or test
changes. Sources: Anthropic's official Claude Code documentation, fetched and
read directly on 2026-09-18 (`code.claude.com/docs/en/headless`,
`code.claude.com/docs/en/hooks-guide`, `code.claude.com/docs/en/agent-sdk/claude-code-features`),
plus six `claude -p` runs (Claude Code v2.1.223, model `haiku`, Windows) against
a throwaway repo bootstrapped with this kit's real `bootstrap.sh`. Every
behavioural claim below is either a quote with its page named or something
one of those runs printed.

## Context

Everything this kit enforces is a `.claude/settings.json` hook. Everything
else in its workflow — Explore → Plan → **Confirm** → Implement → Verify, the
plan-back gate, `CPO ANSWER:` for a reviewer's ESCALATE, `/setup-project`'s
interview — assumes a person is present to answer. `claude -p` (print /
non-interactive mode, also what the Agent SDK and CI integrations drive) has
no person. Two questions: do the hooks still run and still block, and what
becomes of the checkpoints that need a human.

## What the docs say

| Question | Documented answer (verbatim) | Page |
|---|---|---|
| Do project hooks run in `-p`? | "Without `--bare`, a `-p` session runs the hooks in a project's `.claude/settings.json` and connects the servers in its `.mcp.json`, even in a folder you've never trusted. A `-p` session shows no workspace trust dialog and no per-server approval prompt." | `headless`, "Start faster with bare mode" |
| What does `--bare` skip? | "Add `--bare` to reduce startup time by skipping auto-discovery of hooks, skills, custom commands, subagents, plugins, MCP servers, auto memory, and CLAUDE.md." | same |
| Will that stay opt-in? | "`--bare` is the recommended mode for scripted and SDK calls, and **will become the default for `-p` in a future release**." (emphasis added) | same |
| Does a hook `deny` survive bypass mode? | "`PreToolUse` hooks fire before any permission-mode check, in every permission mode, including `dontAsk`. A hook that returns `permissionDecision: "deny"` blocks the tool even in `bypassPermissions` mode or with `--dangerously-skip-permissions`. This lets you enforce policy that users can't bypass by changing their permission mode." | `hooks-guide`, "Hooks and permission modes" |
| What permission mode does `-p` start in? | "For `-p`, the built-in starting permission mode is Manual on every plan" | `headless`, "Auto-approve tools" |
| What happens to a prompt nobody can answer? | "In a `-p` run with no host, these requests are denied either way" | `headless`, "Turn off permission prompts in unattended runs" |
| `AskUserQuestion`? | With `--permission-prompts none`: "Claude Code removes the tools that need an answer from a person, such as `AskUserQuestion`, so Claude can't call them." Under `dontAsk`: "`AskUserQuestion` … are denied even when an allow rule matches" | same page, two sections |
| Subagents in `-p`? | "If Claude starts a background subagent or workflow, `claude -p` instead stays open until that work completes" — and, for their tool calls: "Background subagents can't show a prompt in non-interactive mode. Claude Code still runs the hooks for their tool calls, and if no hook returns a decision, it denies the call." | `headless`, "Background tasks at exit"; `hooks-guide`, "Hooks and permission modes" |
| Agent SDK: are project hooks loaded? | "When you omit `settingSources`, `query()` reads the same filesystem settings as the Claude Code CLI: user, project, and local settings … To run without these, pass `settingSources: []`." "Filesystem hooks: shell commands defined in `settings.json`, loaded when `settingSources` includes the relevant source." "Omitting `settingSources` is equivalent to `["user", "project", "local"]`." And on where: "Project `settings.json` and hooks load only from `<cwd>/.claude/` with no parent-directory fallback." | `agent-sdk/claude-code-features`, intro and "Control filesystem settings with settingSources" / "Hooks" |

Not documented anywhere fetched: whether `CLAUDE_PROJECT_DIR` is set for
hook commands in `-p` (every hook in this kit is wired as
`${CLAUDE_PROJECT_DIR}/.claude/hooks/…`, so this is load-bearing — run 2
below settles it).

## What was run

Fixture: fresh git repo, `bootstrap.sh` applied, branch `feat-x`, one staged
unreviewed file (`hello.txt`), a one-line `.claude/active_work.md`. Each run
was `claude -p --model haiku --output-format json` from inside that repo, with
the parent session's `CLAUDECODE`/`CLAUDE_CODE_*` variables unset so the child
CLI authenticated on its own OAuth login.

| # | Command (flags beyond the common ones) | Observed |
|---|---|---|
| 1 | `--permission-mode acceptEdits --allowedTools Bash`, prompt: run `git commit -m "add hello"` | Result quoted `REVIEW GATE: no review found. Stage the change, run the required reviewers, and write .claude/task/review.md …`; `permission_denials` had one entry for that Bash call; `git log` unchanged. **`commit_review_gate.py` fires and blocks headless.** |
| 2 | `--max-turns 2`, prompt: "Do not use any tool … quote the TASK line from the active-work handover you were given at session start, or reply NONE" | Result: `` `hello.txt must contain exactly 'hello'. Nothing else.` `` — the fixture's handover text. **`SessionStart` (`handover_in.py`) fires headless, and `${CLAUDE_PROJECT_DIR}` resolved to the repo** (the hook command is that path). |
| 3 | `--dangerously-skip-permissions`, same commit prompt | Result: `REVIEW GATE: no review found …`; one denial; no commit. **A hook `deny` blocks under `bypassPermissions`**, as the docs now state. |
| 4 | `--bare --dangerously-skip-permissions`, same commit prompt | `is_error: true`, result `Not logged in · Please run /login`. **Not verifiable here**: bare mode "never reads OAuth credentials or the system keychain" (`headless`, same section) and needs `ANTHROPIC_API_KEY`, which this environment doesn't have. The hook-skipping claim rests on the docs alone. |
| 5 | `--max-turns 4`, prompt: "use the AskUserQuestion tool right now … if not available reply exactly TOOL_NOT_AVAILABLE" | Result: `TOOL_NOT_AVAILABLE`, one turn, no tool call. **The tool is not offered in plain `-p`** — not "denied when called", absent. |
| 6 | As run 1, after writing a `review.md` with the current `--diff-hash` and a `scope-auditor` PASS | Result: `COMMITTED`; `git log` gained `add hello`. **The gate discriminates headless — it isn't an always-deny.** |

## Conclusion

1. **The review gate holds.** Runs 1, 3 and 6 show `commit_review_gate.py`
   denying without a review, denying under `--dangerously-skip-permissions`,
   and allowing with a valid one. The other two deny-capable hooks
   (`branch_discipline.py`, `secret_scan.py`) share the same `PreToolUse(Bash)`
   wiring and the same `${CLAUDE_PROJECT_DIR}` path that run 2 proves resolves,
   and decide from repository state the same way — but neither was pushed to
   deny in a headless run, so for them this is inference from the wiring, not
   observation (see "What this does NOT cover").
2. **The human checkpoints degrade to fail-closed, not to silent approval.**
   `AskUserQuestion` doesn't exist in `-p` (run 5), so a `CPO ANSWER:` can't
   be obtained; the commit gate then keeps refusing until a person writes
   one. The Confirm step and the plan-back gate are advisory text — a headless
   model may read "wait for the user's go" and proceed, since there is no user
   — but the only thing that has consequences, the commit, is still gated.
   `/setup-project`'s interview cannot run headless either: its four decision
   points are `AskUserQuestion` calls (`SKILL.md` steps 3, 3b, 6, 9) and its
   remaining questions are plain-text prompts to the user (steps 3b's
   fallback, 7) — both need a person.
3. **The real off-switch is `--bare`, not a permission mode.** It skips hook
   loading entirely, is Anthropic's recommendation for scripts and the SDK,
   and is slated to become `-p`'s default. When that lands, a headless caller
   gets this kit's gate only by *not* passing `--bare` (or by supplying the
   hooks via `--settings`). The Agent SDK is the other way in: today it loads
   project hooks by default, and `settingSources` can drop `"project"`.

## What this does NOT cover

- `--bare` was not run (run 4) — its hook-skipping is documented, not
  observed. An environment with `ANTHROPIC_API_KEY` could close this in one
  command.
- The Agent SDK (`query()`) was not exercised; its behaviour is taken from
  the docs table above.
- Only `commit_review_gate.py` and `handover_in.py` were observed firing.
  `branch_discipline.py` and `secret_scan.py` share the same `PreToolUse(Bash)`
  wiring and the same `${CLAUDE_PROJECT_DIR}` path, and run 2 proves that path
  resolves, but neither was pushed to deny in a headless run.
- Windows only, one Claude Code version (2.1.223). `--permission-prompts`
  (documented as v2.1.259+) doesn't exist on this version and wasn't tested.
- Runs used `haiku` with small `--max-turns`; the model's *compliance* with
  the advisory checkpoints (would a headless model stop at "wait for go"?)
  was not measured — only whether the gate held regardless.

## Consequences

- No code in this kit changes. Nothing needs redesign for headless use.
- Open owner call, not decided here: whether the `--bare` default flip
  deserves a warning in `README.md` or in what `/setup-project` prints —
  today a CI script that adds `--bare` (as Anthropic's own examples do) runs
  with this kit's gate silently off.
- If this kit is ever driven from the SDK, keep `settingSources` at its
  default or include `"project"`, and pass the repo root as `cwd` — the hooks
  load only from `<cwd>/.claude/`, with no parent-directory fallback. Both
  are documented conditions, neither was run here.
- `auto-mode-and-bypass-compatibility.md`'s "not confirmed" gap is closed by
  the same doc quote and run 3; that ADR carries a dated update pointing here.
