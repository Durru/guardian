#!/usr/bin/env python3
"""
Neural Demo — ejercita todo el pipeline neuronal de Guardian v4.6.0.

Uso: PYTHONPATH=lib python3 demo/neural_demo.py
"""
import sys, os, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

# ── Setup ──────────────────────────────────────────────────────────────
tmpdir = Path(tempfile.mkdtemp(prefix="guardian-demo-"))
slug = "demo-project"

import guardian_shared as shared
shared.MEMORY_DIR = tmpdir
shared.BACKEND_DIR = tmpdir

import guardian_brain as brain
import guardian_brain_schema as schema
import guardian_conciencia as conciencia
import guardian_observer as obs

schema.init_project(slug)
brain._reset_conn_cache()

# Setup minimal genome for conciencia
(Path(tmpdir) / "genome").mkdir(parents=True, exist_ok=True)
(Path(tmpdir) / "genome" / "identity.yaml").write_text("""\
  version: 4.6.0
creator: demo
identity:
  name: Demo Guardian
  principles: ["Test"]
consciousness:
  thresholds: {assume: 0.8, ask_little_floor: 0.5, ask_much_floor: 0.2}
  default_mode: plan
""")

print("=" * 60)
print("🧠  Guardian Neural Demo — v4.8.0")
print("=" * 60)

# ── A: Embeddings ──────────────────────────────────────────────────────
print("\n[ A ] Embeddings")
e = brain.embed("sistema de autenticación con JWT")
print(f"      Dimensiones: {len(brain.embed_to_list('test'))}")
sim = brain.cosine_text("token de acceso", "JWT refresh token")
print(f"      Similitud 'token' ↔ 'JWT': {sim:.3f}")
sim2 = brain.cosine_text("token de acceso", "instalar dependencias")
print(f"      Similitud 'token' ↔ 'instalar': {sim2:.3f}")
print(f"      ✅ Embeddings funcionales")

# ── B: Neural Classifier ──────────────────────────────────────────────
print("\n[ B ] Neural Classifier kNN")
# Seed with examples
obs.record_feedback(slug, "migrate database from postgres to mysql", "db/migration")
obs.record_feedback(slug, "add REST API endpoint for users", "api/endpoint")
obs.record_feedback(slug, "fix critical crash on login page", "bugfix/general")
obs.record_feedback(slug, "deploy docker container to production", "deploy/ci")

# Classify
topic = obs.classify_topic_neural("need to migrate our database", slug)
imp = obs.classify_importance_neural("fix production crash immediately", slug=slug)
print(f"      'migrate database' → topic: {topic}")
print(f"      'fix production crash' → importance: {imp:.2f}")
print(f"      ✅ Neural Classifier funcional")

# ── C: Governor ────────────────────────────────────────────────────────
print("\n[ C ] Governor Adaptativo")
r1 = brain.governor_learn(slug, "merge_was_wrong")
print(f"      merge_was_wrong → duplicate_threshold: {r1['thresholds']['duplicate_threshold']:.2f}")
r2 = brain.governor_learn(slug, "discard_was_wrong")
print(f"      discard_was_wrong → importance_floor: {r2['thresholds']['importance_floor']:.2f}")
r3 = brain.governor_learn(slug, "merge_should_happen")
print(f"      merge_should_happen → duplicate: {r3['thresholds']['duplicate_threshold']:.2f}")
print(f"      ✅ Governor adaptativo funcional")

# ── D: Spiking Memory ─────────────────────────────────────────────────
print("\n[ D ] Spiking Memory")
for i in range(5):
    nid = f"demo-node-{i}"
    brain.write(slug, "semantic", {"id": nid, "kind": "test", "content": f"demo data {i}", "importance": 0.5})
    brain.spike_node(slug, "semantic", nid, 0.3)
brain.hebbian_link(slug, "semantic", "demo-node-0", "demo-node-1", 0.2)
brain.decay_potentials(slug, "semantic", 0.9)
gc = brain.gc_by_potential(slug, "semantic", threshold=0.05, dry_run=True)
print(f"      Nodos spikeados: 5")
print(f"      Enlace Hebbiano: demo-node-0 ↔ demo-node-1")
print(f"      GC potential (dry-run): {gc['pruned']} candidatos")
print(f"      ✅ Spiking Memory funcional")

# ── E: Conciencia Predictiva ──────────────────────────────────────────
print("\n[ E ] Conciencia Predictiva")
for i in range(6):
    result = conciencia.run_cycle(slug, question=f"test query {i}", mode="plan")
    pred = result.get("prediction", {})
    pred_info = f" | pred: {pred.get('predicted', '—')} ({pred.get('method', '—')})" if pred else ""
    print(f"      Ciclo {i+1}: {result['action']} (conf: {result['confidence']:.2f}){pred_info}")

print(f"\n{'=' * 60}")
print(f"✅  Pipeline neuronal completo funcional")
print(f"{'=' * 60}")

# Cleanup
brain._reset_conn_cache()
import shutil
shutil.rmtree(tmpdir, ignore_errors=True)
