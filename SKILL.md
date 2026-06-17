---
name: nexxoria-guardian
description: Universal project guardian for OpenCode AI sessions — v4 orgánico. Auto-detects projects, genome, conciencia (2 niveles), plan/build modes, skills como tomos de conocimiento, RAG unificado, backend persistente y MCP con codegraph AST + advisor + observer.
license: MIT
compatibility: opencode >= 1.17
metadata:
  audience: developers
  workflow: coding
---

# Nexxoria Guardian v4 — Ser Orgánico

Guardian v4 es un ser orgánico: cerebro (LLM + conciencia + meta-conciencia + RAG), ojos (contexto + codegraph), manos (CLI + hooks + git), piernas (backend :9787 + scheduler) y nanos (MCP tools).

## Triggers

- Iniciar sesión en un proyecto
- Usuario pide un cambio de código
- Usuario menciona `guardian`, `proyecto`, `project`
- Usuario ejecuta `@guardian <subcomando>`
- Antes/después de cambios o deploys
- Arranque del backend persistente

## Regla 0: Contexto primero

Antes de cualquier acción, cargar contexto del proyecto.

- Inicio de sesión: `guardian context --brief`
- Antes de cambios: `guardian context --scope <path>`
- Si hay duda: `guardian context --check`
- Si no hay cambios nuevos: no re-inyectar contexto

## Modos de operación

| Modo | Objetivo | Escritura | Conciencia |
|------|----------|-----------|------------|
| Plan | Investigar, diseñar | Solo lectura | Percibe + Reflexiona (fuerte) |
| Build | Implementar, codificar | Lectura + escritura | Decide + Acciona (fuerte) |

- Auto-detección: "¿qué pasaría si...?" → Plan. "Hacé esto" → Build.
- Cambiar con: `guardian mode plan|build` o `curl -X POST :9787/mode`

## Arquitectura

```
lib/
├── guardian.py                    ← CLI principal (60+ comandos)
├── guardian_shared.py             ← Helpers compartidos, paths, i18n
├── guardian_genome.py             ← Genoma + ramas (3 archivos YAML)
├── guardian_conciencia.py         ← Conciencia N1+N2 con Advisor integration
├── guardian_brain.py              ← Cognitive memory: Governor, Reflection Agent
├── guardian_brain_schema.py       ← SQLite schema: 4 niveles + codegraph + logs
├── guardian_brain_symbols.py      ← CodeGraph: tree-sitter AST indexer, lookup, query_smart
├── guardian_brain_advisor.py      ← Contexto dinámico: build_context, advise_on_action
├── guardian_observer.py           ← Captura de eventos, sanitización, clasificación
├── guardian_brain_migration.py    ← Migración v2→v3 (brain memory)
├── guardian_migration_v3_layout.py← Migración v3→v4 layout
├── guardian_evolution.py          ← Evolve + consolidate
├── guardian_memory.py             ← Memoria JSONL + TF-IDF
├── guardian_rag.py                ← RAG unificado (docs + tomes + código + memoria)
├── guardian_absorb.py             ← Skills: scan/match/classify/ingest
├── guardian_knowledge.py          ← Knowledge packs: research/refresh/scrape
├── guardian_specialization.py     ← Stack-aware specializations
├── guardian_plan.py               ← OpenSpec + planes ad-hoc
├── guardian_maintain.py           ← Drift + health
├── guardian_global.py             ← Contexto global cross-project
├── guardian_capability.py         ← Model card + routing
├── guardian_publish.py            ← Publish/clone/fork
├── guardian_lineage.py            ← Genealogía de proyectos
├── guardian_forja.py              ← Meta-módulo del arquitecto
├── guardian_backend.py            ← HTTP :9787 (35+ endpoints)
├── guardian_mcp.py                ← MCP server (40+ tools stdio)
└── guardian_web.py                ← Dashboard web :7878
```

## Conocimiento

- **Skills** → absorb → **tomos de conocimiento** (markdown + YAML metadata)
- **Documentación** → docs scan → auto-chunk → **RAG**
- **RAG unificado**: docs + skills(tomos) + código + memoria + decisiones
- RAG se adapta por modo: plan → docs + knowledge; build → code + memory + docs + knowledge

## Backend persistente

```bash
guardian backend start           # Inicia daemon en :9787
guardian backend status          # Ver estado
guardian backend stop            # Detener

curl :9787/health                # Health check
curl :9787/conciencia/cycle      # POST — ciclo N1
curl :9787/rag?q=consulta&slug=x # GET — RAG query
curl :9787/genome                # GET — genoma
curl :9787/evolve                # POST — evolución
curl :9787/codegraph/query       # GET — query_smart
```

## CLI commands

```
Proyecto:   detect, status, check, report, setup, activate
Cambios:    protect, snapshot, diff, rollback, hooks
AI:         context, rag, mode, conciencia, knowledge, propose
CodeGraph:  codegraph index|query|status
Migración:  migrate status|migrate|rollback
Sistemas:   mode, backend, conciencia, genome, branch, update, evolve, consolidate
GitHub:     pr, issue, projects
Stack:      build, dev, test, lint, typecheck, deploy, logs
Meta:       forja, memory, absorb, web, docs, permission
```

## MCP tools (40+)

- `read_file`, `write_file`, `run_command`
- `rag_query`, `conciencia_cycle`, `mode_switch`
- `knowledge_search`, `genome_status`, `branch_fork`
- `query_smart`, `codegraph_index`, `codegraph_status`
- `forja_*` (scaffold, validate, index, list, doctor, run, endpoint, mcp-tool, function, diff, graph, patch)

## Hooks (8 v4)

- **`permission.ask`** — intercepta writes/bash en módulos protegidos
- **`session.created`** — inyecta contexto dinámico del Advisor
- **`chat.message`** — log de prompts vía Observer
- **`tool.execute.before`** — Advisor advierte si una acción es riesgosa
- **`tool.execute.after`** — Observer enruta el evento post-ejecución
- **`tui.prompt.append`** — auto-detecta modo plan/build por keywords
- **`experimental.session.compacting`** — re-inyecta contexto antes de compactación
- **`shell.env`** — setea GUARDIAN_HOME y GUARDIAN_DATA

## Tests

```bash
python3 -m pytest tests/ -v
# ~260 tests passing
```

## Licencia

MIT
