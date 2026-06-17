#!/usr/bin/env python3
"""Tests for v4.1.0 observation system: write_observation, get_observations, get_last_good, etc."""

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="guardian-obs-test-"))
os.environ["GUARDIAN_DATA"] = str(TMP)
os.environ["GUARDIAN_HOME"] = str(TMP)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

for m in list(sys.modules.keys()):
    if m.startswith("guardian"):
        del sys.modules[m]


SLUG = "obs-test-proj"


class TestObservations(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import guardian_brain_schema as schema
        schema.init_project(SLUG)

        import guardian_brain as brain
        brain.write(SLUG, "semantic", {
            "kind": "goal", "topic_key": "project/goal",
            "content": "obs-test project", "importance": 0.8,
        })

    def test_1_write_and_get_observation(self):
        import guardian_brain as brain
        result = brain.write_observation(
            SLUG, "decision", "db/migration",
            "Se migró PostgreSQL a MySQL",
            why="Cliente cambió hosting",
            location="base de datos completa",
            outcome="success",
            scope="project",
            tags=["postgresql", "mysql", "migration"],
        )
        self.assertIsNotNone(result)
        self.assertIn("id", result or {})

        obs = brain.get_observations(SLUG, "db/migration", limit=5)
        self.assertGreater(len(obs), 0)
        self.assertIn("db/migration", str(obs[0].get("topic_key", "")))

    def test_2_get_last_good(self):
        import guardian_brain as brain
        brain.write_observation(
            SLUG, "error", "db/migration",
            "Collation mismatch: UTF8 vs utf8mb4",
            why="Character set no convertido",
            outcome="failure",
        )
        brain.write_observation(
            SLUG, "decision", "db/migration",
            "Se migró PostgreSQL a MySQL correctamente",
            why="Cliente cambió hosting",
            outcome="success",
        )

        last = brain.get_last_good(SLUG, "db/migration")
        self.assertIsNotNone(last)
        self.assertEqual(last.get("outcome"), "success")

    def test_3_write_global_observation(self):
        import guardian_brain as brain
        import guardian_brain_schema as schema

        brain.write_observation(
            SLUG, "architecture", "auth/jwt",
            "Usar JWT sin refresh tokens, sesión 24h",
            why="Simplificar arquitectura",
            outcome="decision",
            scope="global",
            tags=["auth", "jwt"],
        )

        obs = brain.get_observations(SLUG, "auth/jwt", limit=5, global_too=True)
        self.assertGreater(len(obs), 0)
        topic_keys = [o.get("topic_key") for o in obs]
        self.assertTrue(any("auth/jwt" in str(t) for t in topic_keys))

    def test_4_append_and_compact_guardian_md(self):
        import guardian_brain as brain
        import guardian_brain_schema as schema

        md_path = schema.guardian_md_path(SLUG)
        if md_path.exists():
            md_path.unlink()

        brain.append_guardian_md_line(SLUG, "decision", "test/1", "success", "first line")
        brain.append_guardian_md_line(SLUG, "decision", "test/2", "info", "second line")

        content = brain.read_guardian_md(SLUG)
        self.assertIn("first line", content)
        self.assertIn("second line", content)

        # Write many lines to trigger compaction
        for i in range(40):
            brain.append_guardian_md_line(SLUG, "note", f"test/bulk{i}", "info", f"bulk line {i}")

        content_after = brain.read_guardian_md(SLUG)
        lines = content_after.splitlines()
        self.assertLessEqual(len(lines), brain.GUARDIAN_MD_MAX_LINES + 2)

    def test_5_classify_importance(self):
        from guardian_observer import classify_importance, extract_topic_key

        self.assertAlmostEqual(classify_importance(""), 0.3)
        self.assertAlmostEqual(classify_importance("fix bug"), 0.38, places=1)
        self.assertAlmostEqual(classify_importance("migrate entire db"), 0.5, places=1)
        self.assertEqual(classify_importance("x", "tool.execute.after"), 0.6)

        self.assertEqual(extract_topic_key("migrar la db de postgres a mysql"), "db/migration")
        self.assertEqual(extract_topic_key("agregar auth con jwt"), "auth/jwt")
        self.assertEqual(extract_topic_key("hola mundo"), "")

    def test_6_cli_analyze_intent(self):
        from guardian import cmd_analyze_intent
        import io, contextlib, json

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cmd_analyze_intent(["migrar la db de postgres a mysql"])
        result = json.loads(buf.getvalue())
        self.assertEqual(result["topic_key"], "db/migration")
        self.assertTrue(result["has_context"])

    def test_7_cli_plan_or_act(self):
        from guardian import cmd_plan_or_act
        import io, contextlib, json

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cmd_plan_or_act(["migrar la db", "--confidence=0.9"])
        result = json.loads(buf.getvalue())
        self.assertIn(result["action"], ("assume", "ask_little", "plan", "investigate"))

    def test_8_compact_memory(self):
        import guardian_brain as brain
        import guardian_brain_schema as schema

        md_path = schema.guardian_md_path(SLUG)

        md_path.parent.mkdir(parents=True, exist_ok=True)
        long_content = "# GUARDIAN — test\n" + "\n".join([f"- line {i}" for i in range(45)])
        md_path.write_text(long_content, encoding="utf-8")

        result = brain.compact_guardian_md(SLUG)
        self.assertTrue(result["ok"])
        self.assertGreater(result["removed"], 0)

    def test_9_get_observations_no_match(self):
        import guardian_brain as brain
        obs = brain.get_observations(SLUG, "nonexistent/topic", limit=5)
        self.assertEqual(len(obs), 0)

    def test_10_extract_topic_key_no_match(self):
        from guardian_observer import extract_topic_key
        self.assertEqual(extract_topic_key("hola que tal"), "")
        self.assertEqual(extract_topic_key(""), "")


if __name__ == "__main__":
    unittest.main()
