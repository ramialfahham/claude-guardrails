#!/usr/bin/env bash
#
# bootstrap.sh — add the claude-guardrails guardrails to an EXISTING repo.
#
# Copies this kit checkout's self-contained `.claude/` (hooks, reviewers, skills,
# settings, working agreement, routing) plus the `task/` templates into a target
# repo, so that repo self-guards with no plugin and nothing wired into ~/.claude/.
#
# Usage:
#   scripts/bootstrap.sh [--force] [--dry-run] TARGET_REPO
#
# Run it from a checkout of claude-guardrails; TARGET_REPO is the repo to guard.
#
# Safe to re-run. Kit CODE (hooks/agents/commands/skills/tests + task templates)
# is refreshed every run. Project-OWNED config (settings.json, review_routing.json,
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
  echo "bootstrap: '$KIT_ROOT' doesn't look like a claude-guardrails checkout" >&2; exit 1; }
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

echo "Bootstrapping claude-guardrails guardrails"
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
      "_Bootstrapped with claude-guardrails. Record where you are so the next session continues cleanly._" \
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
