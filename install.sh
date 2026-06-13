#!/bin/bash
# Nexxoria Guardian — install.sh
# Creates symlinks and initializes the guardian for the current system.

set -euo pipefail

GUARDIAN_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_LINK="/root/.agents/skills/nexxoria-guardian/SKILL.md"
COMMAND_LINK="/root/.config/opencode/commands/guardian.md"
SKILL_DIR="$(dirname "$SKILL_LINK")"
CMD_DIR="$(dirname "$COMMAND_LINK")"

# Ensure /var/guardian directory exists
mkdir -p /var/guardian

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

# Auto-detect routes based on project structure
echo ""
echo "Step 4/8: Auto-detecting project structure for docs routes..."
AVAILABLE_DOCS=""

# Check for frontend
if [ -d "$PROJECT_ROOT/src/components" ] || [ -d "$PROJECT_ROOT/src/app" ] || [ -d "$PROJECT_ROOT/components" ]; then
  AVAILABLE_DOCS="${AVAILABLE_DOCS}frontend "
fi

# Check for backend
if [ -d "$PROJECT_ROOT/src/api" ] || [ -d "$PROJECT_ROOT/api" ] || [ -d "$PROJECT_ROOT/server" ] || [ -d "$PROJECT_ROOT/src/server" ]; then
  AVAILABLE_DOCS="${AVAILABLE_DOCS}backend "
fi

# Check for UI/styles
if [ -d "$PROJECT_ROOT/src/styles" ] || [ -d "$PROJECT_ROOT/styles" ] || [ -f "$PROJECT_ROOT/tailwind.config.js" ] || [ -f "$PROJECT_ROOT/tailwind.config.ts" ]; then
  AVAILABLE_DOCS="${AVAILABLE_DOCS}ui "
fi

# Check for features
if [ -d "$PROJECT_ROOT/src/features" ] || [ -d "$PROJECT_ROOT/features" ]; then
  AVAILABLE_DOCS="${AVAILABLE_DOCS}features "
fi

echo "  Detected available docs: ${AVAILABLE_DOCS:-none}"

# Setup project directory structure
echo ""
echo "Step 4/8: Creating project directory structure..."
mkdir -p "$PROJECT_ROOT/docs"
echo "  Created docs/ directory"

# Generate AGENTS.md from template
echo ""
echo "Step 5/8: Generating AGENTS.md..."

# Create AGENTS.md in docs/ from template
AGENTS_TEMPLATE="$GUARDIAN_DIR/templates/AGENTS.md.template"
if [ -f "$AGENTS_TEMPLATE" ]; then
  # Build doc list
  DOC_LIST=""
  for tmpl in "$GUARDIAN_DIR/templates/"*.md.template; do
    if [ "$tmpl" != "$AGENTS_TEMPLATE" ]; then
      docname="$(basename "$tmpl" .md.template)"
      DOC_LIST="${DOC_LIST}- ${docname}\n"
    fi
  done
  
  envsubst "
    slug: $SLUG
    runtime: $STACK_DETECTED
    framework: ${FRAMEWORK:-none}
    test_cmd: npm test
    lint_cmd: npm run lint
    build_cmd: npm run build
    entry_points: $ENTRY_POINTS
    docs_list: $DOC_LIST
  " "$AGENTS_TEMPLATE" > "$PROJECT_ROOT/docs/AGENTS.md"
  echo "  AGENTS.md written to docs/"
  
  # Create symlink for OpenCode compatibility
  ln -sf "docs/AGENTS.md" "$PROJECT_ROOT/AGENTS.md"
  echo "  Symlink AGENTS.md created"
else
  echo "  WARN: AGENTS.md.template not found"
fi

# Auto-generate CONSTRAINTS.md with real detection
echo ""
echo "Step 6/8: Auto-generating CONSTRAINTS.md..."

# Detect protected paths
PROTECTED_PATHS=""
if [ -f "$PROJECT_ROOT/.env" ]; then
  PROTECTED_PATHS="${PROTECTED_PATHS}- .env\n"
fi
if [ -f "$PROJECT_ROOT/.env.local" ]; then
  PROTECTED_PATHS="${PROTECTED_PATHS}- .env.local\n"
fi
if [ -f "$PROJECT_ROOT/.env.production" ]; then
  PROTECTED_PATHS="${PROTECTED_PATHS}- .env.production\n"
fi
if [ -f "$PROJECT_ROOT/prisma/schema.prisma" ]; then
  PROTECTED_PATHS="${PROTECTED_PATHS}- prisma/schema.prisma\n"
fi
if [ -f "$PROJECT_ROOT/.env.example" ]; then
  PROTECTED_PATHS="${PROTECTED_PATHS}- .env.example\n"
fi

# Detect forbidden patterns
FORBIDDEN_DEPS=""
if [ -f "$PROJECT_ROOT/package.json" ]; then
  # Check for deprecated packages
  if grep -q '"moment"' "$PROJECT_ROOT/package.json" 2>/dev/null; then
    FORBIDDEN_DEPS="${FORBIDDEN_DEPS}- moment (use date-fns or native Date)\n"
  fi
  if grep -q '"lodash"' "$PROJECT_ROOT/package.json" 2>/dev/null; then
    FORBIDDEN_DEPS="${FORBIDDEN_DEPS}- lodash (use native methods or es-toolkit)\n"
  fi
fi

# Detect tech debt
TECH_DEBT=""
if [ -f "$PROJECT_ROOT/package.json" ]; then
  if ! grep -q '"typescript"' "$PROJECT_ROOT/package.json" 2>/dev/null; then
    TECH_DEBT="${TECH_DEBT}- No TypeScript configured\n"
  fi
  if ! grep -q '"eslint"' "$PROJECT_ROOT/package.json" 2>/dev/null; then
    TECH_DEBT="${TECH_DEBT}- No ESLint configured\n"
  fi
fi

cat > "$PROJECT_ROOT/docs/CONSTRAINTS.md" <<EOF
## Scope
{{scope_paths}}

## Protected
${PROTECTED_PATHS:-  (no protected paths detected)}

## Forbidden
${FORBIDDEN_DEPS:-  (no forbidden dependencies detected)}

## Tech Debt
${TECH_DEBT:-  (no tech debt detected)}

---
*Generated by Nexxoria Guardian. Run \`@guardian docs scan\` to regenerate.*
EOF

echo "  CONSTRAINTS.md created with real detection"

# Initialize config.yaml in projects/<slug> directory
PROJS_DIR="/var/guardian/projects/$SLUG"
mkdir -p "$PROJS_DIR"

# Build available docs flags
FRONTEND_AVAILABLE=$(echo "$AVAILABLE_DOCS" | grep -q "frontend" && echo "true" || echo "false")
BACKEND_AVAILABLE=$(echo "$AVAILABLE_DOCS" | grep -q "backend" && echo "true" || echo "false")
UI_AVAILABLE=$(echo "$AVAILABLE_DOCS" | grep -q "ui" && echo "true" || echo "false")
FEATURES_AVAILABLE=$(echo "$AVAILABLE_DOCS" | grep -q "features" && echo "true" || echo "false")

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
    frontend: $FRONTEND_AVAILABLE
    backend: $BACKEND_AVAILABLE
    ui: $UI_AVAILABLE
    features: $FEATURES_AVAILABLE
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

# Initialize skills.json in project directory
cat > "$PROJS_DIR/skills.json" <<EOF
{
  "relevant": [],
  "last_absorb": null
}
EOF
echo "  skills.json created"

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
