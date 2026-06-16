#!/usr/bin/env python3
"""
Guardian Brain Migration — migrate v2 memory files to v3 brain.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import guardian_brain
import guardian_brain_schema
import guardian_shared as shared


def _legacy_memory_file(slug: str) -> Path:
    return shared.MEMORY_DIR / slug / "memory.jsonl"


def _legacy_rag_chunks(slug: str) -> Path:
    return shared.MEMORY_DIR / slug / "rag-chunks.json"


def _legacy_legacy_dir(slug: str) -> Path:
    return guardian_brain_schema.brain_dir(slug) / "legacy"


def classify_v2_kind(v2_kind: str, content: str) -> dict:
    if v2_kind == "decision":
        return {"level": "semantic", "kind": "decision", "importance": 0.8, "ttl": None}
    if v2_kind == "landmark":
        return {"level": "semantic", "kind": "decision", "importance": 0.9, "ttl": None}
    if v2_kind == "pattern":
        return {"level": "procedural", "kind": "workflow", "importance": 0.7, "ttl": 60}
    if v2_kind == "note":
        return {"level": "semantic", "kind": "note", "importance": 0.4, "ttl": 30}
    if v2_kind == "analysis":
        return {"level": "semantic", "kind": "analysis", "importance": 0.5, "ttl": 30}
    if v2_kind == "session":
        return {"level": "episodic", "kind": "session", "importance": 0.3, "ttl": 7}
    if v2_kind == "skill_usage":
        return {"level": "procedural", "kind": "skill_usage", "importance": 0.5, "ttl": 60}
    content_lower = (content or "").lower()
    if any(kw in content_lower for kw in ["deploy", "build", "test", "install"]):
        return {"level": "procedural", "kind": "workflow", "importance": 0.6, "ttl": 60}
    if any(kw in content_lower for kw in ["aprend", "lección", "insight", "error"]):
        return {"level": "reflection", "kind": "learning", "importance": 0.5, "ttl": 60}
    return {"level": "semantic", "kind": "note", "importance": 0.4, "ttl": 30}


def status(slug: str) -> dict:
    legacy_memory = _legacy_memory_file(slug)
    legacy_rag = _legacy_rag_chunks(slug)
    brain_initialized = (guardian_brain_schema.brain_dir(slug) / "semantic.db").exists()
    legacy_dir = _legacy_legacy_dir(slug)
    return {
        "slug": slug,
        "v2_memory_exists": legacy_memory.exists(),
        "v2_memory_size": legacy_memory.stat().st_size if legacy_memory.exists() else 0,
        "v2_rag_exists": legacy_rag.exists(),
        "v3_brain_initialized": brain_initialized,
        "v3_legacy_copied": legacy_dir.exists(),
    }


def migrate(slug: str, dry_run: bool = False) -> dict:
    guardian_brain_schema.init_project(slug)
    legacy_memory = _legacy_memory_file(slug)
    legacy_rag = _legacy_rag_chunks(slug)
    legacy_dir = _legacy_legacy_dir(slug)

    results = {
        "slug": slug, "dry_run": dry_run,
        "v2_memory_entries": 0, "v2_rag_chunks": 0,
        "migrated_to": {"semantic": 0, "episodic": 0, "procedural": 0, "reflection": 0},
        "skipped": 0, "discarded": 0, "errors": [],
    }

    if not dry_run:
        legacy_dir.mkdir(parents=True, exist_ok=True)
        if legacy_memory.exists():
            shutil.copy2(legacy_memory, legacy_dir / "memory.jsonl.v2")
        if legacy_rag.exists():
            shutil.copy2(legacy_rag, legacy_dir / "rag-chunks.json.v2")

    if legacy_memory.exists():
        try:
            with open(legacy_memory, encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    results["v2_memory_entries"] += 1
                    raw_kind = entry.get("type") or entry.get("kind") or "note"
                    raw_importance = entry.get("importance")
                    classification = classify_v2_kind(
                        raw_kind,
                        entry.get("content", ""),
                    )
                    node = {
                        "kind": classification["kind"],
                        "content": entry.get("content", ""),
                        "importance": raw_importance if isinstance(raw_importance, (int, float)) else classification["importance"],
                        "ttl": classification["ttl"],
                        "tags": [entry.get("scope", "")] if entry.get("scope") else [],
                        "source": "v2_migration",
                    }
                    if dry_run:
                        results["migrated_to"][classification["level"]] += 1
                    else:
                        try:
                            result = guardian_brain.write_governed(
                                slug, classification["level"], node
                            )
                            if result.get("ok"):
                                results["migrated_to"][classification["level"]] += 1
                            elif result.get("action") == "discarded":
                                results["discarded"] += 1
                            else:
                                results["skipped"] += 1
                        except Exception as e:
                            results["errors"].append(str(e))
        except (OSError, UnicodeDecodeError) as e:
            results["errors"].append(f"read v2 memory: {e}")

    if legacy_rag.exists():
        try:
            with open(legacy_rag, encoding="utf-8") as f:
                raw = f.read()
            rag = json.loads(raw)
            chunks = rag.get("chunks", []) if isinstance(rag, dict) else []
            for chunk in chunks:
                results["v2_rag_chunks"] += 1
                content = chunk.get("content", "")
                source = chunk.get("source", "code")
                kind = "best_practices" if source in ("tome", "doc") else "pattern"
                level = "semantic"
                node = {
                    "kind": kind, "content": content[:500],
                    "importance": 0.4, "ttl": 60,
                    "tags": [source], "source": "v2_rag_migration",
                }
                if dry_run:
                    results["migrated_to"][level] += 1
                else:
                    try:
                        result = guardian_brain.write_governed(slug, level, node)
                        if result.get("ok"):
                            results["migrated_to"][level] += 1
                        elif result.get("action") == "discarded":
                            results["discarded"] += 1
                        else:
                            results["skipped"] += 1
                    except Exception as e:
                        results["errors"].append(str(e))
        except (OSError, json.JSONDecodeError) as e:
            results["errors"].append(f"read v2 rag: {e}")

    if not dry_run:
        gmd_result = guardian_brain.regenerate_guardian_md(slug)
        results["guardian_md"] = gmd_result

    results["ok"] = True
    return results


def rollback(slug: str) -> dict:
    brain_dir = guardian_brain_schema.brain_dir(slug)
    legacy_dir = _legacy_legacy_dir(slug)
    if not legacy_dir.exists():
        return {"ok": False, "error": "no legacy backup found"}
    if brain_dir.exists():
        for f in brain_dir.glob("*.db"):
            f.unlink()
        gmd = brain_dir / "GUARDIAN.md"
        if gmd.exists():
            gmd.unlink()
    if (legacy_dir / "memory.jsonl.v2").exists():
        shutil.copy2(legacy_dir / "memory.jsonl.v2", _legacy_memory_file(slug))
    if (legacy_dir / "rag-chunks.json.v2").exists():
        shutil.copy2(legacy_dir / "rag-chunks.json.v2", _legacy_rag_chunks(slug))
    return {"ok": True, "rolled_back": slug}


USAGE = """Guardian Brain Migration — usage:
  status <slug>
  migrate <slug> [--dry-run]
  rollback <slug>
"""


def main():
    if len(sys.argv) < 2:
        print(USAGE)
        return 1
    cmd = sys.argv[1]
    if cmd == "status":
        if len(sys.argv) < 3:
            print("status requires slug")
            return 1
        print(json.dumps(status(sys.argv[2]), indent=2, ensure_ascii=False))
        return 0
    if cmd == "migrate":
        if len(sys.argv) < 3:
            print("migrate requires slug")
            return 1
        slug = sys.argv[2]
        dry_run = "--dry-run" in sys.argv
        result = migrate(slug, dry_run=dry_run)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    if cmd == "rollback":
        if len(sys.argv) < 3:
            print("rollback requires slug")
            return 1
        print(json.dumps(rollback(sys.argv[2]), indent=2, ensure_ascii=False))
        return 0
    print(f"Unknown command: {cmd}")
    print(USAGE)
    return 1


if __name__ == "__main__":
    sys.exit(main())
