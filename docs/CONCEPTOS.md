# Guardian v2 — Conceptos

## Filosofía

Guardian es un **ser orgánico**. No es una herramienta que se ejecuta — es un ente que vive, percibe, decide, aprende y evoluciona. Tiene ADN, cerebro, ojos, manos, piernas y nanos.

```
┌──────────────────────────────────────────────────────────┐
│                     GUARDIAN                              │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │  CEREBRO                                            │  │
│  │  LLM + Conciencia + Meta-conciencia + RAG           │  │
│  │  Ciclo: percibir→decidir→reflexionar→evolucionar    │  │
│  │  Percentiles: ¿pregunto? ¿asumo? ¿investigo?        │  │
│  └────────────────────┬───────────────────────────────┘  │
│                       │                                  │
│  ┌────────────────────┼────────────────────┐             │
│  ▼                    ▼                    ▼             │
│ ┌──────────┐   ┌──────────┐   ┌──────────────────┐      │
│ │ OJOS      │   │ MANOS    │   │ PIERNAS           │      │
│ │ (Contexto │   │ (CLI +   │   │ (Backend :9787    │      │
│ │  RAG +    │   │  Hooks + │   │  + Scheduler +    │      │
│ │  Skills   │   │  Git)    │   │  API + MCP)       │      │
│ │  como     │   │          │   │                   │      │
│ │  libros)  │   │          │   │                   │      │
│ └──────────┘   └──────────┘   └──────────────────┘      │
│                       │                                  │
│                  ┌────┴────┐                             │
│                  │ NANOS   │                             │
│                  │ (MCP    │                             │
│                  │  Tools) │                             │
│                  └─────────┘                             │
└──────────────────────────────────────────────────────────┘
```

## El Ser

### Cerebro (LLM + Conciencia + Meta-conciencia + RAG)
El cerebro tiene tres capas:
- **Nivel 0 — LLM**: el modelo de lenguaje subyacente (Claude, GPT, etc.)
- **Nivel 1 — Conciencia operativa**: ciclo percibir→decidir→reflexionar que se ejecuta en cada interacción
- **Nivel 2 — Meta-conciencia**: observa el N1, calibra umbrales, evoluciona el comportamiento
- **RAG unificado**: la memoria a largo plazo que combina docs, skills (tomos), código, memoria y decisiones

### Ojos (Contexto + RAG + Skills)
El sistema de percepción. Antes de任何 acción, Guardian carga contexto del proyecto (archivos, config, memoria) y lo enriquece con búsqueda RAG. Los skills no se "activan" — se convierten en tomos de conocimiento que el RAG consulta.

### Manos (CLI + Hooks + Git)
El sistema de acción. CLI para comandos directos, hooks para automatizar pre/post cambios, git para snapshots y rollbacks.

### Piernas (Backend + Scheduler + API + MCP)
El sistema de persistencia y conectividad. Backend HTTP en :9787 que expone toda la funcionalidad como API REST. MCP server para integración con agentes. Scheduler para tareas periódicas (consolidación, meta-evolución).

### Nanos (MCP Tools)
Herramientas finas que el agente OpenCode puede invocar directamente: leer/escribir archivos, ejecutar comandos, consultar RAG, ejecutar ciclos de conciencia.

---

## Genoma — ADN

El genoma es la identidad inmutable de Guardian. Solo el creador lo modifica.

**Archivo:** `/srv/guardian/genome/identity.yaml`

Contiene:
- `version` — versión del genoma
- `creator` — quien creó este Guardian
- `identity` — nombre, propósito, principios, tono, valores
- `origin` — repositorio y lineage
- `consciousness` — umbrales default y configuración de evolución

---

## Ramas — Evolución

Cada usuario tiene su propia **rama** (branch), un fork del genoma que evoluciona con la experiencia.

**Ubicación:** `/var/guardian/genome/branches/<sha256_hash>/`

Cada rama contiene:
- `identity.yaml` — identidad del usuario (forkeada del default)
- `state.json` — estado actual de conciencia y metadatos de sesión
- `memory/` — archivos de memoria (landmarks, decisiones, patrones)
- `knowledge/tomes/` — tomos de conocimiento generados por absorb
- `learnings/` — aprendizajes de meta-evolución

---

## Conciencia — Nivel 1 (operativa)

Ciclo que se ejecuta **en cada sesión o interacción**:

```
PERCIBIR:
  - ¿Qué cambió desde la última vez?
  - ¿Qué contexto sirvió RAG?
  - ¿Qué modo estoy? (Plan / Build)
  - ¿Qué errores ocurrieron?
  - ¿Qué experiencia previa hay en la rama?

DECIDIR:
  - Calcular percentiles de certeza
  - Si > 80%  → ASUME, actúa sin preguntar
  - Si 50-80% → PREGUNTA POCO ("¿Confirmo?")
  - Si 20-50% → PREGUNTA MUCHO ("¿A, B o C?")
  - Si < 20%  → INVESTIGA, pide más contexto

REFLEXIONAR:
  - ¿Funcionó lo que decidí?
  - ¿Qué aprendo de esta interacción?
  - ¿Qué guardo en la memoria?
  - ¿Qué indexo al RAG?
```

### Factores de certeza

| Factor | Peso |
|--------|------|
| Contexto relevante servido (score RAG) | Alto (0.35) |
| Similitud con experiencias pasadas | Medio |
| Claridad del input del usuario | Medio |
| Confianza en tomos de conocimiento matcheados | Medio |
| Frescura del contexto | Bajo |
| Estabilidad del proyecto (cambios recientes, errores) | Bajo |

### Modos y bonus

El modo de operación ajusta los umbrales:
- **Modo Plan**: penaliza `assume` (-0.1) — tiende a preguntar más
- **Modo Build**: bonifica `assume` (+0.1) — tiende a actuar más

---

## Meta-conciencia — Nivel 2 (evoluciona)

Se ejecuta **automáticamente después de cada ciclo** o manualmente vía `guardian conciencia meta` o `POST /conciencia/meta`.

```
OBSERVA el nivel 1:
  - ¿Los percentiles estuvieron bien calibrados?
  - ¿Preguntó cuando debía asumir? ¿Asumió cuando debía preguntar?
  - ¿El contexto servido fue relevante?

EVOLUCIONA:
  - Ajusta umbrales de certeza según resultados históricos
  - Propone mutaciones al genoma (si corresponde)
  - Sugiere cambios en los criterios de evolución
  - Re-indexa conocimiento si es necesario

REGISTRA:
  - Nueva configuración de la conciencia
  - Decisión de evolución tomada
  - Aprendizaje permanente en la rama
```

**Condiciones para evolucionar:**
- Mínimo 5 ciclos acumulados
- Analiza los últimos 20 ciclos
- Si `assume` domina >70% → sube el umbral
- Si `investigate` domina >40% → baja el umbral
- Si `assume` está muy cerca del umbral → lo sube
- Cada ajuste es de ±0.05, clamp entre 0.0 y 1.0

---

## Modos de operación

| Aspecto | Modo Plan | Modo Build |
|---------|-----------|------------|
| Objetivo | Pensar, investigar, diseñar | Implementar, codificar, ejecutar |
| Escritura | Solo lee archivos | Lee y escribe archivos |
| Conciencia | Percibe + Reflexiona (fuerte) | Decide + Acciona (fuerte) |
| Hooks | Solo pre-change (simular) | pre + post completos |
| RAG | docs + knowledge | code + memory + docs + knowledge |
| Output | Planes, diagramas, preguntas | Código, archivos, commits |
| Percentiles | Tiende a preguntar más | Tiende a asumir más |

**Auto-detección:** si el primer mensaje es "¿qué pasaría si...?" → Plan. Si es "hacé esto" → Build.

---

## Conocimiento

El conocimiento de Guardian fluye así:

```
Skills (.skills-global.json)
       │
       ▼
Absorb scan + classify + match
       │
       ▼
cmd_ingest ───→ Tomos de conocimiento (markdown + YAML)
       │               │
       │    knowledge/tomes/     docs/
       │               │           │
       ▼               ▼           ▼
    RAG index ←─── RAG unificado ←── docs scan
       │
       ▼
   Consulta contextual (modo plan/build)
```

### Tomos de conocimiento

Cuando `absorb classify` o `absorb match` encuentran skills relevantes, `absorb ingest` los convierte en **tomos**:

```
knowledge/tomes/
├── frontend-design.md
├── database-ops.md
├── django-security.md
└── ...
```

Cada tomo es markdown con metadata YAML:
```yaml
---
name: frontend-design
description: Frontend design patterns
rating: 3
triggers: ["ui", "component", "layout"]
keywords: ["css", "react", "tailwind"]
---
```

### RAG unificado

El RAG combina 5 fuentes:
1. **documentación** (`docs/`) — generada por `docs scan`
2. **tomos de conocimiento** (`knowledge/tomes/`) — generados por `absorb ingest`
3. **código** (`project_root/`) — indexado por `rag index`
4. **memoria** (`memory/*.json`) — landmarks, decisiones, patrones
5. **aprendizajes** (`learnings/*.json`) — generados por meta-conciencia

La selección de fuentes se adapta al modo:
- **Plan:** docs + knowledge
- **Build:** code + memory + docs + knowledge

---

## Endpoints

El backend expone 19 endpoints REST:

### GET

| Endpoint | Descripción |
|----------|-------------|
| `/health` | Health check |
| `/metrics` | Estadísticas del servidor |
| `/mode?slug=` | Estado del modo actual |
| `/genome` | Identidad del genoma + lista de ramas |
| `/branch?slug=` | Info de una rama (o todas si no hay slug) |
| `/conciencia/state?slug=` | Estado de conciencia (ciclos, última acción) |
| `/conciencia/percentiles?slug=` | Umbrales actuales |
| `/rag?slug=&q=&mode=` | Búsqueda RAG |
| `/knowledge/status?slug=` | Estado del índice de conocimiento |
| `/knowledge/tomes?slug=` | Lista de tomos |
| `/knowledge/search?slug=&q=` | Búsqueda en tomos |
| `/mcp/tools` | Lista de herramientas MCP disponibles |

### POST

| Endpoint | Descripción |
|----------|-------------|
| `/mode` | Cambiar modo (plan/build) |
| `/branch/fork` | Crear rama para usuario |
| `/conciencia/cycle` | Ejecutar ciclo N1 |
| `/conciencia/meta` | Ejecutar meta-evolución N2 |
| `/evolve` | Disparar evolución de rama |
| `/consolidate` | Consolidar memoria + RAG |
| `/absorb/ingest` | Ingestar skills → tomos |
| `/absorb/scan` | Escanear skills globales |
| `/absorb/classify` | Clasificar skills del proyecto |
| `/docs/scan` | Escanear docs → RAG |
| `/mcp/call` | Ejecutar tool MCP |

---

## MCP Tools

9 herramientas disponibles via JSON-RPC 2.0 (stdio) o HTTP POST `/mcp/call`:

| Tool | Descripción |
|------|-------------|
| `read_file` | Leer archivo |
| `write_file` | Escribir archivo (solo modo build) |
| `run_command` | Ejecutar comando bash |
| `rag_query` | Consultar RAG |
| `conciencia_cycle` | Ejecutar ciclo de conciencia |
| `mode_switch` | Cambiar modo plan/build |
| `knowledge_search` | Buscar en tomos |
| `genome_status` | Ver identidad del genoma |
| `branch_fork` | Crear rama para usuario |

---

## Estructura de directorios

```
/srv/guardian/
├── genome/
│   └── identity.yaml              ← ADN inmutable
├── lib/
│   ├── guardian.py                ← CLI principal
│   ├── guardian_shared.py         ← Helpers compartidos
│   ├── guardian_memory.py         ← Memoria TF-IDF
│   ├── guardian_rag.py            ← RAG pipeline
│   ├── guardian_absorb.py         ← Absorb v2
│   ├── guardian_web.py            ← Dashboard web (:7878)
│   ├── guardian_backend.py        ← Backend persistente (:9787)
│   ├── guardian_genome.py         ← Genoma + ramas
│   ├── guardian_conciencia.py     ← Conciencia N1 + N2
│   ├── guardian_evolution.py      ← Evolución + consolidación
│   └── guardian_mcp.py            ← MCP server
├── prompts/                       ← 5 templates de workflow
├── templates/                     ← Doc templates
├── commands/guardian.md           ← @guardian reference
├── SKILL.md                       ← Identidad del agente
├── docs/                          ← Documentación
│   ├── CONCEPTOS.md
│   ├── FLUJOS.md
│   ├── REFERENCIA.md
│   └── GUIA.md
└── tests/
    ├── test_rag.py
    ├── test_memory.py
    ├── test_config.py
    ├── test_integration.py
    └── test_backend.py

/var/guardian/
├── genome/branches/<hash>/
│   ├── identity.yaml
│   ├── state.json
│   ├── memory/
│   ├── knowledge/tomes/
│   └── learnings/
├── projects/<slug>/
│   ├── config.yaml
│   ├── audit.json
│   ├── memory/
│   ├── skills.json
│   └── ...
├── skills-global.json
├── guardian-backend.pid
└── guardian-backend.log
```
