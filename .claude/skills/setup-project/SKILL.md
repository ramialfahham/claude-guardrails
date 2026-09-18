---
name: setup-project
description: Interview to select, preview, and (with explicit confirmation) generate reviewer modules, routing, guard-paths, and a starter README for a project from claude-project-kit.
disable-model-invocation: true
---

**Steps 1-6 are a dry-run preview only — they never create, copy, or modify
any file in any target project, no matter what is answered.** Real writes
only happen from step 7 onward, and only after an explicit SECOND
confirmation in step 9, separate from step 6's "does this reviewer set look
right" confirmation. State this distinction to the user before asking
anything, and restate what actually happened (or didn't) at the end.

**This skill only works from a `claude-project-kit` checkout.** It calls
`scripts/preview_project_setup.py`, which reads `templates/reviewers/` —
neither is copied into a repo bootstrapped from this kit (`bootstrap.sh`
copies `.claude/{hooks,agents,commands,skills,tests}` only). If that script
isn't found at the repo root, tell the user this skill needs to run from
inside the `claude-project-kit` repo itself, not from a project it already
set up, and stop — do not attempt the interview.

## Steps

1. Check `scripts/preview_project_setup.py` exists at the repo root (e.g.
   `ls scripts/preview_project_setup.py`). If it doesn't, say so per the note
   above and stop here.

2. Tell the user: "This previews what `claude-project-kit` would generate for
   a project — reviewer modules, routing, and the guard-paths convention. It
   writes nothing. Actual generation is a separate step, not built yet."

3. Ask ONE `AskUserQuestion` call with these four questions (the tool caps at
   4 per call — the unmatched-stack question is a separate call, step 3b).
   Every option below needs both a `label` (the exact text given) and a
   `description` (the tool requires both) — write a one-line description for
   each from its label's own meaning; none are spelled out verbatim here to
   keep this file from turning into a literal payload dump, but skipping the
   field isn't valid.
   - **Stack** (`multiSelect: true`, header "Stack"): "Which of these apply to
     this project?" — options: "Uses dbt", "Has hand-written ingestion/ETL
     code (not dbt)", "Has a frontend/UI", "Handles PII, credentials, or other
     sensitive/customer data". A plain project with none of these should end
     up with no boxes checked. If the interface won't let you submit with
     nothing selected, use "Other" and write "none — plain project" instead
     of forcing a checkbox — either way, treat the result as "none of the
     four apply" when you get to step 4 (no stack flags at all).
   - **CI provider** (header "CI provider"): "Which CI provider does this
     project use?" — options: "GitHub Actions", "GitLab CI", "Not decided
     yet". Note in your own words that this doesn't change today's preview
     (the shipped routing already covers both) — it's collected for a later
     phase.
   - **Tracker** (header "Tracker"): "Which issue tracker does this project
     use for what's ahead?" — options: "GitHub Issues", "GitLab Issues", "Not
     decided yet". Note in your own words: the roadmap is never a markdown
     file in this kit's convention — whichever tracker they name (or none
     yet) is what the starter README will point at instead.
   - **Process tier** (header "Process tier"): "How much process should this
     project's working agreement enforce?" — options: "Standard — full
     five-step protocol, task contracts, ADRs" (the default; the right choice
     for a team project or anything long-lived), "Solo/small — lighter
     working agreement, no mandatory task contract for routine changes, no
     ADR requirement" (branch discipline and the review gate still apply
     either way — this only changes how much process the *agent* is told to
     add on top). If genuinely unsure which fits, say so and default to
     Standard rather than guessing down.
   - **Unmatched stack** — this is step 3b's own `AskUserQuestion` call, not
     part of this one (see below).

3b. Ask a SEPARATE `AskUserQuestion` call (header "Other area"): "Is there a
    significant part of this project needing its own dedicated reviewer, not
    covered above (e.g. mobile app, ML training pipeline, embedded
    firmware)?" — options: "No, the above covers it" / "Yes, something else
    needs a dedicated reviewer". If the user uses the tool's automatic
    "Other" option to describe it directly, that free text is the
    description for step 5. If instead they pick the plain "Yes, something
    else needs a dedicated reviewer" option with no free text attached, ask
    ONE plain follow-up question in ordinary chat text — NOT another
    `AskUserQuestion` call, since there is no fixed set of options to offer
    here — such as "What is it?", and use their reply as the description for
    step 5.

4. Translate the STACK, CI PROVIDER, TRACKER, and PROCESS TIER answers into
   CLI flags and run, via Bash, from the repo root:
   ```
   python scripts/preview_project_setup.py [--dbt] [--data-eng] [--frontend] \
       [--sensitive-data] [--ci-provider github|gitlab|none] \
       [--tracker-provider github|gitlab|none] [--process-tier solo|standard]
   ```
   Include each boolean flag only if that option was selected. "Not decided
   yet" maps to `none` for both CI provider and tracker; "Standard" maps to
   the `--process-tier` default (omit the flag) and "Solo/small" maps to
   `--process-tier solo`.

   **The CLI has no flag for the unmatched-stack answer, and never pass it
   as an argument to any command regardless.** It is free text a user typed
   into an "Other" box; building a shell command out of unescaped user text
   would be a command-injection risk in a skill whose entire point is
   "writes nothing." Handle it in step 5 instead, in your own text — never
   by inventing a flag or working around its absence.

5. Show the script's stdout to the user VERBATIM. Do not re-derive, re-explain,
   or restate the module list, routing, or guard-paths content yourself — the
   script's output is the source of truth; your job is running it and
   displaying it, not narrating it.

   If step 3's unmatched-stack answer was anything other than "No, the
   above covers it", you now have a description — either the free text
   from "Other", or the plain-text follow-up reply. Add your own
   escalation note AFTER the script's output, in your own words, quoting
   that description back — for example:
   "Escalation: you mentioned '<description>' — no reviewer is drafted for
   this in this preview; drafting one from `templates/reviewers/_skeleton.md`
   is a later, separate step." Do this in plain text, never by re-invoking
   the script with that text as an argument.

6. Ask a second `AskUserQuestion` (header "Confirm"): "Does this reviewer
   set look right?" — options: "Yes, this is right" / "No, toggle one of
   the stack answers".
   - If toggling: ask a follow-up `AskUserQuestion` (header "Which tag?"):
     "Which one should flip?" — options: "dbt", "data-eng", "frontend",
     "sensitive-data" (4 options, all four of step 3's stack tags). Flip
     only that one boolean from step 3's answers, and repeat steps 4-6 with
     the updated flags.
   - If yes: continue to step 7.

7. Ask the user in plain text (not a tool call): "This preview is complete.
   Want me to actually generate these files into a project now? If so, give
   me the path to that project's repo root." If they decline, or don't give
   a path, stop here — restate plainly that this was a dry run and nothing
   was written. Never assume or guess a target path.

8. Check whether `<target>/.claude/settings.json` exists. If it doesn't,
   tell the user this project isn't bootstrapped by claude-project-kit yet
   and offer to run `scripts/bootstrap.sh <target>` — wait for their
   go-ahead before running it, never run it silently. If bootstrapping
   fails or they decline, stop here.

9. Ask ONE more explicit `AskUserQuestion` (header "Confirm write" — a
   separate confirmation from step 6's "does this reviewer set look right",
   since this one is about actually WRITING, a more consequential action):
   "Generate these files into `<target>` now? This writes real files:
   reviewer modules into `.claude/agents/`, a composed
   `.claude/review_routing.json`, a rendered `.claude/rules/guard-paths.md`,
   `README.md` if none exists yet, and — if Solo/small tier was chosen, the
   project is currently on Solo and Standard was chosen to switch it back,
   or `working-agreement.md` doesn't exist yet — a written or replaced
   `.claude/working-agreement.md`. Standard never rewrites an EXISTING,
   already-standard file (whatever kit version it came from) — only Solo, an
   explicit switch back from Solo, or filling in a missing file, ever
   touches it. And — only if a CI provider was given, not 'not decided yet'
   — `templates/ci-audit/ci_automation_audit.py` copied into
   `.claude/hooks/` and wired as a `SessionStart` hook in
   `.claude/settings.json` (idempotent — a second run never duplicates the
   entry)." — options: "Yes, generate now" / "No, stop here". If no: stop —
   the preview from steps 1-6 already showed what would happen; nothing has
   been written.

10. If yes: run, via Bash, from the repo root:
    ```
    python scripts/generate_project_setup.py --target "<target>" [--dbt] \
        [--data-eng] [--frontend] [--sensitive-data] \
        [--ci-provider github|gitlab|none] \
        [--tracker-provider github|gitlab|none] [--process-tier solo|standard]
    ```
    using the SAME flags step 4 already derived from the STACK/CI
    PROVIDER/TRACKER/PROCESS TIER answers. Never add `--force` yourself — it
    exists to deliberately overwrite a
    `review_routing.json`/`guard-paths.md`/`working-agreement.md` that already
    looks hand-customized, which is an owner decision the interview must never
    make silently on their behalf. Show its stdout VERBATIM — same "the
    script is the source of truth, never re-narrate its output" rule as
    step 5 — but ALSO check its exit code and stderr: a nonzero exit means
    it printed `REFUSED: ...` (generation itself refused — e.g. the target
    looks already customized) or `REFUSED (smoke test): ...` (generation
    succeeded but the smoke test didn't pass) on stderr. Show that line to
    the user plainly and stop; never treat a nonzero exit as if it
    succeeded, and never treat generation as fully verified unless the
    command actually exited 0 with the smoke-test line printed.

11. Close by restating plainly, in your own words: what was generated (the
    module list, whether the old `cto-reviewer.md` was removed, whether
    `README.md` was written or already existed and was left alone, and
    whether `working-agreement.md` was replaced or left alone). For
    `working-agreement.md` specifically, quote the script's own printed
    reason verbatim (its stdout line reads `working-agreement.md written:
    True/False (<reason>)`) — never guess or paraphrase a reason yourself,
    since there are more cases than "Solo changed it" / "Standard left it
    alone" (e.g. a hand-customized file left alone with no `--force`, which
    this skill never passes). If a CI provider was given, also say whether
    `ci_automation_audit.py` was installed and wired (quote its own two
    stdout lines the same way — `installed: True/False` and `wired into
    settings.json: True/False (<reason>)`; the reason distinguishes "already
    wired by a prior run or a hand-edit" from "no CI provider given", which
    the bare `wired: False` alone can't).
    Also say whether the smoke test confirmed the review gate fires for this
    project — or, if it was skipped or failed, say so exactly, never imply
    success it didn't earn.
