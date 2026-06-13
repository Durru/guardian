#!/bin/bash
# Nexxoria Guardian — install.sh
# Creates symlinks and initializes the guardian for the current system.

set -euo pipefail

GUARDIAN_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_LINK="/root/.agents/skills/nexxoria-guardian/SKILL.md"
COMMAND_LINK="/root/.config/opencode/commands/guardian.md"
SKILL_DIR="$(dirname "$SKILL_LINK")"
CMD_DIR="$(dirname "$COMMAND_LINK")"

echo "=== Nexxoria Guardian Install ==="
echo "Guardian dir: $GUARDIAN_DIR"

# Ensure target directories exist
mkdir -p "$SKILL_DIR"
mkdir -p "$CMD_DIR"
mkdir -p /var/guardian/projects

# Create symlinks
if [ -f "$SKILL_LINK" ] || [ -L "$SKILL_LINK" ]; then
  rm "$SKILL_LINK"
fi
ln -s "$GUARDIAN_DIR/SKILL.md" "$SKILL_LINK"
echo "  SKILL.md symlink -> $SKILL_LINK"

if [ -f "$COMMAND_LINK" ] || [ -L "$COMMAND_LINK" ]; then
  rm "$COMMAND_LINK"
fi
ln -s "$GUARDIAN_DIR/commands/guardian.md" "$COMMAND_LINK"
echo "  command symlink -> $COMMAND_LINK"

# Initialize git repo if not already
if [ ! -d "$GUARDIAN_DIR/.git" ]; then
  git -C "$GUARDIAN_DIR" init
  git -C "$GUARDIAN_DIR" add -A
  git -C "$GUARDIAN_DIR" commit -m "chore: initial Nexxoria Guardian scaffold" 2>/dev/null || true
  echo "  git repo initialized"
fi

echo "=== Done ==="
echo "Run 'gentle-ai skill-registry refresh' to register the skill."
