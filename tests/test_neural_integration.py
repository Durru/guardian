"""Integration test: neural pipeline completo (A→E).

Tests that ALL neural features work together end-to-end:
  A: Embeddings reales (sentence-transformers o hashing)
  B: NeuralClassifier kNN (classify + feedback)
  C: Governor adaptativo (learn)
  D: Spiking Memory (spike, decay, hebbian)
  E: Conciencia Predictiva (predict_action sobre ciclos)
"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

import guardian_brain as brain
import guardian_brain_schema as schema
import guardian_conciencia as conciencia
import guardian_observer as obs
import guardian_shared as shared


class TestNeuralPipeline(unittest.TestCase):
    """Full neural pipeline integration test."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="guardian-neural-int-"))
        cls.slug = "neural-pipeline"
        shared.MEMORY_DIR = cls.tmpdir
        shared.BACKEND_DIR = cls.tmpdir
        brain._reset_conn_cache()
        schema.init_project(cls.slug)
        # Setup minimal genome for conciencia
        genome_dir = cls.tmpdir / "genome"
        genome_dir.mkdir(parents=True, exist_ok=True)
        (genome_dir / "identity.yaml").write_text("""\
  version: 4.6.0
creator: test
identity:
  name: Nexxoria Guardian
  principles:
    - "Test principle"
consciousness:
  thresholds:
    assume: 0.8
    ask_little_floor: 0.5
    ask_much_floor: 0.2
  default_mode: plan
""")

    @classmethod
    def tearDownClass(cls):
        brain._reset_conn_cache()
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def setUp(self):
        brain._reset_conn_cache()

    # ── A: Embeddings ──

    def test_A_embedding_works(self):
        """A: Embeddings — both backends produce usable vectors."""
        e = brain.embed("test neural embedding pipeline")
        self.assertIsInstance(e, bytes)
        vec = brain.embed_to_list("another test")
        self.assertEqual(len(vec), brain.EMBED_DIM)
        # Cosine similarity with self = 1.0
        self.assertAlmostEqual(brain.cosine_text("same text", "same text"), 1.0, places=4)

    # ── B: Neural Classifier + kNN ──

    def test_B_classifier_seeded_and_predicts(self):
        """B: Neural Classifier — seed with feedback, then classify."""
        # Seed with examples
        obs.record_feedback(self.slug, "need to migrate database from postgres", "db/migration")
        obs.record_feedback(self.slug, "add new REST API endpoint for users", "api/endpoint")
        obs.record_feedback(self.slug, "fix critical crash on login page", "bugfix/general")

        # Classify should find something
        t = obs.classify_topic_neural("migrate database", self.slug)
        self.assertIsInstance(t, str)

        # Importance should be non-trivial
        imp = obs.classify_importance_neural("deploy to production urgently", slug=self.slug)
        self.assertGreater(imp, 0.3)

    # ── C: Governor adaptativo ──

    def test_C_governor_learns_and_persists(self):
        """C: Governor — learn from feedback, thresholds adjust."""
        r = brain.governor_learn(self.slug, "merge_was_wrong")
        self.assertTrue(r["ok"])
        self.assertIn("duplicate_threshold", r["adjustments"])
        first = r["thresholds"]["duplicate_threshold"]

        r2 = brain.governor_learn(self.slug, "merge_was_wrong")
        self.assertLess(r2["thresholds"]["duplicate_threshold"], first)

        # Test positive feedback
        r3 = brain.governor_learn(self.slug, "merge_should_happen")
        self.assertGreater(r3["thresholds"]["duplicate_threshold"], r2["thresholds"]["duplicate_threshold"])

        # Verify persistence (re-read from DB)
        th = brain._get_governor_thresholds(self.slug)
        self.assertLess(th["duplicate_threshold"], 0.92)

    # ── D: Spiking Memory ──

    def test_D_spiking_memory_full_cycle(self):
        """D: Spiking Memory — spike, decay, hebbian, gc."""
        # Write test nodes first
        for i in range(5):
            nid = f"spike-node-{i}"
            brain.write(self.slug, "semantic", {
                "id": nid, "kind": "test", "content": f"spike test {i}",
                "importance": 0.3,
            })

        # Spike some nodes
        brain.spike_node(self.slug, "semantic", "spike-node-0", 0.5)
        brain.spike_node(self.slug, "semantic", "spike-node-1", 0.3)
        brain.spike_node(self.slug, "semantic", "spike-node-2", 0.1)

        # Hebbian link
        brain.hebbian_link(self.slug, "semantic", "spike-node-0", "spike-node-1", 0.2)

        # Decay
        brain.decay_potentials(self.slug, "semantic", 0.5)

        # GC by potential (dry run, just check it doesn't error)
        result = brain.gc_by_potential(self.slug, "semantic", threshold=0.05, dry_run=True)
        self.assertIn("pruned", result)

    # ── E: Conciencia Predictiva ──

    def test_E_conciencia_predicts_from_cycles(self):
        """E: Conciencia Predictiva — run cycles, then predict."""
        # Run some conciencia cycles to seed predictions
        for i in range(5):
            result = conciencia.run_cycle(
                self.slug,
                question=f"test query {i}",
                mode="plan",
            )
            self.assertIn("action", result)
            self.assertIn("prediction", result)

        # Now the next cycle should have prediction data
        result = conciencia.run_cycle(
            self.slug,
            question="test query similar to past",
            mode="plan",
        )
        self.assertIn("prediction", result)
        pred = result["prediction"]
        self.assertIn("method", pred)

    # ── FULL PIPELINE: Everything together ──

    def test_Z_full_neural_pipeline(self):
        """Full pipeline: seed data → classify → govern → spike → predict."""
        slug = "full-pipeline"
        schema.init_project(slug)

        # 1. Write observations (seeds kNN)
        brain.write_observation(slug, "decision", "db/migration",
                                "migrated database from postgres to mysql",
                                why="performance", outcome="success")
        brain.write_observation(slug, "decision", "api/endpoint",
                                "added user CRUD REST API",
                                why="feature", outcome="success")
        brain.write_observation(slug, "bugfix", "bugfix/general",
                                "fixed null pointer in login handler",
                                why="crash fix", outcome="success")

        # 2. Neural classify
        topic = obs.classify_topic_neural("migrate database", slug)
        self.assertIsInstance(topic, str)

        # 3. Governor learn
        brain.governor_learn(slug, "merge_was_wrong")

        # 4. Write and read (triggers spike)
        nodes = brain.list_nodes(slug, "semantic", limit=10)
        if nodes:
            nid = nodes[0]["id"]
            brain.read(slug, "semantic", nid)  # spikes via spike_read

        # 5. Conciencia predict
        result = conciencia.run_cycle(slug, question="migrate database", mode="plan")
        self.assertIn("action", result)
        self.assertIn("prediction", result)

        # Cleanup
        brain._reset_conn_cache()
        shutil.rmtree(shared.project_dir(slug), ignore_errors=True)
