# Plan v4.6.0 — Evolución neuronal y automatización

## Resumen

8 mejoras sobre la base neural de v4.5.1, ordenadas por impacto/esfuerzo.

---

## 1. Spiking GC automático

**Qué**: Al cerrar sesión (`session_end`), ejecutar `gc_by_potential` automáticamente.

**Por qué**: La memoria spiking decae pero nunca se poda sola. El usuario nunca se acuerda de ejecutar `guardian brain gc-potential`.

**Cómo**: 
- `session_end()` ya ejecuta `auto_compact()` → agregar `gc_by_potential()` ahí
- Threshold default: 0.15 (nodos con potencial menor se eliminan)
- Configurable en `mode-state.json`

**Archivos**: `guardian_brain.py`

---

## 2. Pre-carga del modelo ST

**Qué**: Cargar sentence-transformers al inicio en vez de al primer `embed()`.

**Por qué**: La primera llamada a `embed()` tarda ~3s cargando el modelo. Con precarga, todas las llamadas son rápidas.

**Cómo**:
- `_init_transformer()` se llama al import del módulo (si es `auto` o `sentence-transformer`)
- Si falla, silencioso (hashing fallback)
- Timeout de 10s para no bloquear

**Archivos**: `guardian_brain.py`

---

## 3. Métricas de acierto

**Qué**: El clasificador kNN registra cuántas veces acertó/erró.

**Por qué**: Sin métricas no sabemos si el clasificador mejora.

**Cómo**:
- `record_feedback()` ya guarda ejemplos correctos
- Agregar `record_miss(slug, prompt, guessed_topic, correct_topic)` que guarda el error
- Agregar `classifier_stats(slug)` que devuelve acierto/error total

**Archivos**: `guardian_observer.py`

---

## 4. Aprendizaje cross-project

**Qué**: Compartir ejemplos de clasificación entre proyectos del mismo stack.

**Por qué**: Un proyecto nuevo no tiene datos de clasificación. Pero proyectos similares (mismo stack) sí.

**Cómo**:
- `_ensure_knn_data()` también consulta la DB global si el proyecto local tiene pocos ejemplos
- Los ejemplos se etiquetan con el stack del proyecto
- `classify_topic_neural()` fusiona datos locales + globales

**Archivos**: `guardian_observer.py`

---

## 5. Web UI para neural

**Qué**: Endpoints HTTP en `guardian_web.py` para ver estado neural.

**Por qué**: Hoy no hay forma visual de ver el estado del brain, clasificaciones, thresholds.

**Cómo**:
- `/brain/neural` — HTML con: nodos totales, top topics, thresholds del governor, últimas predicciones
- `/brain/spike` — HTML con: activation potentials actuales, top spikes, decay rate
- `/classifier/stats` — JSON con accuracy del clasificador

**Archivos**: `guardian_web.py`

---

## 6. Feedback loop automático

**Qué**: Detectar cuando el usuario corrige una clasificación y aprender automáticamente.

**Por qué**: Si el usuario ejecuta `guardian analyze-intent "X"` y luego `guardian feedback slug Y "X"`, el sistema debería detectar que corrigió y registrar la mejora.

**Cómo**:
- `record_feedback()` verifica si ya existía una clasificación previa para el mismo prompt
- Si existía y era diferente → registrar como "corrección"
- `classifier_stats()` incluye "correcciones" como métrica

**Archivos**: `guardian_observer.py`

---

## 7. RAG híbrido

**Qué**: Agregar búsqueda vectorial por embeddings al pipeline RAG actual.

**Por qué**: RAG actual solo usa TF-IDF. Embeddings capturan semántica.

**Cómo**:
- `_retrieve()` actual: TF-IDF sobre chunks cacheados
- Agregar paso de reranking por embeddings
- Los chunks con mejor score semántico suben en el ranking
- `_rerank()` pesa: 50% TF-IDF + 30% coseno + 20% recency

**Archivos**: `guardian_rag.py`

---

## 8. Fine-tuning del governor por proyecto

**Qué**: Thresholds del governor se ajustan por proyecto, no globalmente.

**Por qué**: Hoy `_get_governor_thresholds(slug)` ya es por proyecto (lee de meta table en semantic.db). Pero `GOVERNOR_DEFAULTS` son iguales para todos.

**Cómo**:
- `governor_evaluate()` usa método `calculate_dynamic_thresholds(slug)` que analiza el historial de decisiones del proyecto
- Si el proyecto tiene muchas fusiones → sube `duplicate_threshold`
- Si tiene muchos descartes → sube `importance_floor`
- Ajuste automático en cada `governor_learn()`

**Archivos**: `guardian_brain.py`

---

## Resumen de archivos a modificar

| Archivo | Items | Tipo |
|---------|-------|------|
| `guardian_brain.py` | 1, 2, 8 | Core |
| `guardian_observer.py` | 3, 4, 6 | Neural |
| `guardian_web.py` | 5 | Web |
| `guardian_rag.py` | 7 | RAG |
| `tests/` | 1-8 | Tests |
