#!/usr/bin/env python3
"""Integration tests for the guardian modules."""

import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
import sys
import importlib.util

LIB_DIR = Path(__file__).resolve().parent.parent / "lib"
sys.path.insert(0, str(LIB_DIR))


def _load_module(name, filename):
    path = LIB_DIR / filename
    # Don't replace shared module to avoid breaking references in other modules
    if name == "guardian_shared" and name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


shared = _load_module("guardian_shared", "guardian_shared.py")
guardian_web = _load_module("guardian_web", "guardian_web.py")
guardian_absorb = _load_module("guardian_absorb", "guardian_absorb.py")


class IntegrationBase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.projects_dir = self.tmpdir / "projects"
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.skills_global = self.tmpdir / "skills-global.json"
        self.skills_global.write_text(json.dumps({"version": 1, "skills": {}, "last_absorb": None}))

        self._orig_shared_mem = shared.MEMORY_DIR
        self._orig_web_mem = guardian_web.MEMORY_DIR
        self._orig_absorb_mem = guardian_absorb.MEMORY_DIR
        self._orig_absorb_skills = guardian_absorb.SKILLS_GLOBAL

        shared.MEMORY_DIR = self.projects_dir
        guardian_web.MEMORY_DIR = self.projects_dir
        guardian_absorb.MEMORY_DIR = self.projects_dir
        guardian_absorb.SKILLS_GLOBAL = self.skills_global

    def tearDown(self):
        shared.MEMORY_DIR = self._orig_shared_mem
        guardian_web.MEMORY_DIR = self._orig_web_mem
        guardian_absorb.MEMORY_DIR = self._orig_absorb_mem
        guardian_absorb.SKILLS_GLOBAL = self._orig_absorb_skills
        shutil.rmtree(self.tmpdir)


class TestWebIntegration(IntegrationBase):
    def test_discovers_only_valid_projects(self):
        valid = self.projects_dir / "valid"
        valid.mkdir(parents=True)
        (valid / "config.yaml").write_text("slug: valid\nproject_root: /tmp/valid\n")
        (self.projects_dir / "empty").mkdir(parents=True)

        self.assertEqual(guardian_web._discover_projects(), ["valid"])

    def test_reads_yaml_config_via_safe_load(self):
        valid = self.projects_dir / "valid"
        valid.mkdir(parents=True)
        (valid / "config.yaml").write_text(
            "project_root: /tmp/valid\nstack:\n  detected: python\n  framework: django\n"
        )

        cfg = guardian_web._read_config("valid")
        self.assertEqual(cfg["stack"]["framework"], "django")


class TestAbsorbIntegration(IntegrationBase):
    def _write_project(self, slug="demo"):
        root = self.tmpdir / "demo-root"
        root.mkdir(parents=True, exist_ok=True)
        (root / "package.json").write_text(
            json.dumps(
                {
                    "dependencies": {"next": "^14.0.0", "react": "^18.0.0", "tailwindcss": "^3.0.0"},
                    "devDependencies": {"eslint": "^8.0.0"},
                }
            )
        )
        proj = self.projects_dir / slug
        proj.mkdir(parents=True, exist_ok=True)
        (proj / "config.yaml").write_text(f"project_root: {root}\nslug: {slug}\n")
        return slug, root

    def _write_skills_global(self):
        payload = {
            "version": 1,
            "skills": {
                "frontend-design": {
                    "name": "frontend-design",
                    "keywords": ["react", "next", "tailwind"],
                    "triggers": ["ui", "component"],
                    "total": 60,
                    "stars": "★★★",
                    "description": "Frontend UI design skill",
                },
                "database-ops": {
                    "name": "database-ops",
                    "keywords": ["postgresql"],
                    "triggers": ["sql"],
                    "total": 30,
                    "stars": "★★",
                    "description": "Database operations skill",
                },
            },
            "last_absorb": "2026-06-13T00:00:00Z",
        }
        self.skills_global.write_text(json.dumps(payload, indent=2))

    def test_classify_json_outputs_and_persists(self):
        slug, root = self._write_project("classify-demo")
        self._write_skills_global()

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = guardian_absorb.cmd_classify(slug, json_output=True)
        self.assertEqual(rc, 0)

        out = buf.getvalue().strip().splitlines()[-1]
        data = json.loads(out)
        self.assertEqual(data["slug"], slug)
        self.assertIn("next", data["features"]["frameworks"])
        self.assertIn("react", data["features"]["frameworks"])

        skills_path = self.projects_dir / slug / "skills.json"
        self.assertTrue(skills_path.exists())
        skills = json.loads(skills_path.read_text())
        self.assertIn("classification", skills)
        self.assertIn("hot", skills)

    def test_suggest_json_after_match(self):
        slug, _ = self._write_project("suggest-demo")
        self._write_skills_global()

        guardian_absorb.cmd_match(slug)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = guardian_absorb.cmd_suggest(slug, show_all=True, json_output=True)
        self.assertEqual(rc, 0)

        data = json.loads(buf.getvalue().strip())
        self.assertEqual(data["slug"], slug)
        self.assertGreaterEqual(len(data["items"]), 1)
        self.assertIn("frontend-design", [item["name"] for item in data["items"]])


if __name__ == "__main__":
    unittest.main()
