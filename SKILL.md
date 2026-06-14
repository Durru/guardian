---
name: nexxoria-guardian
description: Universal project guardian for OpenCode AI sessions — v2 orgánico. Auto-detects projects, genome, conciencia (2 niveles), plan/build modes, skills como tomos de conocimiento, RAG unificado, backend persistente, y MCP.
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: coding
---

# Nexxoria Guardian v2 — Ser Orgánico

Guardian v2 es un ser orgánico: cerebro (LLM + conciencia + meta-conciencia + RAG), ojos (contexto), manos (CLI + hooks + git), piernas (backend :9787 + scheduler) y nanos (MCP tools).

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

```text
/srv/guardian/
├── SKILL.md
├── PLAN.md / PLAN-INTEGRACION.md
├── genome/identity.yaml          ← ADN inmutable (solo creador)
├── lib/
│   ├── guardian.py                ← CLI principal
│   ├── guardian_shared.py         ← Helpers compartidos
│   ├── guardian_memory.py         ← Memoria TF-IDF
│   ├── guardian_rag.py            ← RAG pipeline (docs + skills + código + memoria)
│   ├── guardian_absorb.py         ← Absorb v2 (skills → tomos → RAG)
│   ├── guardian_web.py            ← Dashboard web (:7878)
│   ├── guardian_backend.py        ← Backend persistente HTTP (:9787)
│   ├── guardian_genome.py         ← Genoma + ramas
│   ├── guardian_conciencia.py     ← Conciencia N1 + N2 (meta-evolución)
│   ├── guardian_evolution.py      ← Evolución + consolidación
│   └── guardian_mcp.py            ← Servidor MCP (stdio)
├── prompts/                       ← 5 templates de workflow
├── templates/                     ← Doc templates
└── tests/

/var/guardian/
├── genome/branches/<hash>/        ← Ramas de usuarios
│   ├── identity.yaml
│   ├── state.json
│   ├── memory/
│   ├── knowledge/tomes/
│   └── learnings/
├── projects/<slug>/               ← Proyectos
├── skills-global.json
└── guardian-backend.pid / .log
```

## Conciencia — 2 niveles

### Nivel 1 (operativo — cada sesión)

```
PERCIBIR: contexto, modo, RAG, errores, experiencia previa
DECIDIR:  percentiles de certeza
  > 80%  → ASSUME (actúa sin preguntar)
  50-80% → ASK_LITTLE ("¿Confirmo?")
  20-50% → ASK_MUCH ("¿A, B o C?")
  < 20%  → INVESTIGA (pide más contexto)
REFLEXIONAR: guardar aprendizaje, indexar RAG
```

### Nivel 2 (meta-evolución — periódica)

```
OBSERVA: calibró bien? preguntó cuando debía asumir?
EVOLUCIONA: ajusta umbrales, propone mutaciones, re-indexa
REGISTRA: nueva configuración, aprendizaje permanente
```

## Conocimiento

- **Skills** → absorb → **tomos de conocimiento** (markdown + YAML metadata)
- **Documentación** → docs scan → auto-chunk → **RAG**
- **RAG unificado**: docs + skills(tomos) + memoria + código + decisiones
- RAG se adapta por modo: plan → docs + knowledge; build → code + memory + docs + knowledge

## Backend persistente

```bash
guardian backend start           # Inicia daemon en :9787
guardian backend status          # Ver estado
guardian backend stop            # Detener

curl :9787/health                # Health check
curl :9787/conciencia/cycle      # POST — ciclo
curl :9787/rag?q=consulta&slug=x # GET — RAG query
curl :9787/genome                # GET — genoma
curl :9787/evolve                # POST — evolución
```

## CLI commands

```
Proyecto:   detect, status, check, report, setup
Cambios:    protect, snapshot, diff, rollback, hooks
AI:         context, rag, mode, conciencia, conocimiento
Docs:       docs scan, docs route
Sistemas:   mode, backend, conciencia, knowledge, memory, absorb,
            genome, branch, evolve, consolidate
GitHub:     pr, issue, projects
Stack:      build, dev, test, lint, typecheck, deploy, logs
```

## MCP tools (disponibles via stdio o HTTP)

- `read_file`, `write_file` (respeta modo build)
- `run_command`, `rag_query`, `conciencia_cycle`
- `mode_switch`, `knowledge_search`
- `genome_status`, `branch_fork`

## Hooks

- `pre-change`: snapshot, paths protegidos
- `post-change`: diff, tests, lint, memoria, auditoría
- `pre-deploy`: build check
- `post-deploy`: smoke test, auditoría, memoria

## Memoria

| Tipo | TTL | Uso |
|------|-----|-----|
| `landmark` | 90d | Hallazgos críticos |
| `decision` | 30d | Decisiones de diseño |
| `pattern` | 14d | Convenciones de código |
| `note` | 30d | Notas libres |
| `analysis` | 7d | Hallazgos de impacto |
| `session` | 7d | Marcadores de sesión |

## Notas

- Sin ORM, sin Docker, solo stdlib (+ PyYAML opcional)
- YAML para genoma, JSON para estado
- Todo sincronizado: CLI, backend HTTP y MCP comparten guardian_shared.py
- Las ramas del ser (brain, eyes, hands, legs, nanos) se conectan via API
