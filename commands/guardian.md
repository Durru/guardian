---
description: Carga Nexxoria Guardian - detecta el proyecto, ejecuta workflow de 5 pasos, maneja hooks, memoria semántica, clasificación de skills, integración GitHub y dashboard web.
agent: build
---

# @guardian

Carga Nexxoria Guardian y detecta el proyecto actual.

En el día a día NO necesitás comandos — el guardian opera solo.
Usá estos solo cuando quieras control manual:

| Comando | Qué hace |
|---------|----------|
| `@guardian` | Cargar + detectar proyecto |
| `@guardian activate` | Activar Guardian en el proyecto (setup + branch + absorb + docs + conciencia) |
| `@guardian setup` | Re-ejecutar wizard de configuración |
| `@guardian absorb` | Escanear skills nuevos/actualizados + matchear al proyecto |
| `@guardian absorb --force` | Re-escanear todo (ignorar caché) |
| `@guardian absorb --learn <skill> <rating>` | Feedback manual sobre un skill |
| `@guardian absorb classify <slug> [--json]` | Clasificar skills automáticamente analizando archivos reales del proyecto |
| `@guardian suggest [--json]` | Mostrar skills rankeados para el proyecto |
| `@guardian suggest --all [--json]` | Mostrar todos (incluyendo cold) |
| `@guardian status [slug]` | Dashboard: reglas activas, últimos cambios, docs, hooks |
| `@guardian context [--brief\|--check\|--full\|--json] [--since-last\|--since=<ts>] [--scope=<path>] [slug]` | Contexto del proyecto para inyección AI |
| `@guardian report [slug]` | Violaciones, tendencias, reglas más/menos seguidas |
| `@guardian check [slug]` | Verificar reglas y paths protegidos |
| `@guardian protect <path> [slug]` | Agregar path protegido |
| `@guardian snapshot <path> [slug]` | Backup de archivo antes de modificar |
| `@guardian diff [path] [slug]` | Mostrar diff del proyecto o archivo (git o snapshots) |
| `@guardian prompt <step> [--scope=<path>] [--type=<tipo>] [--files=<paths>] [slug]` | Generar prompt del workflow AI |
| `@guardian prompt status [slug]` | Mostrar estado actual del workflow |
| `@guardian docs scan [slug]` | Generar docs desde templates según stack |
| `@guardian docs route <path> [slug]` | Mostrar qué doc se serviría para un path |
| `@guardian rollback [slug]` | Revertir último cambio |
| `@guardian hooks [slug]` | Estado de hooks |
| `@guardian pre-change <files...> [--auto] [slug]` | Pipeline pre-cambio (snapshot + scope + memory + protected checks) |
| `@guardian post-change [files...] [--auto] [--no-tests] [--no-lint] [slug]` | Pipeline post-cambio (diff real + tests + lint + memory save + audit) |
| `@guardian pre-deploy [--auto] [slug]` | Pipeline pre-despliegue (build check + SDD verify) |
| `@guardian post-deploy [--auto] [slug]` | Pipeline post-despliegue (smoke test + audit + memory) |
| `@guardian memory save <type> <text> [file]` | Guardar en memoria (landmark/decision/pattern/note/analysis) |
| `@guardian memory search <term>` | Buscar texto en memoria |
| `@guardian memory search --semantic <slug> <query>` | Búsqueda semántica TF-IDF |
| `@guardian memory index <slug> [--force]` | Precomputar embeddings semánticos |
| `@guardian memory context [scope]` | Obtener contexto relevante para el AI |
| `@guardian memory session save [--with-config]` | Registrar inicio de sesión AI |
| `@guardian memory session status` | Historial de sesiones |
| `@guardian memory status` | Estadísticas de memoria |
| `@guardian memory gc` | Limpiar entradas vencidas |
| `@guardian pr <create\|status\|comment\|approve\|merge\|list\|checkout> [args]` | Integración GitHub PR |
| `@guardian issue <list\|create\|close\|comment> [args]` | Integración GitHub Issues |
| `@guardian projects list` | Listar todos los proyectos |
| `@guardian projects status` | Estadísticas globales |
| `@guardian projects gc` | Hacer GC de todos los proyectos |
| `@guardian projects absorb match` | Match skills en todos los proyectos |
| `@guardian build\|dev\|test\|lint\|typecheck\|deploy\|logs [slug]` | Stack helpers |
| `guardian_web.py [--port=7878]` | Dashboard web (HTTP + JSON, zero deps) |

---

### Command implementations

**@guardian status**
- Project + stack + active docs
- Protected paths count
- Last 5 changes from audit.json
- Hook statuses
- Docs last_scan date
- Memory entry count, skills count

**@guardian report**
- Total changes, violations, most changed files
- Docs update rate, rule compliance
- 30-day trends

**@guardian check**
- Protected paths not modified
- No forbidden deps
- Docs not stale (< 7 days)
- All available docs exist
- Skills loaded

**@guardian rollback**
- Shows last change from audit.json
- Asks confirmation
- git checkout + audit entry

**@guardian protect <path>**
- Adds to config.yaml routes + CONSTRAINTS.md
- Updates config

**@guardian snapshot <path>**
- Creates .guardian-snapshot-<timestamp>
- Records in audit.json

**@guardian diff [path]**
- Si el proyecto tiene git: `git diff` real con --stat o por archivo
- Si no tiene git: lista snapshots disponibles
- Sin path: diff general del proyecto

**@guardian prompt <step>**
- Steps: identify, consult, analyze, evaluate, execute, status
- `--scope=<path>`: filtra docs y memoria al área relevante
- `--type=<tipo>`: tipo de cambio (component/api/style/etc.)
- `--files=<paths>`: archivos a modificar (separados por coma)
- Genera el prompt listo para inyectar en la conversación del AI
- Auto-trackea el estado del workflow en workflow-state.json
- `status` muestra el paso actual, último scope, y próximo paso sugerido
- Los templates están en `/srv/guardian/prompts/`

**@guardian docs route <path>**
- Matches path against routes with priority (wildcard > exact)
- Checks actual .md file existence before listing
- Shows score breakdown

**@guardian hooks**
- Shows all 4 hook statuses with steps

**@guardian pre-change / post-change / pre-deploy / post-deploy**
- 4 automated pipelines
- `--auto`: auto-confirm each step
- pre-change: path extraction → scope match → memory context → protected check → delete check → snapshot
- post-change: diff real → run tests → run linter → memory save → audit write
- pre-deploy: build check → SDD verify
- post-deploy: smoke test → audit write → memory save

**@guardian absorb**
- `scan`: check mtime vs cache, only process changed skills
- `--force`: full re-scan of all skills
- `match <slug>`: score skills vs project type/stack/framework
- `classify <slug>`: analyzes project files (package.json, pyproject.toml, README, dirs) → auto-detects languages, frameworks, tools, keywords → tiers skills into Hot/Warm/Cold
- `classify <slug> [--json]`: same classification with JSON output for tooling
- `--learn <skill> <rating>`: manual feedback (rated_1 to rated_5)

**@guardian suggest**
- Shows ranked skills with bars, scores, stars
- Hot skills (score>50) 🔥, Warm (30-50) 🟡
- `--all`: includes cold skills
- `--json`: returns machine-readable ranking

**@guardian context**
- Modes: `--brief` (solo proyecto+docs), `--check` (solo constraints), `--full` (todo),
  `--json` (raw output para parsing)
- `--since-last` / `--since=<ts>`: diff — si no hay cambios, no repite contexto
- `--scope=<path>`: filtra memoria y actividad a un área específica
- Designed for AI prompt injection, not human display
- Tracks queries in context-state.json para evitar repeticiones

**@guardian memory**
- `status`: memory file stats, entries by type, top hits, last GC date
- `context [scope]`: returns max 6 relevant entries (< 12 lines)
- `session save [--with-config]`: registra una nueva sesión AI, incluye timestamp + contador
- `session status`: muestra total de sesiones, activas (7d), última sesión y horas desde entonces
- `save <type> <text> [file]`: saves with dedup by MD5 hash
- `search <term>`: full-text search across all entries
- `search --semantic <slug> <query>`: TF-IDF cosine similarity search (threshold 0.10)
- `index <slug> [--force]`: precompute TF-IDF embeddings, cached to memory-embeddings.json
- `gc`: removes expired entries by TTL
- `--json` flag on search/context/status/session-status

**@guardian pr**
- 7 subcommands via `gh` CLI
- `create`: `gh pr create` with audit recording
- `status`: `gh pr status`
- `comment <number> <body>`: `gh pr comment`
- `approve <number>`: `gh pr review --approve` with audit
- `merge <number>`: `gh pr merge` with audit
- `list`: `gh pr list`
- `checkout <number>`: `gh pr checkout`

**@guardian issue**
- 4 subcommands via `gh` CLI
- `list`: `gh issue list`
- `create <title> <body>`: `gh issue create` with audit
- `close <number>`: `gh issue close`
- `comment <number> <body>`: `gh issue comment`

**@guardian projects**
- `list`: table of all projects with audit/skills/memory counts
- `status`: aggregated stats (total projects, memories, skills, hot skills, active)
- `gc`: run gc on all projects
- `absorb match`: run absorb match on all projects

**guardian_web.py**
- Standalone HTTP server, stdlib only (http.server)
- Default port 7878, `--port` flag
- Endpoints:
  - `GET /` — HTML cards for all projects
  - `GET /<slug>/` — HTML detail page
  - `GET /projects.json` — JSON project list
  - `GET /<slug>/status.json` — JSON project status
  - `GET /<slug>/memory.json` — JSON memory entries
  - `GET /<slug>/skills.json` — JSON skills classification
  - `GET /<slug>/audit.json` — JSON audit log
- Dark theme, CORS headers

Todo comando chequea config.yaml del proyecto actual.
