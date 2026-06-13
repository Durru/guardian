# Nexxoria Guardian

Universal project guardian for OpenCode AI coding sessions. Auto-detects projects, prevents LLMs from breaking things, manages documentation, runs hooks, and integrates with CodeGraph, OpenSpec/SDD, and Engram.

## Features

- **Flow mode** — operates automatically, no commands needed day-to-day
- **Auto-detection** — project by git remote or PWD
- **Persistent config** — per-project at `/var/guardian/projects/<slug>/`
- **5-step change workflow** — identify → consult → analyze → evaluate → execute
- **Hooks** — pre/post change, pre/post deploy (automatic)
- **Documentation** — auto-generates from code + narrative docs
- **Stack helpers** — build, dev, test, lint, deploy, logs
- **Skill registry** — absorbs & rates installed skills (global + per-project)
- **Audit** — JSON audit log with violations, change history, trends

## Installation

```bash
git clone <repo-url> /srv/guardian
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
| `@guardian status` | Dashboard: rules, last changes |
| `@guardian report` | Violations, trends |
| `@guardian check` | Verify rules & protected paths |
| `@guardian protect <path>` | Add protected path |
| `@guardian snapshot <path>` | Backup file before modifying |
| `@guardian forget <slug>` | Remove project from guardian |
| `@guardian docs scan` | Auto-generate docs from code |
| `@guardian docs write` | Narrative documentation |
| `@guardian rollback` | Suggest reverting last change |
| `@guardian build|test|...` | Stack helpers |
| `@guardian git branch|commit` | Git helpers |

## Architecture

```
/srv/guardian/                  ← REPO (git-versionable)
/var/guardian/skills-global.json  ← ONE global skill index
/var/guardian/projects/<slug>/    ← per-project data
  ├── config.yaml
  ├── audit.json
  └── skills.json
```

## Requirements

- OpenCode >= 1.x
- Engram (MCP)
- CodeGraph (MCP or binary)
- OpenSpec/SDD (optional)

## License

MIT
