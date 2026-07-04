# Review

Copy this to `.claude/task/review.md`. Stage your change first, then fill it in.
The commit gate reads this file and blocks the commit until it checks out.

Paste the staged-diff hash so the gate can confirm the review covers exactly
what you commit. Get it by running:

    python .claude/hooks/commit_review_gate.py --staged-hash

diff_sha256: <paste the 64-character hash here>

One `##` section per reviewer the routing requires for the staged files
(scope-auditor always; analytics-engineer for dbt files; cto for scripts/CI/
hooks; data-engineer for ingestion). Each must end with a VERDICT block.

## scope-auditor
VERDICT: PASS
risks_checked:
- <risk 1>
- <risk 2>

## analytics-engineer-reviewer
VERDICT: PASS
risks_checked:
- <risk 1>
- <risk 2>

<!-- If a reviewer returns ESCALATE, keep its `questions:` and add the owner's
     decision right beneath that section:
CPO ANSWER: <the decision> -->
