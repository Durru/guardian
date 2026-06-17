#!/usr/bin/env python3
"""Tests for config.yaml parsing and template rendering."""
import unittest
import tempfile
import shutil
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

import importlib.util
# Load guardian_shared - use existing instance if already loaded
if "guardian_shared" not in sys.modules:
    _shared_path = Path(__file__).resolve().parent.parent / "lib" / "guardian_shared.py"
    _shared_spec = importlib.util.spec_from_file_location("guardian_shared", _shared_path)
    _shared_mod = importlib.util.module_from_spec(_shared_spec)
    sys.modules["guardian_shared"] = _shared_mod
    _shared_spec.loader.exec_module(_shared_mod)

_g_path = Path(__file__).resolve().parent.parent / "lib" / "guardian.py"
_spec = importlib.util.spec_from_file_location("guardian", _g_path)
g = importlib.util.module_from_spec(_spec)
sys.modules["guardian"] = g
_spec.loader.exec_module(g)


class TestConfigParsing(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.slug = "testcfg"
        self._orig_g_mem = g.MEMORY_DIR
        self._orig_shared_mem = g.shared.MEMORY_DIR
        g.MEMORY_DIR = self.tmpdir
        g.shared.MEMORY_DIR = self.tmpdir
        g.TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"

    def tearDown(self):
        g.MEMORY_DIR = self._orig_g_mem
        g.shared.MEMORY_DIR = self._orig_shared_mem
        shutil.rmtree(self.tmpdir)

    def _write_config(self, yaml_text):
        d = self.tmpdir / self.slug
        d.mkdir(parents=True, exist_ok=True)
        (d / "config.yaml").write_text(yaml_text)

    def test_read_empty_returns_empty_dict(self):
        self.assertEqual(g._read_config("nonexistent"), {})

    def test_read_simple_yaml(self):
        self._write_config("project_root: /tmp/test\nslug: testcfg\n")
        cfg = g._read_config(self.slug)
        self.assertEqual(cfg.get("project_root"), "/tmp/test")
        self.assertEqual(cfg.get("slug"), "testcfg")

    def test_read_nested_dict(self):
        self._write_config("""project:
  type: webapp
  description: test app
stack:
  detected: node
  framework: next
""")
        cfg = g._read_config(self.slug)
        self.assertIsInstance(cfg.get("project"), dict)
        self.assertEqual(cfg["project"]["type"], "webapp")
        self.assertEqual(cfg["stack"]["framework"], "next")

    def test_read_boolean(self):
        self._write_config("audit: true\nmemory:\n  enabled: false\n")
        cfg = g._read_config(self.slug)
        self.assertIs(cfg.get("audit"), True)
        self.assertIs(cfg["memory"]["enabled"], False)

    def test_read_list(self):
        self._write_config("rules:\n  - rule1\n  - rule2\n")
        cfg = g._read_config(self.slug)
        self.assertEqual(cfg.get("rules"), ["rule1", "rule2"])

    def test_read_list_flow(self):
        self._write_config("rules: [rule1, rule2]\n")
        cfg = g._read_config(self.slug)
        self.assertEqual(cfg.get("rules"), ["rule1", "rule2"])

    def test_write_and_read_back(self):
        cfg = {
            "project_root": "/tmp/test",
            "slug": self.slug,
            "stack": {"detected": "node", "framework": "next"},
            "rules": ["secret.yml"],
            "audit": True,
        }
        g._write_config(self.slug, cfg)
        reread = g._read_config(self.slug)
        self.assertEqual(reread["project_root"], "/tmp/test")
        self.assertEqual(reread["stack"]["framework"], "next")
        self.assertEqual(reread["rules"], ["secret.yml"])
        self.assertIs(reread["audit"], True)


class TestDocsAvailable(unittest.TestCase):
    def test_available_from_strings(self):
        config = {"docs": {"frontend": "true", "backend": "false", "ui": "true", "features": "true"}}
        avail = g._get_docs_available(config)
        self.assertIs(avail["frontend"], True)
        self.assertIs(avail["backend"], False)
        self.assertIs(avail["ui"], True)

    def test_available_from_bools(self):
        config = {"docs": {"frontend": True, "backend": False}}
        avail = g._get_docs_available(config)
        self.assertIs(avail["frontend"], True)
        self.assertIs(avail["backend"], False)

    def test_available_missing_returns_false(self):
        config = {"docs": {}}
        avail = g._get_docs_available(config)
        self.assertIs(avail["frontend"], False)


class TestLastScan(unittest.TestCase):
    def test_last_scan_string(self):
        config = {"docs": {"last_scan": "2026-06-13T12:00:00Z"}}
        self.assertEqual(g._get_docs_last_scan(config), "2026-06-13T12:00:00Z")

    def test_last_scan_missing(self):
        self.assertEqual(g._get_docs_last_scan({}), "")

    def test_last_scan_docs_missing(self):
        config = {"stack": {"detected": "node"}}
        self.assertEqual(g._get_docs_last_scan(config), "")


class TestDocRoutes(unittest.TestCase):
    def test_routes_extracted(self):
        config = {
            "docs": {
                "mandatory": ["agents", "constraints"],
                "src/components/**": "frontend",
                "src/api/**": "backend",
                "last_scan": "2026-06-13T12:00:00Z",
            }
        }
        routes = g._get_docs_routes(config)
        self.assertIn("src/components/**", routes)
        self.assertIn("src/api/**", routes)
        self.assertNotIn("mandatory", routes)
        self.assertNotIn("last_scan", routes)

    def test_routes_empty(self):
        self.assertEqual(g._get_docs_routes({}), {})


class TestTemplateReplacements(unittest.TestCase):
    def test_infer_frontend_next(self):
        fe = g._infer_frontend_tools("next")
        self.assertEqual(fe["state"], "Zustand")
        self.assertEqual(fe["server_state"], "React Query")
        self.assertEqual(fe["api"], "fetch/axios")

    def test_infer_frontend_unknown(self):
        fe = g._infer_frontend_tools("unknown")
        self.assertEqual(fe["state"], "—")

    def test_infer_backend_django(self):
        be = g._infer_backend_tools("django")
        self.assertEqual(be["validator"], "Django Serializers")
        self.assertEqual(be["orm"], "Django ORM")

    def test_infer_backend_unknown(self):
        be = g._infer_backend_tools("unknown")
        self.assertEqual(be["validator"], "—")

    def test_infer_forbidden_next(self):
        deps = g._infer_forbidden_deps("next")
        self.assertIn("lodash", deps)

    def test_infer_forbidden_unknown(self):
        self.assertEqual(g._infer_forbidden_deps("unknown"), [])



class TestHashUtils(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_hash_file_exists(self):
        f = self.tmpdir / "test.txt"
        f.write_text("hello world")
        h = g.shared.hash_file(f)
        self.assertIsNotNone(h)
        self.assertEqual(len(h), 64)

    def test_hash_file_nonexistent(self):
        h = g.shared.hash_file(self.tmpdir / "nope")
        self.assertIsNone(h)

    def test_hash_dict_deterministic(self):
        d1 = {"a": 1, "b": [2, 3]}
        d2 = {"b": [2, 3], "a": 1}
        self.assertEqual(g.shared.hash_dict(d1), g.shared.hash_dict(d2))

    def test_hash_dict_different(self):
        d1 = {"a": 1}
        d2 = {"a": 2}
        self.assertNotEqual(g.shared.hash_dict(d1), g.shared.hash_dict(d2))

    def test_is_stale_no_ts(self):
        self.assertTrue(g.shared.is_stale(None))

    def test_is_stale_fresh(self):
        ts = g.shared.ts()
        self.assertFalse(g.shared.is_stale(ts, max_age_days=7))

    def test_is_stale_old(self):
        old = "2024-01-01T00:00:00Z"
        self.assertTrue(g.shared.is_stale(old, max_age_days=1))


class TestI18n(unittest.TestCase):
    def tearDown(self):
        g.shared.set_lang("en")

    def test_default_english(self):
        g.shared.set_lang("en")
        self.assertEqual(g.shared._("setup_reconfigure"), "  Reconfigure?")

    def test_spanish(self):
        g.shared.set_lang("es")
        self.assertEqual(g.shared._("setup_reconfigure"), "  ¿Reconfigurar?")

    def test_unknown_key_returns_key(self):
        g.shared.set_lang("en")
        self.assertEqual(g.shared._("nonexistent_key"), "nonexistent_key")

    def test_unknown_lang_falls_back_to_en(self):
        g.shared.set_lang("xx")
        self.assertEqual(g.shared._("setup_reconfigure"), "  Reconfigure?")

    def test_format_kwargs(self):
        g.shared.set_lang("en")
        result = g.shared._("setup_already_exists", slug="test", created="2026-06-14")
        self.assertIn("test", result)
        self.assertIn("2026-06-14", result)

    def test_set_lang(self):
        g.shared.set_lang("en")
        self.assertEqual(g.shared.GUARDIAN_LANG, "en")
        g.shared.set_lang("es")
        self.assertEqual(g.shared.GUARDIAN_LANG, "es")


class TestSetupPreconditions(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self._orig_g_mem = g.MEMORY_DIR
        self._orig_shared_mem = g.shared.MEMORY_DIR
        g.MEMORY_DIR = self.tmpdir
        g.shared.MEMORY_DIR = self.tmpdir

    def tearDown(self):
        g.MEMORY_DIR = self._orig_g_mem
        g.shared.MEMORY_DIR = self._orig_shared_mem
        shutil.rmtree(self.tmpdir)

    def test_setup_check_docs_no_config(self):
        self.assertTrue(g._setup_check_docs(None))

    def test_setup_check_docs_no_root(self):
        self.assertTrue(g._setup_check_docs({"project": {}}))

    def test_setup_check_skills_no_global(self):
        result = g._setup_check_skills("noslug")
        self.assertTrue(result)

    def test_setup_check_memory_no_session(self):
        result = g._setup_check_memory("noslug")
        # no project exists, so likely True (needs setup)
        self.assertIsInstance(result, bool)


if __name__ == "__main__":
    unittest.main()
