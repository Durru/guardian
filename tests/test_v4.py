#!/usr/bin/env python3
"""Tests for v4: filesystem, genoma, Conciencia, Observer, Advisor, BrainSymbols."""

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

_ORIG_ENV = {}


def _setup_env():
    """Set up isolated test environment. Must be called in setUpClass."""
    global _ORIG_ENV
    _ORIG_ENV = {
        "GUARDIAN_HOME": os.environ.get("GUARDIAN_HOME", ""),
        "GUARDIAN_DATA": os.environ.get("GUARDIAN_DATA", ""),
    }
    tmp = Path(tempfile.mkdtemp(prefix="guardian-v4-test-"))
    os.environ["GUARDIAN_DATA"] = str(tmp)
    os.environ["GUARDIAN_HOME"] = str(tmp)
    genome_dir = tmp / "genome"
    genome_dir.mkdir(parents=True, exist_ok=True)
    (genome_dir / "identity.yaml").write_text("""\
version: 4.5.0
creator: durru
identity:
  name: Nexxoria Guardian
  creator: durru
  principles:
    - "Proteger el proyecto antes que nada"
    - "Nunca sobrescribir sin preguntar"
    - "Razonar en base a lo que sabe, no a lo que se imagina"
""")
    return tmp


def _teardown_env():
    """Restore environment."""
    for k, v in _ORIG_ENV.items():
        if v:
            os.environ[k] = v
        else:
            os.environ.pop(k, None)


# ── v4 Filesystem ──────────────────────────────────────────────


class TestV4Filesystem(unittest.TestCase):

    def test_project_dir(self):
        import guardian_shared as shared
        p = shared.project_dir("test-proj-v45")
        self.assertTrue(p.exists())
        self.assertIn("projects/test-proj-v45", str(p))
        self.assertTrue((p / "brain").exists())


# ── v4 Genoma ───────────────────────────────────────────────────


class TestV4Genoma(unittest.TestCase):

    def setUp(self):
        self._old_home = os.environ.get("GUARDIAN_HOME", "")
        self._old_data = os.environ.get("GUARDIAN_DATA", "")
        self._tmp = Path(tempfile.mkdtemp(prefix="guardian-v4-test-"))
        os.environ["GUARDIAN_DATA"] = str(self._tmp)
        os.environ["GUARDIAN_HOME"] = str(self._tmp)
        genome_dir = self._tmp / "genome"
        genome_dir.mkdir(parents=True, exist_ok=True)
        (genome_dir / "identity.yaml").write_text("""\
version: 4.5.0
creator: durru
identity:
  name: Nexxoria Guardian
  creator: durru
  principles:
    - "Proteger el proyecto antes que nada"
""")

    def tearDown(self):
        if self._old_home:
            os.environ["GUARDIAN_HOME"] = self._old_home
        else:
            os.environ.pop("GUARDIAN_HOME", None)
        if self._old_data:
            os.environ["GUARDIAN_DATA"] = self._old_data
        else:
            os.environ.pop("GUARDIAN_DATA", None)
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_load_genome_3_files(self):
        import guardian_genome
        g = guardian_genome.load_genome()
        # Identity (yours, immutable)
        self.assertIn("identity", g)
        self.assertEqual(g["identity"]["name"], "Nexxoria Guardian")
        self.assertEqual(g["creator"], "durru")
        # Schema (v4)
        self.assertIn("schema", g)
        self.assertEqual(g["schema"]["schema_version"], 4)
        self.assertIn("codegraph_symbols", g["schema"]["brain"]["extended_levels"])
        # Consciousness (v4)
        self.assertIn("consciousness", g)
        self.assertEqual(g["consciousness"]["thresholds"]["assume"], 0.8)

    def test_apply_to_user_branch(self):
        import guardian_genome
        import guardian_shared as shared
        branch = shared.project_dir("genome-test")
        result = guardian_genome.apply_to_user_branch(branch)
        self.assertTrue(result["ok"])
        self.assertEqual(result["genome_version"], 4)
        self.assertTrue((branch / "branch.json").exists())


# ── v4 Conciencia ──────────────────────────────────────────────


class TestV4Conciencia(unittest.TestCase):

    def test_conciencia_knows_who_i_am(self):
        from guardian_conciencia import Conciencia
        c = Conciencia(slug="test")
        wai = c.who_am_i()
        self.assertEqual(wai["who_i_am"], "Nexxoria Guardian")
        self.assertEqual(wai["who_created_me"], "durru")

    def test_decide_is_traced(self):
        from guardian_conciencia import Conciencia
        c = Conciencia(slug="test")
        p = c.perceive({"question": "add auth"})
        p.sources = ["brain/semantic.db:n_123"]
        d = c.decide(p)
        # Every decision has sources
        self.assertIsNotNone(d.sources)
        # If no sources, action should be investigate (not assume)
        if not d.sources and d.action == "assume":
            self.fail("ASSUME without sources should not happen")

    def test_assume_requires_sources(self):
        from guardian_conciencia import Conciencia
        c = Conciencia(slug="test")
        # Build a percept with high confidence but no sources
        p = c.perceive({"question": "x", "context": {"has_goal": True, "has_task": True,
                                                       "guardian_md_lines": 100}})
        # Make sure no sources
        p.sources = []
        d = c.decide(p)
        # If action is 'assume' but no sources, that's a violation
        if d.action == "assume":
            self.fail("ASSUME without sources should not happen (tracability violation)")

    def test_who_am_i_has_principles(self):
        from guardian_conciencia import Conciencia
        c = Conciencia(slug="test")
        wai = c.who_am_i()
        self.assertIn("principles", wai)
        self.assertGreater(len(wai["principles"]), 0)


# ── v4 Observer ────────────────────────────────────────────────


class TestV4Observer(unittest.TestCase):

    def test_sanitize_removes_api_keys(self):
        from guardian_observer import sanitize
        text = "api_key=sk-abcdefghijklmnopqrstuvwxyz123456"
        out = sanitize(text)
        self.assertNotIn("sk-abcdef", out)
        self.assertIn("[REDACTED", out)

    def test_sanitize_removes_jwt(self):
        from guardian_observer import sanitize
        text = "Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        out = sanitize(text)
        self.assertIn("REDACTED", out)

    def test_sanitize_keeps_normal_text(self):
        from guardian_observer import sanitize
        text = "agregale un endpoint /users con auth jwt"
        out = sanitize(text)
        self.assertEqual(text, out)

    def test_infer_reason(self):
        from guardian_observer import infer_reason_from_prompt
        self.assertEqual(infer_reason_from_prompt("agregale auth"), "add_feature")
        self.assertEqual(infer_reason_from_prompt("fix the bug"), "fix_bug")
        self.assertEqual(infer_reason_from_prompt("delete this file"), "destructive")
        self.assertEqual(infer_reason_from_prompt("how does it work?"), "question")

    def test_observer_logs_events(self):
        import guardian_observer as obs
        o = obs.Observer("observer-test")
        o.observe({"type": "chat.message", "prompt": "test", "mode": "build"})
        o.observe({"type": "test.run", "passed": 5, "failed": 0, "runner": "pytest", "duration_s": 1.0})
        self.assertEqual(o.events_seen, 2)


# ── v4 BrainSymbols (codegraph) ────────────────────────────────


class TestV4BrainSymbols(unittest.TestCase):

    def test_lang_for_file(self):
        from guardian_brain_symbols import _lang_for_file
        self.assertEqual(_lang_for_file(Path("foo.py")), "python")
        self.assertEqual(_lang_for_file(Path("foo.ts")), "typescript")
        self.assertEqual(_lang_for_file(Path("foo.go")), "go")
        self.assertIsNone(_lang_for_file(Path("foo.txt")))

    def test_codegraph_lookup_returns_string(self):
        import guardian_brain_schema as schema
        from guardian_brain_symbols import get_codegraph
        schema.init_project("cg-test")
        cg = get_codegraph("cg-test")
        # Even without indexing, lookup returns "" (not None)
        result = cg.lookup("nonexistent", top_k=3)
        self.assertEqual(result, "")


# ── v4 Brain Advisor ───────────────────────────────────────────


class TestV4Advisor(unittest.TestCase):

    def test_build_context_no_garbage_when_unrelated(self):
        import guardian_brain_schema as schema
        from guardian_brain_advisor import Advisor
        schema.init_project("adv-test")
        a = Advisor("adv-test")
        # 'hello' is not a relevant keyword
        ctx = a.build_context("hello", max_tokens=1000)
        # Should be very short (just identity block) or empty
        self.assertLess(len(ctx), 500)

    def test_build_context_trims_to_max_tokens(self):
        import guardian_brain_schema as schema
        from guardian_brain_advisor import Advisor, _CHARS_PER_TOKEN
        schema.init_project("adv-test2")
        a = Advisor("adv-test2")
        ctx = a.build_context("add auth endpoint with jwt and data", max_tokens=10)
        # Should be truncated (max 40 chars + marker)
        self.assertLessEqual(len(ctx), 60)

    def test_advise_on_destructive(self):
        import guardian_brain_schema as schema
        from guardian_brain_advisor import Advisor
        schema.init_project("adv-test3")
        a = Advisor("adv-test3")
        result = a.advise_on_action({"tool": "Bash", "args": "rm -rf /tmp/foo"})
        self.assertIsNotNone(result)
        self.assertIn("Destructive", result.get("warn", ""))

    def test_advise_on_safe_returns_none(self):
        import guardian_brain_schema as schema
        from guardian_brain_advisor import Advisor
        schema.init_project("adv-test4")
        a = Advisor("adv-test4")
        result = a.advise_on_action({"tool": "Read", "file": "foo.py"})
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
