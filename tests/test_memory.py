#!/usr/bin/env python3
"""Tests for guardian_memory.py"""
import unittest
import tempfile
import shutil
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

# Import guardian_memory.py
import importlib.util
_mem_path = Path(__file__).resolve().parent.parent / "lib" / "guardian_memory.py"
_spec = importlib.util.spec_from_file_location("guardian_memory", _mem_path)
mem = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mem)


class TestMemoryCore(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.slug = "testproj"
        # Override paths for testing (v3 + v4)
        mem.MEMORY_DIR = self.tmpdir
        mem.shared.MEMORY_DIR = self.tmpdir
        mem.shared.BACKEND_DIR = self.tmpdir

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write_entry(self, entry):
        mf = mem._memory_file(self.slug)
        mf.parent.mkdir(parents=True, exist_ok=True)
        with open(mf, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def test_ensure_creates_dir_and_file(self):
        mem._ensure(self.slug)
        self.assertTrue(mem._memory_file(self.slug).exists())

    def test_read_empty_returns_empty_list(self):
        mem._ensure(self.slug)
        self.assertEqual(mem._read_entries(self.slug), [])

    def test_ts_format(self):
        ts = mem._ts()
        self.assertRegex(ts, r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")

    def test_ts_epoch(self):
        self.assertGreater(mem._ts_epoch("2026-06-13T12:00:00Z"), 0)
        self.assertEqual(mem._ts_epoch(""), 0)
        self.assertEqual(mem._ts_epoch("invalid"), 0)

    def test_entry_id_consistent(self):
        eid1 = mem._entry_id("landmark", "test content", "file.ts")
        eid2 = mem._entry_id("landmark", "test content", "file.ts")
        self.assertEqual(eid1, eid2)

    def test_entry_id_differs_for_different_content(self):
        eid1 = mem._entry_id("landmark", "content a", "file.ts")
        eid2 = mem._entry_id("landmark", "content b", "file.ts")
        self.assertNotEqual(eid1, eid2)

    def test_save_and_read(self):
        mem._ensure(self.slug)
        mem.cmd_save(self.slug, "note", "testing save")
        entries = mem._read_entries(self.slug)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["type"], "note")
        self.assertEqual(entries[0]["content"], "testing save")
        self.assertEqual(entries[0]["hits"], 1)

    def test_save_updates_existing(self):
        mem._ensure(self.slug)
        mem.cmd_save(self.slug, "note", "dedup test", file_="f.ts")
        mem.cmd_save(self.slug, "note", "dedup test", file_="f.ts")
        entries = mem._read_entries(self.slug)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["hits"], 2)

    def test_search_finds_by_content(self):
        mem._ensure(self.slug)
        mem.cmd_save(self.slug, "note", "unique search term")
        entries = mem._read_entries(self.slug)
        # Search is a CLI command, test the underlying logic
        results = [e for e in entries if "unique" in e.get("content", "").lower()]
        self.assertEqual(len(results), 1)

    def test_gc_removes_expired(self):
        mem._ensure(self.slug)
        # Add an old entry
        old_ts = "2020-01-01T00:00:00Z"
        self._write_entry({
            "id": "oldentry",
            "ts": old_ts,
            "type": "note",
            "scope": "",
            "content": "old entry",
            "file": "",
            "line": 0,
            "ttl": 1,
            "hits": 1,
        })
        mem.cmd_gc(self.slug)
        entries = mem._read_entries(self.slug)
        self.assertEqual(len(entries), 0)

    def test_context_output_max_6(self):
        mem._ensure(self.slug)
        for i in range(10):
            mem.cmd_save(self.slug, "landmark", f"landmark {i}")
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            mem.cmd_context(self.slug)
        output = f.getvalue()
        lines = [l for l in output.split("\n") if l.startswith("📍") or l.startswith("🧠") or l.startswith("🔁")]
        self.assertLessEqual(len(lines), 6)

    def test_status_counts(self):
        mem._ensure(self.slug)
        mem.cmd_save(self.slug, "landmark", "l1")
        mem.cmd_save(self.slug, "decision", "d1")
        mem.cmd_save(self.slug, "pattern", "p1")
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            mem.cmd_status(self.slug)
        output = f.getvalue()
        self.assertIn("landmark", output)
        self.assertIn("decision", output)
        self.assertIn("pattern", output)

    def test_session_save_and_status(self):
        mem._ensure(self.slug)
        mem.cmd_session_save(self.slug)
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            mem.cmd_session_status(self.slug)
        output = f.getvalue()
        self.assertIn("Sessions", output)
        self.assertIn("1 total", output)

    def test_session_save_increments(self):
        mem._ensure(self.slug)
        mem.cmd_session_save(self.slug)
        mem.cmd_session_save(self.slug)
        entries = mem._read_entries(self.slug)
        sessions = [e for e in entries if e.get("type") == "session"]
        self.assertEqual(len(sessions), 2)


class TestSemanticSearch(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.slug = "semtest"
        mem.MEMORY_DIR = self.tmpdir
        mem.shared.MEMORY_DIR = self.tmpdir
        mem.shared.BACKEND_DIR = self.tmpdir
        # Ensure brain dir exists (project_dir creates it)
        (self.tmpdir / self.slug / "brain").mkdir(parents=True, exist_ok=True)
        mem._ensure(self.slug)
        # Save some entries
        mem.cmd_save(self.slug, "landmark", "El proyecto usa React con TypeScript")
        mem.cmd_save(self.slug, "decision", "Usamos PostgreSQL como base de datos")
        mem.cmd_save(self.slug, "pattern", "Componentes siguen patrón container/presenter")
        mem.cmd_save(self.slug, "analysis", "Endpoint /api/users tiene N+1 queries")
        mem.cmd_save(self.slug, "note", "Recordar actualizar props en UserCard")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_tokenize(self):
        tokens = mem._tokenize("Hola Mundo! React-TypeScript 2024")
        self.assertIn("hola", tokens)
        self.assertIn("mundo", tokens)
        self.assertIn("react", tokens)
        self.assertIn("typescript", tokens)
        self.assertIn("2024", tokens)

    def test_tokenize_empty(self):
        self.assertEqual(mem._tokenize(""), [])

    def test_cosine_sim_identical(self):
        a = [1.0, 0.0, 1.0]
        self.assertAlmostEqual(mem._cosine_sim(a, a), 1.0)

    def test_cosine_sim_orthogonal(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        self.assertAlmostEqual(mem._cosine_sim(a, b), 0.0)

    def test_cosine_sim_empty(self):
        self.assertEqual(mem._cosine_sim([], []), 0.0)
        self.assertEqual(mem._cosine_sim([1.0], []), 0.0)

    def test_compute_tfidf_index(self):
        entries = [{"content": "hola mundo"}, {"content": "hola cosmos"}]
        idf, vocab = mem._compute_tfidf_index(entries)
        self.assertIn("hola", idf)
        self.assertIn("mundo", idf)
        self.assertIn("cosmos", idf)
        self.assertIn("hola", vocab)
        # "hola" appears in both docs, IDF lower than unique terms
        self.assertLess(idf["hola"], idf["mundo"])

    def test_vectorize(self):
        entries = [{"content": "a b"}, {"content": "a c"}]
        idf, vocab = mem._compute_tfidf_index(entries)
        vec = mem._vectorize(mem._tokenize("a b"), idf, vocab)
        self.assertEqual(len(vec), len(vocab))
        self.assertGreater(vec[vocab.index("a")], 0)
        self.assertGreater(vec[vocab.index("b")], 0)

    def test_cmd_index_creates_index(self):
        ret = mem.cmd_index(self.slug)
        self.assertEqual(ret, 0)
        idx_file = mem._embed_index_file(self.slug)
        self.assertTrue(idx_file.exists())
        data = json.loads(idx_file.read_text())
        self.assertIn("meta", data)
        self.assertIn("entries", data)
        self.assertGreater(len(data["entries"]), 0)

    def test_index_semantic_search_finds_related(self):
        mem.cmd_index(self.slug)
        entries = mem._read_entries(self.slug)
        # Semantic search for database-related topic should find the DB entry
        cached = mem._load_cached_embeddings(self.slug)
        meta = cached.get("meta", {})
        idf, vocab = meta.get("idf", {}), meta.get("vocab", [])
        qvec = mem._embed_text("almacenamiento persistente de datos", idf, vocab)
        results = []
        for e in entries:
            eid = e.get("id") or mem._entry_id(e["type"], e["content"], e.get("file", ""))
            ev = cached.get("entries", {}).get(eid, [])
            sim = mem._cosine_sim(qvec, ev)
            if sim > 0.10:
                results.append((sim, e))
        results.sort(key=lambda x: -x[0])
        self.assertGreater(len(results), 0)
        # The top result should be the DB-related entry
        top_content = results[0][1].get("content", "")
        self.assertIn("PostgreSQL", top_content)

    def test_semantic_fallback_to_keyword(self):
        # Without --semantic, keyword should still work
        entries = mem._read_entries(self.slug)
        # Simulate keyword search
        q = "postgresql"
        results = [e for e in entries if q in e.get("content", "").lower()]
        self.assertGreater(len(results), 0)
        self.assertIn("PostgreSQL", results[0].get("content", ""))

    def test_empty_index_search(self):
        # Index an empty project
        empty_slug = "emptyidx"
        mem.MEMORY_DIR = self.tmpdir
        mem._ensure(empty_slug)
        ret = mem.cmd_index(empty_slug)
        self.assertEqual(ret, 0)

    def test_index_force_rebuild(self):
        mem.cmd_index(self.slug)
        idx_file = mem._embed_index_file(self.slug)
        mtime_before = idx_file.stat().st_mtime
        mem.cmd_index(self.slug, force=True)
        mtime_after = idx_file.stat().st_mtime
        self.assertGreaterEqual(mtime_after, mtime_before)
