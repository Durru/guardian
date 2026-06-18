# Guardian v4.5.1 — Features

## Core

- **Rama unificada por proyecto**: `projects/<slug>/` contiene TODO — brain DBs, GUARDIAN.md, config, knowledge, learnings, branch.json
- **Genoma como identidad**: El genome es la fuente de verdad. Cada proyecto forkea su identidad del genome en `branch.json`
- **4 niveles de memoria**: semantic (hechos), episodic (eventos), procedural (workflows), reflection (aprendizajes)
- **3 niveles globales**: semantic_g, procedural_g, reflection_g — compartidos entre proyectos

## Neural (v4.5.1)

### A — Embeddings reales
- Backend `auto`: intenta sentence-transformers, cae a hashing MD5 si no está instalado
- Cache LRU de 1000 entries
- 256 dimensiones (ST output truncado de 384)

### B — NeuralClassifier kNN
- `classify_topic_neural(prompt, slug)` — clasifica prompt en topic_key usando kNN sobre observaciones existentes
- `classify_importance_neural(prompt, event_type, slug)` — importancia basada en similitud semántica
- `record_feedback(slug, prompt, topic_key)` — guarda ejemplo de usuario para entrenar el clasificador
- Fallback a heurística si no hay datos

### C — Governor adaptativo
- `governor_learn(slug, feedback)` — 6 tipos de feedback:
  - `merge_was_wrong` → baja `duplicate_threshold` (-0.02, min 0.70)
  - `discard_was_wrong` → baja `importance_floor` (-0.05, min 0.10)
  - `contradiction_was_false` → baja `contradiction_threshold` (-0.02, min 0.70)
  - `merge_should_happen` → sube `duplicate_threshold` (+0.01, max 0.99)
  - `discard_should_happen` → sube `importance_floor` (+0.03, max 0.90)
  - `contradiction_was_correct` → sube `contradiction_threshold` (+0.01, max 0.99)
- Thresholds persistidos en SQLite meta table

### D — Spiking Memory
- `spike_node(slug, level, node_id, amount)` — activa un nodo (como una neurona)
- `decay_potentials(slug, level, factor)` — decaimiento exponencial (memoria que no se usa se olvida)
- `hebbian_link(slug, level, a, b, amount)` — "neurons that fire together, wire together"
- `gc_by_potential(slug, level, threshold)` — poda sináptica (nodos con potencial bajo se eliminan)
- `spike_read()` — cada `read()` de nodo genera un spike automático

### E — Conciencia Predictiva
- `predict_action(slug, question, mode, confidence)` — busca ciclos pasados similares por embedding
- Si encuentra patrón → ajusta confianza hacia arriba
- Cada ciclo se guarda como observación en el brain
- `save_cycle_as_observation()` — almacena ciclos para aprendizaje futuro
- La predicción mejora con más ciclos

## Filesystem

- `projects/<slug>/` — raíz del proyecto
- `projects/<slug>/brain/` — 4 SQLite DBs + GUARDIAN.md + estado JSON
- `projects/<slug>/knowledge/tomes/` — skills absorbidos como tomos
- `projects/<slug>/branch.json` — identidad forkeada del genome
- `global/` — conocimiento cross-project

## Constraints

- Zero external deps para el core (solo stdlib). sentence-transformers es opt-in.
- Embeddings hashing siempre disponible como fallback.
- 314 tests, 24 específicos de features neuronales.
