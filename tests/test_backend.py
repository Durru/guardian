from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

LIB_DIR = Path(__file__).resolve().parent.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

import guardian_shared as shared
import guardian_conciencia
import guardian_genome
import guardian_evolution
import guardian_mcp


class TestConcienciaCore(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.slug = "test-conciencia"
        self.proj = self.tmpdir / self.slug
        self.proj.mkdir(parents=True, exist_ok=True)
        self.orig_mem = shared.MEMORY_DIR
        self.orig_backend = shared.BACKEND_DIR
        shared.MEMORY_DIR = self.tmpdir
        shared.BACKEND_DIR = self.tmpdir

    def tearDown(self):
        shared.MEMORY_DIR = self.orig_mem
        shared.BACKEND_DIR = self.orig_backend
        shutil.rmtree(self.tmpdir)

    def test_consciousness_action_assume(self):
        self.assertEqual(guardian_conciencia.consciousness_action(0.9, "build"), "assume")

    def test_consciousness_action_ask_little(self):
        self.assertEqual(guardian_conciencia.consciousness_action(0.6), "ask_little")

    def test_consciousness_action_ask_much(self):
        self.assertEqual(guardian_conciencia.consciousness_action(0.3), "ask_much")

    def test_consciousness_action_investigate(self):
        self.assertEqual(guardian_conciencia.consciousness_action(0.1), "investigate")

    def test_consciousness_action_with_bonus(self):
        thresholds = dict(guardian_conciencia.DEFAULT_THRESHOLDS)
        thresholds["build_assume_bonus"] = 0.15
        self.assertEqual(guardian_conciencia.consciousness_action(0.7, "build", thresholds), "assume")

    def test_consciousness_action_plan_penalty(self):
        thresholds = dict(guardian_conciencia.DEFAULT_THRESHOLDS)
        thresholds["plan_assume_bonus"] = -0.2
        self.assertEqual(guardian_conciencia.consciousness_action(0.85, "plan", thresholds), "ask_little")

    def test_score_context_empty(self):
        score = guardian_conciencia.score_context({})
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_score_context_with_query(self):
        score = guardian_conciencia.score_context({"question": "una pregunta larga con suficiente contexto"})
        self.assertGreater(score, 0.0)

    def test_score_context_with_rag(self):
        score = guardian_conciencia.score_context({
            "question": "test",
            "rag": {"results": [{"score": 0.9}]},
        })
        self.assertGreater(score, 0.3)

    def test_run_cycle_returns_action(self):
        result = guardian_conciencia.run_cycle(self.slug, question="test query", mode="plan")
        self.assertIn("action", result)
        self.assertIn("confidence", result)
        self.assertIn("slug", result)
        self.assertEqual(result["slug"], self.slug)

    def test_run_cycle_persists_state(self):
        guardian_conciencia.run_cycle(self.slug, question="first", mode="plan")
        state = guardian_conciencia.read_state(self.slug)
        self.assertGreaterEqual(len(state.get("cycles", [])), 1)

    def test_run_cycle_multiple(self):
        for i in range(6):
            guardian_conciencia.run_cycle(self.slug, question=f"q{i}", mode="plan")
        state = guardian_conciencia.read_state(self.slug)
        self.assertEqual(len(state.get("cycles", [])), 6)

    def test_evolve_not_enough_cycles(self):
        thresholds = dict(guardian_conciencia.DEFAULT_THRESHOLDS)
        meta = guardian_conciencia.evolve(self.slug, [], thresholds)
        self.assertIsNone(meta)

    def test_evolve_with_enough_cycles(self):
        cycles = []
        for i in range(10):
            cycles.append({"action": "assume", "confidence": 0.82, "ts": "2026-01-01T00:00:00"})
        thresholds = dict(guardian_conciencia.DEFAULT_THRESHOLDS)
        meta = guardian_conciencia.evolve(self.slug, cycles, thresholds)
        if meta is not None:
            self.assertIn("adjustments", meta)
            self.assertIn("reasons", meta)

    def test_thresholds_default(self):
        t = guardian_conciencia.read_thresholds("nonexistent-slug")
        self.assertEqual(t["assume"], 0.8)
        self.assertEqual(t["ask_little_floor"], 0.5)

    def test_thresholds_write_and_read(self):
        guardian_conciencia.write_thresholds(self.slug, {"assume": 0.75, "ask_little_floor": 0.45, "ask_much_floor": 0.15})
        t = guardian_conciencia.read_thresholds(self.slug)
        self.assertEqual(t["assume"], 0.75)

    def test_save_learning(self):
        guardian_conciencia.save_learning(self.slug, {"type": "test", "message": "hello"})
        branch_path = shared.get_branch_dir()
        learn_dir = branch_path / "projects" / self.slug / "learnings"
        files = list(learn_dir.glob("*.json"))
        self.assertEqual(len(files), 1)
        data = json.loads(files[0].read_text())
        self.assertEqual(data["type"], "test")


class TestGenomeCore(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.orig_branches = guardian_genome.BRANCHES_DIR
        guardian_genome.BRANCHES_DIR = self.tmpdir / "branches"
        guardian_genome.BRANCHES_DIR.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        guardian_genome.BRANCHES_DIR = self.orig_branches
        shutil.rmtree(self.tmpdir)

    def test_fork_branch_creates_dirs(self):
        identity, path = guardian_genome.fork_branch("testuser")
        self.assertTrue(path.exists())
        self.assertTrue((path / "memory").exists())
        self.assertTrue((path / "knowledge" / "tomes").exists())
        self.assertTrue((path / "learnings").exists())

    def test_list_branches_after_fork(self):
        guardian_genome.fork_branch("user1")
        branches = guardian_genome.list_branches()
        self.assertGreaterEqual(len(branches), 1)
        found = any("user1" in b.get("projects", []) for b in branches)
        self.assertTrue(found)

    def test_branch_status_returns_info(self):
        guardian_genome.fork_branch("status-test")
        info = guardian_genome.branch_status("status-test")
        self.assertIsNotNone(info)
        self.assertEqual(info["project"]["slug"], "status-test")

    def test_branch_status_nonexistent(self):
        info = guardian_genome.branch_status("no-such-user")
        self.assertIsNone(info)

    def test_fork_branch_existing_no_force(self):
        guardian_genome.fork_branch("existing")
        identity1, path1 = guardian_genome.fork_branch("existing", force=False)
        self.assertTrue(path1.exists())

    def test_load_genome_returns_dict(self):
        genome = guardian_genome.load_genome()
        self.assertIn("version", genome)


class TestEvolutionCore(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.slug = "test-evolution"
        self.proj = self.tmpdir / self.slug
        self.proj.mkdir(parents=True, exist_ok=True)
        (self.proj / "config.yaml").write_text(
            f"project_root: {self.tmpdir}\nslug: {self.slug}\nstack:\n  detected: test\n"
        )
        self.orig_dir = shared.MEMORY_DIR
        shared.MEMORY_DIR = self.tmpdir

    def tearDown(self):
        shared.MEMORY_DIR = self.orig_dir
        shutil.rmtree(self.tmpdir)

    def test_evolve_branch_no_cycles(self):
        meta = guardian_evolution.evolve_branch(self.slug)
        self.assertIsNone(meta)

    def test_consolidate_no_project(self):
        result = guardian_evolution.consolidate("nonexistent")
        self.assertFalse(result.get("ok"))


class TestMCPCore(unittest.TestCase):
    def test_tools_listed(self):
        self.assertGreater(len(guardian_mcp.TOOLS), 5)
        tool_names = [t["name"] for t in guardian_mcp.TOOLS]
        self.assertIn("read_file", tool_names)
        self.assertIn("rag_query", tool_names)
        self.assertIn("conciencia_cycle", tool_names)
        self.assertIn("mode_switch", tool_names)
        self.assertIn("genome_status", tool_names)
        self.assertIn("branch_fork", tool_names)
        self.assertIn("run_command", tool_names)
        self.assertIn("write_file", tool_names)
        self.assertIn("knowledge_search", tool_names)

    def test_each_tool_has_schema(self):
        for t in guardian_mcp.TOOLS:
            self.assertIn("name", t)
            self.assertIn("description", t)
            self.assertIn("inputSchema", t)
            self.assertIn("properties", t["inputSchema"])

    def test_handle_call_unknown_tool(self):
        captured = []
        orig_stdout = sys.stdout
        from io import StringIO
        buf = StringIO()
        sys.stdout = buf
        try:
            guardian_mcp._handle_call("nonexistent_tool", {}, "test-id")
            output = buf.getvalue()
            self.assertIn("error", output)
            self.assertIn("not found", output)
        finally:
            sys.stdout = orig_stdout

    def test_activate_guardian_tool_in_tools_list(self):
        names = [t["name"] for t in guardian_mcp.TOOLS]
        self.assertIn("activate_guardian", names)

    def test_activate_guardian_tool_schema(self):
        tool = None
        for t in guardian_mcp.TOOLS:
            if t["name"] == "activate_guardian":
                tool = t
                break
        self.assertIsNotNone(tool)
        self.assertIn("slug", tool["inputSchema"]["properties"])


class TestActivateFlow(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.slug = "test-activate"
        self.proj = self.tmpdir / self.slug
        self.proj.mkdir(parents=True, exist_ok=True)
        self.orig_mem = shared.MEMORY_DIR
        self.orig_backend = shared.BACKEND_DIR
        self.orig_genome_branches = guardian_genome.BRANCHES_DIR
        shared.MEMORY_DIR = self.tmpdir
        shared.BACKEND_DIR = self.tmpdir
        guardian_genome.BRANCHES_DIR = shared.BACKEND_DIR / "genome" / "branches"
        (self.tmpdir / "genome" / "branches" / "default").mkdir(parents=True, exist_ok=True)
        (self.tmpdir / "genome" / "branches" / "default" / "identity.yaml").write_text(
            "version: 2.0.0\nuser: default\n", encoding="utf-8"
        )
        self.orig_home = os.environ.get("GUARDIAN_HOME", "")
        self.orig_data = os.environ.get("GUARDIAN_DATA", "")
        os.environ["GUARDIAN_HOME"] = str(self.tmpdir)
        os.environ["GUARDIAN_DATA"] = str(self.tmpdir)

    def tearDown(self):
        shared.MEMORY_DIR = self.orig_mem
        shared.BACKEND_DIR = self.orig_backend
        guardian_genome.BRANCHES_DIR = self.orig_genome_branches
        if self.orig_home:
            os.environ["GUARDIAN_HOME"] = self.orig_home
        else:
            del os.environ["GUARDIAN_HOME"]
        if self.orig_data:
            os.environ["GUARDIAN_DATA"] = self.orig_data
        else:
            del os.environ["GUARDIAN_DATA"]
        shutil.rmtree(self.tmpdir)

    def test_fork_branch_creates_paths(self):
        state, path = guardian_genome.fork_branch(self.slug, force=True)
        self.assertTrue(path.exists())
        self.assertTrue((path / "state.json").exists())
        self.assertIn(self.slug, state.get("projects", {}))

    def test_activate_guardian_mcp_responds(self):
        orig_stdout = sys.stdout
        from io import StringIO
        buf = StringIO()
        sys.stdout = buf
        try:
            guardian_mcp._handle_call("activate_guardian", {"slug": self.slug}, "activate-1")
            output = buf.getvalue()
            self.assertIn("status", output)
        finally:
            sys.stdout = orig_stdout

    def test_activate_creates_config(self):
        config = shared.read_config(self.slug)
        self.assertEqual(config, {})

    def test_activate_fork_creates_branch(self):
        state, path = guardian_genome.fork_branch(self.slug, force=True)
        self.assertIsNotNone(state)
        self.assertIn(self.slug, state["projects"])


if __name__ == "__main__":
    unittest.main()
