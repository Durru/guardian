# Plan de Integración Completa — Guardian v2

> Basado en PLAN.md. Auditoría: 70% del v2 no está implementado.

## Resumen del gap

| Categoría | Estado |
|-----------|--------|
| `guardian_genome.py` | No existe |
| `guardian_conciencia.py` | No existe (lógica dispersa en backend) |
| `guardian_evolution.py` | No existe |
| `guardian_mcp.py` | No existe |
| `genome/identity.yaml` | No existe |
| `genome/branches/` | No existe en disco |
| Endpoints backend | 11/28 implementados |
| CLI commands nuevos | 3/8 implementados |
| SKILL.md | v1 desactualizada |
| Tests backend | 0 |

## Fases de implementación

### Fase 1 — Genoma + Ramas (`guardian_genome.py`)

- `Genoma` class: carga identity.yaml, hash por contenido, validación
- `Rama` class: fork de genoma, state.json, memory/knowledge/learnings
- `cmd_genome`: status, diff
- `cmd_branch`: status, diff, fork, list
- CLI wired: `guardian genome status`, `guardian branch list|fork|status`
- Backend endpoints: `GET /genome`, `GET /branch`, `POST /branch/fork`

### Fase 2 — Conciencia pura (`guardian_conciencia.py`)

- Extraer lógica de `guardian_backend.py` a módulo propio
- `Conciencia` class: ciclo N1 (percibir→decidir→reflexionar)
- `MetaConciencia` class: N2 (observa→calibra→evoluciona)
- CLI wired: `guardian conciencia cycle|status|history|meta` (ya existe, refactor)
- Backend endpoints ya existen, refactor para usar el módulo

### Fase 3 — Evolución (`guardian_evolution.py`)

- `EvolutionEngine`: consolida memoria, dispara meta-conciencia, escribe learnings
- `consolidate`: limpia memoria vencida, re-indexa RAG, compacta learnings
- CLI wired: `guardian evolve`, `guardian consolidate`
- Backend endpoints: `POST /evolve`, `POST /consolidate`

### Fase 4 — MCP Server (`guardian_mcp.py`)

- JSON-RPC 2.0 sobre stdio (formato MCP estándar)
- Tools: `read_file`, `write_file`, `run_command`, `rag_query`, `conciencia_cycle`, `mode_switch`, `knowledge_search`, `docs_scan`
- Backend endpoints: `GET /mcp/tools`, `POST /mcp/call`
- Integración: el agente OpenCode puede llamar tools MCP

### Fase 5 — Completar backend API

Endpoints faltantes:
- `GET /metrics` — estadísticas de salud
- `GET /genome` — identidad actual
- `GET /branch` — listar ramas, ver rama actual
- `POST /branch/fork` — crear nueva rama
- `POST /evolve` — disparar evolución
- `POST /consolidate` — consolidar memoria
- `GET /knowledge/tomes` — listar tomos
- `GET /knowledge/search?q=` — buscar en tomos

### Fase 6 — Completar CLI

- `guardian genome status|diff`
- `guardian branch list|fork|status|diff`
- `guardian evolve`
- `guardian consolidate`

### Fase 7 — SKILL.md + Tests + Integración

- Actualizar SKILL.md con v2 completo
- `tests/test_genome.py`
- `tests/test_conciencia.py`
- `tests/test_evolution.py`
- `tests/test_backend.py` (endpoints)
- Test end-to-end: ciclo completo conciencia → RAG → meta-evolución
- Verificar que todo pasa

## Orden de implementación

```
Fase 1 → Fase 2 → Fase 3 → Fase 5 → Fase 6 → Fase 4 → Fase 7
         \         /
          └─── Fase 5 y 6 pueden ir en paralelo
```

## Principios

- Sin ORM, sin Docker, stdlib only (PyYAML opcional)
- YAML para genoma, JSON para estado
- Todo sincronizado: CLI, backend HTTP y MCP comparten el mismo `guardian_shared.py`
- Las 4 ramas del ser (brain, eyes, hands, legs) se conectan via API y shared state
