---
name: nexxoria-guardian
description: Universal project guardian for OpenCode AI sessions — v3 con memoria cognitiva. Auto-detects projects, genoma, conciencia (2 niveles), 5 modos (read/plan/build/commit/review), brain persistente con Governor y Reflection Agent, specializations stack-aware, OpenSpec + planes ad-hoc, publish/clone/fork, MCP.
license: MIT
compatibility: opencode >= 1.17
metadata:
  audience: developers
  workflow: coding
---

# Nexxoria Guardian v3 — Ser Cognitivo

Guardian v3 es un ser orgánico con **memoria cognitiva persistente**: cerebro con 5 niveles (WM + 4 project + 3 global), ojos (RAG + specializations), manos (CLI + hooks + git), piernas (backend :9787) y nanos (35 MCP tools).

## Triggers

- Iniciar sesión en un proyecto
- Usuario pide un cambio de código
- Usuario menciona `guardian`, `proyecto`, `project`, `cerebro`
- Usuario ejecuta `@guardian <subcomando>`
- Antes/después de cambios o deploys
- Cuando se necesite contexto histórico del proyecto

## Regla 0: GUARDIAN.md primero

Antes de cualquier acción, leer el cerebro esencial.

```bash
# Working memory — siempre cargada
guardian brain read                  # devuelve GUARDIAN.md

# Si hay duda, consultar memoria profunda
guardian brain query semantic "tema"  # búsqueda vectorial
guardian brain query episodic "recientes"
```

GUARDIAN.md ≤200 líneas, regenerado al cerrar sesión.

## 5 modos de operación

| Modo | Lectura | Escritura | Uso típico |
|---|---|---|---|
| `read` | ✓ | ✗ | Explorar sin tocar |
| `plan` | ✓ | ✗ | Diseñar, proponer |
| `build` | ✓ | ✓ | Implementar |
| `commit` | ✓ | ✓ | Versionar cambios |
| `review` | ✓ | ✗ | Auditar, verificar |

Cambiar con: `guardian mode <nombre>` o `curl -X POST :9787/mode`

## Ciclo de sesión v3

```
1. session start
   → carga GUARDIAN.md (working memory)
   → activa mode
   → conciencia N1 percibe

2. trabajo
   → brain query cuando hay duda
   → brain write (Governor valida importance/TTL/dup)

3. session end
   → Reflection Agent corre
   → extrae lecciones de episodios recientes
   → actualiza PM (procedural) y RM (reflection)
   → regenera GUARDIAN.md
   → handoff a próxima sesión
```

## Arquitectura v3

```
lib/
├── guardian_brain_schema.py    ← 4 DBs proyecto + 3 DBs globales
├── guardian_brain.py           ← Storage + Governor + Orchestrator + Reflection
├── guardian_knowledge.py       ← research/refresh/scrape con TTL
├── guardian_specialization.py  ← 5 stack-aware specializations
├── guardian_plan.py            ← OpenSpec + ad-hoc state machine
├── guardian_maintain.py        ← drift detection + health
├── guardian_global.py          ← cross-project memory
├── guardian_capability.py      ← model card + EMA routing
├── guardian_publish.py         ← sanitización + clone/fork
├── guardian_lineage.py         ← genealogía
├── guardian_brain_migration.py ← v2 → v3
├── guardian_conciencia.py      ← N1 + N2 con brain context
├── guardian_genome.py          ← identidad + ramas
├── guardian_rag.py             ← RAG unificado
├── guardian_shared.py          ← helpers
├── guardian.py                 ← CLI (50+ comandos)
├── guardian_backend.py         ← HTTP :9787 (35+ endpoints)
└── guardian_mcp.py             ← 35 tools stdio

data/projects/<slug>/
├── config.yaml
├── brain/
│   ├── semantic.db
│   ├── episodic.db
│   ├── procedural.db
│   └── reflection.db
├── GUARDIAN.md                  ← working memory
├── audit.json
└── ...

data/global/
├── semantic.db                  ← cross-project
├── procedural.db
└── reflection.db
```

## 5 niveles de memoria

| Nivel | DB | Tipo | TTL | Uso |
|---|---|---|---|---|
| WM | GUARDIAN.md | Texto | regenerado | always-loaded |
| SM | semantic.db | Hechos | 365d | Conocimiento estable |
| EM | episodic.db | Eventos | 90d | Historia con timestamp |
| PM | procedural.db | Cómo | 180d | Workflows, patterns |
| RM | reflection.db | Lecciones | 365d | Aprendizajes |
| SM-G | global/semantic.db | Stack patterns | 365d | Cross-project |
| PM-G | global/procedural.db | Workflows | 180d | Reusables |
| RM-G | global/reflection.db | Lecciones | 365d | Universales |

## Governor — reglas de olvido

Toda escritura pasa por Governor:
1. **Importance** < 0.3 → rechazado
2. **Duplicate** (hash near-match) → merge o reject
3. **TTL** expirado → archive + compress
4. **Contradiction** → mark stale, prompt reflexión

## Conciencia — 2 niveles

### N1 (cada sesión)
```
PERCIBIR: GUARDIAN.md + brain query + mode + contexto
DECIDIR:  percentiles de certeza
  > 80%  → ASSUME
  50-80% → ASK_LITTLE
  20-50% → ASK_MUCH
  < 20%  → INVESTIGA
REFLEXIONAR: brain write si importancia > 0.6
```

### N2 (periódica, post-sesión)
```
OBSERVA: ¿funcionó el routing? ¿se olvidó knowledge stale?
EVOLUCIONA: ajusta umbrales, prune brain, promote lessons a global
```

## Specializations (built-in v3)

Activan tomos de conocimiento stack-aware:

```bash
guardian specialization enable odoo      # arquitectura + ORM + views + módulos
guardian specialization enable nextjs    # app router + RSC + server actions
guardian specialization enable fastapi   # async + deps + middleware
guardian specialization enable postgres  # queries + migrations + indexes
guardian specialization enable python    # type hints + asyncio + testing
```

## Backend persistente

```bash
guardian backend start           # :9787
guardian backend status
guardian backend stop
```

Endpoints v3 clave:
```
GET  /brain/status?slug=X           # estado del cerebro
GET  /brain/guardian?slug=X         # GUARDIAN.md
POST /brain/write                   # escribir nodo
GET  /brain/query?slug=X&level=semantic&q=...
POST /brain/reflect                 # disparar reflection
POST /session/start|continue|end
POST /knowledge/research?slug=X&query=...
POST /specializations/enable
POST /publish                       # publicar como template
POST /migrate                       # v2 → v3
GET  /capability/status
```

## CLI commands v3

```
Sesión:    session start|continue|end
Brain:     brain read|write|query|reflect|regenerate-guardian|auto-compact
Knowledge: knowledge research|refresh|scrape|status
Spec:      specialization enable|disable|list
Plan:      plan new|list|status|transition
Maintain:  maintain
Global:    global status|promote|classify
Capability: capability status|routing|measure
Publish:   publish|clone|fork|migrate
Mode:      mode read|plan|build|commit|review
Core v2:   activate|conciencia|context|rag|genome|branch|...
```

## MCP tools (35 totales)

- v2 core: `read_file`, `write_file`, `run_command`, `rag_query`, `conciencia_cycle`, `mode_switch`, `knowledge_search`, `genome_status`, `branch_fork`, `activate_guardian`
- Forja: `forja_doctor`, `forja_validate`, `forja_index`, `forja_list`, `forja_scaffold`, `forja_run`, `forja_endpoint`, `forja_mcp_tool`, `forja_function`, `forja_diff`, `forja_graph`, `forja_patch`
- v3 brain: `brain_read`, `brain_query`, `brain_write`, `brain_reflect`, `session_end`
- v3 features: `knowledge_research`, `specialization_enable`, `maintain`, `publish`, `clone`, `capability_status`, `capability_routing`, `compact_now`

## Hooks v3

- `pre-change`: snapshot, brain query contextual
- `post-change`: brain write si vale la pena, tests, lint
- `pre-session`: brain read + conciencia
- `post-session`: brain reflect + regenerate GUARDIAN.md
- `pre-deploy`: maintain + capability check
- `post-deploy`: brain write lessons learned

## Tests

```bash
python3 -m pytest tests/ -v
# 223/223 passing (53 Fase1+2 + 22 Fase3 + 28 Fase4 + 120 base v2)
```

## Notas

- **Zero deps** — stdlib only, sin requests, numpy, tiktoken
- **Embeddings = hashing 256-dim** — calidad menor pero predecible
- **4 project DBs + 3 global DBs** — jerárquico, no plano
- **GUARDIAN.md ≤200 líneas** — límite duro
- **publish sanitiza** — regex secrets + manifest log
- **install.sh tiene safety check** — nunca borra su propio dir

## Licencia

MIT
