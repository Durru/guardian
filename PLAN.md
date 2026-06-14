# GUARDIAN v2 — Plan Completo

> Generado: 2026-06-14
> Modo: Build — listo para implementar

---

## 1. Filosofía

Guardian es un **ser orgánico**. No es una herramienta que se ejecuta — es un ente que vive, percibe, decide, aprende y evoluciona. Tiene ADN, cerebro, ojos, manos, piernas y nanos.

### El Ser

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
│ │  Skills   │   │  Git)    │   │  API + WS + MCP)  │      │
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

---

## 2. Estructura de directorios

```
/srv/guardian/
├── genome/
│   ├── identity.yaml              ← ADN inmutable (solo vos)
│   └── branches/
│       ├── default/               ← Semilla para forks nuevos
│       └── <sha256_hash>/
│           ├── identity.yaml      ← Quién es este usuario
│           ├── state.json         ← Estado de conciencia
│           ├── memory/
│           ├── knowledge/
│           │   ├── tomes/         ← Skills como libros de sabiduría
│           │   ├── canon.md       ← Conocimiento fundamental actual
│           │   └── index.json     ← Índice de libros disponibles
│           └── learnings/         ← Patrones aprendidos
│
├── lib/
│   ├── guardian.py                ← CLI principal (se refactoriza)
│   ├── guardian_shared.py         ← Helpers compartidos (existe)
│   ├── guardian_memory.py         ← Memoria TF-IDF (existe)
│   ├── guardian_rag.py            ← RAG pipeline (existe, evoluciona)
│   ├── guardian_absorb.py         ← Absorb v2 (evoluciona)
│   ├── guardian_web.py            ← Dashboard web (existe, evoluciona)
│   ├── guardian_backend.py        ← Servidor persistente HTTP+WS (nuevo)
│   ├── guardian_genome.py         ← Genoma + ramas + forks (nuevo)
│   ├── guardian_conciencia.py     ← Conciencia + Meta-conciencia (nuevo)
│   ├── guardian_evolution.py      ← Evolución y consolidación (nuevo)
│   └── guardian_mcp.py            ← MCP server (nuevo)
│
├── prompts/                       ← 5 templates de workflow (existen)
├── templates/                     ← Doc templates (existen)
├── commands/guardian.md           ← @guardian reference (existe)
├── SKILL.md                       ← Identidad del agente (se actualiza)
├── PLAN.md                        ← Este documento
├── README.md
└── tests/
```

---

## 3. Genoma — ADN inmutable

`genome/identity.yaml` (solo vos lo modificás vía GitHub):

```yaml
version: 2.0.0
creator: durru
created: 2026-06-14
identity:
  name: Nexxoria Guardian
  purpose: "Universal project guardian for OpenCode AI sessions"
  principles:
    - "Proteger el proyecto antes que nada"
    - "Auto-evolucionar sin depender del LLM"
    - "Memoria persistente, cero dependencias externas"
    - "Cada usuario es una rama, no un fork"
core:
  versioning: semver
  mutation_rules: "solo el creator modifica identity.yaml"
```

---

## 4. Ramas — Evolución de cada usuario

Cada usuario obtiene una rama al hacer `guardian setup`:

```
genome/branches/<sha256>/
├── identity.yaml    ← Se genera auto (quién es este usuario)
├── state.json       ← Estado actual de su conciencia
├── knowledge/
│   ├── tomes/       ← Skills transformados a conocimiento (vía absorb ingest)
│   ├── canon.md     ← Conocimiento fundamental acumulado
│   └── index.json   ← Índice de todos los libros
├── memory/          ← Su memoria personal
└── learnings/       ← Patrones aprendidos
```

---

## 5. Conciencia — Nivel 1 (operativa)

Ciclo que se ejecuta **en cada sesión**:

```
PERCIBIR:
  - ¿Qué cambió desde la última sesión?
  - ¿Qué contexto servido por RAG?
  - ¿Qué modo estoy? (Plan / Build)
  - ¿Qué errores ocurrieron?
  - ¿Qué experiencia previa hay en la rama?

DECIDIR:
  - Calcular percentiles de certeza
  - Si > 80% → ASUME, actúa sin preguntar
  - Si 50-80% → PREGUNTA POCO ("¿Confirmo?")
  - Si 20-50% → PREGUNTA MUCHO ("¿A, B o C?")
  - Si < 20% → INVESTIGA, pide más contexto

REFLEXIONAR:
  - ¿Funcionó lo que decidí?
  - ¿Qué aprendo de esta sesión?
  - ¿Qué guardo en la memoria?
  - ¿Qué indexo al RAG?
```

### Factores de certeza

| Factor | Peso |
|--------|------|
| Contexto relevante servido (score RAG) | Alto |
| Similitud con experiencias pasadas (rama + memoria) | Medio |
| Claridad del input del usuario | Medio |
| Confianza en skills activos (tomes matcheados) | Medio |
| Frescura del contexto | Bajo |
| Estabilidad del proyecto (cambios recientes, errores) | Bajo |

---

## 6. Meta-conciencia — Nivel 2 (evoluciona)

Se ejecuta **al final de cada sesión o periódicamente**:

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

---

## 7. Modos de operación

| Aspecto | Modo Plan | Modo Build |
|---------|-----------|------------|
| Objetivo | Pensar, investigar, diseñar | Implementar, codificar, ejecutar |
| Escritura | Solo lee archivos | Lee y escribe archivos |
| Conciencia | Percibe + Reflexiona (fuerte) | Decide + Acciona (fuerte) |
| Hooks | Solo pre-change (simular) | pre + post completos |
| Skills | Consulta warm + cold como contexto | Consulta hot + warm como herramientas |
| Output | Planes, diagramas, preguntas | Código, archivos, commits |
| Percentiles | Tiende a preguntar más | Tiende a asumir más |
| Rama | Marca "plan session" | Marca "build session" |

**Auto-detección:** si el primer mensaje es "qué pasaría si..." → Plan. Si es "hacé esto" → Build.

---

## 8. Skills — Libros de sabiduría

**Absorb v2** (evolución, no reemplazo):

```
absorb v1 (hoy):       scan → match → classify → hot/warm/cold
absorb v2:             scan → classify → ingest → tomes/
                                                  ↓
                                           skills como libros en RAG
                                           (el cerebro consulta,
                                            nadie activa directo)
```

### Subcomandos

| Comando | Función |
|---------|---------|
| `guardian absorb scan [--force]` | Escanea skills/, mide calidad (existe, evoluciona) |
| `guardian absorb classify <slug>` | Analiza proyecto, clasifica contra skills (existe, evoluciona) |
| `guardian absorb ingest <slug>` | **Nuevo**: Skills clasificados → libros de sabiduría en tomes/ + RAG |
| `guardian absorb learn <slug> <skill> <action>` | Registra uso de conocimiento (existe, evoluciona) |
| `guardian absorb status [slug]` | Estado de la base de conocimiento (existe, evoluciona) |

**Principio:** Nadie activa un skill directamente. El cerebro consulta el RAG y recibe el skill relevante para el contexto actual.

---

## 9. Documentación — Todo al RAG

**Docs v2** (evolución, no reemplazo):

```
docs v1 (hoy):    scan → genera .md → rutear por path
docs v2:          scan → genera .md
                  └→ auto-chunk al RAG
                  └→ el cerebro lee docs vía RAG
                  └→ la evolución indexa aprendizajes al RAG
                  └→ skills + docs + memoria + código = un solo RAG
```

---

## 10. RAG — Conocimiento unificado del ser

El RAG existente (`guardian_rag.py`) se potencia:

| Fuente | Contenido | Se indexa cuando |
|---------|-----------|-----------------|
| Docs | Documentación generada + templates | `guardian docs scan` |
| Skills | Libros de sabiduría (tomes/) | `guardian absorb ingest` |
| Memoria | Memoria JSONL del proyecto | `guardian consolidate` |
| Código | Archivos del proyecto | `guardian pre-change` / `post-change` |
| Rama | Aprendizajes de la rama del usuario | Fin de sesión |
| Decisiones | Decisiones registradas | `guardian log decision` o conciencia |

### RAG adaptativo

- `GET /rag?q=...&mode=plan` → prioriza docs y skills
- `GET /rag?q=...&mode=build` → prioriza código y memoria
- `GET /rag?q=...&slug=...&source=tomes` → solo skills como libros

---

## 11. Backend persistente — localhost:9787

| Componente | Tecnología |
|------------|-----------|
| HTTP API | http.server (stdlib), migrable a FastAPI |
| WebSocket | ws (stdlib) |
| MCP | JSON-RPC 2.0 |
| DB | SQLite (20 tablas) |
| Scheduler | threading.Timer (tareas periódicas) |
| Daemon | systemd o `guardian backend start` en background |

### API REST

| Endpoint | Método | Propósito |
|----------|--------|-----------|
| `/health` | GET | Health check |
| `/metrics` | GET | Estadísticas |
| `/mode` | GET/POST | Plan/Build |
| `/genome` | GET/POST | ADN |
| `/genome/mutate` | POST | Mutación controlada |
| `/branch` | GET/POST | Ramas |
| `/branch/:hash/diff` | GET | Diff de rama |
| `/branch/merge` | POST | Mergear core→rama |
| `/session` | GET/POST | Sesiones |
| `/context` | GET/POST | Contextos |
| `/conciencia/cycle` | POST | Ejecutar ciclo |
| `/conciencia/state` | GET | Estado actual |
| `/conciencia/percentiles` | GET | Calibración actual |
| `/conciencia/meta` | POST | Meta-evolución |
| `/evolve` | POST | Disparar evolución |
| `/consolidate` | POST | Consolidar memoria |
| `/rag` | GET | RAG adaptativo |
| `/absorb/scan` | POST | Scan skills |
| `/absorb/classify` | POST | Classify proyecto |
| `/absorb/ingest` | POST | Skills → tomes |
| `/docs/scan` | POST | Docs + chunk a RAG |
| `/knowledge/tomes` | GET | Listar libros |
| `/knowledge/tomes/:name` | GET | Ver libro |
| `/knowledge/search` | GET | Buscar en conocimiento |
| `/mcp/tools` | GET | Tools registradas |
| `/mcp/call` | POST | Llamar tool MCP |
| `/ws` | WS | Eventos en tiempo real |

---

## 12. Criterios de evolución de la rama

| Criterio | Se registra desde |
|----------|------------------|
| Errores | post-hook, decision_log |
| Decisiones | conciencia, decision_log |
| Skills usados | absorb learn, ingest |
| Proyectos | detect, setup, config |
| Experiencias | conciencia (reflexión) |
| LLM detectado | inicio de sesión |
| IDE detectado | env detect |
| Forma de trabajar | conciencia infiere patrón |
| Investigaciones | web fetch, RAG queries |
| Entornos | env detect |
| Interacción del usuario | conciencia analiza |

---

## 13. Comandos CLI

### Existentes que evolucionan

| Comando | Cambio |
|---------|--------|
| `guardian absorb` | scan/classify/learn siguen; se agrega ingest |
| `guardian docs scan` | Ahora también indexa al RAG automáticamente |
| `guardian context` | Modos siguen, ahora servidos vía backend |
| `guardian rag` | Se mantiene, backend lo sirve también vía API |
| `guardian web` | Se conecta al backend en vez de ser autónomo |

### Nuevos

| Comando | Función |
|---------|---------|
| `guardian mode plan\|build\|status` | Modo de operación |
| `guardian backend start\|stop\|status\|restart` | Backend persistente |
| `guardian genome status\|diff\|mutate` | ADN |
| `guardian branch status\|diff\|fork\|merge\|list` | Ramas |
| `guardian conciencia cycle\|status\|history\|meta` | Conciencia + meta |
| `guardian evolve` | Disparar evolución |
| `guardian consolidate` | Consolidar memoria a RAG |
| `guardian knowledge status\|tome\|canon\|search` | Libros de sabiduría |
| `guardian env detect` | Detectar entorno |

---

## 14. Orden de implementación

```
Fase 1:  Schema SQL (20 tablas) + migración inicial
Fase 2:  guardian_genome.py       — genoma + ramas + forks
Fase 3:  guardian_backend.py      — HTTP + WS + Scheduler + API REST
Fase 4:  Modo Plan/Build          — engine de modos + auto-detección
Fase 5:  guardian_conciencia.py   — nivel 1 (ciclo + percentiles)
Fase 6:  guardian_conciencia.py   — nivel 2 (meta-evolución)
Fase 7:  guardian_evolution.py    — evolución de ramas + consolidación
Fase 8:  absorb v2               — ingest → tomes → RAG
Fase 9:  docs v2                 — auto-chunk a RAG
Fase 10: guardian_mcp.py          — MCP server + tools
Fase 11: Refactor CLI             — nuevos comandos, conectar al backend
Fase 12: Actualizar SKILL.md + tests de cada módulo
```

---

## 15. Stack técnico

| Componente | Tecnología |
|------------|-----------|
| Runtime | Python 3.11+ |
| HTTP/WS | http.server + queue (stdlib), migrable a FastAPI |
| DB | SQLite3 (stdlib) |
| RAG | TF-IDF + cosine sim + reranking (existente en guardian_rag.py) |
| MCP | JSON-RPC 2.0 sobre stdio o TCP |
| Skills format | SKILL.md → YAML frontmatter + markdown |
| Logging | JSONL + SQLite |
| Daemon | systemd o fork background |
| Dependencias externas | **Cero** obligatorias (PyYAML opcional) |

---

## 16. Diagrama de flujo completo

```
1. USUARIO ABRE SESIÓN
   │
2. BACKEND detecta → carga rama del usuario → estado de conciencia anterior
   │
3. MODO detectado automático (Plan/Build según primer mensaje)
   │
4. OJOS: RAG sirve contexto relevante para el momento actual
   │
5. CEREBRO (Nivel 1): Conciencia evalúa percentiles de certeza
   │
   ├── < 20%  → "Necesito más contexto" (investiga)
   ├── 20-50% → Pregunta específica
   ├── 50-80% → "¿Confirmo esto?" (pregunta poco)
   └── > 80%  → Asume y ejecuta
   │
6. MANOS/NANOS: ejecutan lo decidido (hooks, tools, MCP)
   │
7. PIERNAS: persisten todo (backend escribe DB + rama)
   │
8. FIN DE SESIÓN:
   ├── Nivel 1 reflexiona → guarda aprendizaje
   ├── Nivel 2 observa → calibra → evoluciona
   └── Rama se actualiza con la evolución
```

---

*Este plan fue generado en modo plan y aprobado para implementación.
Próximo paso: comenzar con Fase 1 — Schema SQL.*
