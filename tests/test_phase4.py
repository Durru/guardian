#!/usr/bin/env python3
"""Tests for Fase 4: global, capability, publish, lineage, migration."""

import json
import os
import shutil
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

import guardian_brain  # noqa: E402
import guardian_brain_migration  # noqa: E402
import guardian_brain_schema  # noqa: E402
import guardian_capability  # noqa: E402
import guardian_global  # noqa: E402
import guardian_lineage  # noqa: E402
import guardian_publish  # noqa: E402
import guardian_shared as shared  # noqa: E402


def _unique_slug(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


from test_base import IsolatedTest


class TestCapability(IsolatedTest):

    def test_status_returns_default_card(self):
        card = guardian_capability.load_card("test-status-card")
        self.assertEqual(card["model"], "test-status-card")
        self.assertEqual(card["sample_size"], 0)
        for task in guardian_capability.TASK_TYPES:
            self.assertIn(task, card["metrics"]["task_success_rate"])

    def test_measure_updates_card(self):
        result = guardian_capability.record_outcome(
            "code_generation", True, drift_score=0.1, model="test-measure-card"
        )
        self.assertTrue(result["ok"])
        card = guardian_capability.load_card("test-measure-card")
        self.assertEqual(card["sample_size"], 1)
        self.assertAlmostEqual(card["metrics"]["task_success_rate"]["code_generation"], 0.55, places=2)

    def test_routing_delegate_when_high_rate(self):
        for _ in range(5):
            guardian_capability.record_outcome("code_review", True, model="test-route-high")
        decision = guardian_capability.routing_decision("code_review", context_size=10000,
                                                        model="test-route-high")
        self.assertTrue(decision["delegate"])

    def test_routing_reject_when_low_rate(self):
        for _ in range(10):
            guardian_capability.record_outcome("debugging", False, model="test-route-low")
        decision = guardian_capability.routing_decision("debugging", context_size=1000,
                                                        model="test-route-low")
        self.assertFalse(decision["delegate"])

    def test_benchmark_runs(self):
        result = guardian_capability.benchmark(model="test-bench")
        self.assertTrue(result["ok"])


class TestGlobal(IsolatedTest):

    def setUp(self):
        guardian_brain_schema.init_global()

    def test_status_reports_global(self):
        result = guardian_brain_schema.status(None)
        self.assertIn("global", result)

    def test_search_global(self):
        result = guardian_brain.global_write("semantic_g", {
            "kind": "best_practices", "content": "odoo postgres config",
            "importance": 0.7, "stack": ["odoo", "postgres"]
        })
        self.assertTrue(result["ok"])
        results = guardian_brain.global_query("semantic_g", "odoo postgres")
        self.assertGreater(len(results), 0)

    def test_classify_for_global_decision_with_stack(self):
        node = {"kind": "decision", "content": "use postgres",
                "stack": ["postgres"]}
        result = guardian_global.classify_for_global(node, {"slug": "test"}, {})
        self.assertEqual(result["scope"], "global")

    def test_classify_for_global_decision_with_project_name(self):
        node = {"kind": "decision", "content": "el proyecto test-foo usa postgres"}
        result = guardian_global.classify_for_global(node, {"slug": "test-foo"}, {})
        self.assertEqual(result["scope"], "project")

    def test_promote_project_to_global(self):
        slug = _unique_slug("promote")
        guardian_brain_schema.init_project(slug)
        guardian_brain.write(slug, "semantic", {
            "kind": "best_practices", "content": "use postgres for high scale",
            "stack": ["postgres"], "importance": 0.8
        })
        nid = guardian_brain.list_nodes(slug, "semantic", limit=1)[0]["id"]
        result = guardian_brain.global_promote(slug, nid, "semantic")
        self.assertTrue(result["ok"])
        self.assertIn("promoted_id", result)


class TestPublish(IsolatedTest):

    def setUp(self):
        self.slug = _unique_slug("pub")
        guardian_brain_schema.init_project(self.slug)
        guardian_brain.write_governed(self.slug, "semantic", {
            "kind": "decision", "content": "el proyecto usa postgres",
            "importance": 0.8, "stack": ["postgres"]
        })
        guardian_brain.write_governed(self.slug, "procedural", {
            "kind": "workflow", "content": "deploy: vercel",
            "importance": 0.8
        })

    def test_publish_creates_template(self):
        result = guardian_publish.publish(self.slug, version="1.0.0")
        self.assertTrue(result["ok"])
        tpl_path = Path(result["target"])
        self.assertTrue(tpl_path.exists())
        self.assertTrue((tpl_path / "manifest.yaml").exists())
        self.assertTrue((tpl_path / "snapshot.json").exists())
        self.assertTrue((tpl_path / "checksums.json").exists())

    def test_clone_creates_new_project(self):
        guardian_publish.publish(self.slug, version="1.0.0")
        new_slug = _unique_slug("clone")
        result = guardian_publish.clone(self.slug, new_slug)
        self.assertTrue(result["ok"])
        results = guardian_brain.query(new_slug, "semantic", "postgres")
        self.assertGreater(len(results), 0)

    def test_fork_copies_with_lineage(self):
        guardian_brain.set_working_memory(self.slug, goal="X", task="Y", mode="build")
        child = _unique_slug("fork")
        result = guardian_publish.fork(self.slug, child)
        self.assertTrue(result["ok"])
        wm = guardian_brain.read_working_memory(child)
        self.assertEqual(wm.get("goal"), "X")

    def test_sanitize_redacts_secrets(self):
        text = "API key: sk-12345abcde and postgres://user:pass@host"
        sanitized = guardian_publish.sanitize_text(text)
        self.assertIn("REDACTED", sanitized)
        self.assertNotIn("sk-12345abcde", sanitized)
        self.assertNotIn("user:pass", sanitized)


class TestLineage(IsolatedTest):

    def setUp(self):
        self.slug = _unique_slug("lin")
        guardian_brain_schema.init_project(self.slug)

    def test_default_lineage(self):
        lineage = guardian_lineage.read_lineage(self.slug)
        self.assertIsNone(lineage["parent"])
        self.assertEqual(lineage["forks_made"], [])

    def test_record_parent(self):
        guardian_lineage.record_parent(self.slug, "parent-project")
        lineage = guardian_lineage.read_lineage(self.slug)
        self.assertEqual(lineage["parent"], "parent-project")

    def test_record_template(self):
        guardian_lineage.record_template_cloned(self.slug, "odoo", "1.0.0")
        lineage = guardian_lineage.read_lineage(self.slug)
        self.assertIn("odoo@1.0.0", lineage["templates_cloned"])

    def test_format_tree(self):
        guardian_lineage.record_parent(self.slug, "parent")
        guardian_lineage.record_template_cloned(self.slug, "odoo", "1.0")
        tree = guardian_lineage.format_tree(self.slug)
        self.assertIn(self.slug, tree)
        self.assertIn("parent", tree)
        self.assertIn("odoo@1.0", tree)


class TestMigration(IsolatedTest):

    def setUp(self):
        self.slug = _unique_slug("mig")
        v2_dir = shared.MEMORY_DIR / self.slug
        v2_dir.mkdir(parents=True, exist_ok=True)
        with open(v2_dir / "memory.jsonl", "w") as f:
            f.write(json.dumps({"id": "a1", "type": "decision",
                                "content": "usar postgres", "ts": "2026-01-01"}) + "\n")
            f.write(json.dumps({"id": "a2", "type": "pattern",
                                "content": "deploy vercel workflow", "ts": "2026-01-01"}) + "\n")
            f.write(json.dumps({"id": "a3", "type": "session",
                                "content": "sesion de desarrollo", "ts": "2026-01-01"}) + "\n")
        with open(v2_dir / "rag-chunks.json", "w") as f:
            json.dump({"chunks": [{"content": "el proyecto usa postgres en db.py",
                                    "source": "code"}]}, f)

    def test_status(self):
        result = guardian_brain_migration.status(self.slug)
        self.assertTrue(result["v2_memory_exists"])
        self.assertTrue(result["v2_rag_exists"])
        self.assertFalse(result["v3_brain_initialized"])

    def test_dry_run_does_not_modify(self):
        pre = guardian_brain_migration.status(self.slug)
        self.assertFalse(pre["v3_brain_initialized"])
        result = guardian_brain_migration.migrate(self.slug, dry_run=True)
        self.assertTrue(result["ok"])
        brain_dir = guardian_brain_schema.brain_dir(self.slug)
        sm_db = brain_dir / "semantic.db"
        if sm_db.exists():
            import sqlite3
            conn = sqlite3.connect(str(sm_db))
            count = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
            conn.close()
            self.assertEqual(count, 0)
        self.assertFalse(pre["v3_legacy_copied"])

    def test_real_migrate(self):
        result = guardian_brain_migration.migrate(self.slug, dry_run=False)
        self.assertTrue(result["ok"])
        self.assertGreater(result["migrated_to"]["semantic"] + result["migrated_to"]["procedural"], 0)
        status = guardian_brain_migration.status(self.slug)
        self.assertTrue(status["v3_brain_initialized"])
        self.assertTrue(status["v3_legacy_copied"])

    def test_classify_decision(self):
        result = guardian_brain_migration.classify_v2_kind("decision", "use postgres")
        self.assertEqual(result["level"], "semantic")
        self.assertEqual(result["kind"], "decision")

    def test_classify_pattern(self):
        result = guardian_brain_migration.classify_v2_kind("pattern", "deploy workflow")
        self.assertEqual(result["level"], "procedural")

    def test_classify_session(self):
        result = guardian_brain_migration.classify_v2_kind("session", "sesion")
        self.assertEqual(result["level"], "episodic")

    def test_rollback(self):
        guardian_brain_migration.migrate(self.slug, dry_run=False)
        result = guardian_brain_migration.rollback(self.slug)
        self.assertTrue(result["ok"])


if __name__ == "__main__":
    unittest.main()
