#!/usr/bin/env python3
"""Tests for Fase 3: knowledge, specialization, plan, maintain."""

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
import guardian_knowledge  # noqa: E402
import guardian_maintain  # noqa: E402
import guardian_plan  # noqa: E402
import guardian_specialization  # noqa: E402


def _unique_slug(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


from test_base import IsolatedTest


class TestKnowledge(IsolatedTest):

    def setUp(self):
        self.slug = _unique_slug("know")
        guardian_brain_schema.init_project(self.slug)

    def test_research_returns_plan(self):
        plan = guardian_knowledge.research(self.slug, "Odoo 17 chatter API")
        self.assertIn("kind", plan)
        self.assertIn("search_suggestions", plan)
        self.assertIn("node_templates", plan)
        self.assertIn("odoo", plan["stacks_detected"])

    def test_research_classifies_kind(self):
        plan = guardian_knowledge.research(self.slug, "common bugs and errors in the module")
        self.assertEqual(plan["kind"], "known_issues")
        plan = guardian_knowledge.research(self.slug, "best practice recommended pattern")
        self.assertEqual(plan["kind"], "best_practices")

    def test_write_research_creates_node(self):
        result = guardian_knowledge.write_research(
            self.slug, "research", "Odoo 17 uses message_post_with_source",
            tags=["odoo", "v17"], stack=["odoo"], importance=0.85
        )
        self.assertTrue(result.get("ok"))
        results = guardian_brain.query(self.slug, "semantic", "odoo chatter")
        self.assertGreater(len(results), 0)

    def test_list_knowledge(self):
        guardian_knowledge.write_research(self.slug, "research", "r1")
        guardian_knowledge.write_research(self.slug, "docs", "d1")
        guardian_brain.write_governed(self.slug, "semantic",
                                       {"kind": "decision", "content": "decision"})
        items = guardian_knowledge.list_knowledge(self.slug)
        self.assertEqual(len(items), 2)
        kinds = {n["kind"] for n in items}
        self.assertEqual(kinds, {"research", "docs"})

    def test_extract_tags(self):
        tags = guardian_knowledge._extract_tags("Working on #odoo v17 with #python")
        self.assertIn("odoo", tags)
        self.assertIn("python", tags)
        self.assertIn("v17", tags)


class TestSpecialization(IsolatedTest):

    def setUp(self):
        self.slug = _unique_slug("spec")
        guardian_brain_schema.init_project(self.slug)

    def test_list_available(self):
        result = guardian_specialization.list_available()
        self.assertGreater(len(result), 0)
        names = [s["name"] for s in result]
        self.assertIn("odoo", names)
        self.assertIn("nextjs", names)

    def test_show_builtin(self):
        result = guardian_specialization.show("odoo")
        self.assertTrue(result["ok"])
        self.assertIn("seed_knowledge", result["spec"])
        self.assertIn("seed_procedures", result["spec"])

    def test_enable_writes_nodes(self):
        result = guardian_specialization.enable(self.slug, "odoo")
        self.assertTrue(result["ok"])
        w = result["written"]
        self.assertGreater(w["semantic"], 0)
        self.assertGreater(w["procedural"], 0)
        status = guardian_brain.status(self.slug)
        self.assertEqual(status["levels"]["semantic"]["nodes"], w["semantic"])
        self.assertEqual(status["levels"]["procedural"]["nodes"], w["procedural"])

    def test_enable_then_query(self):
        guardian_specialization.enable(self.slug, "odoo")
        results = guardian_brain.query(self.slug, "semantic", "chatter odoo")
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertIn("odoo", r.get("source", ""))

    def test_disable_removes_from_enabled(self):
        guardian_specialization.enable(self.slug, "python")
        self.assertIn("python", guardian_specialization.list_enabled(self.slug))
        guardian_specialization.disable(self.slug, "python")
        self.assertNotIn("python", guardian_specialization.list_enabled(self.slug))


class TestPlan(IsolatedTest):

    def setUp(self):
        self.slug = _unique_slug("plan")
        guardian_brain_schema.init_project(self.slug)

    def test_new_plan_creates_files(self):
        result = guardian_plan.new_plan(self.slug, "Test plan", plan_type="full")
        self.assertTrue(result["ok"])
        plan_id = result["plan_id"]
        pd = guardian_brain_schema.plans_dir(self.slug) / plan_id
        self.assertTrue((pd / "proposal.md").exists())
        self.assertTrue((pd / "status.json").exists())

    def test_new_plan_quick(self):
        result = guardian_plan.new_plan(self.slug, "Quick fix", plan_type="quick")
        self.assertTrue(result["ok"])
        self.assertEqual(result["type"], "quick")

    def test_full_lifecycle(self):
        result = guardian_plan.new_plan(self.slug, "Migrate to v17", plan_type="full")
        plan_id = result["plan_id"]
        for target in ("specs", "designed", "tasks", "applying", "verifying"):
            t = guardian_plan.transition(self.slug, plan_id, target)
            self.assertTrue(t["ok"], f"failed transition to {target}: {t}")
        v = guardian_plan.verify(self.slug, plan_id, {"c1": {"ok": True}})
        self.assertTrue(v["ok"])
        self.assertTrue(v["verify_passed"])
        a = guardian_plan.archive(self.slug, plan_id)
        self.assertTrue(a["ok"])
        self.assertTrue((guardian_brain_schema.brain_dir(self.slug) / "plans" / "archive" / plan_id).exists())

    def test_invalid_transition_rejected(self):
        full = guardian_plan.new_plan(self.slug, "Full test", plan_type="full")
        pid = full["plan_id"]
        t = guardian_plan.transition(self.slug, pid, "designed")
        self.assertFalse(t["ok"])
        self.assertIn("invalid transition", t["error"])

    def test_list_plans(self):
        guardian_plan.new_plan(self.slug, "Plan 1")
        guardian_plan.new_plan(self.slug, "Plan 2")
        result = guardian_plan.list_plans(self.slug)
        self.assertEqual(len(result), 2)

    def test_archive_extracts_learning(self):
        result = guardian_plan.new_plan(self.slug, "Won plan", plan_type="full")
        plan_id = result["plan_id"]
        guardian_plan.transition(self.slug, plan_id, "specs")
        guardian_plan.transition(self.slug, plan_id, "applying")
        guardian_plan.transition(self.slug, plan_id, "verifying")
        guardian_plan.verify(self.slug, plan_id, {"c1": {"ok": True}})
        a = guardian_plan.archive(self.slug, plan_id)
        self.assertEqual(a["learnings_extracted"], 1)
        learnings = guardian_brain.list_nodes(self.slug, "reflection")
        self.assertGreater(len(learnings), 0)


class TestMaintain(IsolatedTest):

    def setUp(self):
        self.slug = _unique_slug("maint")
        guardian_brain_schema.init_project(self.slug)

    def test_health_report_empty(self):
        report = guardian_maintain.health_report(self.slug)
        self.assertEqual(report["slug"], self.slug)
        self.assertLess(report["health_score"], 100)
        self.assertIn("Brain is empty", report["issues"])

    def test_health_report_with_content(self):
        guardian_brain.write_governed(self.slug, "semantic",
                                       {"kind": "decision", "content": "use postgres",
                                        "importance": 0.8})
        guardian_brain.set_working_memory(self.slug, goal="X", task="Y", mode="build")
        report = guardian_maintain.health_report(self.slug)
        self.assertEqual(report["health_score"], 100)
        self.assertEqual(report["working_memory"]["goal"], "X")

    def test_format_report_is_string(self):
        report = guardian_maintain.health_report(self.slug)
        formatted = guardian_maintain.format_report(report)
        self.assertIsInstance(formatted, str)
        self.assertIn(self.slug, formatted)
        self.assertIn("Health", formatted)

    def test_drift_detection(self):
        project_root = self._tmpdir / "fake-project"
        project_root.mkdir()
        (project_root / "main.py").write_text(
            "import psycopg2\nconn = psycopg2.connect('postgresql://localhost')"
        )
        guardian_brain.write_governed(self.slug, "semantic",
                                       {"kind": "decision", "content": "use sqlite",
                                        "importance": 0.8})
        report = guardian_maintain.health_report(self.slug, project_root=str(project_root))
        self.assertGreater(report["drift"]["count"], 0)


if __name__ == "__main__":
    unittest.main()
