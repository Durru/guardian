#!/usr/bin/env python3
"""Tests for the guardian RAG system."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
import sys

LIB_DIR = Path(__file__).resolve().parent.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

import guardian_shared as shared
import guardian_rag


class TestRAGCore(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(guardian_rag._slugify("Hello World"), "hello-world")
        self.assertEqual(guardian_rag._slugify("My App!"), "my-app")
        self.assertEqual(guardian_rag._slugify("  --test--  "), "test")

    def test_highlight_basic(self):
        result = guardian_rag._highlight("hello world hello", ["hello"])
        self.assertIn("\033[1;33mhello\033[0m", result)
        self.assertIn("world", result)

    def test_highlight_no_match(self):
        result = guardian_rag._highlight("hello world", ["xyz"])
        self.assertEqual(result, "hello world")

    def test_highlight_short_token(self):
        result = guardian_rag._highlight("a b c", ["a"])
        self.assertEqual(result, "a b c")

    def test_highlight_empty_tokens(self):
        result = guardian_rag._highlight("hello world", [])
        self.assertEqual(result, "hello world")

    def test_highlight_case_insensitive(self):
        result = guardian_rag._highlight("Hello World", ["hello"])
        self.assertIn("\033[1;33mHello\033[0m", result)

    def test_fmt_citation_doc(self):
        c = {"source": "doc", "doc_name": "README.md", "section": "Install"}
        cit = guardian_rag._fmt_citation(c)
        self.assertIn("README.md", cit)
        self.assertIn("Install", cit)

    def test_fmt_citation_code(self):
        c = {"source": "code", "file": "lib/main.py", "line_start": 10, "line_end": 20}
        cit = guardian_rag._fmt_citation(c)
        self.assertIn("lib/main.py", cit)
        self.assertIn("10", cit)
        self.assertIn("20", cit)

    def test_fmt_citation_memory(self):
        c = {"source": "memory", "type": "note", "content": "some remembered thing"}
        cit = guardian_rag._fmt_citation(c)
        self.assertIn("note", cit)

    def test_fmt_citation_fallback(self):
        c = {"source": "unknown"}
        self.assertEqual(guardian_rag._fmt_citation(c), "unknown")

    def test_collect_chunks_unknown_slug(self):
        config = {"project_root": "/tmp/__rag_test_empty__"}
        chunks = guardian_rag._collect_chunks("nonexistent", config, {"code"})
        self.assertEqual(chunks, [])

    def test_type_weights_present(self):
        expected = {"doc", "code", "landmark", "decision", "pattern", "note", "analysis", "memory", "tome"}
        self.assertEqual(set(guardian_rag.TYPE_WEIGHTS.keys()), expected)

    def test_rerank_empty(self):
        scored = guardian_rag._rerank([], {}, {}, {}, None)
        self.assertEqual(scored, [])


class TestRAGIndex(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.projects_dir = self.tmpdir / "projects"
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        shared.MEMORY_DIR = self.projects_dir

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_cmd_index_no_slug(self):
        rc = guardian_rag.cmd_index("nonexistent")
        self.assertEqual(rc, 1)

    def test_chunks_file_path(self):
        path = guardian_rag._chunks_file("test-slug")
        self.assertTrue(str(path).endswith("rag-chunks.json"))
        self.assertIn("test-slug", str(path))


class TestRAGQuery(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.projects_dir = self.tmpdir / "projects"
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        shared.MEMORY_DIR = self.projects_dir

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_cmd_rag_no_slug(self):
        rc = guardian_rag.cmd_rag("nonexistent", "test query")
        self.assertEqual(rc, 1)

    def test_cmd_rag_empty_memory(self):
        slug = "empty-test"
        proj = self.projects_dir / slug
        proj.mkdir(parents=True, exist_ok=True)
        root = self.tmpdir / "code-root"
        root.mkdir(parents=True, exist_ok=True)
        (proj / "config.yaml").write_text(
            f"project_root: {root}\nstack:\n  detected: test\n"
        )
        rc = guardian_rag.cmd_rag(slug, "hello", top_k=3, json_output=True, source_filter={"memory"})
        self.assertEqual(rc, 0)

    def test_cmd_index_then_rag(self):
        slug = "rag-test-proj"
        proj = self.projects_dir / slug
        proj.mkdir(parents=True, exist_ok=True)
        root = self.tmpdir / "code-root2"
        root.mkdir(parents=True, exist_ok=True)
        (root / "main.py").write_text("def hello():\n    print('hello world')\n")
        (proj / "config.yaml").write_text(
            f"project_root: {root}\nslug: {slug}\nstack:\n  detected: test\n"
        )
        rc = guardian_rag.cmd_index(slug, force=True)
        self.assertEqual(rc, 0)

        cache = guardian_rag._chunks_file(slug)
        self.assertTrue(cache.exists())
        data = json.loads(cache.read_text())
        self.assertGreater(len(data), 0)

        rc2 = guardian_rag.cmd_index(slug, force=False)
        self.assertEqual(rc2, 0)


class TestRAGWebIntegration(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.projects_dir = self.tmpdir / "projects"
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        shared.MEMORY_DIR = self.projects_dir

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_query_rag_no_project(self):
        from guardian_web import _query_rag
        result = _query_rag("nonexistent", "test")
        self.assertIsNone(result)

    def test_query_rag_empty_project(self):
        slug = "empty"
        proj = self.projects_dir / slug
        proj.mkdir(parents=True, exist_ok=True)
        root = self.tmpdir / "code-root"
        root.mkdir(parents=True, exist_ok=True)
        (proj / "config.yaml").write_text(
            f"project_root: {root}\nstack:\n  detected: test\n"
        )
        from guardian_web import _query_rag
        result = _query_rag(slug, "hello", source_filter={"memory"})
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
