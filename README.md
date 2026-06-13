# Nexxoria Guardian

Universal project guardian for OpenCode AI coding sessions. Auto-detects projects, manages documentation, runs hooks, and integrates with CodeGraph, OpenSpec/SDD, and Engram.

## Features

- **Auto-detection** — detects project by git remote or PWD
- **Persistent config** — per-project settings at `/srv/guardian/projects/<slug>/`
- **OpenSpec integration** — integrates SDD workflow into change management
- **CodeGraph** — code intelligence for impact analysis and context
- **Engram** — persistent memory for decisions and session summaries
- **Documentation** — auto-generates from code (CodeGraph) + narrative docs (documentation-writer)
- **Hooks** — pre/post change, pre/post deploy
- **Stack helpers** — build, dev, test, lint, deploy, logs
- **Skill registry** — absorbs and rates installed skills

## Installation

```bash
git clone <repo-url> /srv/guardian
cd /srv/guardian
chmod +x install.sh
./install.sh
gentle-ai skill-registry refresh
```

## Usage

```
@guardian                 — load skill and detect project
@guardian setup           — re-run setup wizard
@guardian absorb          — re-scan and rate skills
@guardian docs scan       — auto-generate docs from code
@guardian docs write      — invoke documentation-writer
@guardian sdd status      — show OpenSpec/SDD status
@guardian build|test|...  — stack helpers
@guardian hooks           — show hook status
```

## Requirements

- OpenCode >= 1.x
- Engram (MCP)
- CodeGraph (MCP or binary)
- OpenSpec/SDD (optional)

## License

MIT
