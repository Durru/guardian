from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import guardian_conciencia
import guardian_rag
import guardian_shared as shared


def evolve_branch(slug):
    state = guardian_conciencia.read_state(slug)
    thresholds = guardian_conciencia.read_thresholds(slug)
    meta = guardian_conciencia.evolve(slug, state.get("cycles", []), thresholds)
    return meta


def consolidate(slug):
    config = shared.read_config(slug)
    if not config:
        return {"ok": False, "error": f"Proyecto '{slug}' no encontrado"}

    results = {}
    mem_dir = shared.branch_path_for(slug, "memory")
    if not mem_dir.exists():
        mem_dir = shared.MEMORY_DIR / slug / "memory"  # legacy fallback
    if mem_dir.exists():
        before = len(list(mem_dir.glob("*.json")))
        mem_script = Path(__file__).with_name("guardian_memory.py")
        proc = subprocess.run(
            [sys.executable, str(mem_script), "gc", slug],
            capture_output=True, text=True, timeout=30,
        )
        after = len(list(mem_dir.glob("*.json")))
        results["memory_gc"] = {"before": before, "after": after, "removed": before - after}

    rag_script = Path(__file__).with_name("guardian_rag.py")
    proc = subprocess.run(
        [sys.executable, str(rag_script), "index", "--slug", slug, "--force"],
        capture_output=True, text=True, timeout=60,
    )
    results["rag_reindex"] = {"rc": proc.returncode}

    learnings = []
    learnings_dir = shared.branch_path_for(slug, "learnings")
    if not learnings_dir.exists():
        learnings_dir = shared.MEMORY_DIR / slug / "learnings"  # legacy
    if learnings_dir.exists():
        before_l = len(list(learnings_dir.glob("*.json")))
        existing = sorted(learnings_dir.glob("*.json"))
        for p in existing[:-100]:
            p.unlink()
        after_l = len(list(learnings_dir.glob("*.json")))
        results["learnings_consolidated"] = {"before": before_l, "after": after_l}

    results["ok"] = True
    return results
