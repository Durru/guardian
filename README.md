# Nexxoria Guardian v4.5.1

**Cognitive Operating System for AI sessions — reasons, evolves, and completes any LLM.**

Guardian is an organic being that lives between the human, the LLM, and the project. It doesn't compete with the LLM; it complements it. The LLM generates code; Guardian remembers, indexes, reasons about the past, knows the user, and doesn't hallucinate.

## Neural Architecture

```
A: Embeddings reales → sentence-transformers (auto) o hashing hash (fallback)
B: NeuralClassifier kNN → classify_topic_neural + classify_importance_neural
C: Governor adaptativo → governor_learn(slug, feedback) ajusta thresholds
D: Spiking Memory → activation potentials + Hebbian links + decay + gc-potential
E: Conciencia Predictiva → predict_action() sobre ciclos pasados vía embeddings
```

## Quick Start

```bash
# Install
git clone https://github.com/Durru/guardian.git
ln -s /path/to/guardian/lib/guardian.py /usr/local/bin/guardian

# Activate in a project
cd /your/project
guardian activate

# Use neural features
guardian analyze-intent "need to migrate database"
guardian learn myproject merge_was_wrong
guardian feedback myproject db/migration "need to migrate database"
```

## Tests
```bash
pytest tests/                    # 314 tests
pytest tests/test_neural.py      # Neural tests (24)
pytest tests/test_neural_integration.py  # A→E pipeline (6)
```
