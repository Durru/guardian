#!/usr/bin/env python3
"""
Tests for guardian_brain_schema and guardian_brain.

Zero external deps. Uses temp GUARDIAN_DATA to isolate from real /var/guardian.
"""

import json
import math
import os
import shutil
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

import guardian_brain  # noqa: E402
import guardian_brain_schema  # noqa: E402


def _unique_slug(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


from test_base import IsolatedTest


class TestSchema(IsolatedTest):

    def setUp(self):
        self.slug = _unique_slug("schema")

    def test_init_project_creates_all_4_dbs(self):
        result = guardian_brain_schema.init_project(self.slug)
        self.assertTrue(result["ok"])
        self.assertEqual(set(result["databases"].keys()),
                         {"semantic", "episodic", "procedural", "reflection"})
        for level in guardian_brain_schema.PROJECT_LEVELS:
            db = guardian_brain_schema.brain_db_path(self.slug, level)
            self.assertTrue(db.exists(), f"DB {level} should exist")

    def test_init_project_idempotent(self):
        guardian_brain_schema.init_project(self.slug)
        result = guardian_brain_schema.init_project(self.slug)
        self.assertTrue(result["ok"])
        for level, info in result["databases"].items():
            self.assertFalse(info["created"], f"{level} should not be re-created")

    def test_init_global_creates_3_dbs(self):
        result = guardian_brain_schema.init_global()
        self.assertTrue(result["ok"])
        self.assertEqual(set(result["databases"].keys()),
                         {"semantic", "procedural", "reflection"})
        for level in guardian_brain_schema.GLOBAL_LEVELS:
            db = guardian_brain_schema.global_db_path(level)
            self.assertTrue(db.exists(), f"Global DB {level} should exist")

    def test_status_reports_state(self):
        guardian_brain_schema.init_project(self.slug)
        result = guardian_brain_schema.status(self.slug)
        self.assertEqual(result["slug"], self.slug)
        for level in guardian_brain_schema.PROJECT_LEVELS:
            self.assertIn(level, result["project"])

    def test_path_helpers(self):
        self.assertEqual(
            guardian_brain_schema.brain_db_path("foo", "semantic").name,
            "semantic.db",
        )
        self.assertEqual(
            guardian_brain_schema.global_db_path("semantic_g").name,
            "semantic_global.db",
        )

    def test_invalid_level_raises(self):
        with self.assertRaises(ValueError):
            guardian_brain_schema.brain_db_path("foo", "bogus")
        with self.assertRaises(ValueError):
            guardian_brain_schema.global_db_path("bogus_g")


class TestEmbedding(unittest.TestCase):

    def test_embed_deterministic(self):
        e1 = guardian_brain.embed("hola mundo")
        e2 = guardian_brain.embed("hola mundo")
        self.assertEqual(e1, e2)

    def test_embed_dimension(self):
        vec = guardian_brain.embed_to_list("test")
        self.assertEqual(len(vec), guardian_brain.EMBED_DIM)

    def test_embed_normalized(self):
        vec = guardian_brain.embed_to_list("palabra una dos tres")
        norm = math.sqrt(sum(x * x for x in vec))
        self.assertAlmostEqual(norm, 1.0, places=5)

    def test_cosine_identical_is_one(self):
        text = "postgres database"
        self.assertAlmostEqual(guardian_brain.cosine_text(text, text), 1.0, places=5)

    def test_cosine_orthogonal_near_zero(self):
        sim = guardian_brain.cosine_text("postgres alpha", "xyz123 abc456")
        self.assertLess(sim, 0.5)

    def test_cosine_shared_tokens_higher(self):
        a = "el proyecto usa postgres"
        b = "postgres es la base de datos"
        c = "me gusta el cafe con leche"
        sim_ab = guardian_brain.cosine_text(a, b)
        sim_ac = guardian_brain.cosine_text(a, c)
        self.assertIsInstance(sim_ab, float)
        self.assertGreaterEqual(sim_ab, -1.0)
        self.assertLessEqual(sim_ab, 1.0)
        self.assertGreater(sim_ab, 0.0)


class TestStorage(unittest.TestCase):

    def setUp(self):
        self.slug = _unique_slug("storage")
        guardian_brain_schema.init_project(self.slug)

    def test_write_and_read(self):
        node = {"kind": "decision", "content": "usar postgres", "importance": 0.8}
        result = guardian_brain.write(self.slug, "semantic", node)
        self.assertTrue(result["ok"])
        nid = result["id"]
        self.assertTrue(nid.startswith("n_"))
        read_back = guardian_brain.read(self.slug, "semantic", nid)
        self.assertIsNotNone(read_back)
        self.assertEqual(read_back["content"], "usar postgres")
        self.assertEqual(read_back["kind"], "decision")
        self.assertEqual(read_back["importance"], 0.8)
        self.assertTrue(read_back["has_embedding"])

    def test_read_updates_access_count(self):
        node = {"kind": "decision", "content": "test access"}
        nid = guardian_brain.write(self.slug, "semantic", node)["id"]
        first = guardian_brain.read(self.slug, "semantic", nid)
        self.assertEqual(first["access_count"], 1)
        guardian_brain.read(self.slug, "semantic", nid)
        result = guardian_brain.read(self.slug, "semantic", nid)
        self.assertEqual(result["access_count"], 3)

    def test_query_finds_similar(self):
        guardian_brain.write(self.slug, "semantic", {"kind": "decision",
                                              "content": "el proyecto usa postgres 16",
                                              "importance": 0.9})
        guardian_brain.write(self.slug, "semantic", {"kind": "decision",
                                              "content": "el cafe tiene leche",
                                              "importance": 0.5})
        results = guardian_brain.query(self.slug, "semantic", "postgres database", top_k=5)
        self.assertGreater(len(results), 0)
        self.assertIn("postgres", results[0]["content"].lower())

    def test_query_empty_db(self):
        guardian_brain_schema.init_project("empty-slug")
        results = guardian_brain.query("empty-slug", "semantic", "anything")
        self.assertEqual(results, [])

    def test_list_nodes_with_filters(self):
        guardian_brain.write(self.slug, "semantic", {"kind": "decision", "content": "a", "importance": 0.9})
        guardian_brain.write(self.slug, "semantic", {"kind": "preference", "content": "b", "importance": 0.3})
        guardian_brain.write(self.slug, "semantic", {"kind": "decision", "content": "c", "importance": 0.7})
        all_nodes = guardian_brain.list_nodes(self.slug, "semantic")
        self.assertEqual(len(all_nodes), 3)
        only_decisions = guardian_brain.list_nodes(self.slug, "semantic", filters={"kind": "decision"})
        self.assertEqual(len(only_decisions), 2)
        important = guardian_brain.list_nodes(self.slug, "semantic", filters={"min_importance": 0.7})
        self.assertEqual(len(important), 2)

    def test_count(self):
        self.assertEqual(guardian_brain.count(self.slug, "semantic"), 0)
        guardian_brain.write(self.slug, "semantic", {"kind": "x", "content": "a"})
        guardian_brain.write(self.slug, "semantic", {"kind": "y", "content": "b"})
        self.assertEqual(guardian_brain.count(self.slug, "semantic"), 2)

    def test_delete(self):
        nid = guardian_brain.write(self.slug, "semantic", {"kind": "x", "content": "delete me"})["id"]
        self.assertEqual(guardian_brain.count(self.slug, "semantic"), 1)
        result = guardian_brain.delete(self.slug, "semantic", nid)
        self.assertTrue(result["ok"])
        self.assertEqual(result["deleted"], 1)
        self.assertEqual(guardian_brain.count(self.slug, "semantic"), 0)

    def test_node_id_deterministic(self):
        a = guardian_brain.write(self.slug, "semantic", {"kind": "x", "content": "same"})["id"]
        b = guardian_brain.write(self.slug, "semantic", {"kind": "x", "content": "same", "importance": 0.99})["id"]
        self.assertEqual(a, b)


class TestGovernor(unittest.TestCase):

    def setUp(self):
        self.slug = _unique_slug("governor")
        guardian_brain_schema.init_project(self.slug)

    def test_low_importance_discarded(self):
        node = {"kind": "decision", "content": "low importance thing", "importance": 0.2}
        result = guardian_brain.write_governed(self.slug, "semantic", node)
        self.assertEqual(result["action"], "discarded")

    def test_high_importance_written(self):
        node = {"kind": "decision", "content": "high importance thing", "importance": 0.8}
        result = guardian_brain.write_governed(self.slug, "semantic", node)
        self.assertEqual(result["action"], "wrote")
        self.assertEqual(guardian_brain.count(self.slug, "semantic"), 1)

    def test_duplicate_detected_and_merged(self):
        guardian_brain.write_governed(self.slug, "semantic",
                             {"kind": "decision", "content": "el proyecto usa postgres",
                              "importance": 0.8})
        result = guardian_brain.write_governed(self.slug, "semantic",
                                       {"kind": "decision", "content": "el proyecto usa postgres",
                                        "importance": 0.9})
        self.assertEqual(result["action"], "merged")
        self.assertEqual(guardian_brain.count(self.slug, "semantic"), 1)

    def test_gc_removes_low_importance_never_accessed(self):
        guardian_brain.write(self.slug, "semantic",
                    {"kind": "decision", "content": "low no access", "importance": 0.2})
        guardian_brain.write(self.slug, "semantic",
                    {"kind": "decision", "content": "high always", "importance": 0.9})
        result = guardian_brain.governor_gc(self.slug, "semantic", dry_run=False)
        self.assertEqual(result["removed"], 1)
        self.assertEqual(guardian_brain.count(self.slug, "semantic"), 1)

    def test_gc_archives_ttl_expired(self):
        import time
        past_ts = time.time() - (40 * 86400)
        guardian_brain.write(self.slug, "semantic",
                    {"kind": "decision", "content": "old ttl",
                     "importance": 0.7, "ttl": 30, "created_at": past_ts})
        guardian_brain.write(self.slug, "semantic",
                    {"kind": "decision", "content": "fresh", "importance": 0.7})
        result = guardian_brain.governor_gc(self.slug, "semantic", dry_run=False)
        self.assertEqual(result["archived"], 1)
        self.assertEqual(result["removed"], 0)

    def test_gc_dry_run_does_not_modify(self):
        guardian_brain.write(self.slug, "semantic",
                    {"kind": "decision", "content": "low no access", "importance": 0.2})
        result = guardian_brain.governor_gc(self.slug, "semantic", dry_run=True)
        self.assertEqual(result["removed"], 1)
        self.assertTrue(result["dry_run"])
        self.assertEqual(guardian_brain.count(self.slug, "semantic"), 1)


class TestGuardianMd(unittest.TestCase):

    def setUp(self):
        self.slug = _unique_slug("guardian-md")
        guardian_brain_schema.init_project(self.slug)

    def test_empty_project_no_guardian_md(self):
        content = guardian_brain.read_guardian_md(self.slug)
        self.assertEqual(content, "")

    def test_generate_guardian_md(self):
        guardian_brain.write(self.slug, "semantic", {"kind": "decision",
                                              "content": "usar postgres", "importance": 0.9,
                                              "topic_key": "db/postgres"})
        result = guardian_brain.regenerate_guardian_md(self.slug)
        self.assertTrue(result["ok"])
        self.assertGreater(result["lines"], 3)
        content = guardian_brain.read_guardian_md(self.slug)
        self.assertIn("postgres", content)
        self.assertIn("GUARDIAN", content)

    def test_guardian_md_line_limit(self):
        long_content = "# Test\n" + "\n".join([f"line {i}" for i in range(250)])
        result = guardian_brain.write_guardian_md(self.slug, long_content)
        self.assertTrue(result["truncated"])
        self.assertEqual(result["lines"], guardian_brain.GUARDIAN_MD_MAX_LINES)


class TestWorkingMemory(unittest.TestCase):

    def setUp(self):
        self.slug = _unique_slug("wm")
        guardian_brain_schema.init_project(self.slug)

    def test_read_empty_wm(self):
        wm = guardian_brain.read_working_memory(self.slug)
        self.assertIsNone(wm.get("goal"))
        self.assertIsNone(wm.get("task"))
        self.assertIsNone(wm.get("mode"))

    def test_set_and_get_wm(self):
        guardian_brain.set_working_memory(self.slug, goal="test", task="abc", mode="build")
        wm = guardian_brain.read_working_memory(self.slug)
        self.assertEqual(wm["goal"], "test")
        self.assertEqual(wm["task"], "abc")
        self.assertEqual(wm["mode"], "build")


class TestHandoff(unittest.TestCase):

    def setUp(self):
        self.slug = _unique_slug("handoff")
        guardian_brain_schema.init_project(self.slug)

    def test_handoff_roundtrip(self):
        handoff = {
            "goal": "build X", "task": "implement Y",
            "progress": ["✓ a", "→ b"], "mode": "build",
        }
        result = guardian_brain.write_handoff(self.slug, handoff)
        self.assertTrue(result["ok"])
        loaded = guardian_brain.read_handoff(self.slug)
        self.assertEqual(loaded["goal"], "build X")
        self.assertEqual(loaded["task"], "implement Y")
        self.assertEqual(loaded["mode"], "build")

    def test_handoff_none_when_missing(self):
        h = guardian_brain.read_handoff(self.slug)
        self.assertIsNone(h)


class TestContextBudget(unittest.TestCase):

    def setUp(self):
        self.slug = _unique_slug("budget")
        guardian_brain_schema.init_project(self.slug)
        for i in range(20):
            guardian_brain.write(self.slug, "semantic",
                        {"kind": "decision", "content": f"decision {i}",
                         "importance": 0.5 + i * 0.02})

    def test_build_context_respects_budget(self):
        context = guardian_brain.build_context(self.slug, mode="build")
        self.assertLessEqual(context["budget_used"]["semantic"], 800)
        self.assertGreater(len(context["levels"]["semantic"]), 0)

    def test_read_mode_allows_more_semantic(self):
        context = guardian_brain.build_context(self.slug, mode="read")
        self.assertLessEqual(context["budget_used"]["semantic"], 1500)

    def test_commit_mode_limits_episodic(self):
        context = guardian_brain.build_context(self.slug, mode="commit")
        self.assertEqual(context["budget_used"]["episodic"], 0)
        self.assertEqual(len(context["levels"]["episodic"]), 0)


class TestOrchestrator(unittest.TestCase):

    def setUp(self):
        self.slug = _unique_slug("orch")
        guardian_brain_schema.init_project(self.slug)
        guardian_brain.write(self.slug, "semantic", {"kind": "decision", "content": "usar postgres",
                                              "importance": 0.9})
        guardian_brain.write(self.slug, "procedural", {"kind": "workflow", "content": "deploy vercel",
                                                "importance": 0.8})
        guardian_brain.write(self.slug, "episodic", {"kind": "event", "content": "ayer deployé",
                                              "importance": 0.6})

    def test_how_question_queries_procedural(self):
        result = guardian_brain.orchestrate(self.slug, "cómo hago deploy")
        self.assertIn("procedural", result["levels_queried"])

    def test_what_question_queries_semantic(self):
        result = guardian_brain.orchestrate(self.slug, "qué decisión tomaste")
        self.assertIn("semantic", result["levels_queried"])

    def test_when_question_queries_episodic(self):
        result = guardian_brain.orchestrate(self.slug, "cuándo deployé")
        self.assertIn("episodic", result["levels_queried"])

    def test_default_to_semantic(self):
        result = guardian_brain.orchestrate(self.slug, "asdf qwerty")
        self.assertEqual(result["levels_queried"], ["semantic"])


class TestReflection(unittest.TestCase):

    def setUp(self):
        self.slug = _unique_slug("refl")
        guardian_brain_schema.init_project(self.slug)

    def test_reflection_no_events(self):
        result = guardian_brain.run_reflection(self.slug)
        self.assertEqual(result["events"], 0)
        self.assertEqual(result["promoted"], 0)

    def test_reflection_clusters_similar_events(self):
        guardian_brain.write(self.slug, "episodic", {"kind": "event",
                                             "content": "deployé el modulo a staging vercel"})
        guardian_brain.write(self.slug, "episodic", {"kind": "event",
                                             "content": "deployé el modulo a produccion vercel"})
        guardian_brain.write(self.slug, "episodic", {"kind": "event",
                                             "content": "deployé el modulo vercel"})
        result = guardian_brain.run_reflection(self.slug)
        self.assertEqual(result["events"], 3)
        self.assertEqual(result["clusters"], 1)
        self.assertGreaterEqual(len(result["candidates"]), 1)
        self.assertGreaterEqual(result["promoted"], 1)


class TestAutoCompact(unittest.TestCase):

    def setUp(self):
        self.slug = _unique_slug("compact")
        guardian_brain_schema.init_project(self.slug)

    def test_should_compact_empty_brain(self):
        result = guardian_brain.should_compact(self.slug)
        self.assertFalse(result["should"])
        self.assertEqual(result["triggers"], [])

    def test_should_compact_with_pressure(self):
        guardian_brain.GUARDIAN_MD_MAX_LINES = 30
        large = "# Big\n" + "\n".join([f"line {i}" for i in range(50)])
        guardian_brain.write_guardian_md(self.slug, large)
        result = guardian_brain.should_compact(self.slug)
        self.assertIn("guardian_md_pressure", str(result["triggers"]))

    def test_auto_compact_runs_gc(self):
        guardian_brain.write(self.slug, "semantic", {"kind": "x", "content": "low imp", "importance": 0.1})
        guardian_brain.write(self.slug, "semantic", {"kind": "x", "content": "high imp", "importance": 0.9})
        result = guardian_brain.auto_compact(self.slug, dry_run=False)
        self.assertGreaterEqual(result["gc_semantic"]["removed"], 1)


class TestSessionLifecycle(unittest.TestCase):

    def setUp(self):
        self.slug = _unique_slug("lifecycle")
        guardian_brain_schema.init_project(self.slug)

    def test_start_returns_greeting(self):
        result = guardian_brain.session_start(self.slug, mode="build")
        self.assertIn("build", result["mode"])
        self.assertIn("🛡️", result["greeting"])
        wm = guardian_brain.read_working_memory(self.slug)
        self.assertEqual(wm["mode"], "build")
        self.assertIsNotNone(wm["session_started_at"])

    def test_continue_restores_handoff(self):
        guardian_brain.session_end(self.slug, reason="test")
        result = guardian_brain.session_continue(self.slug)
        self.assertIsNotNone(result["handoff"])
        self.assertIn(result["mode"], (None, "read", "plan", "build"))

    def test_end_writes_handoff(self):
        guardian_brain.set_working_memory(self.slug, goal="X", task="Y", mode="build")
        guardian_brain.session_end(self.slug, reason="done")
        handoff = guardian_brain.read_handoff(self.slug)
        self.assertEqual(handoff["goal"], "X")
        self.assertEqual(handoff["task"], "Y")
        self.assertEqual(handoff["ended_in_mode"], "build")

    def test_end_runs_reflection(self):
        for content in ["deploy vercel", "deploy vercel", "deploy vercel"]:
            guardian_brain.write(self.slug, "episodic", {"kind": "event", "content": content})
        result = guardian_brain.session_end(self.slug)
        self.assertIn("reflection", result)
        self.assertIn("handoff", result)

    def test_full_lifecycle(self):
        guardian_brain.set_working_memory(self.slug, goal="build X", task="impl Y", mode="build")
        guardian_brain.write_governed(self.slug, "semantic",
                             {"kind": "decision", "content": "usar Z", "importance": 0.8})
        end = guardian_brain.session_end(self.slug)
        self.assertTrue(end["guardian_md"]["ok"])
        cont = guardian_brain.session_continue(self.slug)
        self.assertEqual(cont["working_memory"]["goal"], "build X")


class TestGlobal(unittest.TestCase):

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

    def test_global_promote(self):
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


if __name__ == "__main__":
    unittest.main()
