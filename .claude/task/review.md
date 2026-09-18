# Review

diff_sha256: 5d31f087f1d2e998b316ef2f49b35007c42fec0c6bb94061464f7d697f05faf4

rounds: 3

Within the cap. Round-by-round findings and fixes are in `.claude/task/contract.md`'s
amendments. Round 2 was the first time the "Round completeness" rule this diff adds fired — the
opus platform-reviewer labelled both of its own round-2 findings "present since round 1 — review
miss", which is the behaviour the rule was written to produce.

## scope-auditor
VERDICT: PASS (round 3, final)
risks_checked:
- Scope: all changed files inside the contract's 13 `scope_paths`; no hook, script, or test-logic
  change; `_ROUNDS_CAP` and the CPO ANSWER convention untouched; no hook enforcement of the new
  rules added (both stay procedural, as the contract reserves).
- Authority: the rule change is the owner's "now, go" on the post-MR !33 diagnosis (A + B now,
  C deferred). Adding a "Claims against source" hunt item to every reviewer module — chosen in
  round 2 over deleting an unbacked sentence — judged the authorised implementation of (B), not
  a §6 rule extension. Replacing this branch's own never-released digests rather than
  accumulating them is a plain application of the "never remove" rule's stated purpose
  (protecting shipped defaults), not a reinterpretation.
- Consistency: the "Round completeness" bullet and the "Claims against source" item are
  textually identical across all 8 modules; both working agreements now state the same
  self-check with the same claim-type list (round 1's FAIL, fixed).

## platform-reviewer
VERDICT: PASS (round 3, final — opus, guard paths touched: templates/*, .claude/agents/*)
risks_checked:
- Every rule the diff adds names an input reviewers actually have: all 8 modules list
  `.claude/task/contract.md` under `## Inputs`; `task/CONTRACT_TEMPLATE.md` defines
  `amendments:` and `scripts/bootstrap.sh` ships that template, so the round-context reference
  resolves in generated projects, not just here (round 2's finding 2, fixed).
- "Reviewers are asked to check exactly this" is now backed by a numbered hunt item in all 8
  modules, numbered max+1 per module; nothing in `scripts/` parses hunt-list numbering
  (round 2's finding 1, fixed).
- Kit/template byte-identity for `platform-reviewer.md` holds (identical blob ids before and
  after in the patch).
- Digest list: all pre-existing digests retained vs main, two appended; the parity test
  `test_known_working_agreement_digests_lists_both_current_templates` runs fail-closed in both
  CI configs. Reviewer could not hash the files itself (no shell) — builder ran the test:
  passed, not skipped.
- Step renumbering in §2 leaves no dangling "step N" reference anywhere in the repo; the new
  bullet contains no `VERDICT:` line, so `commit_review_gate.py`'s parser is unaffected (it
  parses `review.md`, not agent files, regardless).
- Every behavioural claim in the diff checked against source (`_ROUNDS_CAP` at
  `commit_review_gate.py:65`; `rounds:` in `task/REVIEW_TEMPLATE.md:18`; the ADR quote in
  `active_work.md`; §2 section numbers) — all hold.
- Non-blocking, left as-is: `_skeleton.md`'s "Keep the item below as-is" could read "renumber it
  to follow your last item"; nothing parses the numbering.

Full test suite: 237 passed, 0 failed (`python -m pytest .claude/tests/ -q`, Windows); the
digest-parity test confirmed PASSED with `-rs`, not skipped.
