# Sandboxing is recommended, not defaulted on

**Status**: documented, not adopted as a default. Source: Anthropic's official
Claude Code documentation, fetched and read directly (not inferred from
memory) — `code.claude.com/docs/en/sandboxing`, September 2026.

## What `/sandbox` actually does

Claude Code's built-in sandbox restricts what a Bash command (and its child
processes) can access, enforced by the operating system rather than by Claude
Code itself:

> "The Bash sandbox lets Claude run most shell commands without stopping to
> ask permission. Instead of approving each command, you define which files
> and network domains commands can touch, and the operating system enforces
> that boundary for every Bash command and its child processes."
> — `docs/en/sandboxing`, "Configure the sandboxed Bash tool"

Two independent layers, each with its own citation:

> "Default write behavior: read and write access to the current working
> directory and its subdirectories, any directories you've added with
> `--add-dir`... plus the session temp directory... Default read behavior:
> read access to the entire computer, except certain denied directories.
> Note that this default still allows reading credential files such as
> `~/.aws/credentials` and `~/.ssh/`. Use `sandbox.credentials` to block
> reads of these files and unset secret environment variables, or add the
> paths to `denyRead`."
> — `docs/en/sandboxing`, "Filesystem isolation"

Stated plainly since it matters for the recommendation below: the default
read boundary is broad — credential files are readable unless explicitly
denied via `sandbox.credentials` or `denyRead`, per the quote directly
above. More broadly, Anthropic's own docs are explicit that sandboxing isn't
a complete boundary at all: "Sandboxing reduces risk but is not a complete
isolation boundary" (`docs/en/sandboxing`, "Limitations"). This document recommends sandboxing
as a real improvement over no isolation at all, not as a substitute for
reviewing what a session actually does.

> "Domain restrictions: Claude Code pre-allows no domains by default. The
> first time a command needs a new domain, Claude Code prompts for approval,
> or in auto mode sends the request to the classifier."
> — `docs/en/sandboxing`, "Network isolation"

Both layers are configurable via `sandbox.*` settings — see Anthropic's own
settings reference for the full list; this document doesn't duplicate it.

## How this relates to this kit's own gate — complementary, not overlapping

This kit's actual enforcement (`commit_review_gate.py`, `branch_discipline.py`)
and `/sandbox` operate at different points and by different mechanisms:

| | This kit's hooks | `/sandbox` |
|---|---|---|
| When it acts | Before a command runs | While a command runs |
| What it evaluates | The command string / a diff's review state | What the running process actually touches |
| Enforcement | Claude Code's own hook evaluation | The operating system |
| Real limits | A command that reads as safe but isn't fools a text-based check | Bash-only (Edit/Write tool calls aren't in scope at all); fails open if unavailable (see below); doesn't restrict anything actually *allowed* within its own boundary — a write inside the working directory, or traffic to an already-approved domain, goes through; reads are broad by default and include credential files unless explicitly denied |

The "operating system" enforcement row means literally the kernel, not a
Claude Code check:

> "The sandboxed Bash tool uses operating system security primitives: macOS:
> uses Seatbelt for sandbox enforcement; Linux: uses bubblewrap for
> isolation; WSL2: uses bubblewrap, same as Linux."
> — `docs/en/sandboxing`, "OS-level enforcement"

Anthropic's own docs make the same distinction between "before" and "while":

> "Claude Code evaluates permission decisions before a command runs, based on
> the command string and, in auto mode, a separate classifier's judgment about
> whether the command is safe. The operating system enforces the sandbox
> boundary on the running process, so it holds regardless of what the model
> chose to run and even if an allowed command does more than its name
> suggests."
> — `docs/en/sandboxing`, "How sandboxing relates to permissions and
> permission modes"

Neither replaces the other. This kit's gate stops an unreviewed commit before
it happens — the sandbox can't do that, since it only restricts a Bash
command's *access*, not whether a review was recorded. The sandbox stops a
compromised or overreaching command from touching things it shouldn't —
this kit's gate can't do that, since it evaluates a diff's review state, not
what an individual Bash command actually accesses while running.

## A real synergy, found in the docs rather than designed for

Anthropic's sandbox already protects a specific list of paths from writes by
sandboxed commands, independent of any configuration:

> "Inside the directories that sandboxed commands can write to, the sandbox
> still denies writes to the files Claude Code loads configuration and code
> from... It covers four groups of paths:
>
> * In your working directory and the directories above it: the `.claude`
>   settings files, the `.claude/skills`, `.claude/agents`, `.claude/commands`,
>   and `.claude/hooks` directories, `.mcp.json`, and the files Claude Code
>   runs on its own, such as `.claude/workflows` and
>   `.claude/scheduled_tasks.json`
> * In your working directory only: shell startup files such as `.bashrc`
>   and `.zshrc`, `.gitconfig`, the `.vscode` and `.idea` directories, and
>   `hooks` and `config` inside `.git`
> * Files that would turn your working directory into a bare git
>   repository: `HEAD`, `objects`, and `refs` at the top level, plus
>   `config` and `hooks` there when they already exist
> * In `~/.claude`, or the directory `CLAUDE_CONFIG_DIR` points to: most of
>   its contents, plus `~/.claude.json` and the `.credentials.json`
>   credential store"
> — `docs/en/sandboxing`, "Protected paths"

Checked against `.claude/rules/guard-paths.md`'s full 11 patterns, against
all four groups above: 4 match cleanly — `.claude/agents/*`,
`.claude/commands/*`, `.claude/settings.json`, `.mcp.json`. `*hooks/*`
matches partially — `guard-paths.md`'s glob matches a `hooks/` directory
anywhere in the tree (per this repo's own `review_routing.json` comment: "a
single `*` also matches across `/`"), while the quote protects specific
instances (`.claude/hooks`; `hooks` inside `.git`; a top-level `hooks` only
when mimicking a bare repo) — not a blanket "any `hooks/` directory,
anywhere." The remaining 6 patterns — `scripts/*`, `.claude/tests/*`,
`.github/workflows/*`, `requirements*.txt`, `.claude/review_routing.json`,
`.cursor/mcp.json` — appear in none of the four groups above. `.cursor/mcp.json`
is the sharpest of the six: `.mcp.json` is protected, an equally executable
Cursor config sitting right next to it is not. This is a partial,
coincidental overlap on 4-and-a-bit of 11 paths, not a general guarantee.

It's also scoped to Bash specifically, matching the whole document's own
opening scope: this blocks a *Bash command* from writing to those paths.
It says nothing about the Edit/Write tools:

> "Built-in file tools: Read, Edit, and Write use the permission system
> directly rather than running through the sandbox."
> — `docs/en/sandboxing`, "Scope"

So a compromised or overreaching *edit*, as opposed to a Bash command, is
untouched by any of this.

This is also not something to describe as a second enforcement layer
alongside `guard-paths.md` itself — that file is explicit that it names "a
procedural convention, not hook-enforced": "there is no equivalent of
`commit_review_gate.py` for 'which model did this reviewer actually run
on.'" `guard-paths.md` routes review scrutiny; it doesn't block writes at
all. So this sandbox protection isn't a second layer duplicating an existing
one — it's a genuinely new protection, on 4 (fully) plus 1 (partially) of the
11 paths this kit already flags as worth extra care by convention, that this
kit did nothing to build
and gets for free the moment sandboxing is enabled. Worth knowing about, not
worth overselling.

## Why `bootstrap.sh`-generated projects do NOT get this enabled by default

Recommended, not shipped as a default, for three concrete reasons:

1. **Platform support is real and this can't be verified live from every
   environment.** Sandboxing runs on macOS, Linux, and WSL2 only:

   > "Platform support: supports macOS, Linux, and WSL2. WSL1 and native
   > Windows are not supported."
   > — `docs/en/sandboxing`, "Platform and tool compatibility"

   This kit's own dev environment for this phase is native Windows — this
   ADR is written from research and direct documentation review, not from
   running a sandboxed command and observing the result. Stated plainly so
   this isn't confused with this repo's usual "verify by running" standard,
   which this phase does not meet.
2. **A default that silently no-ops on unsupported platforms while changing
   real behavior on supported ones is a visible product decision, not a
   safe-to-default toggle.** By design, when the sandbox can't start:

   > "By default, if the sandbox cannot start because dependencies are
   > missing or the platform is unsupported, Claude Code shows a warning and
   > runs commands without sandboxing. To make this a hard failure instead,
   > set `sandbox.failIfUnavailable` to `true`."
   > — `docs/en/sandboxing`, "Get started"

   > "On Linux and WSL2, the sandbox relies on two packages: `bubblewrap`,
   > the unprivileged sandboxing tool that enforces filesystem isolation, and
   > `socat`, the relay used to route network traffic through the sandbox
   > proxy."
   > — `docs/en/sandboxing`, "Set up Linux and WSL2"

   So a silent default would do nothing for users on native Windows without
   WSL2, or on Linux/WSL2 without `bubblewrap`/`socat` installed, while
   adding new filesystem/network prompts for everyone else it does apply to.
   How large either group is within this kit's own user base isn't something
   this document has data for — stated as a real, unquantified population,
   not a claimed majority.
3. **Enabling it project-wide can break a legitimate workflow without an
   obvious cause.** A script that writes outside the working directory (e.g.
   a build tool writing to a shared cache, or `npm`/`kubectl`/`terraform`
   touching `~/.kube` or similar) would need an explicit
   `sandbox.filesystem.allowWrite` entry to keep working — a real
   configuration step, not something a generated project should silently
   assume the owner wants to figure out.

Recommendation stands regardless, with the real cost stated rather than
waved away: a project owner who runs on macOS or Linux/WSL2 gains a genuine,
OS-enforced safety layer by running `/sandbox` — at the cost of the new
prompts and possible `allowWrite` configuration named in reasons 2 and 3
above. For most Bash usage confined to a project's own working directory,
that cost is small and one-time; for a workflow that legitimately writes
elsewhere, it's a real setup step, not nothing. Anthropic's own `/sandbox`
panel and settings reference cover the actual configuration (which mode to
pick, what to allow) — this document doesn't duplicate that, only the
decision of whether to adopt it as a kit default, which is: not yet, as an
owner's own deliberate choice instead.

## Consequences

- No code in this kit changes as a result of this document. `bootstrap.sh`,
  every hook, and every generated project's `settings.json` are unaffected.
- If a future phase of this kit's own work runs on macOS or Linux and can
  verify sandboxed behavior by actually running it, that phase should revisit
  whether a project-level `sandbox.enabled` recommendation belongs in the
  `setup-project` interview's output — this document intentionally stops
  short of that, since it can't be verified from here.
- If Anthropic's protected-paths list or platform support changes materially,
  re-verify this document's citations against the then-current docs before
  trusting it — it was accurate as of the date above, not guaranteed to stay
  so.
