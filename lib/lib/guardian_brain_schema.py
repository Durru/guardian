#!/usr/bin/env python3
"""
Guardian Brain Schema — SQLite schema for the cognitive memory system.

Defines 4 per-project DBs (semantic, episodic, procedural, reflection)
and 3 global DBs (semantic_g, procedural_g, reflection_g).

Zero deps — uses only Python stdlib sqlite3.

Commands:
  init <slug>                    create all 4 project DBs
  init-global                    create all 3 global DBs
  status <slug>                  report schema state
  migrate <slug>                 apply migrations if needed
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import guardian_shared as shared


SCHEMA_VERSION = 1

PROJECT_LEVELS = ["semantic", "episodic", "procedural", "reflection"]
GLOBAL_LEVELS = ["semantic_g", "procedural_g", "reflection_g"]

ALL_LEVELS = PROJECT_LEVELS + GLOBAL_LEVELS

# ── Path helpers ───────────────────────────────────────────────────────


def _branch_root():
    """Root of the current machine's branch (where projects live)."""
    return shared.BACKEND_DIR / "genome" / "branches" / shared._branch_hash()


def brain_dir(slug):
    """Per-project brain directory."""
    return _branch_root() / "projects" / slug / "brain"


def global_brain_dir():
    """Global brain directory (shared across all projects)."""
    return shared.BACKEND_DIR / "global"


def brain_db_path(slug, level):
    """Path to one of the 4 project DBs."""
    if level not in PROJECT_LEVELS:
        raise ValueError(f"Invalid project level: {level}. Must be one of {PROJECT_LEVELS}")
    return brain_dir(slug) / f"{level}.db"


def global_db_path(level):
    """Path to one of the 3 global DBs."""
    if level not in GLOBAL_LEVELS:
        raise ValueError(f"Invalid global level: {level}. Must be one of {GLOBAL_LEVELS}")
    suffix = level.replace("_g", "_global")
    return global_brain_dir() / f"{suffix}.db"


def guardian_md_path(slug):
    """Path to the essential GUARDIAN.md (always-loaded context)."""
    return brain_dir(slug) / "GUARDIAN.md"


def global_guardian_md_path():
    """Path to the global GUARDIAN.md (cross-project essentials)."""
    return global_brain_dir() / "GUARDIAN.md"


def governor_log_path(slug):
    """Path to the Governor's decision log."""
    return brain_dir(slug) / "governor.log"


def plans_dir(slug):
    """Path to plans directory."""
    return brain_dir(slug) / "plans"


def production_dir(slug):
    """Path to production snapshots directory."""
    return brain_dir(slug) / "production"


# ── Schema DDL ─────────────────────────────────────────────────────────

NODE_DDL = """
CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    level TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding BLOB,
    importance REAL DEFAULT 0.5,
    ttl INTEGER,
    confidence REAL DEFAULT 0.7,
    source TEXT,
    stack TEXT,
    version_range TEXT,
    project_slug TEXT,
    url TEXT,
    source_checksum TEXT,
    created_at REAL,
    last_accessed REAL,
    access_count INTEGER DEFAULT 0,
    consolidated INTEGER DEFAULT 0,
    needs_review INTEGER DEFAULT 0,
    tags TEXT,
    meta TEXT
);

CREATE INDEX IF NOT EXISTS idx_nodes_kind ON nodes(kind);
CREATE INDEX IF NOT EXISTS idx_nodes_level ON nodes(level);
CREATE INDEX IF NOT EXISTS idx_nodes_importance ON nodes(importance);
CREATE INDEX IF NOT EXISTS idx_nodes_stack ON nodes(stack);
CREATE INDEX IF NOT EXISTS idx_nodes_project ON nodes(project_slug);
CREATE INDEX IF NOT EXISTS idx_nodes_needs_review ON nodes(needs_review);
CREATE INDEX IF NOT EXISTS idx_nodes_last_accessed ON nodes(last_accessed);

CREATE TABLE IF NOT EXISTS edges (
    from_id TEXT,
    to_id TEXT,
    relation TEXT,
    weight REAL DEFAULT 1.0,
    PRIMARY KEY (from_id, to_id, relation)
);

CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(from_id);
CREATE INDEX IF NOT EXISTS idx_edges_to ON edges(to_id);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def _now_epoch() -> float:
    return datetime.now(timezone.utc).timestamp()


def _apply_schema(db_path: Path, default_level: str):
    """Apply schema to a single DB file. Creates file if missing."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(NODE_DDL)
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            ("schema_version", str(SCHEMA_VERSION)),
        )
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            ("default_level", default_level),
        )
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            ("created_at", str(_now_epoch())),
        )
        conn.commit()
    finally:
        conn.close()


def init_project(slug: str) -> dict:
    """Create all 4 project DBs if they don't exist. Returns report."""
    if not slug:
        return {"ok": False, "error": "slug is required"}
    slug = _slugify(slug)
    brain_dir(slug).mkdir(parents=True, exist_ok=True)
    results = {}
    for level in PROJECT_LEVELS:
        db = brain_db_path(slug, level)
        existed = db.exists()
        _apply_schema(db, level)
        results[level] = {"path": str(db), "created": not existed}
    return {"ok": True, "slug": slug, "databases": results}


def _slugify(name: str) -> str:
    import re
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def init_global() -> dict:
    """Create all 3 global DBs if they don't exist. Returns report."""
    global_brain_dir().mkdir(parents=True, exist_ok=True)
    results = {}
    for level in GLOBAL_LEVELS:
        db = global_db_path(level)
        existed = db.exists()
        _apply_schema(db, level)
        suffix = level.replace("_g", "")
        results[suffix] = {"path": str(db), "created": not existed}
    return {"ok": True, "databases": results}


def status(slug: str = None) -> dict:
    """Report schema state for a project (or global if slug is None)."""
    if slug:
        brain_dir(slug).mkdir(parents=True, exist_ok=True)
        result = {"slug": slug, "project": {}}
        for level in PROJECT_LEVELS:
            db = brain_db_path(slug, level)
            if not db.exists():
                result["project"][level] = {"exists": False}
                continue
            conn = sqlite3.connect(str(db))
            try:
                count = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
                version = conn.execute(
                    "SELECT value FROM meta WHERE key = 'schema_version'"
                ).fetchone()
                conn.close()
                result["project"][level] = {
                    "exists": True,
                    "nodes": count,
                    "schema_version": version[0] if version else "?",
                    "size_bytes": db.stat().st_size,
                }
            except Exception as e:
                result["project"][level] = {"exists": True, "error": str(e)}
        guardian_md = guardian_md_path(slug)
        result["guardian_md"] = {
            "exists": guardian_md.exists(),
            "lines": len(guardian_md.read_text().splitlines()) if guardian_md.exists() else 0,
        }
        return result
    else:
        global_brain_dir().mkdir(parents=True, exist_ok=True)
        result = {"global": {}}
        for level in GLOBAL_LEVELS:
            db = global_db_path(level)
            if not db.exists():
                result["global"][level] = {"exists": False}
                continue
            conn = sqlite3.connect(str(db))
            try:
                count = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
                version = conn.execute(
                    "SELECT value FROM meta WHERE key = 'schema_version'"
                ).fetchone()
                conn.close()
                result["global"][level] = {
                    "exists": True,
                    "nodes": count,
                    "schema_version": version[0] if version else "?",
                    "size_bytes": db.stat().st_size,
                }
            except Exception as e:
                result["global"][level] = {"exists": True, "error": str(e)}
        gmd = global_guardian_md_path()
        result["global_guardian_md"] = {
            "exists": gmd.exists(),
            "lines": len(gmd.read_text().splitlines()) if gmd.exists() else 0,
        }
        return result


def migrate(slug: str) -> dict:
    """Apply any pending migrations. Currently a no-op stub for v1."""
    return {"ok": True, "slug": slug, "migrated": 0, "current_version": SCHEMA_VERSION}


# ── main ──────────────────────────────────────────────────────────────

USAGE = """Guardian Brain Schema — usage:
  init <slug>          create all 4 project DBs
  init-global          create all 3 global DBs
  status [slug]        report schema state
  migrate <slug>       apply migrations
"""


def main():
    if len(sys.argv) < 2:
        print(USAGE)
        return 1
    cmd = sys.argv[1]
    if cmd == "init":
        if len(sys.argv) < 3:
            print("init requires a slug")
            return 1
        slug = sys.argv[2]
        result = init_project(slug)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    elif cmd == "init-global":
        result = init_global()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    elif cmd == "status":
        slug = sys.argv[2] if len(sys.argv) > 2 else None
        result = status(slug)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    elif cmd == "migrate":
        if len(sys.argv) < 3:
            print("migrate requires a slug")
            return 1
        slug = sys.argv[2]
        result = migrate(slug)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    else:
        print(f"Unknown command: {cmd}")
        print(USAGE)
        return 1


if __name__ == "__main__":
    sys.exit(main())
