# Task contract

objective: First of the deferred "later phases" from "Post-plan hardening" (see
  `C:\Users\Rami\.claude\plans\happy-stargazing-mccarthy.md`'s "Later phases (not
  yet contracted)" list) — sandboxing adoption. Anthropic's `/sandbox` restricts
  what a Bash command can access at the OS level (filesystem writes, network
  domains), enforced by the kernel regardless of what the command claims to do —
  complementary to, not a replacement for, this kit's own hook-based governance
  (hooks decide whether a command runs; the sandbox restricts what it can touch
  once running). Research (direct fetch of Anthropic's official
  `code.claude.com/docs/en/sandboxing`, not from memory) found one concrete
  synergy worth documenting: the sandbox's own built-in "protected paths" list
  already blocks writes to `.claude/hooks`, `.claude/agents`, `.claude/commands`,
  `.mcp.json`, and settings files — a partial overlap with this kit's
  `guard-paths.md` convention (4 of 11 patterns cleanly, 1 more partially —
  see the round-1/2/3 amendments for how this count was corrected across
  review), not the "exactly the paths" claim this objective originally made
  before review caught it — with zero configuration required from this kit
  for the paths it does cover. This contract: document sandboxing and its
  relation to
  this kit's gate, recommend project owners enable it themselves. Explicitly does
  NOT make `bootstrap.sh`-generated projects sandbox-enabled by default — see
  decisions_reserved.

scope_paths:
  - docs/decisions/sandboxing-recommended-not-defaulted.md
  - docs/project-kit-design.md
  - README.md
  - .claude/active_work.md
  - .claude/task/contract.md
  - .claude/task/review.md

decisions_reserved:
  - **`bootstrap.sh`-generated projects do NOT get `sandbox.enabled: true` by
    default — documented and recommended, not silently defaulted on.** Owner
    decision, made explicitly during planning (the owner approved this exact
    framing before implementation started). Reasoning: (1) sandboxing only runs
    on macOS, Linux, and WSL2, not native Windows (confirmed directly against
    Anthropic's docs) — this exact dev box can't run it, so this phase can't
    verify sandboxed behavior live, only via research and review, short of this
    repo's own established "verify by running" standard; (2) a project-wide
    default that silently no-ops on unsupported platforms while changing
    behavior (more prompts, restricted writes) on supported ones is a real,
    visible behavior change a project owner should choose consciously, not
    inherit silently from a kit default; (3) enabling it project-wide could
    break a script that legitimately writes outside the working directory
    without the project owner understanding why, until they read the ADR this
    contract adds.
  - The new ADR states the platform limitation plainly (not native Windows) and
    the verification limitation plainly (documented from research, not
    confirmed by running sandboxed commands on this dev box) — this must not be
    overstated as "tested" when it wasn't.
  - Parallel-session/worktree safety audit and headless-mode compatibility audit
    (the other two deferred phases) are explicitly OUT of scope for this
    contract — do not fold either in here even if related issues are noticed in
    passing; flag separately instead.

done_when:
  - `docs/decisions/sandboxing-recommended-not-defaulted.md`: new ADR. States
    what `/sandbox` does (filesystem + network isolation for Bash subprocesses,
    OS-enforced), how it differs from and complements this kit's hook-based gate
    (different layer, different enforcement point — cites the real distinction:
    permission rules/hooks evaluate before a command runs based on command
    text/classifier judgment, the sandbox enforces on the running process
    regardless), the protected-paths synergy (cites the real doc text, all
    four groups in full: sandbox denies writes to `.claude/hooks`,
    `.claude/agents`, `.claude/commands`, `.mcp.json`, settings files, and
    others — a partial, coincidental overlap with 4 of `guard-paths.md`'s 11
    patterns cleanly and 1 more (`*hooks/*`) partially, not the full list and
    not by this kit's own design), the platform limitation (macOS/Linux/WSL2
    only), and the not-defaulted decision
    with its real reasoning (see decisions_reserved). Recommends project owners
    run `/sandbox` themselves and points at Anthropic's own docs for
    configuration detail — does not duplicate Anthropic's settings reference.
  - `docs/project-kit-design.md`: gains a short pointer to the new ADR, sized
    like the existing ADR pointers in that file (one or two sentences, not a
    re-explanation).
  - `README.md`: gains a short mention if there's a natural place for it (e.g.
    near other security/hardening mentions) — skipped if it would be a forced
    insertion with no natural anchor point.
  - No code changes anywhere — `bootstrap.sh`, `.claude/hooks/*`,
    `.claude/settings.json`, and every existing template are untouched.
  - scope-auditor PASS (required on every commit per `review_routing.json`'s
    `always` list). Checked `review_routing.json`'s `paths` map directly:
    none of `docs/decisions/*`, `docs/project-kit-design.md`, or `README.md`
    match any pattern that routes to `cto-reviewer` — this is the first phase
    in this hardening initiative where that's genuinely true, since it's pure
    documentation touching no guard path. Dispatching cto-reviewer anyway for
    a real second opinion given the size of this change, but it is not a
    routing requirement — record that distinction plainly rather than
    implying the routing config demanded it.

amendments:
  - 2026-09-11 — contract created after research (direct fetch of Anthropic's
    sandboxing docs) and a short plan presented to the owner in chat (not
    formal plan mode, given the small scope) — owner said "go ahead" on the
    proposed scope, including the one real judgment call (document-not-default)
    with its reasoning stated up front.
  - 2026-09-11 — round 1 review: scope-auditor FAIL, cto-reviewer FAIL. Both
    independently found the same central defect (converging findings, not
    duplicated ones — real confirmation): the ADR's "overlaps almost exactly"/
    "covers most" claim about the sandbox's protected-paths list vs. this kit's
    `guard-paths.md` was false — `guard-paths.md` names 11 patterns, the sandbox
    list covers 5 (`*hooks/*`, `.claude/agents/*`, `.claude/commands/*`,
    `.claude/settings.json`, `.mcp.json`); it does NOT cover `scripts/*`,
    `.claude/tests/*`, `.github/workflows/*`, `requirements*.txt`,
    `.claude/review_routing.json`, or `.cursor/mcp.json` — the uncovered half
    includes this kit's entire executable surface. Also found:
    - The synergy claim silently dropped the document's own Bash-only scope,
      reading as a general write-protection backstop when Edit/Write tool
      calls aren't covered by the sandbox at all.
    - "A second, independent layer protecting the same files, not a duplicate
      of the first" misrepresented `guard-paths.md` itself, which explicitly
      states it is "a procedural convention, not hook-enforced" — it routes
      review, it doesn't block writes, so there was no "first layer" to be
      second to.
    - The closing recommendation's "essentially no downside" directly
      contradicted the same document's own stated reasons 2 and 3 (new
      prompts; possible `allowWrite` configuration needed).
    - "auto-allow mode" (the closing recommendation) vs. "auto-mode classifier"
      (§1) read as inconsistent terminology for two actually-different
      sandbox/permission-mode concepts, without ever explaining the
      distinction — confusing as written even if each term individually named
      a real thing.
    - Two technical claims (fail-open-when-unavailable behavior; Seatbelt on
      macOS / bubblewrap on Linux+WSL2) were stated as fact with no citation,
      in a document whose own Status line advertises direct sourcing for
      every load-bearing claim — inconsistent with the document's own stated
      standard.
    - **Fixed**: the overlap claim corrected to state "5 of 11" precisely, with
      the uncovered 6 named; the Bash-only scope stated explicitly at the
      point of the synergy claim, not just in the document's opening; the
      "second layer" framing replaced with an accurate description (a new,
      free protection on already-flagged paths, not a second layer alongside
      a non-existent first one); the "essentially no downside" claim replaced
      with an honest statement of the real, already-named costs; the
      ambiguous "auto-allow mode" recommendation dropped entirely (this
      document doesn't need to recommend a specific sandbox mode — Anthropic's
      own panel/settings reference already covers that) rather than trying to
      explain a distinction not central to this document's point; both
      previously-uncited claims given real citations (`docs/en/sandboxing`,
      "Get started" and "OS-level enforcement" respectively).
      `docs/project-kit-design.md`'s matching "covers most" claim corrected to
      match.
    - No `CPO ANSWER:` needed — within the 3-round cap.
  - 2026-09-11 — round 2 review: scope-auditor FAIL, cto-reviewer FAIL. Both
    independently caught the same broken cross-reference (real confirmation, not
    duplication): a sentence pointed at "see 'Scope' in Anthropic's own docs,
    cited in Limitations below" — this document has no "Limitations" section at
    all, so the citation the round-1 Bash-only-scope fix promised was never
    actually delivered. Also found:
    - scope-auditor: the round-1 protected-paths quote was truncated with an
      ellipsis (`.mcp.json`...) at exactly the point that decides whether the
      "does NOT cover the other 6" negative claim is correct — a negative claim
      can't rest on a citation that cuts off mid-enumeration.
    - scope-auditor: "the uncovered half includes this kit's entire executable
      surface" directly contradicted the same paragraph's own count 3 lines
      earlier, which puts `*hooks/*` — the actual location of this kit's
      enforcement code (`commit_review_gate.py`, `branch_discipline.py`,
      `completion_gate.py`) — in the covered 5. Self-contradiction of the same
      class round 1 FAILed on ("essentially no downside" vs. stated costs),
      this time rounding pessimistically instead of optimistically.
    - cto-reviewer: `*hooks/*` was counted as one of "5 fully covered," but the
      quote only protects the specific `.claude/hooks` directory while
      `guard-paths.md`'s glob matches `hooks/` anywhere in the tree — counting
      it as a full match rounds up exactly the way the paragraph itself warns
      against 8 lines later.
    - cto-reviewer: the "Two independent layers" opening paragraph (filesystem
      defaults, network domain-approval behavior, `sandbox.*` configurability)
      had zero citations for any of its 4 factual claims, in the one section
      `done_when` specifically requires be sourced; and the network-domain
      claim attributed approval to "the auto-mode classifier," a term the
      document's OWN cited quote (§2, permission decisions generally) doesn't
      actually establish for network-isolation specifically — a second,
      independent citation was needed, not reuse of the first.
    - scope-auditor: `.claude/active_work.md` still listed sandboxing under
      "Later phases... (not yet contracted)," which this branch makes false,
      with no recorded decision to defer the fix or update it in-branch.
    - **Fixed**: the protected-paths quote now given in full (verified against
      the raw source — no additional `guard-paths.md` patterns hide behind the
      ellipsis; the 4-full-plus-1-partial count was already correct and stays
      unchanged); the "5 covered" claim corrected to "4 fully, 1 partially"
      with the `*hooks/*` nuance stated explicitly; "entire executable surface"
      corrected to name only the actually-uncovered build/CI/dependency
      surface, with `.claude/hooks/*.py` itself explicitly noted as covered;
      the broken "Limitations" forward-reference replaced with the real
      `docs/en/sandboxing` "Scope" quote inlined at that point; the opening
      "Two independent layers" paragraph given two real, separate citations
      (`docs/en/sandboxing`'s own "Filesystem isolation" and "Network
      isolation" sections — the network-isolation quote independently
      confirms the auto-mode-classifier claim in its own right, resolving the
      cto-reviewer concern without needing to explain terminology not central
      to this document). `docs/project-kit-design.md`'s count corrected to
      match. `.claude/active_work.md` added to `scope_paths` and updated in
      this same branch — "not yet contracted" replaced with a short "done"
      summary, kept plainly out of scope from the still-genuinely-deferred
      other two phases.
    - No `CPO ANSWER:` needed — within the 3-round cap.
  - 2026-09-11 — round 3 review (last round before the cap): scope-auditor FAIL
    (5 findings), cto-reviewer FAIL (3 findings). Both independently found real,
    NEW defects this time — not just re-litigating round 2's list, and one of
    round 2's own fixes (the `*hooks/*` "none of the other groups overlap"
    framing) turned out to be itself wrong, caught by cto-reviewer. In order of
    severity:
    - scope-auditor's most serious finding: `.claude/active_work.md` still said
      "MR !18... Not merged yet" — false; MR !18, !19, and !20 have all
      genuinely merged (confirmed: `completion_gate.py` is on `main`, wired in
      `settings.json`, referenced in `test_hooks_import.py` and
      `project-kit-design.md`). This handover header was never updated after
      the actual merges landed, earlier in this same session.
    - scope-auditor: "Sandboxing adoption — done" claimed a merged state for
      still-unreviewed branch work, with no MR number or merge caveat, while
      the file's own established convention (used 70 lines earlier for Phase 1)
      names the MR and states merge status honestly.
    - scope-auditor: `docs/project-kit-design.md`'s ADR pointer had grown to 11
      lines against this file's own established 2-3 line convention for every
      other ADR pointer, and re-stated the "4 fully/1 partially of 11" count a
      third time (ADR, this file, `active_work.md`) — the exact
      cross-file-duplication pattern that already forced two-file corrections
      in rounds 1 and 2.
    - scope-auditor: a "Linux/WSL2 missing `bubblewrap`/`socat`" claim named
      `socat` as a sandbox dependency with zero citation — the same
      uncited-technical-claim defect round 1 already FAILed on, reintroduced.
    - scope-auditor: `active_work.md`'s edit went beyond what this contract
      authorized (remove the now-false sandboxing listing) by also writing new
      descriptive framing for the two phases `decisions_reserved` explicitly
      fences off — a real scope-boundary violation of this contract's own
      terms, even though the content itself wasn't wrong.
    - cto-reviewer's most substantive finding: round 2's own fix — "the other
      three [protected-paths] groups... none of which overlap `guard-paths.md`"
      — was itself false. Anthropic's protected-paths groups 2 and 3 (quoted in
      the doc) DO touch `hooks`-named paths (`.git/hooks`; a top-level `hooks`
      when mimicking a bare repo), which `guard-paths.md`'s `*hooks/*` glob
      (this document's own cited fnmatch semantics) would match. The `*hooks/*`
      "partial match" conclusion survived, but the stated REASON for it was
      incomplete — round 2's fix relocated round 2's own defect class (a
      negative claim resting on unexamined text) rather than resolving it.
    - cto-reviewer: the filesystem "Default read behavior" quote was cut
      immediately before the source's own credential-file caveat ("still
      allows reading `~/.aws/credentials` and `~/.ssh/`") — an omission that
      oversells the protection in a document that recommends adoption, the
      same defect class as round 1's "essentially no downside" (overselling by
      omission on the security side this time, not the cost side).
    - cto-reviewer: the synergy section's recap of the uncovered 6 silently
      dropped 2 of them (`.claude/tests/*`, `.cursor/mcp.json`) — losing the
      single sharpest, most security-relevant point in the whole document
      (`.mcp.json` is protected; `.cursor/mcp.json`, an equally executable MCP
      config, is not).
    - **Fixed**: `active_work.md`'s header and MR status corrected to reflect
      the real, already-verified merges; "Sandboxing adoption — done" replaced
      with "in review" naming the actual branch, no false completion claim;
      the other two deferred phases' descriptions reverted to a one-line
      mention, matching what this contract actually authorized;
      `project-kit-design.md`'s pointer trimmed back to 2 sentences with no
      restated count (the ADR is the one place that count lives now);
      `socat` given a real citation (`docs/en/sandboxing`, "Set up Linux and
      WSL2") and the "meaningful fraction of users" claim explicitly hedged as
      an unquantified population, not a claimed majority; the `*hooks/*`
      reasoning rewritten to accurately describe what groups 2/3 protect
      (`.git/hooks` specifically; a top-level `hooks` only when mimicking a
      bare repo) without either overclaiming full coverage or falsely denying
      any overlap; the credential-read caveat quoted in full plus a citation
      to Anthropic's own "Limitations" section ("not a complete isolation
      boundary"), and reflected in the comparison table's "Real limits" row;
      the uncovered-6 recap restored to name all 6, with `.cursor/mcp.json`'s
      asymmetry against `.mcp.json` called out explicitly as the sharpest
      point rather than left to disappear in a summary. Also fixed in passing
      (cto-reviewer flagged as a non-blocking note, not a finding): this
      contract's own `objective` still read the round-1-corrected "exactly the
      paths" overclaim as current truth — corrected to match what actually
      shipped.
    - Full 3-round cap reached. Asked the owner directly before dispatching
      round 4. Owner answered "Yes, dispatch round 4" — fresh, recorded
      authorization.
  - 2026-09-11 — round 4 review: BOTH scope-auditor and cto-reviewer FAIL,
    converging heavily on the same paragraph a third time — the `*hooks/*`
    coverage explanation kept being re-written, and each rewrite introduced a
    NEW instance of the same underlying defect (a claim resting on source text
    not actually examined). cto-reviewer named this pattern explicitly and
    recommended cutting the paragraph down to what's defensible rather than
    continuing to patch it — the same "stop engineering around it, simplify"
    call as the completion_gate.py phase's fingerprint-cache saga. Specific
    findings:
    - Both reviewers: the protected-paths quote covers "four groups," but the
      document only ever examined 2 of them (paraphrased, not quoted) and
      never mentioned the 4th at all, while asserting a hard negative ("the
      other 6 patterns are NOT covered at all") that depends on having checked
      all four.
    - Both reviewers: "the only `hooks/` directory that exists [in this repo]
      is `.claude/hooks`... coverage happens to be complete" was flatly false
      — `.git/hooks/` exists in this exact repo with 19 sample files, directly
      contradicting the same paragraph's own claim 5 lines earlier that group
      2 protects `.git/hooks`.
    - Both reviewers, independently phrased: internal self-contradiction —
      the citation's own parenthetical said group 1 was "the one relevant to
      guard-paths.md," then immediately explained why groups 2 and 3 were ALSO
      relevant.
    - scope-auditor: the negative claim also rested on an explicitly
      non-exhaustive clause ("the files Claude Code runs on its own, **such
      as**...") — open-ended, so a hard "NOT covered at all" conclusion was
      never fully supported by what was quoted.
    - scope-auditor: `.claude/task/review.md` is stale — still shows the
      already-merged MR !20 `.pyc`-cleanup task's content, not this one. This
      is expected under this repo's own workflow (review.md is written once,
      at the end, after all reviewers PASS — not per round) rather than a
      defect to fix mid-review; noted here so it isn't re-flagged as new.
    - scope-auditor: `review_input.patch` has no hunk for `contract.md`/
      `review.md`. Also expected and already established repeatedly in this
      repo's history (matches `commit_review_gate.py`'s own `_diff_to_hash`
      exclusion of `.claude/task`) — not re-litigated, noted for the record
      since a fresh reviewer instance has no memory of that prior resolution.
    - cto-reviewer: the credential-read caveat's citation was attached to the
      wrong sentence — "Anthropic's own docs say so directly" pointed the
      *general* "Limitations" quote at the *specific* credential claim, when
      the specific claim was already well-supported by the quote directly
      above it.
    - **Fixed, by simplifying rather than patching further**: the protected-paths
      citation now quotes all four groups in full (not just the first), so the
      negative claim over the uncovered 6 rests on the complete list, not a
      partial read; the false "only hooks/ directory that exists" claim and
      its "coverage happens to be complete for this repo" conclusion deleted
      entirely — replaced with the plain, defensible version: 4 clean matches,
      `*hooks/*` partial (specific instances vs. the broader glob), 6 patterns
      appear in none of the four groups, full stop, no speculation about one
      repo's specific layout; the citation misattachment fixed (the specific
      credential claim now points to the quote directly above it; the general
      "not a complete boundary" quote kept for the broader point only).
      `active_work.md`'s remaining ambiguity (sandboxing listed as still "not
      yet contracted" 5 lines after stating it's in review) removed —
      sandboxing dropped from that list entirely, its own status stated once,
      unambiguously, above. Also simplified (cto-reviewer's non-blocking
      note): "verified against the real job trace, not just the pass/fail
      status" was unfalsifiable self-attestation in a handover — trimmed to
      the plain, checkable claim ("CI green on `main` after each").
    - Full 3-round cap reached again (this was itself a past-cap round). Given
      4 rounds have now passed on a zero-code documentation change, with a
      reviewer explicitly naming the pattern as worth the owner's attention —
      surfaced that directly rather than just mechanically requesting round 5.
      Owner answered "Dispatch round 5" — fresh, recorded authorization.
  - 2026-09-11 — round 5 review: both reviewers FAIL, but a real turning
    point — every substantive claim in the ADR itself was independently
    re-verified and held (including the four-group quote's completeness, and
    the deleted false repo-layout claim actually being gone — cto-reviewer and
    scope-auditor each independently confirmed `.git/hooks/` genuinely exists
    in this repo, closing round 4's central defect for real this time).
    Remaining findings were narrow:
    - cto-reviewer (3 findings, all deletions, no new research): leftover
      "narrating the fix to the reviewer" text had survived into the shipped
      document — a citation's source line carrying a defensive parenthetical
      ("all four groups quoted, not just the first, so..."), a sentence
      rebutting round-1's already-fixed "most"/"almost exactly" wording and
      round-4's already-deleted layout speculation with no argument left for
      either to rebut, and `active_work.md` explaining its own edit
      ("sandboxing, above, is no longer in this list"). None involved new
      facts or citations — pure copy cleanup.
    - scope-auditor (1 finding): `contract.md`'s own `done_when` still carried
      the unqualified "matching this kit's own guard-paths list" overclaim —
      fixed in the `objective` back in round 3, but never fixed here, the
      exact "corrected in one file, stale in another" pattern this contract
      has reproduced before (round 1: ADR fixed, `project-kit-design.md`
      stale). Also caught a genuinely wrong list element: `.claude/skills`
      was named as if it were one of `guard-paths.md`'s 11 patterns; it isn't.
    - **Fixed**: all 3 meta-commentary passages deleted; `done_when` corrected
      to state the real 4-clean/1-partial/6-uncovered relationship instead of
      the flat "matching" claim, and the incorrect `.claude/skills` reference
      removed.
    - Full local check: no code anywhere in this diff (still 3 markdown
      files); no test suite applies.
  - 2026-09-15 — asked the owner whether to dispatch round 6 or treat round 5's
    fixes as settled. Owner said "review must pass" — fresh, recorded
    authorization to continue until both reviewers genuinely PASS, not to stop
    short.
