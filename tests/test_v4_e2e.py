#!/usr/bin/env python3
"""Tests E2E v4 — ciclo completo: filesystem → genoma → conciencia → advisor → observer → codegraph.

Ejercita el pipeline completo que PLAN_V4 describe en D18-19.
"""

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path


SLUG = "e2e-test-proj"


class TestV4E2E(unittest.TestCase):
    """End-to-end: v4 cycle completo."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="guardian-v4-e2e-"))
        os.environ["GUARDIAN_DATA"] = str(cls.tmpdir)
        os.environ["GUARDIAN_HOME"] = str(cls.tmpdir)
        os.environ["GUARDIAN_MACHINE_ID"] = "e2e-test-machine"

        # Setup minimal genome
        genome_dir = cls.tmpdir / "genome"
        genome_dir.mkdir(parents=True, exist_ok=True)
        (genome_dir / "identity.yaml").write_text("""\
version: 4.0.0
creator: durru
identity:
  name: Nexxoria Guardian E2E
  creator: durru
  principles:
    - "Test the full cycle"
""")
        (genome_dir / "schema.yaml").write_text("""\
schema_version: 4
brain:
  levels:
    - semantic
    - episodic
    - procedural
    - reflection
  extended_levels:
    - codegraph_symbols
""")
        (genome_dir / "consciousness.yaml").write_text("""\
default_mode: plan
thresholds:
  assume: 0.8
  ask_little_floor: 0.5
  ask_much_floor: 0.2
tracability:
  require_sources_for_assume: true
""")

        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

        for m in list(sys.modules.keys()):
            if m.startswith("guardian"):
                del sys.modules[m]

        # Project root with source files
        cls.project_root = cls.tmpdir / "projects" / SLUG
        cls.project_root.mkdir(parents=True, exist_ok=True)
        (cls.project_root / "config.yaml").write_text(
            json.dumps({"slug": SLUG, "project_root": str(cls.project_root), "stack": {}, "created_at": time.time()})
        )

        # Create mini source files for codegraph
        (cls.project_root / "src").mkdir(exist_ok=True)
        (cls.project_root / "src" / "main.py").write_text("""\
def hello(name: str) -> str:
    return f"Hello, {name}!"

class Calculator:
    def add(self, a: int, b: int) -> int:
        return a + b
""")
        (cls.project_root / "src" / "utils.ts").write_text("""\
export function formatDate(date: Date): string {
    return date.toISOString();
}
""")

    def setUp(self):
        import guardian_shared as shared
        root = shared.project_dir(SLUG)
        (root / "mode-state.json").write_text(
            json.dumps({"mode": "plan", "updated_at": time.time()})
        )

    def test_1_filesystem_v4_layout(self):
        """Verify v4 filesystem layout exists."""
        import guardian_shared as shared
        root = shared.project_dir(SLUG)
        self.assertTrue(root.exists())
        self.assertIn(SLUG, str(root))
        self.assertTrue((root / "brain").exists())

    def test_2_genome_3_files(self):
        """Verify genoma is loaded from 3 files."""
        import guardian_genome
        g = guardian_genome.load_genome()
        self.assertEqual(g["identity"]["name"], "Nexxoria Guardian E2E")
        self.assertIn("schema", g)
        self.assertEqual(g["schema"]["schema_version"], 4)
        self.assertIn("consciousness", g)
        self.assertEqual(g["consciousness"]["thresholds"]["assume"], 0.8)

    def test_3_conciencia_cycle_with_advisor_integration(self):
        """Full conciencia cycle with D15 Advisor integration."""
        from guardian_conciencia import Conciencia

        c = Conciencia(slug=SLUG)
        self.assertEqual(c.who_i_am, "Nexxoria Guardian E2E")
        self.assertEqual(str(c.creator), "durru")

        # Perceive with advisor enrichment
        p = c.perceive({"question": "add auth endpoint", "explicit_question": True, "context": {"has_goal": True}})
        self.assertIsNotNone(p)
        self.assertGreaterEqual(len(p.sources), 1)

        # Enriched by advisor?
        has_advisor = any("advisor" in s for s in p.sources)
        self.assertTrue(has_advisor, "Advisor should enrich perception (D15)")

        # Decide with sources
        d = c.decide(p)
        self.assertIsNotNone(d)
        self.assertIsNotNone(d.sources)
        self.assertIn(d.action, ("assume", "ask_little", "ask_much", "investigate"))

        # If action is assume, must have sources
        if d.action == "assume":
            self.assertGreater(len(d.sources), 0, "ASSUME requires sources")

        # who_am_i has principles
        wai = c.who_am_i()
        self.assertIn("principles", wai)

    def test_4_codegraph_tree_sitter_index_query(self):
        """CodeGraph: full index + query_smart."""
        import guardian_brain_symbols as symbols
        import guardian_brain_schema as schema

        schema.init_project(SLUG)
        cg = symbols.get_codegraph(SLUG)

        # Before index: no symbols
        self.assertFalse(cg.has_index())

        # Full index
        result = cg.full_index(self.project_root)
        self.assertGreater(result["files_indexed"], 0, "Should index at least 1 file")
        self.assertGreater(result["symbols"], 0, "Should find at least 1 symbol")

        # After index: has symbols
        self.assertTrue(cg.has_index())

        # Lookup by query
        lookup_result = cg.lookup("hello", top_k=5)
        self.assertIsNotNone(lookup_result)
        self.assertIn("hello", lookup_result)

        # query_smart
        smart = cg.lookup_smart("Calculator", top_k=5)
        self.assertIsNotNone(smart)
        self.assertIn("Calculator", smart)

        # Module-level query_smart
        smart2 = symbols.query_smart(SLUG, "formatDate", top_k=5)
        self.assertIsNotNone(smart2)
        self.assertIn("formatDate", smart2)

    def test_5_observer_sanitize_and_classify(self):
        """Observer: sanitize secrets + classify prompts."""
        import guardian_observer as obs

        # Sanitize API keys
        clean = obs.sanitize("api_key=sk-abcdefghijklmnopqrstuvwxyz123456")
        self.assertNotIn("sk-abcdefgh", clean)
        self.assertIn("[REDACTED", clean)

        # Sanitize JWT
        jwt_text = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        clean_jwt = obs.sanitize(jwt_text)
        self.assertIn("REDACTED", clean_jwt)

        # Normal text preserved
        self.assertEqual(obs.sanitize("add a /users endpoint"), "add a /users endpoint")

        # Classify prompts
        self.assertEqual(obs.infer_reason_from_prompt("add auth"), "add_feature")
        self.assertEqual(obs.infer_reason_from_prompt("fix bug"), "fix_bug")
        self.assertEqual(obs.infer_reason_from_prompt("how does it work?"), "question")

        # Observer logs events
        o = obs.Observer(SLUG)
        o.observe({"type": "chat.message", "prompt": "test", "mode": "build"})
        o.observe({"type": "test.run", "passed": 5, "failed": 0, "runner": "pytest", "duration_s": 1.0})
        self.assertEqual(o.events_seen, 2)

    def test_6_advisor_build_context(self):
        """Advisor: build_context returns '' when nothing relevant, warns on destructive."""
        import guardian_brain_schema as schema
        from guardian_brain_advisor import Advisor

        schema.init_project(SLUG)
        a = Advisor(SLUG)

        # Empty/irrelevant prompt → short or empty
        ctx = a.build_context("", max_tokens=1000)
        self.assertLess(len(ctx), 500)

        # Relevant prompt → has context
        ctx_rel = a.build_context("add auth endpoint with jwt", max_tokens=1000)
        self.assertGreater(len(ctx_rel), 0)

        # Trims to max_tokens
        ctx_trimmed = a.build_context("add auth endpoint with jwt and data", max_tokens=10)
        self.assertLessEqual(len(ctx_trimmed), 60)

        # Warn on destructive action
        warn = a.advise_on_action({"tool": "Bash", "args": "rm -rf /tmp/foo"})
        self.assertIsNotNone(warn)
        self.assertIn("Destructive", warn.get("warn", ""))

        # Safe action → None
        safe = a.advise_on_action({"tool": "Read", "file": "foo.py"})
        self.assertIsNone(safe)

    def test_7_migration_v3_to_v4_detect(self):
        """Migration module: status detection."""
        import guardian_migration_v3_layout as migration

        # Status should detect project even without v3 data (v4 path created by project_dir)
        s = migration.status(SLUG)
        self.assertEqual(s["slug"], SLUG)
        self.assertIn("v3_exists", s)
        self.assertIn("v4_config_synced", s)

    def test_8_migration_v3_to_v4_migrate(self):
        """Migration: simulate v3→v4 with dry-run."""
        import guardian_migration_v3_layout as migration

        # Create v3-like directory structure
        v3_dir = self.tmpdir / "projects" / "v3-legacy-slug"
        v3_dir.mkdir(parents=True, exist_ok=True)
        (v3_dir / "config.yaml").write_text(f"slug: v3-legacy-slug\nproject_root: {self.project_root}\n")
        (v3_dir / "memory.jsonl").write_text('{"type": "session", "ts": 1}\n{"type": "decision", "ts": 2}\n')
        (v3_dir / "conciencia-state.json").write_text('{"cycles": [], "last_action": "assume"}')
        (v3_dir / "conciencia-thresholds.json").write_text('{"assume": 0.8, "ask_little_floor": 0.5}')

        # Dry-run migration
        result = migration.migrate("v3-legacy-slug", dry_run=True)
        self.assertTrue(result["ok"])
        self.assertTrue(result["dry_run"])
        self.assertGreater(len(result["steps"]), 0)

    def test_9_full_cycle_activate_like(self):
        """Simulate 'guardian activate' pipeline: perceive → decide → reflect."""
        from guardian_conciencia import Conciencia

        c = Conciencia(slug=SLUG)

        # Like cmd_activate would do
        event = {
            "question": "activate guardian on this project",
            "explicit_question": True,
            "context": {"has_goal": True, "has_task": True, "guardian_md_lines": 50},
        }

        p = c.perceive(event)
        d = c.decide(p)

        # Must have sources from advisor integration
        self.assertGreater(len(p.sources), 0)
        self.assertIsNotNone(d.reason)

        # If confidence is high and sources exist, should assume
        if d.action == "assume":
            self.assertGreater(len(d.sources), 0)
            self.assertEqual(d.risk, "low")

    def test_10_n2_meta_never_alucinates(self):
        """N2 meta never invents. Percept without sources → not assume."""
        from guardian_conciencia import Conciencia

        c = Conciencia(slug=SLUG)

        # Event with no context, no question, no sources
        event = {"question": ""}
        p = c.perceive(event)

        # Strip advisor sources to test no-sources path
        p.sources = [s for s in p.sources if "advisor" not in s]

        d = c.decide(p)

        # Without sources and no context, should NOT assume
        if not d.sources:
            self.assertNotEqual(d.action, "assume",
                                "Should not ASSUME without sources (tracability rule #4)")

    def test_11_conciencia_who_am_i(self):
        """who_am_i always returns identity with principles."""
        from guardian_conciencia import Conciencia
        c = Conciencia(slug=SLUG)
        wai = c.who_am_i()
        self.assertEqual(wai["who_i_am"], "Nexxoria Guardian E2E")
        self.assertEqual(wai["who_created_me"], "durru")
        self.assertGreater(len(wai["principles"]), 0)

    def test_12_advisor_build_context_returns_empty_when_nothing(self):
        """Advisor returns '' when prompt has no relevant keywords (Rule #3)."""
        import guardian_brain_schema as schema
        from guardian_brain_advisor import Advisor
        schema.init_project("adv-e2e-empty")
        a = Advisor("adv-e2e-empty")
        ctx = a.build_context("hello world this is a test", max_tokens=1000)
        self.assertLess(len(ctx), 500,
                        "Advisor should return '' or very short when nothing relevant")


if __name__ == "__main__":
    unittest.main()
