# Nexxoria Guardian

Universal project guardian for OpenCode AI coding sessions. Auto-detects projects, prevents LLMs from breaking things, manages documentation, runs hooks, and integrates with CodeGraph, OpenSpec/SDD, and Engram.

## Features

- **Flow mode** — operates automatically, no commands needed day-to-day
- **Auto-detection** — project by git remote or PWD
- **Persistent config** — per-project at `/var/guardian/projects/<slug>/`
- **5-step change workflow** — identify → consult (scope router) → analyze → evaluate → execute
- **Hooks** — pre/post change (with real diff), pre/post deploy
- **Documentation** — scope router: sirve solo el doc relevante según qué archivo se toca
- **Just-in-time context** — AGENTS.md (~25 líneas) al arrancar, docs por dominio bajo demanda
- **Post-change diff** — detecta archivos nuevos y verifica restricciones automáticamente
- **Stack helpers** — build, dev, test, lint, deploy, logs
- **Skill registry** — absorbs & rates installed skills (global + per-project)
- **Audit** — JSON audit log with violations, change history, trends

## Installation

```bash
git clone https://github.com/Durru/guardian /srv/guardian
cd /srv/guardian
chmod +x install.sh
./install.sh
gentle-ai skill-registry refresh
```

## Commands (optional — guardian works without them)

| Command | What it does |
|---------|-------------|
| `@guardian` | Load + detect project |
| `@guardian setup` | Re-run setup wizard |
| `@guardian absorb` | Re-scan + rate skills |
| `@guardian status` | Dashboard: project, changes, hooks, docs |
| `@guardian report` | Violations, trends, compliance |
| `@guardian check` | Verify rules, protected paths, docs freshness |
| `@guardian protect <path>` | Add protected path to config + constraints |
| `@guardian snapshot <path>` | Backup file before modifying |
| `@guardian forget <slug>` | Remove project from guardian |
| `@guardian docs scan` | Generate docs from templates by stack |
| `@guardian docs write` | Narrative documentation |
| `@guardian docs route <path>` | Show which doc would be served for a path |
| `@guardian rollback` | Revert last change with confirmation |
| `@guardian hooks` | Show all hook statuses |
| `@guardian build|dev|test|lint|typecheck|deploy|logs` | Stack helpers |
| `@guardian git branch|commit` | Git helpers |

## Architecture

```
/srv/guardian/                          ← REPO (git-versionable)
├── SKILL.md                             ← Guardian skill definition
├── commands/guardian.md                 ← @guardian command
├── install.sh                           ← Interactive setup wizard
├── templates/                           ← 6 doc templates
└── README.md

/var/guardian/
├── skills-global.json                   ← Global skill index (306 skills)
└── projects/<slug>/                     ← Per-project data (NOT in repo)
    ├── config.yaml                      ← Stack, routes, rules
    ├── audit.json                       ← Change audit trail (JSON)
    └── skills.json                      ← Relevant skill references

<project_root>/
├── AGENTS.md                            ← Symlink to docs/AGENTS.md
└── docs/
    ├── AGENTS.md                        ← AI entry point (~25 lines)
    ├── CONSTRAINTS.md                   ← Project rules (always checked)
    ├── FRONTEND.md                      ← Components, hooks, state
    ├── BACKEND.md                       ← API, DB, auth
    ├── UI.md                            ← Design tokens, patterns
    └── FEATURES.md                      ← Business logic, flows
```

## Requirements

- OpenCode >= 1.x
- **Optional (enhance functionality):**
  - Engram (MCP) — persistent memory
  - CodeGraph (MCP or binary) — code intelligence
  - OpenSpec/SDD — spec-driven development

## License

MIT
