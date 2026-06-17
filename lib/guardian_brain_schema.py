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

CODEGRAPH_DDL = """
CREATE TABLE IF NOT EXISTS codegraph_symbols (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_slug TEXT,
    file TEXT NOT NULL,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    qualified_name TEXT,
    signature TEXT,
    line_start INTEGER,
    line_end INTEGER,
    language TEXT,
    docstring TEXT,
    hash TEXT,
    last_indexed_at REAL
);
CREATE INDEX IF NOT EXISTS idx_cg_file ON codegraph_symbols(file);
CREATE INDEX IF NOT EXISTS idx_cg_kind ON codegraph_symbols(kind);
CREATE INDEX IF NOT EXISTS idx_cg_lang ON codegraph_symbols(language);
CREATE INDEX IF NOT EXISTS idx_cg_project ON codegraph_symbols(project_slug);

CREATE TABLE IF NOT EXISTS codegraph_edges (
    from_id INTEGER,
    to_id INTEGER,
    relation TEXT,
    file TEXT,
    line INTEGER,
    PRIMARY KEY (from_id, to_id, relation)
);
CREATE INDEX IF NOT EXISTS idx_cg_edges_to ON codegraph_edges(to_id);
"""

PROMPT_LOG_DDL = """
CREATE TABLE IF NOT EXISTS prompt_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL,
    prompt TEXT,
    reason_inferred TEXT,
    mode TEXT,
    files_in_context TEXT,
    outcome TEXT
);
CREATE INDEX IF NOT EXISTS idx_pl_ts ON prompt_log(ts);
"""

DECISION_LOG_DDL = """
CREATE TABLE IF NOT EXISTS decision_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL,
    decision TEXT,
    why TEXT,
    alternatives TEXT,
    project_slug TEXT
);
CREATE INDEX IF NOT EXISTS idx_dl_ts ON decision_log(ts);
"""

STACK_HISTORY_DDL = """
CREATE TABLE IF NOT EXISTS stack_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL,
    runner TEXT,
    packages TEXT,
    project_slug TEXT
);
CREATE INDEX IF NOT EXISTS idx_sh_ts ON stack_history(ts);
"""

TEST_RESULTS_DDL = """
CREATE TABLE IF NOT EXISTS test_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL,
    runner TEXT,
    passed INTEGER,
    failed INTEGER,
    duration_s REAL,
    output TEXT,
    project_slug TEXT
);
CREATE INDEX IF NOT EXISTS idx_tr_ts ON test_results(ts);
"""

EVENT_LOG_DDL = """
CREATE TABLE IF NOT EXISTS event_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL,
    event_type TEXT,
    payload TEXT,
    project_slug TEXT
);
CREATE INDEX IF NOT EXISTS idx_el_ts ON event_log(ts);
CREATE INDEX IF NOT EXISTS idx_el_type ON event_log(event_type);
"""

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
    meta TEXT,
    topic_key TEXT,
    outcome TEXT DEFAULT 'info',
    why TEXT,
    location TEXT,
    scope TEXT DEFAULT 'project'
);

CREATE INDEX IF NOT EXISTS idx_nodes_topic_key ON nodes(topic_key);
CREATE INDEX IF NOT EXISTS idx_nodes_outcome ON nodes(outcome);

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
    """Apply schema to a single DB file. Creates file if missing. Recovers from corruption."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists() and db_path.stat().st_size > 0:
        try:
            test_conn = sqlite3.connect(str(db_path))
            test_conn.execute("PRAGMA integrity_check").fetchone()
            test_conn.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1").fetchone()
            test_conn.close()
        except sqlite3.DatabaseError:
            import shutil
            corrupt_path = db_path.with_suffix(db_path.suffix + f".corrupt-{int(datetime.now().timestamp())}")
            shutil.move(str(db_path), str(corrupt_path))
            print(f"  ⚠ DB corrupto movido a: {corrupt_path.name}")
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(NODE_DDL)
        # v4.1.0: migrate existing databases — add new columns if missing
        existing_cols = [r[1] for r in conn.execute("PRAGMA table_info(nodes)").fetchall()]
        for col_name, col_def in [("topic_key", "topic_key TEXT"),
                                   ("outcome", "outcome TEXT DEFAULT 'info'"),
                                   ("why", "why TEXT"),
                                   ("location", "location TEXT"),
                                   ("scope", "scope TEXT DEFAULT 'project'")]:
            if col_name not in existing_cols:
                try:
                    conn.execute(f"ALTER TABLE nodes ADD COLUMN {col_def}")
                except sqlite3.OperationalError:
                    pass
        existing_idxs = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()]
        if "idx_nodes_topic_key" not in existing_idxs:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_nodes_topic_key ON nodes(topic_key)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_nodes_outcome ON nodes(outcome)")
        # v4: extended tables in semantic.db
        if default_level == "semantic":
            conn.executescript(CODEGRAPH_DDL)
            conn.executescript(PROMPT_LOG_DDL)
            conn.executescript(DECISION_LOG_DDL)
            conn.executescript(STACK_HISTORY_DDL)
            conn.executescript(TEST_RESULTS_DDL)
            conn.executescript(EVENT_LOG_DDL)
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
