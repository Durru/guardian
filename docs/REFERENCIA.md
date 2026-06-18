# Guardian v4.5.1 — Referencia completa

## CLI commands

### Proyecto

| Comando | Descripción |
|---------|-------------|
| `guardian activate [slug]` | Activar Guardian (setup + branch + brain + absorb + docs + codegraph + conciencia) |
| `guardian detect` | Detectar proyecto desde git remote o PWD |
| `guardian status [slug]` | Dashboard del proyecto |
| `guardian check [slug]` | Verificar reglas y paths protegidos |
| `guardian report [slug]` | Violaciones, tendencias, cumplimiento |

### Memoria y Cerebro

| Comando | Descripción |
|---------|-------------|
| `guardian brain <sub> [args]` | Acceso directo al cerebro (status, read, write, query, list, delete, count, gc, embed, cosine, learn, spike, decay, gc-potential, hebbian) |
| `guardian save-observation <slug> <obs_type> <topic_key> <content> [--outcome=] [--why=]` | Guardar observación con metadata |
| `guardian get-observation <slug> <topic_key>` | Buscar observaciones por topic |
| `guardian get-last-good <slug> <topic_key>` | Última observación exitosa |
| `guardian analyze-intent <text>` | Clasificar intent con kNN neuronal |
| `guardian plan-or-act <text> [--confidence=N]` | Decidir si planificar o actuar |

### Inteligencia Neuronal (v4.5.1)

| Comando | Descripción |
|---------|-------------|
| `guardian learn <slug> <feedback>` | Governor adaptativo: merge_was_wrong, discard_was_wrong, contradiction_was_false, merge_should_happen, discard_should_happen, contradiction_was_correct |
| `guardian feedback <slug> <topic_key> <content>` | Entrenar clasificador neuronal con ejemplo |
| `guardian brain embed <text>` | Mostrar embedding (sentence-transformers si instalado, hashing si no) |
| `guardian brain cosine <a> <b>` | Similitud coseno entre dos textos |
| `guardian brain spike <slug> <level> <id> [amount]` | Spike de potencial de activación |
| `guardian brain decay <slug> <level> [factor]` | Decaer potenciales |
| `guardian brain gc-potential <slug> <level> [threshold]` | Podar nodos por potencial bajo |
| `guardian brain hebbian <slug> <level> <a> <b>` | Reforzar enlace Hebbiano |

### Conciencia

| Comando | Descripción |
|---------|-------------|
| `guardian conciencia <cycle\|status\|history\|meta> [question]` | Conciencia + meta-evolución |
| `guardian think <pregunta> [slug]` | Conciencia N1 |
| `guardian evolve [slug]` | Disparar evolución de rama |

### RAG y Conocimiento

| Comando | Descripción |
|---------|-------------|
| `guardian rag <query> [--slug] [--top-k] [--json] [--scope]` | Búsqueda RAG |
| `guardian knowledge <status\|tomes\|search> [query]` | Conocimiento / tomos |

### Memoria Persistente

| Comando | Descripción |
|---------|-------------|
| `guardian remember <contenido> [--level=X] [--kind=Y] [slug]` | Guardar en memoria |
| `guardian recall <pregunta> [slug]` | Consultar memoria |
| `guardian reflect [slug]` | Disparar reflexión |

### Proyectos

| Comando | Descripción |
|---------|-------------|
| `guardian projects list` | Listar proyectos |
| `guardian projects absorb` | Re-absorber skills en todos los proyectos |

### Branch y Genome

| Comando | Descripción |
|---------|-------------|
| `guardian genome <status\|diff> [slug]` | ADN del ser |
| `guardian branch <list\|fork\|status\|diff> [slug]` | Ramas de evolución |
| `guardian migrate <status\|migrate\|rollback> <slug>` | Migrar proyecto de v3 a v4 layout |
| `guardian migrate-v45 <status\|migrate> [slug]` | Migrar de v4 split-brain a v4.5 unificado |

### CodeGraph

| Comando | Descripción |
|---------|-------------|
| `guardian codegraph <index\|query\|status> [slug]` | CodeGraph: AST del proyecto |

### Modo

| Comando | Descripción |
|---------|-------------|
| `guardian mode <plan\|build\|status> [reason...]` | Cambiar/ver modo |

### GitHub

| Comando | Descripción |
|---------|-------------|
| `guardian pr <sub> [args]` | GitHub PR integration |
| `guardian issue <sub> [args]` | GitHub Issues integration |

### Session

| Comando | Descripción |
|---------|-------------|
| `guardian start [slug] [--mode=plan\|build\|read]` | Iniciar sesión |
| `guardian continue [slug]` | Retomar sesión |
| `guardian end [slug]` | Cerrar sesión |

### Publicación

| Comando | Descripción |
|---------|-------------|
| `guardian publish <slug> [--to=template] [--version=X]` | Publicar template |
| `guardian templates <list\|show\|export\|import>` | Gestionar templates |
| `guardian clone <template> <new>` | Clonar desde template |
| `guardian fork <parent> <child>` | Fork con linaje |
| `guardian lineage <slug>` | Ver árbol genealógico |

## Filesystem layout (v4.5.0+)

```
/var/guardian/
├── projects/<slug>/          ← UNA rama TODO del proyecto
│   ├── branch.json           ← identidad forkeada del genome
│   ├── config.yaml           ← stack, docs, project_root
│   ├── brain/                ← cerebro completo
│   │   ├── semantic.db       ← hechos, decisiones, config
│   │   ├── episodic.db       ← eventos temporales
│   │   ├── procedural.db     ← workflows
│   │   ├── reflection.db     ← aprendizajes
│   │   ├── GUARDIAN.md       ← resumen compacto (~30 líneas)
│   │   ├── working_memory.json
│   │   ├── handoff.json
│   │   ├── conciencia-state.json
│   │   ├── conciencia-thresholds.json
│   │   ├── memory.jsonl
│   │   └── memory-embeddings.json
│   ├── knowledge/tomes/      ← skills absorbidos
│   └── learnings/            ← aprendizajes
├── global/                   ← conocimiento cross-project
│   └── brain/
│       ├── semantic_global.db
│       ├── procedural_global.db
│       └── reflection_global.db
└── genome/                   ← genoma (en /srv/guardian/genome o $GUARDIAN_DATA/genome)
    └── identity.yaml         ← identidad inmutable
```

## Neural Architecture (v4.5.1)

```
A: Embeddings reales → sentence-transformers (auto) o hashing (fallback)
B: NeuralClassifier kNN → classify_topic_neural + classify_importance_neural
C: Governor adaptativo → governor_learn(slug, feedback) ajusta thresholds
D: Spiking Memory → activation potentials + Hebbian links + decay + gc-potential
E: Conciencia Predictiva → predict_action() sobre ciclos pasados vía embeddings
```

## Architecture

### Módulos del core

| Módulo | Descripción |
|--------|-------------|
| `guardian.py` | CLI principal |
| `guardian_shared.py` | Helpers compartidos, project_dir() |
| `guardian_brain.py` | Sistema de memoria cognitiva (SQLite + embeddings) |
| `guardian_brain_schema.py` | Esquemas SQLite, path helpers |
| `guardian_conciencia.py` | Motor de razonamiento trazable + predictivo |
| `guardian_observer.py` | Observador de eventos + clasificador neuronal |
| `guardian_genome.py` | Genoma: identidad, schema, conciencia |
| `guardian_rag.py` | RAG: chunk + TF-IDF + rerank |
| `guardian_memory.py` | Memoria JSONL legacy |
| `guardian_mcp.py` | MCP server (tools para OpenCode) |
| `guardian_backend.py` | Backend HTTP persistente |
| `guardian_web.py` | Web UI |
| `guardian_lineage.py` | Árbol genealógico de proyectos |
| `guardian_evolution.py` | Evolución de rama |
| `guardian_absorb.py` | Absorción de skills |
| `guardian_migration_v3_layout.py` | Migración v3 → v4 |
| `guardian_migration_v45.py` | Migración v4 → v4.5 unificado |

## Tests

```bash
pytest tests/                    # Suite completa (~314 tests)
pytest tests/test_neural.py      # Tests de inteligencia neuronal (24)
pytest tests/test_neural_integration.py  # Pipeline completo A→E (6)
```
