# Guardian v2 — Módulos

> Mapa completo de cada módulo en `/opt/nexxoria-guardian/lib/`: qué hace, cómo funciona, qué exporta, y quién lo consume.

---

## Índice

1. [`guardian.py`](#1-guardianpy) — CLI Dispatcher
2. [`guardian_shared.py`](#2-guardian_sharedpy) — Shared utilities
3. [`guardian_genome.py`](#3-guardian_genomepy) — Genome + Ramas
4. [`guardian_conciencia.py`](#4-guardian_concienciapy) — Conciencia N1/N2
5. [`guardian_memory.py`](#5-guardian_memorypy) — Memoria TF-IDF
6. [`guardian_rag.py`](#6-guardian_ragpy) — RAG Pipeline
7. [`guardian_absorb.py`](#7-guardian_absorbpy) — Skill Absorb v2
8. [`guardian_evolution.py`](#8-guardian_evolutionpy) — Evolución + Consolidación
9. [`guardian_mcp.py`](#9-guardian_mcppy) — MCP Server (stdio)
10. [`guardian_backend.py`](#10-guardian_backendpy) — HTTP Backend (:9787)
11. [`guardian_web.py`](#11-guardian_webpy) — Web Dashboard (:7878)
12. [`guardian_forja.py`](#12-guardian_forjapy) — La Forja: meta-módulo del arquitecto

---

## 1. `guardian.py` — CLI Dispatcher

**Archivo**: `/opt/nexxoria-guardian/lib/guardian.py` (2961 líneas)
**Propósito**: Punto de entrada CLI. Parsea todos los subcomandos y delega a los módulos correspondientes.

### Flujo general

```
$ guardian <subcommand> [args]
  → sys.argv parsing en `if __name__ == "__main__": main()`
    → dispatch(argv)
      → detecta slug (flag, git remote, o PWD)
      → llama a cmd_<subcommand>() en guardian.py
        O ejecuta subprocess con sys.executable al módulo correspondiente
```

### Subcomandos soportados (30+)

| Grupo | Comandos |
|-------|----------|
| **Proyecto** | `detect`, `status`, `check`, `report`, `setup`, `projects` |
| **Cambios** | `protect`, `snapshot`, `diff`, `rollback`, `hooks` |
| **Permisos** | `permission check` |
| **Workflow AI** | `context`, `rag`, `mode`, `conciencia`, `knowledge`, `prompt` |
| **Sistemas** | `backend`, `memory`, `absorb`, `genome`, `branch`, `evolve`, `consolidate` |
| **GitHub** | `pr`, `issue` |
| **Web** | `web` |
| **Docs** | `docs scan`, `docs route` |
| **Hooks** | `pre-change`, `post-change`, `pre-deploy`, `post-deploy` |
| **Dev** | `build`, `dev`, `test`, `lint`, `typecheck`, `deploy`, `logs` |

### Hard-gate router (`guardian prompt`)

El subcomando `prompt` tiene un sistema de ruteo con 3 modos:
- **direct**: ejecuta el paso de workflow directamente
- **clarify**: pide aclaración al usuario antes de continuar
- **delegate**: delega a otro agente/herramienta

### Cómo delega a otros módulos

```python
# Ejemplo: memory subcommand
subprocess.run([sys.executable, MEMORY_MODULE, slug, action, ...])

# Ejemplo: absorb subcommand
subprocess.run([sys.executable, ABSORB_MODULE, slug, action, ...])
```

Usa `sys.executable` para asegurar el mismo intérprete de Python. La salida se captura y retorna al usuario.

---

## 2. `guardian_shared.py` — Shared Utilities

**Archivo**: `/opt/nexxoria-guardian/lib/guardian_shared.py` (1353 líneas)
**Propósito**: Funciones compartidas importadas por TODOS los demás módulos.

### Constantes de ruta

| Constante | Default | Descripción |
|-----------|---------|-------------|
| `MEMORY_DIR` | `$GUARDIAN_DATA` o `/var/guardian/projects` | Proyectos persistentes |
| `BACKEND_DIR` | `/var/guardian` | Backend + branches |
| `GENOME_DIR` | `/srv/guardian` | Genome base |
| `BRANCHES_DIR` | `/var/guardian/genome/branches` | Ramas de evolución |
| `SKILLS_GLOBAL` | `/var/guardian/skills-global.json` | Registro global de skills |

### Funciones principales

| Función | Qué hace |
|---------|----------|
| `_(string)` | i18n: busca string en ES, retorna traducción EN (o el original si no existe) |
| `read_config(slug)` | Lee `MEMORY_DIR/slug/config.yaml`, retorna dict |
| `write_config(slug, data)` | Escribe config.yaml de un proyecto |
| `project_exists(slug)` | Verifica si `MEMORY_DIR/slug/` existe |
| `discover_projects()` | Lista todos los proyectos en `MEMORY_DIR` |
| `read_memory(slug)` | Lee memoria de un proyecto |
| `write_memory(slug, data)` | Escribe memoria |
| `read_audit(slug)` | Lee auditoría |
| `write_audit(slug, entry)` | Agrega entrada a auditoría |
| `read_skills_json()` | Lee skills-global.json |
| `branch_path_for(slug)` | Retorna ruta de branch para un proyecto |
| `slugify(name)` | Normaliza string a slug |
| `_hash(data)` | SHA-256 hash |
| `ts_epoch()` | Timestamp UNIX actual |
| `_get_git_info(path)` | Retorna `(status, diff)` de git en un path |

### i18n

```python
_STRINGS = {
    "en": { "project_not_found": "Project not found: {slug}", ... },
    "es": { "project_not_found": "Proyecto no encontrado: {slug}", ... },
}
# lookup: _(string) busca en ES_EN_DICT primero, luego en _STRINGS[lang]
```

También tiene `ES_EN_DICT` para strings en español hardcodeadas en el código (para migración gradual).

### JSON

- `JsonEncoder` — custom JSON encoder que serializa `datetime`, `Path`, `set`, etc.
- Usa `json.dumps` con `cls=JsonEncoder` en toda la base de código

---

## 3. `guardian_genome.py` — Genome + Ramas

**Archivo**: `/opt/nexxoria-guardian/lib/guardian_genome.py` (311 líneas)
**Propósito**: Identity (`identity.yaml`), branch detection, fork/diff entre genomas.

### `identity.yaml` — formato

```yaml
name: nexxoria-guardian
version: 2.0.0
slug: nexxoria-guardian
manifest:
  stack: [python, typescript, shell]
  features: [rag, conciencia, absorb, mcp, backend, web, memory, evolution]
  mode: build
```

### Funciones principales

| Función | Descripción |
|---------|-------------|
| `load_genome(slug)` | Lee `GENOME_DIR/slug/identity.yaml`, retorna `dict` |
| `fork_branch(slug, user)` | Crea branch para un usuario: copia `GENOME_DIR/slug/` a `BRANCHES_DIR/<hash>/`
| `load_branch(slug)` | Lee branch activa (detecta por hostname hash) |
| `diff_genome(genome_a, genome_b)` | Compara dos genomas, retorna `GenomeDiff(added, modified, removed)` |

### Branch detection

```python
def _branch_hash():
    hostname = socket.gethostname()
    return hashlib.sha256(hostname.encode()).hexdigest()[:12]
```

- 1 branch por máquina (identificada por hostname)
- Projects están dentro de esa branch como sub-contextos
- `GenomeDiff` dataclass con `added: dict`, `modified: dict`, `removed: dict`

### CLI

- `guardian genome status <slug>` — muestra identidad del genoma
- `guardian genome diff <slug>` — diff entre genoma base y branch activa
- `guardian branch list/fork/status/diff`

---

## 4. `guardian_conciencia.py` — Conciencia N1/N2

**Archivo**: `/opt/nexxoria-guardian/lib/guardian_conciencia.py` (562 líneas)
**Propósito**: Ciclo de conciencia de 2 niveles, scoring de contexto, y acciones autónomas.

### N1 — Percibir / Decidir / Reflexionar

```
consciousness_cycle(slug, question, mode)
  ↓
_percibir(slug, question, mode)
  → score_context(slug, question, mode) → dict de factores con scores
  → assembly system prompt + context
  ↓
_decidir(context)
  → consciousness_action(scores) → (action, params)
  ↓
_reflexionar(slug, action, result)
  → log + audit de lo que pasó
```

### `score_context()` — Factores evaluados

| Factor | Descripción | Range |
|--------|-------------|-------|
| `peligro` | Peligro potencial de la operación | 0.0 - 1.0 |
| `complejidad` | Qué tan compleja es la tarea | 0.0 - 1.0 |
| `confianza` | Qué tan seguro está el agente | 0.0 - 1.0 |
| `urgencia` | Qué tan urgente es | 0.0 - 1.0 |
| `modo` | Plan vs build | 0.0 / 0.5 / 1.0 |
| `skills` | Skills disponibles para la tarea | 0.0 - 1.0 |
| `memoria` | Relevancia de memoria existente | 0.0 - 1.0 |
| `cambio` | Impacto del cambio propuesto | 0.0 - 1.0 |

### `consciousness_action(scores, thresholds)` — 5 acciones

| Acción | Threshold | Qué hace |
|--------|-----------|----------|
| `read` | peligro > 0.7 o confianza < 0.3 | Solo leer, no ejecutar |
| `write` | complejidad < 0.5 y confianza > 0.7 | Escribir directamente |
| `run` | urgencia > 0.8 y peligro < 0.3 | Ejecutar comando |
| `reflect` | scores mixtos | Preguntar al usuario |
| `evolve` | ciclo regular sin urgencia | Ajustar thresholds |

### N2 — Meta-evolución

```
meta_evolution(slug, history)
  → analiza acciones recientes
  → ajusta thresholds en conciencia thresholds.json
  → evoluciona pesos de los factores
```

- Se ejecuta periódicamente
- Ajusta thresholds basado en resultados históricos (éxitos/fracasos)
- Persiste en `BRANCHES_DIR/<hash>/conciencia/thresholds.json`

### System prompt assembly

```python
_system_prompt(context):
  → genome identity (nombre, versión, stack)
  → modo actual (plan/build)
  → scores de contexto
  → memoria relevante (últimos N landmarks)
  → skills disponibles
```

### CLI

- `guardian conciencia cycle <slug> [question] [--mode]`
- `guardian conciencia status <slug>`
- `guardian conciencia history <slug>`
- `guardian conciencia meta <slug>`

---

## 5. `guardian_memory.py` — Memoria TF-IDF

**Archivo**: `/opt/nexxoria-guardian/lib/guardian_memory.py` (476 líneas)
**Propósito**: Persistencia de landmarks, patrones de decisión, aprendizajes, con búsqueda TF-IDF.

### Estructura de datos

```
MEMORY_DIR/<slug>/
├── memory.json          → landmarks [{id, type, content, timestamp, tags}]
├── decisions.json       → patrones de decisión [{pattern, outcome, weight}]
└── learnings.json       → aprendizajes [{id, content, source, success, weight, timestamp}]
```

### Tipos de landmarks

| Tipo | Descripción |
|------|-------------|
| `decision` | Decisión importante tomada |
| `observation` | Observación sobre el código/proyecto |
| `change` | Cambio realizado |
| `question` | Pregunta hecha por el usuario |
| `error` | Error encontrado |
| `insight` | Descubrimiento no obvio |

### Funciones principales

| Función | Descripción |
|---------|-------------|
| `memory_create(slug, type, content, tags)` | Crea nuevo landmark |
| `memory_read(slug, id)` | Lee landmark por ID |
| `memory_update(slug, id, content, tags)` | Actualiza landmark |
| `memory_delete(slug, id)` | Elimina landmark |
| `memory_search(slug, query, top_k)` | Busca por TF-IDF |
| `memory_decide(slug, context)` | Busca patrón de decisión similar |
| `memory_clean(slug, days)` | Poda landmarks viejos |

### TF-IDF Index

```python
_compute_tfidf_index(entries):
  # Por cada entry: tokeniza, calcula TF-IDF
  # TF = freq del término en el doc / total términos
  # IDF = log(total docs / docs con el término)
  # Peso final = TF * IDF

_embed_text(text):
  # Si sentence-transformers está instalado: usa embedding model
  # Sino: vector de ceros (fallback)
```

### Decision patterns

- `memory_decide()` busca en `decisions.json` por patrón similar usando TF-IDF
- Cada decisión tiene un `weight` que se actualiza con el outcome:
  - **success**: weight += 1
  - **failure**: weight += 2 (aprende más del fracaso)

### CLI

- `guardian memory save <slug> <content> [--type] [--tags]`
- `guardian memory search <slug> <query> [--top-k]`
- `guardian memory context <slug> [--limit]`
- `guardian memory index <slug> [--force]`
- `guardian memory gc <slug> [--days]`
- `guardian memory status <slug>`

### Consumido por

- `guardian_rag.py` — importa inline `_compute_tfidf_index()` y `_embed_text()`
- `guardian_conciencia.py` — usa `memory_search()` para contexto
- `guardian_evolution.py` — llama `guardian_memory.py gc <slug>` via subprocess

---

## 6. `guardian_rag.py` — RAG Pipeline

**Archivo**: `/opt/nexxoria-guardian/lib/guardian_rag.py` (523 líneas)
**Propósito**: Retrieval-Augmented Generation con 5 fuentes de conocimiento, reranking TF-IDF, y armado de contexto.

### Pipeline completo

```
rag_query(slug, query, mode, top_k, source_filter, max_tokens)
  ↓
_collect_chunks(slug, source_filter)
  → recolecta chunks de 5 fuentes
  ↓
_compute_tfidf_index(chunks)   ← inline, importa de guardian_memory
  ↓
_embed_text(chunks)            ← inline
  ↓
_rerank(query, chunks, index, top_k)
  → cosine similarity entre query y cada chunk
  ↓
assemble_context(chunks, mode, max_tokens, source_filter)
  → arma string plano con límite de tokens
```

### 5 fuentes de conocimiento

| Fuente | Origen | Modo |
|--------|--------|------|
| `docs` | `MEMORY_DIR/<slug>/docs/` — archivos `.md` | plan + build |
| `learnings` | `MEMORY_DIR/<slug>/learnings.json` | plan + build |
| `memory` | `MEMORY_DIR/<slug>/memory.json` (landmarks) | plan + build |
| `skills` | Skills globales (skills-global.json) + específicas del proyecto | plan + build |
| `tomes` | `MEMORY_DIR/<slug>/knowledge/tomes/` — tomos de conocimiento | plan + build |

### Filtrado por modo

- **plan**: todas las fuentes
- **build**: skills + tomes (prioriza conocimiento técnico)

### Reranking

1. Calcula TF-IDF para todos los chunks
2. Embediza la query (sentence-transformers si disponible)
3. Cosine similarity entre query embedding y cada chunk embedding
4. Retorna top_k chunks ordenados por score

### `assemble_context()`

- Aplica `source_filter` si se especifica
- Limita a `max_tokens` (estima tokens como chars/4)
- Arma string con formato:
  ```
  [source: docs] archivo.md
  contenido...

  [source: memory] landmark
  contenido...
  ```

### Heurística `need_full_context()`

```python
def need_full_context(query):
    # Retorna True si la query sugiere que necesita contexto completo
    # Palabras clave: "context", "full", "all", "todo", "complete", "proyecto"
    # Si query es corta (< 10 chars) → False
    # Si query tiene palabras clave → True
```

### CLI

- `guardian rag <slug> <query> [--top-k] [--json] [--scope] [--mode]`

### Consumido por

- `guardian_conciencia.py` — `consciousness_cycle()` usa RAG para contexto
- `guardian_backend.py` — endpoint `/api/rag/query`
- `guardian_mcp.py` — tool `rag_query`
- `guardian_web.py` — interfaz de búsqueda RAG

---

## 7. `guardian_absorb.py` — Skill Absorb v2

**Archivo**: `/opt/nexxoria-guardian/lib/guardian_absorb.py` (354 líneas)
**Propósito**: Escanea, clasifica, matchea e ingiere skills como tomos de conocimiento.

### Pipeline absorb

```
absorb_scan(slug, path)
  ↓
absorb_classify(files, genome)
  → clasifica cada archivo por prefijo + extensión
  ↓
absorb_match(classified, genome)
  → TF-IDF cosine similarity contra genome manifest
  → threshold: 0.35
  ↓
absorb_ingest(slug, matched)
  → copia skills detectados como tomos a knowledge/tomes/
  → registra en skills-global.json
```

### `AbsorbClass` enum

| Valor | Descripción |
|-------|-------------|
| `DIRECTORY` | Directorio completo (match/) |
| `FILE_PYTHON` | Archivo .py |
| `FILE_SHELL` | Archivo .sh |
| `FILE_TYPESCRIPT` | Archivo .ts/.tsx |
| `FILE_MARKDOWN` | Archivo .md |
| `FILE_YAML` | Archivo .yaml/.yml |
| `FILE_JSON` | Archivo .json |
| `FILE_OTHER` | Otro tipo |
| `UNKNOWN` | No clasificado |

### Clasificación por prefijo

| Prefijo | Clasificación |
|---------|---------------|
| `match/` o `skill/` | Skill |
| `guard/` o `protect/` | Guard |
| `test/` o `spec/` | Test |
| `docs/` o `doc/` | Doc |
| `guide/` | Guide |
| `template/` | Template |
| `workflow/` | Workflow |
| `prompt/` | Prompt |
| Otro | FILE_LANG |

### Matching contra genome

```python
absorb_match(classified, genome):
  for file in classified:
    # TF-IDF entre filename + contenido parcial vs manifest.requirements
    # threshold: 0.35
    # Si match: asigna a tomo con metadata del genome
```

### CLI

- `guardian absorb scan <slug> [--path]`
- `guardian absorb classify <slug>`
- `guardian absorb match <slug>`
- `guardian absorb ingest <slug>`
- `guardian absorb learn <slug>`
- `guardian absorb suggest <slug>`
- `guardian absorb status <slug>`

---

## 8. `guardian_evolution.py` — Evolución + Consolidación

**Archivo**: `/opt/nexxoria-guardian/lib/guardian_evolution.py` (365 líneas)
**Propósito**: Evolución de thresholds de conciencia (N2) y consolidación periódica de memoria/RAG.

### `evolve_branch(slug)`

```
evolve_branch(slug):
  1. Lee branch state actual + thresholds de conciencia
  2. Ejecuta meta_evolution() de conciencia
     → ajusta thresholds basado en historia de acciones
  3. Persiste nuevos thresholds
  4. Retorna diff de cambios
```

### `consolidate(slug)`

```
consolidate(slug):
  1. Memory GC
     → subprocess: guardian_memory.py gc <slug>
     → poda landmarks viejos (>30 días por defecto)
  2. RAG reindex
     → subprocess: guardian_memory.py index <slug> --force
  3. Prune learnings
     → elimina aprendizajes con weight bajo (< 0.5)
  4. Absorb match
     → llama absorb_match() para re-clasificar skills
  5. Retorna resumen de lo que hizo
```

### CLI

- `guardian evolve <slug>` — dispara evolución
- `guardian consolidate <slug>` — dispara consolidación

### Dependencias

Importa directamente:
- `guardian_shared` — paths, config
- `guardian_genome` — branch state
- `guardian_rag` — reindex

Llama via subprocess:
- `guardian_memory.py gc <slug>`
- `guardian_memory.py index <slug> --force`

---

## 9. `guardian_mcp.py` — MCP Server (stdio)

**Archivo**: `/opt/nexxoria-guardian/lib/guardian_mcp.py` (275 líneas)
**Propósito**: Servidor JSON-RPC sobre stdin/stdout que expone herramientas de Guardian como MCP tools.

### Protocolo

```
← JSON-RPC request  → stdin
→ JSON-RPC response ← stdout
```

Usa `mcp.types` para definiciones de tools y resource templates.

### Tools registradas

| Tool | Descripción | Parámetros |
|------|-------------|------------|
| `read_file` | Leer archivo | `path` |
| `write_file` | Escribir archivo (solo build mode) | `path`, `content` |
| `run_command` | Ejecutar comando bash | `command`, `timeout` |
| `rag_query` | Consultar RAG | `slug`, `query`, `top_k`, `source_filter` |
| `conciencia_prompt` | Obtener system prompt | `slug`, `question`, `mode` |
| `genome_diff` | Diff de genoma | `slug` |
| `mode_switch` | Cambiar modo | `slug`, `mode`, `reason` |
| `mode_status` | Ver modo actual | `slug` |
| `absorb_scan` | Escanear skills | `slug`, `path` |

### Clase `MCPServer`

```python
class MCPServer:
    def __init__(self, slug):
        self.slug = slug
        self.tool_handlers = { ... }

    def handle_request(self, request: dict) -> dict:
        # Parsea método y params
        # Busca en tool_handlers
        # Ejecuta y retorna resultado
```

### Arranque

```python
if __name__ == "__main__":
    slug = sys.argv[1] if len(sys.argv) > 1 else None
    server = MCPServer(slug)
    # Lee stdin línea por línea, procesa requests
```

### Consumido por

- OpenCode plugin (`guardian.ts`) se conecta a este server via MCP
- `guardian_backend.py` expone endpoint para health check

---

## 10. `guardian_backend.py` — HTTP Backend (:9787)

**Archivo**: `/opt/nexxoria-guardian/lib/guardian_backend.py` (481 líneas)
**Propósito**: Servidor HTTP persistente con API REST para todos los sistemas de Guardian.

### Clase `BackendHandler`

```python
class BackendHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # rutea por self.path
    def do_POST(self):
        # parsea body JSON, rutea
```

### Endpoints

| Ruta | Método | Descripción |
|------|--------|-------------|
| `/health` | GET | Health check |
| `/metrics` | GET | Métricas básicas |
| `/api/projects` | GET | Lista proyectos |
| `/api/projects/config` | GET | Config de proyecto |
| `/api/projects/setup` | POST | Setup de proyecto |
| `/api/genome/diff` | POST | Diff de genoma |
| `/api/genome/branches` | GET | Lista branches |
| `/api/genome/branch/fork` | POST | Fork branch |
| `/api/conciencia/state` | POST | Estado de conciencia |
| `/api/conciencia/thresholds` | POST | Thresholds actuales |
| `/api/conciencia/prompt` | POST | System prompt |
| `/api/rag/query` | POST | Búsqueda RAG |
| `/api/evolution/evolve` | POST | Disparar evolución |
| `/api/evolution/consolidate` | POST | Disparar consolidación |
| `/api/absorb/run` | POST | Ejecutar absorb |
| `/api/git/status` | POST | Git status |
| `/api/git/diff` | POST | Git diff |
| `/api/git/commit` | POST | Git commit |
| `/api/skills` | GET | Skills globales |
| `/api/mcp/call` | POST | Proxy a MCP |

### Arranque y ciclo de vida

```python
def run_server(host="127.0.0.1", port=9787):
    server = HTTPServer((host, port), BackendHandler)
    server.serve_forever()

# PID file en BACKEND_DIR/backend.pid
```

### CLI

- `guardian backend start|stop|restart|status`

### who calls it

- OpenCode plugin (`guardian.ts`) — health check + permission check
- `guardian_conciencia.py` — permission scoring via HTTP POST
- `guardian.py` — start/stop/restart

---

## 11. `guardian_web.py` — Web Dashboard (:7878)

**Archivo**: `/opt/nexxoria-guardian/lib/guardian_web.py` (78 líneas)
**Propósito**: Dashboard web HTML con inline CSS para monitoreo de proyectos.

### Funciones

| Función | Descripción |
|---------|-------------|
| `run_web(host, port)` | Inicia servidor HTTP |
| `_discover_projects()` | Lista proyectos desde `MEMORY_DIR` |
| `_read_memory(slug)` | Lee últimos 50 landmarks |
| `_read_audit(slug)` | Lee últimos 50 entries de auditoría |
| `_read_skills(slug)` | Lee skills del proyecto |
| `_query_rag(slug, query, source_filter)` | Búsqueda RAG vía `guardian_rag.py` |

### Páginas

- `/` — Dashboard principal: lista de proyectos con estado
- `/<slug>` — Vista de proyecto: memoria, auditoría, skills
- `/<slug>/rag` — Búsqueda RAG con filtro por fuente
- `/<slug>/genome` — Diff de genoma
- `/<slug>/skills` — Skills clasificados

### Estilo

- Inline CSS (sin frameworks)
- Diseño oscuro (dark theme)
- Cards para cada sección
- Responsive básico

### CLI

- `guardian web [--port <n>]`

---

## 12. `guardian_forja.py` — La Forja: meta-módulo del arquitecto

**Archivo:** `lib/guardian_forja.py`
**Propósito:** Meta-módulo para crear, leer, editar, eliminar, y mantener los módulos centrales del Guardian. Es el "taller del arquitecto" — auto-conocimiento del sistema, validación estructural, análisis de impacto, edición directa por lenguaje natural, y protección de módulos críticos.

### Subcomandos CLI

| Subcomando | Descripción |
|------------|-------------|
| `guardian forja index` | Reconstruye el índice de todos los módulos lib/*.py |
| `guardian forja list` | Lista todos los módulos con su estado |
| `guardian forja doctor` | Diagnóstico de salud de todos los módulos |
| `guardian forja new <nombre>` | Crea un nuevo módulo desde plantilla |
| `guardian forja validate <archivo>` | Valida un módulo (AST, imports, funciones, endpoints, MCP tools) |
| `guardian forja edit <archivo>` | Edita un archivo (abre editor o modo no-interactivo) |
| `guardian forja rm <archivo>` | Elimina un módulo con backup y confirmación |
| `guardian forja protect <archivo>` | Marca un archivo como protegido |
| `guardian forja run "<texto>"` | Ejecuta una instrucción en lenguaje natural |

### Endpoints REST

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/forja/index` | Obtiene el índice de módulos |
| GET | `/api/forja/list` | Lista módulos con estado |
| GET | `/api/forja/doctor` | Diagnóstico de salud |
| GET | `/api/forja/validate?path=...` | Valida un archivo específico |
| POST | `/api/forja/module/new` | Crea un nuevo módulo |
| POST | `/api/forja/rm` | Elimina un módulo |
| POST | `/api/forja/edit` | Edita un archivo |
| POST | `/api/forja/run` | Ejecuta instrucción en lenguaje natural |
| POST | `/api/forja/protect` | Marca archivo como protegido |

### MCP Tools

| Tool | Descripción |
|------|-------------|
| `forja_doctor` | Diagnóstico de todos los módulos |
| `forja_validate` | Valida un módulo específico |
| `forja_index` | Reconstruye el índice |
| `forja_list` | Lista módulos con estado |
| `forja_scaffold` | Crea un nuevo módulo |
| `forja_run` | Ejecuta instrucción en lenguaje natural |

### Archivos de estado

| Archivo | Propósito |
|---------|-----------|
| `~/.forja/index.json` | Índice de módulos (auto-conocimiento) |
| `~/.forja/backups/*` | Backups antes de eliminaciones |
| `~/.forja/audit/changes.jsonl` | Auditoría de cambios |

### Funciones clave

| Función | Descripción |
|---------|-------------|
| `scan_index()` | Escanea `lib/` y reconstruye `index.json` con metadatos (funciones, clases, endpoints, MCP tools) |
| `module_new()` | Crea módulo desde plantilla con naming `guardian_{nombre}.py` |
| `validate_module()` | Valida sintaxis AST, detecta funciones/endpoints/MCP tools vía regex |
| `impact_analysis()` | Analiza dependencias, imports, y qué módulos se ven afectados |
| `doctor_check()` | Diagnóstico completo: parseo, imports, firma vs código |
| `list_inventory()` | Lista todos los módulos con tamaño, funciones, fecha |
| `edit_file()` / `write_file_content()` | Edición segura de archivos |
| `delete_module()` | Elimina con backup, confirmación doble, y protección por módulos críticos |
| `protect_module()` | Agrega un módulo a la lista de protegidos en runtime |
| `run_direct()` | Procesa instrucciones en lenguaje natural |

### Módulos protegidos (requieren `--force` para eliminar)

- `guardian_shared.py`
- `guardian_genome.py`
- `guardian_conciencia.py`
- `guardian_forja.py` (auto-protegido)
- `guardian_mcp.py`
- `guardian_backend.py`

### Dependencias que importa

- `guardian_shared.py` — para `_(string)`, `pprint()`, `ERR()`, `sh()`
- `ast`, `re`, `os`, `json`, `shutil`, `datetime` — stdlib

---

## Diagrama de Arquitectura

```
┌─────────────────────────────────────────────────────────────────────┐
│                        OpenCode Plugin                              │
│                    .opencode/plugins/guardian.ts                     │
│                    MCP client → guardian_mcp.py                      │
└──────────┬──────────────────────────────────────┬───────────────────┘
           │ MCP stdio                            │ HTTP health check
           ▼                                      ▼
┌──────────────────┐                ┌──────────────────────────┐
│ guardian_mcp.py  │                │  guardian_backend.py     │
│ JSON-RPC stdio   │                │  REST API :9787          │
│ 9 tools          │                │  20+ endpoints           │
└────────┬─────────┘                └────────┬─────────────────┘
         │                                    │
         ▼                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         guardian.py                                 │
│                     CLI Dispatcher (30+ subcommands)                  │
│                                                                     │
│  subprocess ──────┬──────┬──────┬──────┬──────┬──────┬──────┬────┐ │
└───────────────────┼──────┼──────┼──────┼──────┼──────┼──────┼────┘ │
                    │      │      │      │      │      │      │       │
         ┌─────────┴┐ ┌───┴───┐ ┌─┴───┐ ┌┴────┐ ┌┴───┐ ┌┴────┐ ┌┴──┐
         │shared.py │ │genome │ │con- │ │mem │ │rag │ │abs │ │evo│
         │i18n,cfg  │ │.py    │ │cien-│ │.py  │ │.py │ │orb │ │lu-│
         │mem,audit │ │branch │ │cia  │ │TF-  │ │5   │ │.py │ │tion│
         │git,path  │ │fork   │ │.py  │ │IDF  │ │srcs │ │class│ │.py │
         └──────────┘ │diff   │ │N1/N2│ │mem  │ │rerank│ │ify  │ │cons│
                      └───────┘ │scor │ │idx  │ │ctx  │ │matc │ │olid│
                                │act  │ └─────┘ │asmb │ │ingst│ └────┘
                                └─────┘         └─────┘ └─────┘
                                                    │
                                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         guardian_web.py                             │
│                    Dashboard HTML :7878                              │
│                    projects, memory, RAG, skills                     │
└─────────────────────────────────────────────────────────────────────┘

Persistence:
  /var/guardian/projects/<slug>/  → config.yaml, memory.json, decisions.json
                                      learnings.json, audit.log, docs/, knowledge/
  /var/guardian/genome/branches/  → <hash>/ (identity.yaml, thresholds.json)
  /srv/guardian/                  → genome base, identity.yaml
  /var/guardian/skills-global.json → registro global de skills
```

---

## Dependencias entre módulos

```
guardian.py
├── guardian_shared.py        (i18n, file ops, config, git)
├── guardian_genome.py        (genome + branches)
├── guardian_evolution.py     (evolve + consolidate)
├── guardian_memory.py (CLI)  (memory subcommand)
├── guardian_absorb.py (CLI)  (absorb subcommand)
├── guardian_rag.py (CLI)     (rag subcommand)
└── (subprocess) → cada módulo se ejecuta como script independiente

guardian_backend.py
├── guardian_shared.py
├── guardian_absorb.py
├── guardian_conciencia.py
├── guardian_evolution.py
├── guardian_genome.py
└── guardian_rag.py

guardian_conciencia.py
├── guardian_shared.py
├── guardian_genome.py
└── guardian_rag.py

guardian_mcp.py
├── guardian_shared.py
├── guardian_genome.py
├── guardian_conciencia.py
└── guardian_rag.py

guardian_rag.py
├── guardian_shared.py
└── guardian_memory.py (importa inline _compute_tfidf_index, _embed_text)

guardian_absorb.py
└── guardian_shared.py

guardian_evolution.py
├── guardian_shared.py
├── guardian_genome.py
├── guardian_rag.py
└── guardian_memory.py (subprocess)
```

---

## Flujos de datos críticos

### CLI → Ejecución
```
guardian memory search mi-slug "algo"
  → guardian.py dispatch()
    → detecta "memory" → subprocess([sys.executable, guardian_memory.py, "mi-slug", "search", "algo"])
      → guardian_memory.py main()
        → memory_search("mi-slug", "algo")
          → _compute_tfidf_index()
          → _embed_text()
          → cosine similarity
        ← resultados
      ← stdout
    ← print
```

### Plugin → MCP → Backend
```
OpenCode tool call
  → guardian.ts tool.execute()
    → stdin: {"method": "rag_query", "params": {"slug": "x", "query": "y"}}
      → guardian_mcp.py handle_request()
        → import guardian_rag → rag_query()
        ← response
    ← stdout: {"result": ...}
  ← parse
```

### Permission check
```
OpenCode permission.ask
  → guardian.ts matchModule(path) → level
    → if conciencia: POST /permission/check
      → guardian_backend.py
        → guardian_conciencia.score_context()
        → guardian_conciencia.consciousness_action()
      ← {"allowed": true/false, "action": "read"/"write"}
    ← cached 5 min
  → allow/deny
```
