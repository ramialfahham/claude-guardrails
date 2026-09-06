# Review

Copy this to `.claude/task/review.md`. Stage your change first, then fill it in.
The commit gate reads this file and blocks the commit until it checks out.

Paste the diff hash so the gate can confirm the review covers exactly what the
branch will contain after this commit — the CUMULATIVE diff (everything
already committed on this branch since it split from main/master, plus what's
currently staged), not just this commit's own staged diff. Get it by running:

    python .claude/hooks/commit_review_gate.py --diff-hash

diff_sha256: <paste the 64-character hash here>

If review.md gets rewritten more than once for the same round of work (a FAIL,
fixed, re-reviewed), record which attempt this is:

rounds: <2, 3, ... — omit on the first attempt, it defaults to 1>

Past round 3, the gate blocks until a `CPO ANSWER:` is recorded anywhere in
this file — the owner needs to see why review keeps failing, not just get
another silent re-try. `rounds:` is self-reported: increment it yourself each
time you rewrite this file after a FAIL, don't rely on the gate to count for you.

One `##` section per reviewer the routing requires for the changed files
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
