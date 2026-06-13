# Nexxoria Guardian

Universal project guardian for OpenCode AI sessions. Auto-detects projects,
manages documentation, runs hooks, integrates CodeGraph + OpenSpec/SDD + Engram.

## Triggers

- User runs `@guardian`
- User mentions "guardian", "proyecto", "project", "setup", "docs scan"
- Starting work in a new or existing project
- User asks about project structure, documentation, or stack helpers

## Architecture overview

```
/srv/guardian/
├── SKILL.md                     ← this file
├── commands/guardian.md         ← @guardian command
├── projects/<slug>/             ← per-project data
│   ├── config.yaml              ← detected stack, rules, paths
│   ├── audit.log                ← change audit trail
│   └── skills.json              ← absorbed skill ratings
├── registry/skills-global.json  ← global skill index
├── templates/                   ← doc templates
├── install.sh                   ← symlink setup
└── README.md
```

Project root: `/srv/guardian/` — git-versionable, shareable on GitHub.

---

## 1. Detection + Config

On load (`@guardian` or session start):

```
1. git remote origin → extract repo name → slug
2. If no git: basename $PWD → slug
3. If /srv/guardian/projects/<slug>/config.yaml exists:
   → load config + skills.json
   → report: "Guardian activo para <slug> (stack: <detected>)"
4. If not found:
   → run Setup Wizard
```

### Setup Wizard

```
1. Confirm PROJECT_ROOT (detected from PWD)
2. Scan for package.json / Cargo.toml / pyproject.toml / composer.json
3. Detect stack (framework, language, CSS approach, test runner, linter)
4. Detect OpenSpec: check /root/p/openspec/
   └── Ask mode: openspec | engram | hybrid (default: hybrid)
5. Detect CodeGraph: check if .codegraph/ exists in project root
   └── If missing → suggest `codegraph init`
6. Ask: which paths are protected docs? (default: none)
7. Ask: any project rules? (e.g. "no modificar X sin consultar")
8. Save /srv/guardian/projects/<slug>/config.yaml
9. Run @guardian docs scan + @guardian absorb
10. mem_save: "Project <slug> registered in guardian"
```

### config.yaml structure

```yaml
project_root: /srv/myapp
slug: myapp
registered: 2026-06-12
stack:
  detected: [next, react, tailwind, typescript]
  build: npm run build
  dev: npm run dev
  test: npm test
  lint: npm run lint
  typecheck: npm run typecheck
  deploy: pm2 restart myapp
  logs: pm2 logs myapp --lines 20
docs:
  protected: []
  auto_generated: true
  last_scan: null
openspec:
  enabled: true
  mode: hybrid
codegraph:
  enabled: true
  path: /srv/myapp
hooks:
  pre_change: true
  post_change: true
  pre_deploy: true
  post_deploy: true
rules: []
audit: true
```

---

## 2. Change Workflow (5 steps)

Execute this sequence for ANY code change. Do not skip steps.

```
┌─────────────────────────────────────────────────────────┐
│ 1. IDENTIFY                                             │
│    Classify the change:                                 │
│    - component (new/modify visual component)            │
│    - api (route, controller, endpoint)                  │
│    - style (CSS, theme, layout)                         │
│    - structure (files, directories, config)             │
│    - bugfix                                             │
│    - refactor                                           │
│    - feature (larger, multi-step)                       │
├─────────────────────────────────────────────────────────┤
│ 2. CONSULT                                              │
│    ├── Read project docs: STYLE.md, COMPONENTS.md,      │
│    │   API_SPEC.md, ARCHITECTURE.md (if they exist)     │
│    ├── OpenSpec: search /root/p/openspec/specs/ for     │
│    │   specs related to the change                      │
│    │   └── If no spec found and change is 'feature':    │
│    │       suggest starting an SDD change               │
│    ├── Engram: mem_search for previous decisions on     │
│    │   this topic                                       │
│    └── config.yaml rules — check restrictions           │
├─────────────────────────────────────────────────────────┤
│ 3. ANALYZE with CodeGraph                               │
│    ├── codegraph context "<task description>"           │
│    ├── codegraph impact <symbol> if touching existing   │
│    ├── codegraph callers/callees <symbol> for flow      │
│    └── codegraph query <term> to find related code      │
├─────────────────────────────────────────────────────────┤
│ 4. EVALUATE                                             │
│    ├── Does the component / function already exist?     │
│    ├── Will the change break anything?                  │
│    ├── Are the docs up to date?                         │
│    └── Is there a spec that must be followed?           │
├─────────────────────────────────────────────────────────┤
│ 5. EXECUTE                                              │
│    ├── Present findings to user:                        │
│    │   "Detected: <type>. Found <N> related docs.      │
│    │    Impact: <N> symbols affected. ¿Procedo?"       │
│    ├── On approval:                                     │
│    │   ├── Run pre-change hook                          │
│    │   ├── Make the change                              │
│    │   ├── Run post-change hook                         │
│    │   └── Register in audit.log + mem_save             │
│    └── On rejection: wait                               │
└─────────────────────────────────────────────────────────┘
```

### When to suggest SDD

If the change is type `feature` (multi-step, >1 file, involves design decisions)
and no OpenSpec spec exists for it:

> "Este cambio parece grande. ¿Querés crear un SDD spec primero?
>  Usá /sdd-new para empezar."

---

## 3. Hooks

### Pre-change hook

Runs BEFORE writing any code:

```
1. codegraph impact <symbol> — check what breaks
2. Verify project docs exist and reference the area
3. If docs are out of date → warn user
4. Check Engram for relevant past decisions
```

### Post-change hook

Runs AFTER code is written:

```
1. Run tests (config.stack.test) if available
2. Run linter (config.stack.lint) if available
3. Detect new components/APIs added or removed
4. If structural change detected:
   → "Detected new components. ¿Actualizo COMPONENTS.md?"
5. Guard en audit.log + mem_save
```

### Pre-deploy hook

Runs before deploy:

```
1. Run build (config.stack.build)
2. If build fails → STOP, report error
3. Check OpenSpec: if there's an active SDD change
   → "Hay un SDD change activo. ¿Corro sdd-verify?"
```

### Post-deploy hook

Runs after deploy:

```
1. Smoke test: curl health endpoint (if configured)
2. Write to audit.log
3. mem_save session summary
```

Hook results go to audit.log:

```
[2026-06-12T10:30:00] PRE_CHANGE | component: Navbar | impact: 2 files | OK
[2026-06-12T10:32:00] CHANGE | type: component | file: src/components/Navbar.tsx | desc: Added mobile menu
[2026-06-12T10:32:15] POST_CHANGE | tests: passed | lint: passed | docs_suggested: true | OK
```

---

## 4. Documentation (unified)

Two approaches, unified in one system.

### Auto-generation from code (`@guardian docs scan`)

```
1. codegraph files → project tree
2. Scan for component files (JSX/TSX patterns)
3. Scan for API routes (app router, express, etc.)
4. Compare with existing docs
5. Generate/update:
   ├── STYLE.md — from detected stack (framework, CSS, conventions)
   ├── COMPONENTS.md — components with paths and props
   ├── API_SPEC.md — routes with methods and params
   ├── ARCHITECTURE.md — directory structure
   └── AGENTS.md — invoke agents-md-generator if installed
6. Save to project root (not in /srv/guardian/)
7. Update last_scan timestamp in config.yaml
```

### Narrative docs (`@guardian docs write`)

```
1. Ask user what they need:
   ├── "tutorial" → invokes documentation-writer
   ├── "how-to" → invokes documentation-writer
   ├── "explanation" → invokes documentation-writer
   ├── "reference" → invokes documentation-writer
   └── "AGENTS.md" → invokes agents-md-generator
2. Pass project context (stack, tree, key files)
3. Save output to project root
```

### Sync (automatic, in post-change hook)

```
After any change:
  - If a new component was added and COMPONENTS.md exists
    → "Nuevo componente detectado. ¿Lo agrego a COMPONENTS.md?"
  - If a new route was added and API_SPEC.md exists
    → "Nueva ruta detectada. ¿La agrego a API_SPEC.md?"
  - If docs exist but are stale (last_scan > 7 days)
    → "Los docs tienen >7 días. ¿Corro @guardian docs scan?"
```

---

## 5. Stack helpers

Run these using the configured commands from config.yaml.

| Command | Action |
|---------|--------|
| `@guardian build` | Run build command for detected stack |
| `@guardian dev` | Run dev server command |
| `@guardian test` | Run test suite |
| `@guardian lint` | Run linter |
| `@guardian typecheck` | Run type checker |
| `@guardian deploy` | Run deploy command |
| `@guardian logs` | Show recent logs |
| `@guardian git branch <name>` | Create branch with project prefix |
| `@guardian git commit` | Stage changes and create conventional commit |

If a command is not configured:
> "No hay comando configurado para <action>. Configuralo con @guardian setup."

---

## 6. Skill registry & rating

### Absorption (`@guardian absorb`)

Scans all installed skills and builds a searchable registry:

```
1. Scan /root/.agents/skills/*/SKILL.md
2. Scan /root/.config/opencode/skills/*/SKILL.md
3. For each SKILL.md:
   └── Extract: name, description, triggers
4. Rate each skill (0-50):
   ├── Clarity (0-10) — is the purpose clear?
   ├── Triggers (0-10) — are triggers well-defined?
   ├── Workflow (0-10) — does it have a clear process?
   ├── DOs/DON'Ts (0-10) — are there practical guardrails?
   └── Examples (0-10) — are there concrete examples?
5. Convert to stars:
   ├── 0-16 → ★
   ├── 17-33 → ★★
   └── 34-50 → ★★★
6. Save global: /srv/guardian/registry/skills-global.json
7. Save per-project: /srv/guardian/projects/<slug>/skills.json (filtered by relevance)
```

### Skill usage in workflow

When the change workflow needs a specialized skill (e.g. doc writing,
bug hunting), check the registry for the best-rated skill matching
the need and suggest loading it.

---

## 7. Integrations

| Tool | Integration point |
|------|-------------------|
| **Engram** | `mem_search` in step 2 (consult), `mem_save` after changes and sessions |
| **CodeGraph** | `codegraph {context,impact,callers,callees,query,files}` in step 3 (analyze) |
| **OpenSpec/SDD** | Check specs in step 2, suggest SDD for features, link in audit |
| **documentation-writer** | Invoke for narrative docs (`@guardian docs write`) |
| **agents-md-generator** | Invoke for AGENTS.md generation |

---

## 8. Commands

| Command | Action |
|---------|--------|
| `@guardian` | Load skill + detect project (setup wizard if new) |
| `@guardian setup` | Re-run setup wizard |
| `@guardian absorb` | Re-scan and rate all skills |
| `@guardian docs scan` | Auto-generate/update docs from code |
| `@guardian docs write` | Invoke documentation-writer for narrative docs |
| `@guardian sdd status` | Show OpenSpec/SDD status and active changes |
| `@guardian hooks` | Show which hooks are enabled |
| `@guardian build | dev | test | lint | typecheck | deploy | logs` | Stack helpers |
| `@guardian git branch <name>` | Git branch helper |
| `@guardian git commit` | Git commit helper |

---

## 9. Project ephemeral memory

The guardian keeps no in-session state beyond what's in config.yaml
and skills.json. All cross-session state lives in:

- `/srv/guardian/projects/<slug>/config.yaml` — project config
- `/srv/guardian/projects/<slug>/audit.log` — change log
- `/srv/guardian/projects/<slug>/skills.json` — project skill index
- `/srv/guardian/registry/skills-global.json` — global skill index
- **Engram** — persistent memory (decisions, summaries)
