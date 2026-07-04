---
description: Snapshot of where work stands — branch, tree, open PRs + CI, and the active handover.
allowed-tools: Bash(git branch --show-current), Bash(git status --short), Bash(git log --oneline -5), Bash(gh pr list *), Read(.claude/active_work.md)
---

Give the user a fast, read-only situational snapshot. Be concise — short sections, no
preamble — and do NOT start any work.

## Branch & working tree
- Branch: !`git branch --show-current`
- Uncommitted changes: !`git status --short`
- Recent commits: !`git log --oneline -5`

## Open PRs + CI
!`gh pr list --state open --json number,title,headRefName,statusCheckRollup --jq '.[] | {pr: .number, branch: .headRefName, title, checks: [.statusCheckRollup[]? | (.conclusion // .status)]}'`

Summarize each open PR as one line: `#<n> <title> [branch] — CI: <pass/fail/pending>`.

## Active handover
Read `.claude/active_work.md` if it exists. Report ONLY the _Last updated_ line, the
**NEXT** actions, and any live **Do NOT** items. Don't reproduce the whole file.

## Bottom line
Close with 2–3 plain lines: where things stand and the single most likely next action.
This command is reporting only — take no action.
