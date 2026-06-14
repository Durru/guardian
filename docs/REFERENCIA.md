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
| `/mcp/tools` | — | Lista de 9 herramientas MCP disponibles |

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
| `/mcp/call` | `{"slug": "", "tool": "", "args": {}}` | `{"ok": true}` |

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
| MCP | `guardian_mcp.py` | JSON-RPC 2.0 server, 9 tool definitions y handlers |

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
└── test_backend.py       # 28 tests — conciencia, genoma, evolución, MCP
```

**Total: 119 tests (2 fallos pre-existentes de aislamiento al ejecutar suite completa)**
