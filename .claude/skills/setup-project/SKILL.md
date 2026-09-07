---
name: setup-project
description: Interview to preview which reviewer modules, routing, and guard-paths a project would get from claude-guardrails. DRY RUN ONLY — writes nothing. Phase 6a; actual generation into a target project ships as a separate, later skill.
disable-model-invocation: true
---

**This skill performs a dry-run preview only. It never creates, copies, or
modifies any file in any target project, no matter what is answered.** State
this to the user before asking anything, and restate it at the end.

**This skill only works from a `claude-guardrails` checkout.** It calls
`scripts/preview_project_setup.py`, which reads `templates/reviewers/` —
neither is copied into a repo bootstrapped from this kit (`bootstrap.sh`
copies `.claude/{hooks,agents,commands,skills,tests}` only). If that script
isn't found at the repo root, tell the user this skill needs to run from
inside the `claude-guardrails` repo itself, not from a project it already
set up, and stop — do not attempt the interview.

## Steps

1. Check `scripts/preview_project_setup.py` exists at the repo root (e.g.
   `ls scripts/preview_project_setup.py`). If it doesn't, say so per the note
   above and stop here.

2. Tell the user: "This previews what `claude-project-kit` would generate for
   a project — reviewer modules, routing, and the guard-paths convention. It
   writes nothing. Actual generation is a separate step, not built yet."

3. Ask ONE `AskUserQuestion` call with these three questions. Every option
   below needs both a `label` (the exact text given) and a `description`
   (the tool requires both) — write a one-line description for each from
   its label's own meaning; none are spelled out verbatim here to keep this
   file from turning into a literal payload dump, but skipping the field
   isn't valid.
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
   - **Unmatched stack** (header "Other area"): "Is there a significant part
     of this project needing its own dedicated reviewer, not covered above
     (e.g. mobile app, ML training pipeline, embedded firmware)?" —
     options: "No, the above covers it" / "Yes, something else needs a
     dedicated reviewer". If the user uses the tool's automatic "Other"
     option to describe it directly, that free text is the description for
     step 5. If instead they pick the plain "Yes, something else needs a
     dedicated reviewer" option with no free text attached, ask ONE plain
     follow-up question in ordinary chat text — NOT another
     `AskUserQuestion` call, since there is no fixed set of options to offer
     here — such as "What is it?", and use their reply as the description
     for step 5.

4. Translate the STACK and CI PROVIDER answers into CLI flags and run, via
   Bash, from the repo root:
   ```
   python scripts/preview_project_setup.py [--dbt] [--data-eng] [--frontend] \
       [--sensitive-data] [--ci-provider github|gitlab|none]
   ```
   Include each boolean flag only if that option was selected.

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
   - If yes: stop.

7. Close by restating plainly: this was a dry run, nothing was written, and
   generating the actual files (copying reviewer modules, composing a real
   `review_routing.json`, writing a rendered `guard-paths.md`, a starter
   `README.md`, and the post-setup verification commit) is a separate skill
   that doesn't exist yet.
