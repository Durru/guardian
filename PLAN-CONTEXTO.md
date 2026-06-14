# Nexxoria Guardian — Plan de Arquitectura (Contexto Central + Global/Proyecto)

> Basado en discusión: separar funciones globales de per-proyecto, sistema nervioso central de contexto,
> dedup de contexto, evolución N2 basada en contexto real, RAG unificado global+proyecto,
> ramas por usuario, sin re-ejecutar lo que ya está fresco.

---

## Principios

1. **Todo es contexto.** El contexto es la base de la conciencia, la evolución, y la memoria.
2. **Global ≠ proyecto.** Skills globales, tomos globales, perfil de usuario → 1 vez.
3. **Cada proyecto su rama.** Fork del genoma, estado, conciencia, learnings.
4. **Cada usuario su rama.** Mismo proyecto, distinto usuario = distinta rama.
5. **RAG universal.** Todo termina en RAG: skills, docs, código, memoria, decisiones, contexto.
6. **Contexto no repetitivo.** RAG + sesión trackean qué contexto ya se inyectó.
7. **Evolución contextual.** N2 no solo ajusta thresholds, ajusta QUÉ contexto se sirve y CÓMO.

---

## Arquitectura: Sistema Nervioso Central de Contexto

```
╔══════════════════════════════════════════════════════╗
║              GUARDIAN BRAIN (LLM)                    ║
║  ┌────────────────────────────────────────────────┐  ║
║  │      CENTRAL CONTEXT SYSTEM                    │  ║
║  │  (guardián_context.py)                         │  ║
║  │                                                │  ║
║  │  get_relevant_context(query, slug, mode)       │  ║
║  │    → busca en TODAS las capas                  │  ║
║  │    → rankea por relevancia                     │  ║
║  │    → filtra lo ya mostrado (dedup)             │  ║
║  │    → devuelve contexto listo para inyectar     │  ║
║  └────────────────────────────────────────────────┘  ║
║                       │                               ║
║        ┌──────────────┼──────────────┐                ║
║        ▼              ▼              ▼                ║
║  ┌──────────┐ ┌────────────┐ ┌────────────┐          ║
║  │ GLOBAL   │ │ PROYECTO   │ │ SESIÓN     │          ║
║  │ context  │ │ context    │ │ context    │          ║
║  │          │ │            │ │            │          ║
║  │• usuario │ │• código    │ │• ya visto  │          ║
║  │• prefs   │ │• docs      │ │• timestamp │          ║
║  │• patrón  │ │• memoria   │ │• prioridad │          ║
║  │• cross-  │ │• skills    │ │            │          ║
║  │  learn   │ │• conciencia│ │            │          ║
║  │• genome  │ │• tomes     │ │            │          ║
║  └──────────┘ └────────────┘ └────────────┘          ║
║       │              │              │                 ║
║       └──────────────┼──────────────┘                 ║
║                      ▼                                ║
║           ┌──────────────────┐                        ║
║           │  EVOLUCIÓN (N2)  │                        ║
║           │  base = contexto  │                        ║
║           └──────────────────┘                        ║
╚══════════════════════════════════════════════════════╝
```

---

## API Central: `get_relevant_context()`

```python
def get_relevant_context(query, slug=None, mode="plan", top_k=5):
    """API única: busca en global + proyecto + sesión, rankea, deduplica"""
    
    # 1. CAPA GLOBAL — siempre incluida
    context += load_user_context()            # preferencias, patrones del usuario
    context += load_cross_project_learnings() # lecciones de otros proyectos
    context += load_genome_context()          # identidad, principios
    
    # 2. CAPA PROYECTO — si hay slug
    if slug:
        context += load_project_memory(slug)        # memory.jsonl
        context += load_project_knowledge(slug)     # tomes
        context += load_project_docs(slug)          # docs from project_root
        context += load_project_code(slug)          # source code chunks
        context += load_project_conciencia(slug)    # último estado + ciclos
    
    # 3. FILTRAR DUPLICADOS DE SESIÓN
    context = [c for c in context if not is_already_shown(c)]
    mark_as_shown(context)
    
    # 4. RANKEAR POR RELEVANCIA (TF-IDF + recency + priority)
    ranked = rank_context(context, query, mode)
    
    return ranked[:top_k]
```

---

## Conexiones

| Componente | Llama a | Para qué |
|-----------|---------|----------|
| `guardian context` | `get_relevant_context()` | Inyectar contexto al agente |
| `conciencia.run_cycle()` | `get_relevant_context(question, slug, mode)` | Alimentar percepción N1 |
| `conciencia.evolve()` | `get_context_for_evolution()` | Base para meta-evolución N2 |
| `cmd_activate()` | `get_relevant_context("activate", slug)` | Contexto al activar proyecto |
| `guardian evolve` | `get_evolution_insights()` | Stats cross-project + tendencias |
| `guardian context --global` | `get_global_context()` | Contexto solo global |
| `guardian context --reset` | `reset_session(slug)` | Nueva sesión |

---

## Módulos

### Nuevo: `guardian_context.py`

| Función | Descripción |
|---------|-------------|
| `get_relevant_context(query, slug, mode, top_k)` | **API principal**: busca + rankea + dedup |
| `get_global_context()` | Contexto del usuario (prefs, patrones) |
| `get_cross_project_context()` | Learnings de otros proyectos |
| `get_evolution_context()` | stats + tendencias para N2 |
| `mark_as_shown(context_items, slug)` | Guarda hash en sesión para no repetir |
| `is_already_shown(context_hash, slug)` | Verifica dedup |
| `get_session_context(slug)` | Estado de sesión actual |
| `reset_session(slug)` | Nueva sesión |
| `load_user_context()` | Lee `global/context/user.json` |
| `save_user_context(data)` | Escribe perfil de usuario |
| `load_cross_project_learnings()` | Lee `global/context/cross-learnings.json` |
| `save_cross_project_learning(data)` | Agrega learning cross-project |
| `rank_context(context_list, query, mode)` | TF-IDF + recency + priority score |

### Nuevo: `guardian_global.py`

| Función | Descripción |
|---------|-------------|
| `cmd_global_scan(force=False)` | Escanea skills + ingiere como tomos globales |
| `cmd_global_knowledge(force=False)` | Re-indexa RAG global |
| `cmd_global_status()` | Muestra tomos, skills, fecha último scan |
| `load_global_tomes()` | Devuelve tomos globales para RAG |
| `global_is_fresh()` | True si < 1h desde último scan |
| `load_user_context()` | Perfil de usuario desde `global/context/user.json` |
| `save_user_context(data)` | Persiste perfil de usuario |

### Modificado: `guardian_absorb.py`

| Hoy | Nuevo |
|-----|-------|
| `cmd_scan()` solo escanea | `cmd_scan(global_ingest=True)` → escanea + ingiere a global |
| `cmd_match()` llama a `cmd_ingest` al final | `cmd_match()` YA NO llama a ingest |
| `cmd_ingest(slug)` genera tomos por proyecto | `cmd_ingest(slug, scope="global"\|"project")` |
| skills → tomes por proyecto (N copias) | skills → tomos globales (1 copia), proyecto solo linkea |

### Modificado: `guardian_rag.py`

| Función | Cambio |
|---------|--------|
| `_collect_chunks()` | Nueva fuente `"global"`: incluye tomos globales SIEMPRE |
| `cmd_rag()` | Por defecto busca global + project |
| `_chunk_global_knowledge()` | Lee `$GUARDIAN_DATA/global/knowledge/tomes/` |

### Modificado: `guardian_conciencia.py`

| Función | Cambio |
|---------|--------|
| `run_cycle()` | Llama a `get_relevant_context()` automáticamente para percibir |
| `evolve()` | Usa `get_evolution_context()` en lugar de solo thresholds |
| N2 mejorado | Analiza tendencias, cross-project, anomalías, contexto ignorado |

### Modificado: `guardian_evolution.py`

| Función | Cambio |
|---------|--------|
| `evolve_branch()` | Llama a `get_evolution_context()` para decisiones informadas |
| `consolidate()` | También consolida contexto global |

### Modificado: `guardian.py`

| Función | Cambio |
|---------|--------|
| `cmd_context()` | Usa `get_relevant_context()`; nuevo flag `--global`, `--reset` |
| `cmd_activate()` | Freshness checks + contexto central |
| Nuevo `cmd_global()` | Subcomandos: scan, knowledge, status |
| Nuevo `cmd_project()` | Subcomandos: activate, status |

### Modificado: `guardian_backend.py`

| Endpoint | Nuevo |
|----------|-------|
| `GET /context` | Contexto relevante via query params |
| `POST /context/reset` | Resetear sesión |
| `GET /global` | Estado global |
| `POST /global/scan` | Escaneo global |

### Modificado: `guardian_mcp.py`

| Tool | Nuevo |
|------|-------|
| `get_context` | Obtener contexto relevante |
| `reset_session` | Resetear sesión actual |

---

## Archivos en disco

```
$GUARDIAN_DATA/global/
├── knowledge/
│   ├── tomes/               ← Skills como tomos (1 vez, no por proyecto)
│   └── index.json           ← Índice global
├── context/
│   ├── user.json            ← Perfil del usuario (prefs, stack fav, patrones)
│   ├── cross-learnings.json ← Learnings que aplican a todos los proyectos
│   ├── evolution-history.json ← Historial de evoluciones (para tendencias)
│   └── context-usage.json   ← Stats de qué contexto se sirvió vs se ignoró
├── conciencia/
│   └── meta-learnings.json  ← Aprendizaje cross-proyecto de conciencia
└── sessions/
    └── <slug>.json          ← Contexto ya mostrado en sesión actual

$GUARDIAN_DATA/projects/<slug>/
├── config.yaml              ← Config del proyecto
├── skills.json              ← Skills matcheados (solo scores, no tomos)
├── conciencia-state.json    ← Ciclos de conciencia
├── conciencia-thresholds.json ← Thresholds evolucionados
├── memory.jsonl             ← Memoria del proyecto
├── knowledge/
│   └── tomes/               ← Tomos ESPECÍFICOS del proyecto (no skills globales)
└── learnings/               ← Learnings del proyecto

$GUARDIAN_DATA/genome/
└── branches/
    ├── default/             ← Rama template
    └── <hash>/              ← Rama por usuario/proyecto
        ├── identity.yaml
        ├── state.json
        ├── memory/
        ├── knowledge/tomes/
        └── learnings/
```

---

## Flujo completo con el nuevo sistema

```
1. USUARIO DICE "activo guardian en mi-proyecto"
   ↓
2. cmd_activate("mi-proyecto")
   → setup (skip si config existe)
   → fork_branch (skip si rama existe)
   → global scan (skip si < 1h)
   → match (skip si skills.json fresco)
   → docs scan (skip si docs al día)
   → get_relevant_context("activar guardian", "mi-proyecto", mode)
     ├── global: usuario prefiere node, asume en build
     ├── proyecto: stack next.js, skills relevantes
     └── sesión: nada aún, sesión nueva
   → conciencia.run_cycle()
     ├── percibe con contexto completo
     ├── decide acción
     └── guarda ciclo
   ↓
3. RESULTADO
   → Rama creada, skills matcheados, docs escaneados
   → Conciencia con contexto completo
   → Contexto marcado como mostrado
   ↓
4. EVOLUCIÓN (cuando haya ≥5 ciclos)
   → get_evolution_context()
     ├── thresholds de todos los proyectos
     ├── contexto más usado vs ignorado
     ├── tendencias de confianza
     └── feedback del usuario
   → ajusta thresholds
   → guarda learning cross-project
   → guarda en learnings/ del proyecto
```

---

## Freshness checks en `cmd_activate()`

```python
def cmd_activate(slug):
    steps = []
    
    # 1. Setup (skip si existe)
    if not project_exists(slug):
        cmd_setup(slug, auto=True)
        steps.append("setup")
    
    # 2. Branch (skip si existe)
    path = branch_path(slug)
    if not path.exists():
        fork_branch(slug)
        steps.append("branch_fork")
    
    # 3. Global scan (skip si fresco)
    if not global_is_fresh():
        cmd_global_scan()
        steps.append("global_scan")
    
    # 4. Match (skip si fresco)
    skills = read_skills_json(slug)
    if not skills.get("last_match") or is_stale(skills["last_match"], max_age_hours=1):
        cmd_match(slug)
        steps.append("match")
    
    # 5. Docs scan (skip si fresco)
    config = read_config(slug)
    last_scan = get_docs_last_scan(config)
    if not last_scan or is_stale(last_scan, max_age_days=7):
        cmd_docs_scan(slug)
        steps.append("docs_scan")
    
    # 6. Conciencia (siempre)
    context = get_relevant_context("activar guardian", slug, mode)
    conciencia.run_cycle(slug, question="activar guardian", mode=mode, context=context)
    steps.append("conciencia_cycle")
    
    return steps
```

---

## Evolución N2 mejorada

**Hoy:** Ajusta thresholds ±0.05 según promedios simples de confianza.

**Nuevo N2:**

| Mecanismo | Descripción |
|-----------|-------------|
| Análisis de tendencias | Detectar si la confianza sube/baja en el tiempo (regresión lineal simple) |
| Cross-project learning | Comparar thresholds de todos los proyectos, usar mediana como default |
| Anomalías | Detectar ciclos outlier (confianza muy baja o acción inesperada) |
| Contexto ignorado | Si cierto tipo de contexto nunca se usa, dejar de servirlo |
| Feedback implícito | Si usuario sobreescribe decisión de conciencia, eso es input para evolucionar |
| LLM hook (opcional) | Llamar a LLM para generar razones de evolución ricas |

**Nuevos umbrales evolucionables:**

```
- plan_assume_bonus: -0.1  (se ajusta si plan asume demasiado)
- build_assume_bonus: 0.1  (se ajusta si build duda demasiado)
- max_cycles_for_analysis: 20 (crece si hay muchos ciclos)
- advisory: true (se apaga si usuario nunca pide consejo)
```

---

## Próximos pasos (por completar)

- [ ] Detallar implementación de `guardian_context.py`
- [ ] Detallar integración con LLM (hooks para razones evolutivas)
- [ ] Especificar formato exacto de archivos en disco (JSON schema)
- [ ] Diseñar sistema de prioridad/score para rank_context()
- [ ] Plan de migración desde paths viejos (/var/guardian → /var/lib/nexxoria-guardian)
- [ ] Tests específicos para cada módulo nuevo
- [ ] Estrategia de consolidación de contexto (GC de contexto viejo)
