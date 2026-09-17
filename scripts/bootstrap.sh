#!/usr/bin/env bash
#
# bootstrap.sh — add the claude-project-kit guardrails to an EXISTING repo.
#
# Copies this kit checkout's self-contained `.claude/` (hooks, reviewers, skills,
# settings, working agreement, routing) plus the `task/` templates into a target
# repo, so that repo self-guards with no plugin and nothing wired into ~/.claude/.
#
# Usage:
#   scripts/bootstrap.sh [--force] [--dry-run] TARGET_REPO
#
# Run it from a checkout of claude-project-kit; TARGET_REPO is the repo to guard.
#
# Safe to re-run. Kit CODE (hooks/agents/commands/skills/tests + task templates)
# is refreshed every run, and .claude/.kit-version is stamped with this checkout's
# commit SHA each time. Project-OWNED config (settings.json, review_routing.json,
# working-agreement.md, active_work.md) is preserved if it already exists — pass
# --force to overwrite it with the kit's version.
#
set -euo pipefail

FORCE=0
DRY=0
TARGET=""

usage() {
  sed -n '3,18p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --force)   FORCE=1 ;;
    --dry-run) DRY=1 ;;
    -h|--help) usage 0 ;;
    -*)        echo "bootstrap: unknown option '$1'" >&2; usage 1 ;;
    *)
      if [ -n "$TARGET" ]; then
        echo "bootstrap: unexpected extra argument '$1'" >&2; usage 1
      fi
      TARGET="$1" ;;
  esac
  shift
done

[ -n "$TARGET" ] || { echo "bootstrap: TARGET_REPO is required" >&2; usage 1; }
[ -d "$TARGET" ] || { echo "bootstrap: target '$TARGET' is not a directory" >&2; exit 1; }

# Canonicalise via cd/pwd -P (portable; realpath isn't everywhere).
abspath() { CDPATH= cd -- "$1" && pwd -P; }
SCRIPT_DIR="$(abspath "$(dirname -- "$0")")"
KIT_ROOT="$(abspath "$SCRIPT_DIR/..")"
TARGET_ABS="$(abspath "$TARGET")"

if [ "$TARGET_ABS" = "$KIT_ROOT" ]; then
  echo "bootstrap: refusing to bootstrap the kit into itself" >&2
  exit 1
fi
[ -f "$KIT_ROOT/.claude/settings.json" ] || {
  echo "bootstrap: '$KIT_ROOT' doesn't look like a claude-project-kit checkout" >&2; exit 1; }
[ -d "$TARGET_ABS/.git" ] || echo "bootstrap: note — '$TARGET' has no .git (not a git repo yet)"

# run CMD... — execute, or just print under --dry-run.
run() {
  if [ "$DRY" -eq 1 ]; then echo "DRY   $*"; else "$@"; fi
}

# refresh_dir REL — merge the kit's REL directory into the target (kit code wins).
refresh_dir() {
  local rel="$1"
  [ -d "$KIT_ROOT/$rel" ] || return 0
  run mkdir -p "$TARGET_ABS/$rel"
  run cp -R "$KIT_ROOT/$rel/." "$TARGET_ABS/$rel/"
  echo "sync   $rel/"
}

# refresh_file REL — always copy the kit's REL file over the target's.
refresh_file() {
  local rel="$1"
  [ -f "$KIT_ROOT/$rel" ] || return 0
  run mkdir -p "$(dirname "$TARGET_ABS/$rel")"
  run cp "$KIT_ROOT/$rel" "$TARGET_ABS/$rel"
  echo "sync   $rel"
}

# keep_file REL [note] — copy only if absent (or --force); never clobber silently.
keep_file() {
  local rel="$1" note="${2:-}"
  if [ -e "$TARGET_ABS/$rel" ] && [ "$FORCE" -eq 0 ]; then
    echo "keep   $rel (exists${note:+; $note})"
    return 0
  fi
  run mkdir -p "$(dirname "$TARGET_ABS/$rel")"
  run cp "$KIT_ROOT/$rel" "$TARGET_ABS/$rel"
  echo "write  $rel"
}

echo "Bootstrapping claude-project-kit guardrails"
echo "  from: $KIT_ROOT"
echo "  into: $TARGET_ABS"
[ "$DRY" -eq 1 ] && echo "  (dry run — no files written)"
echo

# 1) Kit code — always refreshed (updating it is the point of a re-run).
refresh_dir ".claude/hooks"
refresh_dir ".claude/agents"
refresh_dir ".claude/commands"
refresh_dir ".claude/skills"
refresh_dir ".claude/tests"
refresh_file "task/CONTRACT_TEMPLATE.md"
refresh_file "task/REVIEW_TEMPLATE.md"

# Kit version stamp — lets a project owner tell which kit commit they last
# refreshed from. A fact about the kit, not project-owned config: always
# overwritten, never keep_file semantics. Skips quietly (not a hard failure)
# if the kit checkout has no git history to read from — e.g. a zip-extracted
# copy with no .git, or a repo with an unborn HEAD (no commits yet).
if [ "$DRY" -eq 1 ]; then
  echo "DRY   write .claude/.kit-version"
else
  kit_sha=""
  skip_reason="kit checkout has no git history"
  # Deliberately a plain existence check on "$KIT_ROOT/.git", NOT a
  # `rev-parse --show-toplevel` path comparison — an earlier version of
  # this block compared git's toplevel output against $KIT_ROOT as strings,
  # which broke twice on real path-format mismatches on this exact dev
  # setup: once from a drive-letter ("D:/...") vs MSYS ("/d/...") form
  # difference, and then AGAIN once that was normalised through abspath(),
  # because Git Bash treats %TEMP% (AppData\Local\Temp) as mount-aliased to
  # /tmp — so re-running abspath() on an already-canonical path can still
  # change its string form depending on which literal prefix it started
  # from. Comparing absolute path TEXT is fundamentally fragile here. A
  # plain "does $KIT_ROOT/.git exist" sidesteps all of it: git -C walking
  # up to find an ENCLOSING repo is exactly what made the old check
  # necessary in the first place, and this check never invokes git at all
  # for the ownership question, so there's nothing for it to walk up from.
  # Correctly recognises a worktree too — its ".git" is a FILE (a "gitdir:"
  # pointer), not a directory, and -e matches either.
  if [ -e "$KIT_ROOT/.git" ]; then
    # --verify (not a bare `rev-parse HEAD`): on an unborn HEAD (a repo with
    # zero commits), a bare rev-parse echoes the literal argument "HEAD" to
    # stdout before failing on stderr — the 2>/dev/null wouldn't catch that,
    # and "HEAD" is not a valid SHA. --verify fails cleanly instead, with
    # nothing on stdout.
    kit_sha="$(git -C "$KIT_ROOT" rev-parse --verify HEAD 2>/dev/null || true)"
    [ -z "$kit_sha" ] && skip_reason="kit checkout has an unborn HEAD (no commits yet)"
  fi
  if [ -n "$kit_sha" ]; then
    mkdir -p "$TARGET_ABS/.claude"
    printf '%s\n' "$kit_sha" > "$TARGET_ABS/.claude/.kit-version"
    echo "sync   .claude/.kit-version"
  else
    echo "skip   .claude/.kit-version ($skip_reason)"
  fi
fi

# Drop any __pycache__ the copy may have carried along.
if [ "$DRY" -eq 0 ] && [ -d "$TARGET_ABS/.claude" ]; then
  find "$TARGET_ABS/.claude" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
fi

# 2) Project-owned config — preserved if present (--force to overwrite).
# settings.json is special: if the target already has one, its hooks block must be
# merged by hand, because overwriting could drop the target's own hooks/settings.
if [ -e "$TARGET_ABS/.claude/settings.json" ] && [ "$FORCE" -eq 0 ]; then
  echo "keep   .claude/settings.json (exists) — merge the kit's 'hooks' block into it by hand"
else
  keep_file ".claude/settings.json"
fi
keep_file ".claude/review_routing.json" "edit it there to customise routing"
keep_file ".claude/working-agreement.md"

# 3) A fresh handover — never copy the kit's own migration notes.
if [ ! -e "$TARGET_ABS/.claude/active_work.md" ]; then
  if [ "$DRY" -eq 1 ]; then
    echo "DRY   write .claude/active_work.md (starter)"
  else
    run mkdir -p "$TARGET_ABS/.claude"
    printf '%s\n' \
      "# Active work" \
      "" \
      "_Bootstrapped with claude-project-kit. Record where you are so the next session continues cleanly._" \
      > "$TARGET_ABS/.claude/active_work.md"
  fi
  echo "write  .claude/active_work.md (starter)"
else
  echo "keep   .claude/active_work.md (exists)"
fi

echo
echo "Done. Next:"
echo "  1. Ensure 'python' and a bash shell are on PATH (the hooks need both)."
echo "  2. Start Claude Code in '$TARGET' and approve the project hooks when prompted."
echo "  3. Review .claude/review_routing.json — tune which reviewers gate which paths."
echo "  4. Commit the new .claude/ so the guardrails travel with the repo."
