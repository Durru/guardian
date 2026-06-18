# Nexxoria Guardian v4.5.1

Sistema operativo cognitivo para sesiones de IA — razona, evoluciona y completa a cualquier LLM.

## Stack
- runtime: python
- framework: —
- database: sqlite
- dev: —
- test: pytest (314 tests)
- lint: ruff check .

## Docs
- [REFERENCIA.md](docs/REFERENCIA.md) — CLI completo + neural architecture + filesystem layout
- [FEATURES.md](docs/FEATURES.md) — Features y constraints
- [CONSTRAINTS.md](docs/CONSTRAINTS.md) — Constraints del proyecto
- [GUIA.md](docs/GUIA.md) — Inicio rápido
- [CONCEPTOS.md](docs/CONCEPTOS.md) — Filosofía, ser orgánico, conciencia, genoma
- [FLUJOS.md](docs/FLUJOS.md) — Workflows

## CLI rápido

```bash
guardian --version              # v4.5.1
guardian activate               # Activar en proyecto
guardian learn <slug> <feedback> # Governor adaptativo
guardian feedback <slug> <topic> <txt>  # Entrenar clasificador
guardian brain status <slug>    # Estado del cerebro
guardian brain query <slug> <level> <q>  # Búsqueda semántica
guardian analyze-intent "texto" # Clasificar con kNN neuronal
```

## Neural Features (v4.5.1)
- A: Embeddings reales (sentence-transformers auto, hashing fallback)
- B: NeuralClassifier kNN + record_feedback
- C: Governor adaptativo (6 tipos de feedback)
- D: Spiking Memory (activation potentials, Hebbian, decay, gc-potential)
- E: Conciencia Predictiva (predict_action sobre ciclos)

## Filesystem
- `projects/<slug>/` — UNA rama por proyecto, TODO ahí
- `projects/<slug>/brain/` — 4 SQLite DBs + GUARDIAN.md + estado
- `projects/<slug>/branch.json` — Identidad forkeada del genome
- `global/` — Conocimiento cross-project

## Tests
```bash
pytest tests/                    # 314 tests
pytest tests/test_neural.py      # Tests neuronales (24)
pytest tests/test_neural_integration.py  # Pipeline A→E (6)
```

## GitHub
- `git push origin master`
