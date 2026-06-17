# Guardian v2 — Referencia completa

## CLI commands

### Proyecto

| Comando | Descripción |
|---------|-------------|
| `guardian detect` | Detectar proyecto desde git remote o PWD |
| `guardian status [slug]` | Dashboard del proyecto |
| `guardian check [slug]` | Verificar reglas y paths protegidos |
| `guardian report [slug]` | Violaciones, tendencias, cumplimiento |
| `guardian setup [slug]` | Configurar proyecto nuevo |

### Cambios

| Comando | Descripción |
|---------|-------------|
| `guardian protect <path> [slug]` | Proteger un path |
| `guardian snapshot <path> [slug]` | Backup de archivo |
| `guardian diff [path] [slug]` | Mostrar diff (git o snapshot) |
| `guardian rollback [slug]` | Revertir último cambio |
| `guardian hooks [slug]` | Estado de hooks |

### Permisos

| Comando | Descripción |
|---------|-------------|
| `guardian permission check <path> [slug]` | Quick check de permiso para editar/ejecutar |

### Workflow AI

| Comando | Descripción |
|---------|-------------|
| `guardian context [opts] [slug]` | Contexto del proyecto para AI |
| `guardian rag <query> [--slug] [--top-k] [--json] [--scope]` | Búsqueda RAG |
| `guardian mode <plan\|build\|status> [reason...]` | Cambiar/ver modo |
| `guardian conciencia <cycle\|status\|history\|meta> [question]` | Conciencia + meta-evolución |
| `guardian knowledge <status\|tomes\|search> [query]` | Conocimiento / tomos |
| `guardian prompt <paso> [--scope] [--type] [--files] [slug]` | Workflow prompt |

### Sistemas

| Comando | Descripción |
|---------|-------------|
| `guardian backend <start\|stop\|restart\|status>` | Backend persistente |
| `guardian memory <save\|search\|context\|index\|gc\|status\|session>` | Memoria persistente |
| `guardian absorb <scan\|match\|classify\|ingest\|learn\|suggest\|status>` | Skills |
| `guardian genome <status\|diff> [slug]` | ADN del ser |
| `guardian branch <list\|fork\|status\|diff> [slug]` | Ramas de evolución |
| `guardian evolve [slug]` | Disparar evolución de rama |
| `guardian consolidate [slug]` | Consolidar memoria + RAG |
| `guardian forja <index\|list\|doctor\|new\|validate\|impact\|edit\|rm\|protect\|run\|function\|endpoint\|mcp-tool\|diff\|graph\|patch>` | La Forja: meta-módulo del arquitecto |
| `guardian codegraph <index\|query\|status> [slug]` | CodeGraph: indexar/buscar/status del AST del proyecto |
| `guardian migrate <status\|migrate\|rollback> <slug>` | Migrar proyecto de v3 a v4 layout |

### GitHub

| Comando | Descripción |
|---------|-------------|
| `guardian pr <create\|status\|comment\|approve\|merge\|list\|checkout>` | Pull requests |
| `guardian issue <list\|create\|close\|comment>` | Issues |
| `guardian projects <list\|status\|gc\|absorb>` | Multi-proyecto |

### Web

| Comando | Descripción |
|---------|-------------|
| `guardian web [--port <n>]` | Dashboard web con RAG search |

### Documentación

| Comando | Descripción |
|---------|-------------|
| `guardian docs scan [slug]` | Generar docs desde templates |
| `guardian docs route <path> [slug]` | Ver qué doc se sirve para un path |

### Hooks

| Comando | Descripción |
|---------|-------------|
| `guardian pre-change <files...> [--auto] [slug]` | Pre-change hook pipeline |
| `guardian post-change [files...] [--auto] [slug]` | Post-change hook pipeline |
| `guardian pre-deploy [--auto] [slug]` | Pre-deploy checks |
| `guardian post-deploy [--auto] [slug]` | Post-deploy smoke test |

### Stack

| Comando | Descripción |
|---------|-------------|
| `guardian build [slug]` | Build project |
| `guardian dev [slug]` | Start dev server |
| `guardian test [slug]` | Run tests |
| `guardian lint [slug]` | Run linter |
| `guardian typecheck [slug]` | Run type checker |
| `guardian deploy [slug]` | Deploy project |
| `guardian logs [slug]` | Show logs |

---

## Backend API — 19 endpoints

### GET

| Endpoint | Params | Respuesta |
|----------|--------|-----------|
| `/health` | — | `{"ok": true, "service": "guardian-backend", "pid": N}` |
| `/metrics` | — | `{"projects": N, "pid": N, "uptime": N}` |
| `/mode` | `slug` | Estado del modo (mode, updated, history) |
| `/genome` | — | Genoma completo + lista de ramas |
| `/branch` | `slug` (opcional) | Info de rama específica o todas |
| `/conciencia/state` | `slug` | Ciclos, última acción, última confianza |
| `/conciencia/percentiles` | `slug` | Umbrales actuales (assume, ask_little_floor, ask_much_floor) |
| `/rag` | `slug`, `q`, `mode` (opcional) | Resultados RAG con scores y citas |
| `/knowledge/status` | `slug` | Índice de conocimiento + lista de tomos |
| `/knowledge/tomes` | `slug` | Lista detallada de tomos con preview |
| `/knowledge/search` | `slug`, `q` | Búsqueda semántica en tomos |
| `/mcp/tools` | — | Lista de herramientas MCP disponibles |
| `/codegraph/status` | `slug` | Estado del CodeGraph (indexado o no, counts) |
| `/codegraph/query` | `slug`, `q`, `top_k`, `max_tokens` | Búsqueda query_smart de símbolos |

### POST

| Endpoint | Body | Respuesta |
|----------|------|-----------|
| `/mode` | `{"slug": "", "mode": "plan\|build", "reason": ""}` | Estado del modo actualizado |
| `/branch/fork` | `{"slug": ""}` | `{"slug": "", "path": "/var/guardian/..."}` |
| `/conciencia/cycle` | `{"slug": "", "question": "", "mode": "plan\|build"}` | Acción, confianza, meta (opcional) |
| `/conciencia/meta` | `{"slug": ""}` | Ajustes, razones, nuevos umbrales |
| `/evolve` | `{"slug": ""}` | Meta-evolución (o null si ≤5 ciclos) |
| `/consolidate` | `{"slug": ""}` | Resultados: memory_gc, rag_reindex, learnings |
| `/absorb/ingest` | `{"slug": "", "rebuild": false}` | `{"rc": 0}` |
| `/absorb/scan` | `{"slug": ""}` | Resultado del scan |
| `/absorb/classify` | `{"slug": ""}` | Resultado de clasificación |
| `/docs/scan` | `{"slug": ""}` | Resultado del scan + auto RAG index |
| `/permission/check` | `{"slug": "", "path": "", "operation": "edit\|bash"}` | `{"slug", "path", "operation", "mode", "confidence", "action", "allowed"}` |
| `/mcp/call` | `{"slug": "", "tool": "", "args": {}}` | `{"ok": true}` |
| `/forja/index` | — | Índice de módulos del sistema |
| `/forja/list` | — | Listado de módulos con estado |
| `/forja/doctor` | — | Diagnóstico de salud |
| `/forja/validate` | `path` | Validar un módulo contra convenciones |
| `/forja/module/new` | `{"name": "", "desc": ""}` | Scaffold nuevo módulo |
| `/forja/rm` | `{"module": "", "force": false}` | Eliminar módulo (con seguridad) |
| `/forja/edit` | `{"file": ""}` | Leer contenido de archivo |
| `/forja/run` | `{"text": ""}` | Ejecutar instrucción en lenguaje natural |
| `/forja/protect` | `{"module": ""}` | Marcar módulo como protegido |
| `/forja/function` | `{"module": "", "name": "", "register": false}` | Agregar función cmd_ a módulo |
| `/forja/endpoint` | `{"method": "GET", "path": "", "module": ""}` | Scaffold endpoint REST |
| `/forja/mcp-tool` | `{"name": "", "module": ""}` | Scaffold tool MCP |
| `/forja/diff` | — | Mostrar cambios desde último snapshot |
| `/forja/graph` | — | Grafo de dependencias ASCII |
| `/forja/patch` | `{"file": "", "old": "", "new": ""}` | Edición parcial find+replace |

---

## MCP Tools — JSON-RPC 2.0

### Protocolo

Entrada: línea JSON por stdin con método y params.
Salida: línea JSON por stdout con resultado o error.

```
→ {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
← {"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2025-03-26", ...}}

→ {"jsonrpc": "2.0", "id": 2, "method": "list_tools", "params": {}}
← {"jsonrpc": "2.0", "id": 2, "result": {"tools": [...]}}
```

### Tools

| Método | Params requeridos | Descripción |
|--------|------------------|-------------|
| `read_file` | `path` | Leer contenido de archivo |
| `write_file` | `path`, `content`, `slug` | Escribir archivo (solo modo build) |
| `run_command` | `command` | Ejecutar comando bash |
| `rag_query` | `slug`, `query` | Consultar RAG |
| `conciencia_cycle` | `slug` | Ejecutar ciclo de conciencia |
| `mode_switch` | `slug`, `mode` | Cambiar modo plan/build |
| `knowledge_search` | `slug`, `query` | Buscar en tomos |
| `genome_status` | `slug` | Ver identidad del genoma |
| `branch_fork` | `slug` | Crear rama para usuario |
| `forja_doctor` | — | Diagnóstico de todos los módulos |
| `forja_validate` | `module` | Validar un módulo |
| `forja_index` | — | Reconstruir índice de auto-conocimiento |
| `forja_list` | — | Listar módulos con estado |
| `forja_scaffold` | `name`, `desc` | Crear nuevo módulo |
| `forja_run` | `text` | Ejecutar instrucción en lenguaje natural |
| `forja_diff` | — | Mostrar cambios desde último snapshot |
| `forja_graph` | — | Grafo de dependencias ASCII |
| `forja_patch` | `file`, `old`, `new` | Edición parcial find+replace |
| `analyze_intent` | `prompt` | Analiza intent, extrae topic_key, clasifica importancia |
| `save_observation` | `slug`, `type`, `topic_key`, `content`, `why`, `where`, `outcome`, `scope` | Guarda observación en brain |
| `get_observation` | `slug`, `topic_key`, `limit`, `global` | Busca observaciones por topic_key |
| `get_last_good` | `slug`, `topic_key` | Último estado exitoso de un topic |
| `plan_or_act` | `question`, `slug`, `confidence` | Decide si asumir o planificar |
| `compact_memory` | `slug` | Compacta GUARDIAN.md |

---

## Módulos del sistema

| Módulo | Archivo | Responsabilidad |
|--------|---------|-----------------|
| CLI | `guardian.py` | Interfaz de línea de comandos, enrutamiento, helpers |
| Shared | `guardian_shared.py` | Constantes, i18n, lectura/escritura de config, mode state, knowledge index |
| Memoria | `guardian_memory.py` | JSONL memory, TF-IDF search, embeddings, sessions, GC |
| RAG | `guardian_rag.py` | Chunking, reranking, citas, resaltado, caché de chunks |
| Absorb | `guardian_absorb.py` | Scan/match/classify/ingest de skills, sugerencias |
| Web | `guardian_web.py` | Dashboard HTTP, RAG search UI, discovery |
| Backend | `guardian_backend.py` | Servidor HTTP persistente, 19 endpoints, daemon lifecycle |
| Genoma | `guardian_genome.py` | Carga de identity.yaml, ramas, forks, diff, list |
| Conciencia | `guardian_conciencia.py` | N1 (score_context, consciousness_action, run_cycle), N2 (evolve, thresholds) |
| Evolución | `guardian_evolution.py` | evolve_branch, consolidate (memory GC + RAG reindex + learnings) |
| MCP | `guardian_mcp.py` | JSON-RPC 2.0 server, tool definitions y handlers |
| Forja | `guardian_forja.py` | Meta-módulo del arquitecto: scaffold, validación, impacto, edición, diagnóstico |
| Migration | `guardian_migration_v3_layout.py` | Migración de proyectos de v3 a v4 layout |
| Brain Symbols | `guardian_brain_symbols.py` | CodeGraph: tree-sitter AST indexer, lookup, query_smart |
| Brain Advisor | `guardian_brain_advisor.py` | Contexto dinámico: build_context, advise_on_action |
| Observer | `guardian_observer.py` | Captura de eventos, sanitización, clasificación |

---

## Archivos en disco

### Configuración y estado

| Archivo | Propósito |
|---------|-----------|
| `genome/identity.yaml` | ADN inmutable de Guardian |
| `/var/guardian/genome/branches/<hash>/identity.yaml` | Identidad de rama de usuario |
| `/var/guardian/genome/branches/<hash>/state.json` | Estado de conciencia y sesión |
| `/var/guardian/projects/<slug>/config.yaml` | Configuración de proyecto |
| `/var/guardian/projects/<slug>/conciencia-state.json` | Historial de ciclos de conciencia |
| `/var/guardian/projects/<slug>/conciencia-thresholds.json` | Umbrales calibrados |
| `/var/guardian/projects/<slug>/audit.json` | Registro de auditoría |
| `/var/guardian/skills-global.json` | Índice global de skills disponibles |

### Datos

| Archivo | Propósito |
|---------|-----------|
| `/var/guardian/projects/<slug>/memory/*.json` | Entradas de memoria (landmarks, decisiones, etc.) |
| `/var/guardian/projects/<slug>/knowledge/tomes/*.md` | Tomos de conocimiento |
| `/var/guardian/projects/<slug>/knowledge/index.json` | Índice de tomos |
| `/var/guardian/projects/<slug>/learnings/*.json` | Aprendizajes de meta-evolución |
| `/var/guardian/projects/<slug>/rag-chunks.json` | Caché de chunks RAG |
| `/var/guardian/projects/<slug>/memory-embeddings.json` | Embeddings TF-IDF |

### Backend

| Archivo | Propósito |
|---------|-----------|
| `/var/guardian/guardian-backend.pid` | PID del proceso backend |
| `/var/guardian/guardian-backend.log` | Logs del backend |

---

## Tests

```
python3 -m unittest discover -s tests -p "test_*.py"

tests/
├── test_rag.py           # 18 tests — RAG core, index, query, web integration
├── test_memory.py        # ~40 tests — memory CRUD, TF-IDF, sessions
├── test_config.py        # ~10 tests — config parsing, CLI
├── test_integration.py   # ~20 tests — web, absorb integration
├── test_backend.py       # 28 tests — conciencia, genoma, evolución, MCP
├── test_brain.py         # Tests de brain schema, advisor, symbols
├── test_phase3.py        # Tests de cognitive memory phase 3
├── test_phase4.py        # Tests de cognitive memory phase 4
├── test_v4.py            # 19 tests — v4: filesystem, genoma, conciencia, observer, advisor, codegraph
└── test_v4_e2e.py        # Tests end-to-end del ciclo v4 completo
```

---

## Plugin OpenCode (guardian.ts)

El plugin `.opencode/plugins/guardian.ts` integra Guardian con OpenCode como agente.

### Instalación

```bash
guardian setup <slug>          # Crea project config
guardian backend start          # Inicia backend persistente
```

El plugin se auto-descubre desde `.opencode/plugins/`.

### Herramientas expuestas (plugin tools)

| Tool | Descripción |
|------|-------------|
| `nexxoria-guardian_status` | Estado del proyecto, modo, backend health |
| `nexxoria-guardian_conciencia` | Ejecutar ciclo de conciencia |
| `nexxoria-guardian_rag` | Consultar RAG |
| `nexxoria-guardian_mode` | Cambiar modo plan/build |
| `nexxoria-guardian_brain_read` | Leer GUARDIAN.md |
| `nexxoria-guardian_brain_query` | Buscar en brain |
| `nexxoria-guardian_brain_write` | Escribir en brain |
| `nexxoria-guardian_query_smart` | CodeGraph: buscar símbolos |
| `nexxoria-guardian_codegraph_index` | Indexar AST con tree-sitter |
| `nexxoria-guardian_codegraph_status` | Estado del CodeGraph |
| `nexxoria-guardian_analyze_intent` | Analiza intent del usuario |
| `nexxoria-guardian_save_observation` | Guarda observación con metadata |
| `nexxoria-guardian_get_observation` | Busca observaciones por topic |
| `nexxoria-guardian_get_last_good` | Último estado exitoso de un topic |
| `nexxoria-guardian_plan_or_act` | Decide si asumir o planificar |
| `nexxoria-guardian_compact_memory` | Compacta GUARDIAN.md |
| `nexxoria-guardian_check_permission` | Verificar permiso de operación |
| `nexxoria-guardian_why_blocked` | Explicar por qué un path está bloqueado |

### Agentes OpenCode (v4.2.0 — 1 primario + 8 subagentes)

| Agente | Rol | Tools |
|--------|-----|-------|
| **`guardian`** (primary) | 🧠 Conciencia — percibe, decide, delega, reflexiona | read + task |
| `guardian-executor` | 🔧 Manos — escribe código, edita, ejecuta comandos | bash, edit, write, read |
| `guardian-researcher` | 🔍 Ojos — investiga temas, busca, analiza | bash, read |
| `guardian-memory` | 💾 Nanos — memoria persistente, compactación | bash, read |
| `guardian-observer` | 👁️ Sentidos — clasifica eventos, extrae topics | bash, read |
| `guardian-planner` | 📋 Planificador — descompone tareas en pasos | bash, read |
| `guardian-reviewer` | 🔎 Revisor — code review antes de ejecutar | bash, read |
| `guardian-tester` | 🧪 Verificador — ejecuta tests post-cambio | bash, read |
| `guardian-documenter` | 📝 Documentador — actualiza GUARDIAN.md + brain | bash, read, write |

### Árbol de delegación

```
Tarea simple + confianza alta → executor
Tarea compleja → planner → reviewer → executor → tester → documenter
Necesito información → researcher
Memoria → memory
Evento → observer
Plan multi-etapa → sdd-propose/spec/design/tasks/apply/verify/archive
```

### Hooks (v4.2.0 — 6 hooks)

- **`session.created`**: Solo inyecta GUARDIAN.md (~25 líneas). NADA de Advisor.
- **`permission.ask`**: Intercepta writes/bash en módulos protegidos, consulta backend con cache LRU (5min TTL, max 200 entries)
- **`chat.message`**: Analiza intent + busca observaciones relevantes + auto-save si > 0.5 importancia
- **`tool.execute.before`**: Advisor advierte si una acción es riesgosa
- **`tool.execute.after`**: Observa resultado + guarda observación si fue edit/write
- **`tui.prompt.append`**: Detecta keywords para auto-cambiar modo plan/build
- **`experimental.session.compacting`**: Re-inyecta GUARDIAN.md antes de compactar
- **`shell.env`**: Setea GUARDIAN_HOME y GUARDIAN_DATA en el entorno

### Niveles de guardia en módulos

| Nivel | Descripción |
|-------|-------------|
| `blocked` | Denegado siempre |
| `readonly` | Lectura permitida, escritura denegada |
| `conciencia` | Evalúa con backend `quick_check()` |
| `allowed` | Permitido siempre |
