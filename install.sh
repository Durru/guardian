#!/bin/bash
# Nexxoria Guardian — install.sh
# Creates symlinks and initializes the guardian for the current system.

set -euo pipefail

GUARDIAN_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_LINK="/root/.agents/skills/nexxoria-guardian/SKILL.md"
COMMAND_LINK="/root/.config/opencode/commands/guardian.md"
SKILL_DIR="$(dirname "$SKILL_LINK")"
CMD_DIR="$(dirname "$COMMAND_LINK")"

# Initialize skills-global.json if missing
if [ ! -f /var/guardian/skills-global.json ]; then
  echo '{"version":1,"skills":{},"last_absorb":null}' > /var/guardian/skills-global.json
  echo "  skills-global.json created"
fi

# Verify templates exist
TEMPLATE_COUNT=$(ls "$GUARDIAN_DIR/templates/"*.md.template 2>/dev/null | wc -l)
if [ "$TEMPLATE_COUNT" -lt 6 ]; then
  echo "  WARN: Expected 6 templates, found $TEMPLATE_COUNT"
  echo "  Re-run git pull or re-clone"
fi

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

echo "=== Setup Wizard ==="
echo "Please answer the following questions to set up your project:"

# Prompt for project root
echo ""
echo "Step 1/8: What is your project root path? (default: current directory)"
read -r PROJECT_ROOT
PROJECT_ROOT=${PROJECT_ROOT:-"$(pwd)"}
echo "  Project root: $PROJECT_ROOT"

# Prompt for project slug
echo ""
echo "Step 2/8: What is your project slug? (used for config)"
read -r SLUG
SLUG=${SLUG:-"$(basename "$PROJECT_ROOT")"}
echo "  Project slug: $SLUG"

# Detect stack by checking common files
echo ""
echo "Step 3/8: Detecting stack..."
STACK_DETECTED=""
if [ -f "$PROJECT_ROOT/package.json" ]; then
  STACK_DETECTED="node"
elif [ -f "$PROJECT_ROOT/pyproject.toml" ]; then
  STACK_DETECTED="python"
elif [ -f "$PROJECT_ROOT/Cargo.toml" ]; then
  STACK_DETECTED="rust"
fi
echo "  Detected stack: $STACK_DETECTED"

# Check for specific frameworks
FRAMEWORK=""
if [ "$STACK_DETECTED" = "node" ]; then
  if grep -q '"next"' "$PROJECT_ROOT/package.json" 2>/dev/null; then
    FRAMEWORK="next"
elif grep -q '"react"' "$PROJECT_ROOT/package.json" 2>/dev/null; then
    FRAMEWORK="react"
elif grep -q '"vite"' "$PROJECT_ROOT/package.json" 2>/dev/null; then
    FRAMEWORK="vite"
  fi
fi
echo "  Framework: ${FRAMEWORK:-none}"

# Setup project directory structure
echo ""
echo "Step 4/8: Creating project directory structure..."
mkdir -p "$PROJECT_ROOT/docs"
echo "  Created docs/ directory"

# Generate AGENTS.md from template
echo ""
echo "Step 5/8: Generating AGENTS.md..."

# Simple template for AGENTS.md
cat > "$PROJECT_ROOT/AGENTS.md" <<EOF
# $SLUG

## Stack
- runtime: $STACK_DETECTED
- framework: ${FRAMEWORK:-none}
- test: npm test
- lint: npm run lint
- build: npm run build

## Entry
Entry points will be scanned and populated later.

## Docs
- AGENTS.md (this file)
- CONSTRAINTS.md (project rules)
- FRONTEND.md (if applicable)
- BACKEND.md (if applicable)
- UI.md (if applicable)
- FEATURES.md (if applicable)
EOF

echo "  AGENTS.md written to project root"

# Create placeholder CONSTRAINTS.md in docs directory
cat > "$PROJECT_ROOT/docs/CONSTRAINTS.md" <<EOF
## Scope
- .env files (environment variables)
- database configuration
- API keys and secrets

## Protected
- Production environment files
- Database credentials
- API keys and secrets

## Forbidden
- Modifying .env files
- Committing secrets to git
- Exposing credentials

## Tech Debt
- TODO: Add project-specific rules

EOF

echo "  CONSTRAINTS.md created"

# Create AGENTS.md from template
AGENTS_TEMPLATE="$GUARDIAN_DIR/templates/AGENTS.md.template"
if [ -f "$AGENTS_TEMPLATE" ]; then
  # Replace template variables
  DOC_LIST=""
  for tmpl in "$GUARDIAN_DIR/templates/"*.md.template; do
    if [ "$tmpl" != "$AGENTS_TEMPLATE" ]; then
      docname="$(basename "$tmpl" .md.template)"
      DOC_LIST="$DOC_LIST- $docname\n$DOC_LIST"
    fi
done
  # Remove leading newline
  DOC_LIST="${DOC_LIST#*$'\n'}"
  
  envsubst "
    slug: $SLUG
    runtime: $STACK_DETECTED
    framework: ${FRAMEWORK:-none}
    test_cmd: npm test
    lint_cmd: npm run lint
    build_cmd: npm run build
    entry_points: $ENTRY_POINTS
    docs_list: $DOC_LIST
  " "$AGENTS_TEMPLATE" > "$PROJECT_ROOT/AGENTS.md"
  echo "  AGENTS.md populated from template"
else
  echo "  WARN: AGENTS.md.template not found"
fi

# Initialize config.yaml in projects/<slug> directory
PROJS_DIR="/var/guardian/projects/$SLUG"
mkdir -p "$PROJS_DIR"

cat > "$PROJS_DIR/config.yaml" <<EOF
project_root: $PROJECT_ROOT
slug: $SLUG
registered: $(date +%Y-%m-%d)
stack:
  detected: []
  build: npm run build
  dev: npm run dev
  test: npm test
  lint: npm run lint
  deploy: pm2 restart $SLUG
  logs: pm2 logs $SLUG --lines 20
docs:
  mandatory: [agents, constraints]
  routes:
    "src/components/**": frontend
    "src/hooks/**": frontend
    "src/store/**": frontend
    "src/api/**": backend
    "src/db/**": backend
    "src/middleware/**": backend
    "src/styles/**": ui
    "tailwind.config.*": ui
    "src/features/**": features
  available:
    frontend: true
    backend: true
    ui: true
    features: true
  last_scan: ~
openspec:
  enabled: true
  mode: hybrid
codegraph:
  enabled: true
  path: $PROJECT_ROOT
rules: []
audit: true
EOF

echo "  config.yaml written to $PROJS_DIR/config.yaml"

echo "  Project registered: $SLUG"
echo "  Project root: $PROJECT_ROOT"
echo "  AGENTS.md: $PROJECT_ROOT/AGENTS.md"
echo "  docs/: $PROJECT_ROOT/docs/"

echo ""
echo "Setup completed successfully!"
echo "You can now run '@guardian' in any project to use the guardian."

# Register the project for the guardian
/usr/local/bin/gentle-ai register-project "$SLUG" "$PROJECT_ROOT"

echo "=== Done ==="
echo "Run 'gentle-ai skill-registry refresh' to register the skill."
echo "Run '@guardian' in any project to start the setup wizard."
