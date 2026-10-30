#!/usr/bin/env bash
# install.sh — deploy the LumenPDF skill to agent skill directories.
#
# Usage:
#   ./install.sh              # install to all detected runtimes
#   ./install.sh pi           # ~/.agents/skills/lumenpdf      (pi)
#   ./install.sh claude       # ~/.claude/skills/lumenpdf       (Claude Code)
#   ./install.sh --uninstall [pi|claude]

set -euo pipefail
cd "$(dirname "$0")"

SKILL_NAME="lumenpdf"
TARGETS=(
  "$HOME/.agents/skills"        # pi
  "$HOME/.claude/skills"        # Claude Code
)

UNINSTALL=0
ACTION="all"
if [[ "${1:-}" == "--uninstall" ]]; then UNINSTALL=1; ACTION="${2:-all}"; else ACTION="${1:-all}"; fi

deploy() {
  local base="$1"
  mkdir -p "$base"
  local dest="$base/$SKILL_NAME"
  if [[ $UNINSTALL -eq 1 ]]; then
    if [[ -d "$dest" ]]; then rm -rf "$dest"; echo "removed: $dest"; else echo "not installed: $dest"; fi
    return
  fi
  rm -rf "$dest"
  mkdir -p "$dest"
  cp SKILL.md "$dest/"
  cp -R scripts references "$dest/"
  rm -rf "$dest"/scripts/__pycache__
  echo "installed: $dest"
}

case "$ACTION" in
  all)     for t in "${TARGETS[@]}"; do deploy "$t"; done ;;
  pi)      deploy "$HOME/.agents/skills" ;;
  claude)  deploy "$HOME/.claude/skills" ;;
  *)       echo "usage: install.sh [pi|claude|--uninstall [pi|claude]]" >&2; exit 1 ;;
esac
