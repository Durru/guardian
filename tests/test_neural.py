"""Tests for v4.5.1 neural features: embeddings, kNN, governor_learn, spiking memory."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

import guardian_brain as brain
import guardian_brain_schema as schema
import guardian_shared as shared


class TestEmbeddings(unittest.TestCase):
    def test_embed_returns_bytes(self):
        e = brain.embed("test text for embedding")
        self.assertIsInstance(e, bytes)
        self.assertEqual(len(e), 1024)  # 256 floats * 4 bytes

    def test_embed_deterministic(self):
        e1 = brain.embed("same text")
        e2 = brain.embed("same text")
        self.assertEqual(e1, e2)

    def test_embed_differs_for_different_text(self):
        e1 = brain.embed("hello world")
        e2 = brain.embed("goodbye world")
        self.assertNotEqual(e1, e2)

    def test_cosine_identical(self):
        e = brain.embed("test")
        self.assertAlmostEqual(brain.cosine(e, e), 1.0)

    def test_cosine_orthogonal(self):
        a = brain.embed("python programming database query")
        b = brain.embed("quantum physics particle wave")
        # Different enough that they're not identical
        self.assertLess(brain.cosine(a, b), 0.8)

    def test_embed_to_list_length(self):
        lst = brain.embed_to_list("test")
        self.assertEqual(len(lst), 256)

    def test_cosine_bulk(self):
        q = brain.embed("query")
        candidates = [brain.embed("query"), brain.embed("different")]
        sims = brain.cosine_bulk(q, candidates)
        self.assertEqual(len(sims), 2)
        self.assertGreater(sims[0], sims[1])


class TestGovernorLearn(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.slug = "test-gov-learn"
        shared.MEMORY_DIR = self.tmpdir
        shared.BACKEND_DIR = self.tmpdir
        schema.init_project(self.slug)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_learn_merge_was_wrong(self):
        r = brain.governor_learn(self.slug, "merge_was_wrong")
        self.assertTrue(r["ok"])
        self.assertIn("duplicate_threshold", r["adjustments"])
        self.assertLess(r["thresholds"]["duplicate_threshold"], 0.92)

    def test_learn_discard_was_wrong(self):
        r = brain.governor_learn(self.slug, "discard_was_wrong")
        self.assertTrue(r["ok"])
        self.assertLess(r["thresholds"]["importance_floor"], 0.4)

    def test_learn_compounds(self):
        brain.governor_learn(self.slug, "merge_was_wrong")
        brain.governor_learn(self.slug, "merge_was_wrong")
        brain.governor_learn(self.slug, "merge_was_wrong")
        r = brain.governor_learn(self.slug, "merge_was_wrong")
        self.assertAlmostEqual(r["thresholds"]["duplicate_threshold"], 0.84)

    def test_learn_has_minimum(self):
        for _ in range(20):
            brain.governor_learn(self.slug, "merge_was_wrong")
        r = brain.governor_learn(self.slug, "merge_was_wrong")
        self.assertGreaterEqual(r["thresholds"]["duplicate_threshold"], 0.70)

    def test_learn_all_feedback_types(self):
        types = ["merge_was_wrong", "discard_was_wrong", "contradiction_was_false",
                 "merge_should_happen", "discard_should_happen", "contradiction_was_correct"]
        for fb in types:
            r = brain.governor_learn(self.slug, fb)
            self.assertTrue(r["ok"], f"Failed for {fb}")
            self.assertIn(fb, str(r["feedback"]))


class TestSpikingMemory(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.slug = "test-spike"
        shared.MEMORY_DIR = self.tmpdir
        shared.BACKEND_DIR = self.tmpdir
        brain._reset_conn_cache()
        schema.init_project(self.slug)

    def tearDown(self):
        brain._reset_conn_cache()
        shutil.rmtree(self.tmpdir)

    def test_spike_node_creates_potential(self):
        r = brain.spike_node(self.slug, "semantic", "test-node-1", 0.5)
        self.assertTrue(r["ok"])

    def test_spike_node_increases_potential(self):
        brain.spike_node(self.slug, "semantic", "test-node-2", 0.3)
        brain.spike_node(self.slug, "semantic", "test-node-2", 0.3)
        brain.spike_node(self.slug, "semantic", "test-node-2", 0.3)
        db = schema.brain_db_path(self.slug, "semantic")
        import sqlite3
        conn = sqlite3.connect(str(db))
        row = conn.execute(
            "SELECT potential FROM activation_potentials WHERE node_id = ?",
            ("test-node-2",),
        ).fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertGreater(row[0], 0.5)

    def test_decay_reduces_potential(self):
        brain.spike_node(self.slug, "semantic", "test-node-3", 0.5)
        brain.decay_potentials(self.slug, "semantic", 0.5)
        db = schema.brain_db_path(self.slug, "semantic")
        import sqlite3
        conn = sqlite3.connect(str(db))
        row = conn.execute(
            "SELECT potential FROM activation_potentials WHERE node_id = ?",
            ("test-node-3",),
        ).fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertLess(row[0], 0.5)

    def test_hebbian_link(self):
        r = brain.hebbian_link(self.slug, "semantic", "node-a", "node-b", 0.2)
        self.assertTrue(r["ok"])

    def test_hebbian_link_self_fails(self):
        r = brain.hebbian_link(self.slug, "semantic", "self", "self")
        self.assertFalse(r["ok"])

    def test_gc_by_potential_dry_run(self):
        brain.spike_node(self.slug, "semantic", "keep-node", 0.5)
        r = brain.gc_by_potential(self.slug, "semantic", threshold=0.3, dry_run=True)
        self.assertTrue(r["ok"])
        self.assertIn("pruned", r)


class TestNeuralClassifier(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.slug = f"test-cls-{id(self)}"
        shared.MEMORY_DIR = self.tmpdir
        shared.BACKEND_DIR = self.tmpdir
        brain._reset_conn_cache()
        schema.init_project(self.slug)

    def tearDown(self):
        brain._reset_conn_cache()
        shutil.rmtree(self.tmpdir)

    def test_record_feedback(self):
        import guardian_observer as obs
        obs.record_feedback(self.slug, "test feedback content", "test/topic")
        brain._reset_conn_cache()
        results = brain.list_nodes(self.slug, "semantic", filters={"topic_key": "test/topic"}, limit=10)
        self.assertGreaterEqual(len(results), 1)

    def test_classify_topic_heuristic_fallback(self):
        import guardian_observer as obs
        t = obs.classify_topic_neural("migrate database to postgres", self.slug)
        self.assertIn(t, ("db/migration", ""))

    def test_classify_importance_neural_fallback(self):
        import guardian_observer as obs
        imp = obs.classify_importance_neural("fix critical bug in production", slug=self.slug)
        self.assertGreater(imp, 0.3)

    def test_knn_with_feedback_data(self):
        import guardian_observer as obs
        obs.record_feedback(self.slug, "need to migrate database", "db/migration")
        obs.record_feedback(self.slug, "add new API endpoint", "api/endpoint")
        obs.record_feedback(self.slug, "fix login bug", "bugfix/general")
        t = obs.classify_topic_neural("migrate from mysql", self.slug)
        self.assertIsInstance(t, str)


class TestListNodesIncludeEmbedding(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.slug = "test-list-emb"
        shared.MEMORY_DIR = self.tmpdir
        shared.BACKEND_DIR = self.tmpdir
        schema.init_project(self.slug)
        brain.write(self.slug, "semantic", {
            "kind": "note", "content": "test with embedding",
            "topic_key": "test/emb", "importance": 0.6,
        })

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_list_nodes_with_embedding(self):
        nodes = brain.list_nodes(self.slug, "semantic", include_embedding=True)
        self.assertGreater(len(nodes), 0)
        self.assertIn("embedding", nodes[0])

    def test_list_nodes_without_embedding(self):
        nodes = brain.list_nodes(self.slug, "semantic", include_embedding=False)
        self.assertGreater(len(nodes), 0)
        self.assertNotIn("embedding", nodes[0])


if __name__ == "__main__":
    unittest.main()
