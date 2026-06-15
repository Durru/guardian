# Nexxoria Guardian — Agent Blueprint

## Architecture Layers

```
┌──────────────────────────────────────────────────────────────────┐
│  L1 — PLUGIN (OpenCode)       .opencode/plugins/guardian.ts     │
│  L2 — CLI (entry)             guardian → lib/guardian.py        │
│  L3 — PYTHON LIBS             lib/guardian_*.py                 │
│  L4 — PERSISTENCE             /var/guardian/ + /srv/guardian/   │
└──────────────────────────────────────────────────────────────────┘
```

Data flows DOWN (plugin→CLI→libs→disk), answers flow UP.
Each layer can ONLY depend on layers below it.

---

## File Map — Every File, Its Job, Its Consumers

### Layer 1 — Plugin (TypeScript, runs in OpenCode)

| File | Job | Used By |
|------|-----|---------|
| `.opencode/plugins/guardian.ts` | 6 MCP tools, permission guard, mode detection, session context, compact hook | OpenCode runtime |

### Layer 2 — CLI Entry Point

| File | Job | Consumers |
|------|-----|-----------|
| `guardian` | Shell wrapper, `exec(guardian.py "$@")` | User/plugin calls this |
| `lib/guardian.py` (2961 lines) | **CLI dispatcher** — parses ALL subcommands, delegates to `guardian_*.py` libs | guardian (via argv) |
| `lib/guardian_shared.py` (1353 lines) | Shared: i18n (`_()`), file ops, config read/write, git helpers, YAML/json utils | EVERY .py file imports this |

### Layer 3 — Python Libraries

| File | Job | Key Symbols | Consumers |
|------|-----|-------------|-----------|
| `lib/guardian_genome.py` (311 lines) | Genoma + ramas: load/fork/diff identity.yaml, branch state | `load_genome()`, `fork_branch()`, `load_branch()`, `diff_genome()` | guardian.py, backend |
| `lib/guardian_conciencia.py` (562 lines) | Conciencia N1 (percibir/decidir/reflexionar) + N2 (meta-evolución) + percentiles | `consciousness_cycle()`, `meta_evolution()`, `score_context()`, `consciousness_action()` | guardian.py, backend |
| `lib/guardian_memory.py` (476 lines) | TF-IDF memory: create/read/update/delete landmarks, decision patterns, learnings | `memory_create()`, `memory_search()`, `memory_decide()`, `_compute_tfidf_index()`, `_embed_text()` | guardian.py, rag, conciencia |
| `lib/guardian_rag.py` (523 lines) | RAG pipeline: collect chunks from 5 sources, TF-IDF rerank, context assembly | `_collect_chunks()`, `_rerank()`, `rag_query()` | guardian.py, backend, conciencia |
| `lib/guardian_absorb.py` (354 lines) | Absorb v2: scan/classify/match/ingest skills → tomes | `absorb_scan()`, `absorb_classify()`, `absorb_match()`, `absorb_ingest()` | guardian.py, backend |
| `lib/guardian_evolution.py` (365 lines) | Evolution + consolidation: evolve thresholds, GC memory, reindex RAG | `evolve()`, `consolidate()` | guardian.py, backend |
| `lib/guardian_mcp.py` (562 lines) | MCP JSON-RPC server over stdio: 17 tools (read/write/run, RAG, conciencia, mode, forja, etc.) | `MCPServer` class, `handle_request()` | OpenCode MCP agent |
| `lib/guardian_backend.py` (609 lines) | HTTP server on :9787: 32 REST endpoints, health/metrics/genome/branch/conciencia/rag/absorb/docs/mcp/forja | `BackendHandler` class, `run_server()` | guardian.py (start/stop), plugin (health check) |
| `lib/guardian_web.py` (78 lines) | Dashboard web UI on :7878 (Flask-like mini server) | `run_web()` | guardian.py |
| `lib/guardian_forja.py` (1125 lines) | La Forja: meta-módulo del arquitecto — scaffold, edit, validate, impact, doctor, index, graph, diff, patch | `scan_index()`, `module_new()`, `validate_module()`, `doctor_check()`, `impact_analysis()`, `edit_file()`, `delete_module()`, `run_direct()`, `cmd_endpoint()`, `cmd_mcp_tool()`, `function_add()`, `graph_deps()`, `diff_snapshot()`, `patch_file()` | guardian.py (subprocess), backend, mcp |

### Layer 0 — Config & Bootstrap

| File | Job |
|------|-----|
| `install.sh` | One-shot install: create dirs, copy genome, set up guardian CLI symlink |
| `SKILL.md` | Guardian's own identity as an OpenCode skill |

---

## Critical Data Paths

### Path 1: CLI command → execution
```
guardian <subcommand> [args]
  → guardian.py dispatch()
    → check project config (shared.read_config)
    → route to handler in same file or guardián_*.py
    → return string
```

### Path 2: Plugin tool call → execution
```
OpenCode tool call
  → guardian.ts tool.execute()
    → exec(`guardian <args>`)
      → guardian.py dispatch()
        → handler
      ← stdout
    ← parse/return
```

### Path 3: Permission check
```
permission.ask hook
  → guardian.ts matchModule(path) → module guard level
    → if conciencia level: checkPermission(slug, path, op)
      → POST /permission/check to backend (guardian_backend.py)
        → guardian_conciencia.score_context()
        → guardian_conciencia.consciousness_action()
      ← allowed + action
    ← cached 5min
  → allow/deny
```

### Path 4: Backend HTTP API → handler
```
curl :9787/<endpoint>
  → BackendHandler.do_GET/do_POST
    → parse slug + params
    → call guardian_*.py function
    → JSON response
```

---

## Change Impact Matrix

When adding or modifying a feature, here's what you MUST touch:

### 🔧 New CLI command
| What | Where |
|------|-------|
| Parse args | `guardian.py` — add to `dispatch()` and `HELP` constant |
| Handler logic | `guardian.py` OR new `lib/guardian_*.py` if complex |
| Shared helpers | `guardian_shared.py` if needed across modules |
| Docs | `docs/REFERENCIA.md` — add to CLI table |
| Plugin tool | `guardian.ts` — optional, if exposing to OpenCode |
| Backend endpoint | `guardian_backend.py` — optional, if exposing via REST |

### 🔧 New backend endpoint (REST API)
| What | Where |
|------|-------|
| Route handler | `guardian_backend.py` — add `do_GET`/`do_POST` branch |
| Business logic | existing `guardian_*.py` or new lib |
| Docs | `docs/REFERENCIA.md` — add to API tables |
| Plugin tool | `guardian.ts` — optional, if auto-calling this endpoint |
| CLI command | `guardian.py` — optional, if exposing via CLI |

### 🔧 New MCP tool
| What | Where |
|------|-------|
| Tool def | `guardian_mcp.py` — add to `MCPServer.tool_handlers` |
| Logic | `guardian_*.py` — delegate to existing lib |
| Plugin mirror | `guardian.ts` — add `tool.xxx` entry |
| Backend proxy | `guardian_backend.py` — add route to `/mcp/call` dispatch |
| Docs | `docs/REFERENCIA.md` — add to MCP table |

### 🔧 New module guard level
| What | Where |
|------|-------|
| Module rule | `guardian.ts` — add to `MODULES` array |
| Path matching | `guardian.ts` — add to `matchModule()` |
| Permission logic | `guardian.ts` — guard already handles blocked/readonly/conciencia/allowed |

### 🔧 New consciousness factor
| What | Where |
|------|-------|
| Factor score | `guardian_conciencia.py` — add to `score_context()` |
| Weight config | `genome/identity.yaml` or conciencia thresholds |
| Meta-evolution | `guardian_conciencia.py` — N2 may auto-adjust |

### 🔧 New RAG source
| What | Where |
|------|-------|
| Collector | `guardian_rag.py` — add `_collect_chunks_<source>()` |
| Source filter | `guardian_rag.py` OR `guardian_backend.py` — add to mode-based filter set |
| Re-index | `guardian_evolution.py` — add to `consolidate()` |

### 🔧 New lifecycle hook (pre/post change/deploy)
| What | Where |
|------|-------|
| Hook handler | `guardian.py` — add to `HOOKS` list, implement `cmd_<hook>()` |
| Snapshot logic | `guardian.py` — `_snapshot()` if pre-change |
| Auto-mode | same — wire into `--auto` flow |

---

## Dependency Graph

```
guardian.py
├── guardian_shared.py        (i18n, file ops, config)
├── guardian_genome.py        (genome + branches)
├── guardian_evolution.py     (evolve + consolidate)
├── guardian_memory.py (CLI)  (memory subcommand only)
├── guardian_absorb.py (CLI)  (absorb subcommand only)
├── guardian_rag.py (CLI)     (rag subcommand only)
└── (subprocess) guardian_memory.py / absorb / rag / web / backend

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
└── guardian_memory.py (imported inline for TF-IDF)

guardian_absorb.py
└── guardian_shared.py

guardian_evolution.py
├── guardian_shared.py
├── guardian_genome.py
├── guardian_rag.py
└── guardian_memory.py
```

---

## Key Conventions

### Naming
- `cmd_<name>()` in `guardian.py` = handler for `<name>` subcommand
- `absorb_<action>()` in `guardian_absorb.py` = absorb action
- `_private()` = internal helper, not CLI-facing

### Config
- Project config: `MEMORY_DIR/<slug>/config.yaml`
- Schema: `{stack, created, updated, memory, skills, docs, backend, ...}`
- Read via `shared.read_config(slug)`, write via `shared.write_config(slug, data)`

### i18n
- All user-facing strings go through `shared._(string)` which does ES→EN lookup
- ES strings in code → `ES_EN_DICT` in `guardian_shared.py`
- Core strings in `_STRINGS` dict by language

### Branch/Persistence
- ONE branch per machine (sha256 of hostname)
- Projects are sub-contexts within that branch
- Branch path: `BRANCHES_DIR / _branch_hash() /`
- Projects: `<branch>/projects/<slug>/`

### Mode
- `plan` = read-only, research, ask questions
- `build` = write allowed, implement
- Stored in config, switched via `mode` command, `guardian_mode` tool, or auto-detected from prompt keywords

---

## Quick Reference: Where Things Live

```
/srv/guardian/                    ← Guardian home (genome)
/var/guardian/                    ← Guardian data (branches, projects, logs)
/var/guardian/genome/branches/    ← Branch data per machine
/var/guardian/projects/<slug>/    ← Project config + memory + skills
/var/guardian/skills-global.json  ← Global skill registry

/opt/nexxoria-guardian/           ← Code home
├── guardian                      ← CLI entry (shell wrapper)
├── lib/guardian.py               ← CLI dispatcher
├── lib/guardian_shared.py        ← Shared helpers + i18n
├── lib/guardian_genome.py        ← Genome + branches
├── lib/guardian_conciencia.py    ← Consciousness N1 + N2
├── lib/guardian_memory.py        ← TF-IDF memory
├── lib/guardian_rag.py           ← RAG pipeline
├── lib/guardian_absorb.py        ← Skill absorb
├── lib/guardian_evolution.py     ← Evolution + consolidation
├── lib/guardian_mcp.py           ← MCP server (stdio)
├── lib/guardian_backend.py       ← HTTP backend (:9787)
├── lib/guardian_web.py           ← Dashboard (:7878)
├── lib/guardian_forja.py         ← La Forja (meta-módulo)
├── docs/                         ← Documentation
├── templates/                    ← Doc templates
├── prompts/                      ← Workflow prompts
└── .opencode/plugins/guardian.ts ← OpenCode plugin
```
