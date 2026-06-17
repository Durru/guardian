# Plan V3 — Memoria Cognitiva

## Contexto

Guardian v2 funcionaba como "wrapper de scripts": RAG + conciencia por sesión + docs scan. Era stateless entre proyectos y obligaba al LLM a re-leer todo en cada sesión.

V3 introduce **memoria cognitiva persistente** estructurada como un cerebro digital:
- 4 memorias por proyecto (semántica, episódica, procedural, reflexiva)
- 3 memorias globales (entre proyectos)
- GUARDIAN.md ≤200 líneas cargado en cada sesión
- Governor con forget/importance/TTL/duplicate-detection
- Reflection Agent post-sesión
- OpenSpec + planes ad-hoc
- Specializations stack-aware
- Publish/clone/fork para distribuir conocimiento

## Fases

### Fase 1 — Storage + Governor (5 días)
- `lib/guardian_brain_schema.py` (SQLite + path helpers)
- `lib/guardian_brain.py` (storage CRUD + Governor con 4 reglas de olvido)
- Tests: 53

### Fase 2 — Orchestrator + Reflection + GUARDIAN.md (5 días)
- `lib/guardian_brain.py` (orchestrator, reflection, GUARDIAN.md, working memory, handoff, auto-compact, lifecycle, global)
- Tests: 53 (Fase 1) + 0 nuevos (cubierto por test_brain.py)

### Fase 3 — Knowledge + Specialization + Plan + Maintain (5 días)
- `lib/guardian_knowledge.py` (research/refresh/scrape con TTL)
- `lib/guardian_specialization.py` (5 built-ins)
- `lib/guardian_plan.py` (OpenSpec state machine)
- `lib/guardian_maintain.py` (drift detection)
- Tests: 22

### Fase 4 — Global + Capability + Publish + Lineage + Migration (4 días)
- `lib/guardian_global.py` (cross-project scoring)
- `lib/guardian_capability.py` (model card con EMA)
- `lib/guardian_publish.py` (sanitización + secret detection)
- `lib/guardian_lineage.py` (genealogía)
- `lib/guardian_brain_migration.py` (v2→v3)
- Tests: 28

### Fase 5 — Distribución (3 días)
- `install.sh` v3 con safety check (nunca borrar dir del script)
- `pyproject.toml` con zero deps
- CI matrix Python 3.9-3.13
- `docs/PLAN_V3.md`, `docs/CONCEPTOS.md`, `README.md`, `SKILL.md` v3
- Tag `v3.0.0` + push

## Stack

- **Lenguaje:** Python 3.9+ (zero deps externos)
- **Storage:** SQLite (4 DBs por proyecto + 3 globales)
- **Embeddings:** Hashing MD5-based, 256-dim (zero deps)
- **Tests:** pytest
- **Lint:** ruff
- **Packaging:** pyproject.toml + install.sh
- **Distribución:** git tag + GitHub release

## Métricas de éxito

- 223/223 tests passing
- <50ms latencia para brain_query
- <5s startup del backend
- GUARDIAN.md ≤200 líneas (límite duro)
- Importancia >0.5 promedio de nodos en reflection
- 0 secretos filtrados en publish (regex tested)

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Embeddings de baja calidad | GUARDIAN.md always-loaded compensa |
| Acoplamiento cross-project | Líneas de proyecto via global DBs, no pointer |
| Migration corrupta v2→v3 | Dry-run + backup en `*.v2.bak` |
| Publish filtra secretos | Sanitización regex + manifest log |
| install.sh borra su propio dir | Safety check en v3 |
| Drift silencioso | Weekly maintain cron + alerts |

## Decisiones tomadas

- **Zero deps** — stdlib only, sin requests, sin numpy, sin tiktoken
- **Hashing embeddings** — calidad menor pero predecible, sin ML
- **4 niveles por proyecto** — semántica/episódica/procedural/reflexiva (no 3 ni 5)
- **OpenSpec + ad-hoc** — no solo OpenSpec (flexibilidad)
- **CLI + Backend + MCP** — tres superficies, mismo backend
- **Specializations built-in** — 5 stacks, no user-defined (v3.1)
- **Capability routing** — EMA α=0.1, decisión binaria delegar/no

## Próximos pasos (v3.1+)

- Specializations user-defined (YAML)
- Cross-project lineage visualization
- LLM-based embeddings (sentence-transformers, opcional)
- Web UI para GUARDIAN.md editor
- Multi-tenant con auth
- Vector index con HNSW (cuando deps sean OK)
