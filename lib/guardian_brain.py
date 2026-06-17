#!/usr/bin/env python3
"""
Guardian Brain — Cognitive memory system (Phase 1: storage + governor).

The 5-level memory architecture:
  Working Memory     (session, ephemeral)
  Project Semantic   (per-project, stable knowledge)
  Project Episodic   (per-project, events with timestamps)
  Project Procedural (per-project, workflows)
  Project Reflection (per-project, learnings)
  Global Semantic    (shared, stable knowledge)
  Global Procedural  (shared, generic workflows)
  Global Reflection  (shared, meta-learnings)

Hashing features embeddings (zero deps, stdlib only).
SQLite storage. Governor with TTL, importance, duplicate detection.

Public API:
  read(slug, level, id)              -> dict | None
  write(slug, level, node)           -> {ok, id, decision}
  query(slug, level, q, top_k)      -> [nodes]
  list_nodes(slug, level, filters)   -> [nodes]
  delete(slug, level, id)            -> {ok}
  count(slug, level)                 -> int
  governor_evaluate(slug, candidate) -> {action, reason, target_id?}
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import guardian_brain_schema as schema
import guardian_shared as shared


# ── Embedding: hashing features (zero deps) ─────────────────────────────

EMBED_DIM = 256


def _tokenize(text: str) -> list[str]:
    return re.findall(r'[a-záéíóúñü0-9]+', text.lower())


_EMBED_BACKEND = os.environ.get("GUARDIAN_EMBED_BACKEND", "hashing").lower()
_SENTENCE_TRANSFORMER = None


def _embed_external(text: str) -> bytes | None:
    """Optional sentence-transformers backend. Returns None if unavailable.

    Set GUARDIAN_EMBED_BACKEND=sentence-transformer to enable. Requires
    `pip install sentence-transformers` (NOT a zero-dep dependency, opt-in only).
    Returns embeddings of EMBED_DIM if possible, else None (fall back to hashing).
    """
    global _SENTENCE_TRANSFORMER
    if _EMBED_BACKEND != "sentence-transformer":
        return None
    if _SENTENCE_TRANSFORMER is None:
        try:
            from sentence_transformers import SentenceTransformer
            import os as _os
            model_name = _os.environ.get("GUARDIAN_EMBED_MODEL", "all-MiniLM-L6-v2")
            _SENTENCE_TRANSFORMER = SentenceTransformer(model_name)
        except ImportError:
            return None
        except Exception:
            return None
    try:
        vec = _SENTENCE_TRANSFORMER.encode(text, normalize_embeddings=True)
        if len(vec) != EMBED_DIM:
            if len(vec) > EMBED_DIM:
                vec = vec[:EMBED_DIM]
            else:
                vec = list(vec) + [0.0] * (EMBED_DIM - len(vec))
        return struct.pack(f"{EMBED_DIM}f", *vec)
    except Exception:
        return None


def embed(text: str) -> bytes:
    """Compute embedding of `text`. Returns BLOB.

    Backends (via GUARDIAN_EMBED_BACKEND env var):
    - 'hashing' (default): zero-deps MD5 hashing features
    - 'sentence-transformer': real embeddings (requires pip install sentence-transformers)
    Falls back to hashing if external backend unavailable.
    """
    external = _embed_external(text)
    if external is not None:
        return external
    tokens = _tokenize(text)
    vec = [0.0] * EMBED_DIM
    for tok in tokens:
        h = int(hashlib.md5(tok.encode()).hexdigest()[:8], 16)
        idx = h % EMBED_DIM
        vec[idx] += 1.0
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]
    return struct.pack(f"{EMBED_DIM}f", *vec)


def embed_to_list(text: str) -> list[float]:
    """Same as embed() but returns a Python list (useful for tests)."""
    return list(struct.unpack(f"{EMBED_DIM}f", embed(text)))


def cosine(a_bytes: bytes, b_bytes: bytes) -> float:
    """Cosine similarity between two embedding BLOBs."""
    if not a_bytes or not b_bytes:
        return 0.0
    a = struct.unpack(f"{EMBED_DIM}f", a_bytes)
    b = struct.unpack(f"{EMBED_DIM}f", b_bytes)
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def cosine_bulk(q_bytes: bytes, candidates: list[bytes]) -> list[float]:
    """Cosine similarity between q and a list of candidates. Faster than calling cosine() N times.

    Unpacks q once and reuses it across all candidates.
    """
    if not q_bytes or not candidates:
        return [0.0] * len(candidates)
    q = struct.unpack(f"{EMBED_DIM}f", q_bytes)
    qn_sq = sum(x * x for x in q)
    if qn_sq == 0:
        return [0.0] * len(candidates)
    qn = math.sqrt(qn_sq)
    out = []
    for cb in candidates:
        if not cb:
            out.append(0.0)
            continue
        c = struct.unpack(f"{EMBED_DIM}f", cb)
        cn_sq = sum(x * x for x in c)
        if cn_sq == 0:
            out.append(0.0)
            continue
        dot = sum(x * y for x, y in zip(q, c))
        out.append(dot / (qn * math.sqrt(cn_sq)))
    return out


def cosine_text(text_a: str, text_b: str) -> float:
    """Convenience: embed two strings and return cosine similarity."""
    return cosine(embed(text_a), embed(text_b))


# ── ID generation ───────────────────────────────────────────────────────


def _node_id(kind: str, content: str, project_slug: str = None) -> str:
    """Deterministic ID for a node. Same content = same ID."""
    raw = f"{kind}|{content}|{project_slug or ''}"
    h = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"n_{h}"


# ── Low-level DB ops ───────────────────────────────────────────────────


_CONN_CACHE = {}

def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if not db_path.exists():
        level_name = db_path.stem.replace(".db", "")
        if level_name in schema.PROJECT_LEVELS:
            schema._apply_schema(db_path, level_name)
        elif level_name in ["semantic_global", "procedural_global", "reflection_global"]:
            schema._apply_schema(db_path, level_name.replace("_global", "_g"))
    key = str(db_path)
    if key in _CONN_CACHE:
        return _CONN_CACHE[key]
    conn = sqlite3.connect(str(db_path), timeout=30.0, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    _CONN_CACHE[key] = conn
    return conn


def _reset_conn_cache():
    """Clear connection cache. By default does NOT close conns (faster for tests).

    Pass close=True to also close all cached conns.
    """
    global _CONN_CACHE
    _CONN_CACHE = {}


def _now_epoch() -> float:
    return datetime.now(timezone.utc).timestamp()


def _row_to_dict(row: sqlite3.Row, include_embedding: bool = False) -> dict:
    d = dict(row)
    for k in ("tags", "meta", "stack"):
        if d.get(k):
            try:
                d[k] = json.loads(d[k])
            except (json.JSONDecodeError, TypeError):
                pass
    if not include_embedding and "embedding" in d:
        d["has_embedding"] = d["embedding"] is not None
        d["embedding_dim"] = EMBED_DIM if d["embedding"] else 0
        del d["embedding"]
    return d


def _row_with_embedding(row: sqlite3.Row) -> dict:
    return _row_to_dict(row, include_embedding=True)


def _dict_to_node_fields(node: dict) -> dict:
    out = {
        "id": node.get("id") or _node_id(
            node.get("kind", "unknown"),
            node.get("content", ""),
            node.get("project_slug"),
        ),
        "kind": node.get("kind", "unknown"),
        "level": node.get("level", "semantic"),
        "content": node.get("content", ""),
        "embedding": node.get("embedding") or embed(node.get("content", "")),
        "importance": float(node.get("importance", 0.5)),
        "ttl": node.get("ttl"),
        "confidence": float(node.get("confidence", 0.7)),
        "source": node.get("source", "user"),
        "stack": json.dumps(node.get("stack", [])),
        "version_range": node.get("version_range"),
        "project_slug": node.get("project_slug"),
        "url": node.get("url"),
        "source_checksum": node.get("source_checksum"),
        "created_at": node.get("created_at") or _now_epoch(),
        "last_accessed": node.get("last_accessed") or _now_epoch(),
        "access_count": int(node.get("access_count", 0)),
        "consolidated": int(node.get("consolidated", 0)),
        "needs_review": int(node.get("needs_review", 0)),
        "tags": json.dumps(node.get("tags", [])),
        "meta": json.dumps(node.get("meta", {})),
    }
    return out


# ── Public API: read / write / query / list / delete ───────────────────


def read(slug: str, level: str, node_id: str) -> dict | None:
    """Read a single node by ID. Updates last_accessed and access_count."""
    if level not in schema.PROJECT_LEVELS:
        raise ValueError(f"Invalid project level: {level}")
    db = schema.brain_db_path(slug, level)
    if not db.exists():
        return None
    conn = _connect(db)
    try:
        conn.execute(
            "UPDATE nodes SET last_accessed = ?, access_count = access_count + 1 WHERE id = ?",
            (_now_epoch(), node_id),
        )
        conn.commit()
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
        if row is None:
            return None
        return _row_to_dict(row)
    finally:
        if str(db) not in _CONN_CACHE:
            conn.close()


def write(slug: str, level: str, node: dict) -> dict:
    """Write a node. If a node with the same ID exists, updates it.

    The Governor is NOT invoked here — use write_governed() for that.
    """
    if level not in schema.PROJECT_LEVELS:
        raise ValueError(f"Invalid project level: {level}")
    db = schema.brain_db_path(slug, level)
    conn = _connect(db)
    try:
        fields = _dict_to_node_fields(node)
        fields["project_slug"] = slug
        cols = ", ".join(fields.keys())
        placeholders = ", ".join("?" for _ in fields)
        conn.execute(
            f"INSERT OR REPLACE INTO nodes ({cols}) VALUES ({placeholders})",
            list(fields.values()),
        )
        conn.commit()
        return {"ok": True, "id": fields["id"], "action": "wrote"}
    finally:
        if str(db) not in _CONN_CACHE:
            conn.close()


def write_governed(slug: str, level: str, node: dict) -> dict:
    """Write a node through the Governor."""
    candidate = {
        "kind": node.get("kind", "unknown"),
        "content": node.get("content", ""),
        "level": level,
        "project_slug": slug,
        "importance": node.get("importance", 0.5),
        "tags": node.get("tags", []),
    }
    decision = governor_evaluate(slug, candidate)

    if decision["action"] == "discard":
        return {"ok": False, "action": "discarded", "reason": decision.get("reason")}

    if decision["action"] == "merge":
        target_id = decision.get("target_id")
        existing = read(slug, level, target_id) if target_id else None
        if existing:
            existing["importance"] = max(existing.get("importance", 0.5), node.get("importance", 0.5))
            existing["access_count"] = existing.get("access_count", 0) + 1
            existing["last_accessed"] = _now_epoch()
            existing["confidence"] = max(existing.get("confidence", 0.7), node.get("confidence", 0.7))
            write(slug, level, existing)
            return {"ok": True, "id": target_id, "action": "merged"}

    if decision["action"] == "needs_review":
        node["needs_review"] = 1

    result = write(slug, level, node)
    result["decision"] = decision
    return result


def query(slug: str, level: str, q: str, top_k: int = 5,
          min_similarity: float = 0.01, project_only: bool = True,
          limit_scan: int = None) -> list[dict]:
    """Vector search using hashing features. Returns top_k most similar nodes.

    limit_scan: if set, only scan the most recent N nodes (performance optimization
    for the Governor's duplicate check during writes).
    """
    if level not in schema.PROJECT_LEVELS:
        raise ValueError(f"Invalid project level: {level}")
    db = schema.brain_db_path(slug, level)
    if not db.exists():
        return []
    q_embed = embed(q)
    conn = _connect(db)
    try:
        conn.row_factory = sqlite3.Row
        if limit_scan is not None:
            rows = conn.execute(
                "SELECT * FROM nodes WHERE embedding IS NOT NULL "
                "ORDER BY created_at DESC LIMIT ?",
                (limit_scan,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM nodes WHERE embedding IS NOT NULL"
            ).fetchall()
    finally:
        if str(db) not in _CONN_CACHE:
            conn.close()
    scored = []
    embs = [r["embedding"] if "embedding" in r.keys() else None for r in rows]
    sims = cosine_bulk(q_embed, embs)
    for row, sim in zip(rows, sims):
        d = _row_with_embedding(row)
        if project_only and d.get("project_slug") and d.get("project_slug") != slug:
            continue
        if sim >= min_similarity:
            scored.append((sim, d))
    scored.sort(key=lambda x: -x[0])
    result = []
    for sim, d in scored[:top_k]:
        if "embedding" in d:
            d["has_embedding"] = d["embedding"] is not None
            d["embedding_dim"] = EMBED_DIM if d["embedding"] else 0
            del d["embedding"]
        d["similarity"] = round(sim, 4)
        result.append(d)
    return result


def list_nodes(slug: str, level: str, filters: dict | None = None,
               limit: int = 100) -> list[dict]:
    """List nodes with optional filters."""
    if level not in schema.PROJECT_LEVELS:
        raise ValueError(f"Invalid project level: {level}")
    db = schema.brain_db_path(slug, level)
    if not db.exists():
        return []
    conn = _connect(db)
    try:
        conn.row_factory = sqlite3.Row
        where = []
        params = []
        if filters:
            if "kind" in filters:
                where.append("kind = ?")
                params.append(filters["kind"])
            if "min_importance" in filters:
                where.append("importance >= ?")
                params.append(float(filters["min_importance"]))
            if "needs_review" in filters:
                where.append("needs_review = ?")
                params.append(1 if filters["needs_review"] else 0)
            if "since" in filters:
                where.append("created_at >= ?")
                params.append(float(filters["since"]))
            if "project_slug" in filters:
                where.append("project_slug = ?")
                params.append(filters["project_slug"])
        sql = "SELECT * FROM nodes"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY importance DESC, created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        if str(db) not in _CONN_CACHE:
            conn.close()


def delete(slug: str, level: str, node_id: str) -> dict:
    """Hard delete a node by ID."""
    if level not in schema.PROJECT_LEVELS:
        raise ValueError(f"Invalid project level: {level}")
    db = schema.brain_db_path(slug, level)
    if not db.exists():
        return {"ok": False, "error": "DB does not exist"}
    conn = _connect(db)
    try:
        cur = conn.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
        conn.commit()
        return {"ok": True, "deleted": cur.rowcount}
    finally:
        if str(db) not in _CONN_CACHE:
            conn.close()


def count(slug: str, level: str, filters: dict | None = None) -> int:
    """Count nodes matching filters."""
    if level not in schema.PROJECT_LEVELS:
        raise ValueError(f"Invalid project level: {level}")
    db = schema.brain_db_path(slug, level)
    if not db.exists():
        return 0
    conn = _connect(db)
    try:
        where = []
        params = []
        if filters:
            if "kind" in filters:
                where.append("kind = ?")
                params.append(filters["kind"])
            if "min_importance" in filters:
                where.append("importance >= ?")
                params.append(float(filters["min_importance"]))
        sql = "SELECT COUNT(*) FROM nodes"
        if where:
            sql += " WHERE " + " AND ".join(where)
        return conn.execute(sql, params).fetchone()[0]
    finally:
        if str(db) not in _CONN_CACHE:
            conn.close()


# ── Governor ────────────────────────────────────────────────────────────

GOVERNOR_DEFAULTS = {
    "importance_floor": 0.4,
    "duplicate_threshold": 0.92,
    "contradiction_threshold": 0.85,
    "ttl_check_enabled": True,
}


def _get_governor_thresholds(slug: str) -> dict:
    th = dict(GOVERNOR_DEFAULTS)
    try:
        db = schema.brain_db_path(slug, "semantic")
        if db.exists():
            conn = sqlite3.connect(str(db))
            try:
                row = conn.execute(
                    "SELECT value FROM meta WHERE key = 'governor_thresholds'"
                ).fetchone()
                if row:
                    stored = json.loads(row[0])
                    th.update(stored)
            finally:
                conn.close()
    except Exception:
        pass
    return th


def governor_evaluate(slug: str, candidate: dict) -> dict:
    """Evaluate whether a candidate node should be written."""
    th = _get_governor_thresholds(slug)
    content = candidate.get("content", "")
    kind = candidate.get("kind", "unknown")
    level = candidate.get("level", "semantic")
    importance = float(candidate.get("importance", 0.5))

    if importance < th["importance_floor"]:
        return {
            "action": "discard",
            "reason": f"importance {importance:.2f} below floor {th['importance_floor']:.2f}",
        }

    similar = query(slug, level, content, top_k=3,
                    min_similarity=th["duplicate_threshold"] - 0.1,
                    limit_scan=50)

    if similar:
        top_node = similar[0]
        sim = cosine_text(content, top_node.get("content", ""))
        if sim >= th["duplicate_threshold"]:
            return {
                "action": "merge",
                "target_id": top_node["id"],
                "reason": f"semantic duplicate of existing node (sim={sim:.2f})",
            }
        if sim >= th["contradiction_threshold"] and top_node.get("content", "").strip() != content.strip():
            return {
                "action": "needs_review",
                "reason": f"similar to existing but different content (sim={sim:.2f}); possible contradiction",
                "target_id": top_node["id"],
            }

    if candidate.get("created_at") and candidate.get("ttl"):
        age_days = (_now_epoch() - candidate["created_at"]) / 86400
        if age_days > candidate["ttl"]:
            return {
                "action": "discard",
                "reason": f"TTL expired ({age_days:.1f}d > {candidate['ttl']}d)",
            }

    return {"action": "write", "reason": "passed all checks"}


def governor_gc(slug: str, level: str, dry_run: bool = False) -> dict:
    """Run garbage collection on a level."""
    if level not in schema.PROJECT_LEVELS:
        raise ValueError(f"Invalid project level: {level}")
    th = _get_governor_thresholds(slug)
    db = schema.brain_db_path(slug, level)
    if not db.exists():
        return {"ok": True, "removed": 0, "archived": 0}
    conn = _connect(db)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM nodes").fetchall()
        to_remove = []
        to_archive = []
        now = _now_epoch()
        for row in rows:
            d = _row_to_dict(row)
            importance = d.get("importance", 0.5)
            ttl = d.get("ttl")
            created = d.get("created_at", now)
            if importance < th["importance_floor"] and d.get("access_count", 0) == 0:
                to_remove.append(d["id"])
                continue
            if ttl and (now - created) / 86400 > ttl:
                to_archive.append(d["id"])
        if not dry_run:
            for nid in to_remove:
                conn.execute("DELETE FROM nodes WHERE id = ?", (nid,))
            for nid in to_archive:
                conn.execute("UPDATE nodes SET consolidated = 1 WHERE id = ?", (nid,))
            conn.commit()
        return {
            "ok": True,
            "removed": len(to_remove),
            "archived": len(to_archive),
            "dry_run": dry_run,
        }
    finally:
        if str(db) not in _CONN_CACHE:
            conn.close()


# ── Stats / status ─────────────────────────────────────────────────────


def status(slug: str) -> dict:
    """Report brain status for a project."""
    schema.init_project(slug)
    result = {
        "slug": slug,
        "brain_dir": str(schema.brain_dir(slug)),
        "levels": {},
        "totals": {"nodes": 0, "by_kind": {}, "by_level": {}},
    }
    for level in schema.PROJECT_LEVELS:
        c = count(slug, level)
        result["levels"][level] = {"nodes": c}
        result["totals"]["nodes"] += c
        if c > 0:
            db = schema.brain_db_path(slug, level)
            conn = _connect(db)
            try:
                rows = conn.execute(
                    "SELECT kind, COUNT(*) as n FROM nodes GROUP BY kind"
                ).fetchall()
                for kind, n in rows:
                    result["totals"]["by_kind"][kind] = result["totals"]["by_kind"].get(kind, 0) + n
                    result["totals"]["by_level"][level] = result["totals"]["by_level"].get(level, 0) + n
            finally:
                if str(db) not in _CONN_CACHE:
                    conn.close()
    gmd = schema.guardian_md_path(slug)
    result["guardian_md"] = {
        "exists": gmd.exists(),
        "lines": len(gmd.read_text().splitlines()) if gmd.exists() else 0,
    }
    return result


# ── main (for CLI testing) ──────────────────────────────────────────────

USAGE = """Guardian Brain — usage:
  status <slug>                        report brain state
  read <slug> <level> <id>             read a node
  write <slug> <level> <kind> <content> [--importance=N] [--ttl=N] [--tags=a,b]
  query <slug> <level> <query> [--top-k=N]
  list <slug> <level> [--kind=X] [--min-importance=N] [--limit=N]
  delete <slug> <level> <id>           delete a node
  count <slug> <level>                 count nodes
  gc <slug> <level> [--dry-run]        run governor GC
  embed <text>                         show embedding dimension
  cosine <text-a> <text-b>             show cosine similarity
"""


def main():
    if len(sys.argv) < 2:
        print(USAGE)
        return 1
    cmd = sys.argv[1]
    if cmd == "status":
        slug = sys.argv[2]
        print(json.dumps(status(slug), indent=2, ensure_ascii=False))
        return 0
    if cmd == "read":
        slug, level, nid = sys.argv[2], sys.argv[3], sys.argv[4]
        result = read(slug, level, nid)
        print(json.dumps(result, indent=2, ensure_ascii=False) if result else "null")
        return 0
    if cmd == "write":
        if len(sys.argv) < 5:
            print("write requires slug, level, kind, content")
            return 1
        slug, level, kind = sys.argv[2], sys.argv[3], sys.argv[4]
        content = sys.argv[5]
        node = {"kind": kind, "content": content, "level": level}
        for arg in sys.argv[6:]:
            if arg.startswith("--importance="):
                node["importance"] = float(arg.split("=", 1)[1])
            elif arg.startswith("--ttl="):
                node["ttl"] = int(arg.split("=", 1)[1])
            elif arg.startswith("--tags="):
                node["tags"] = arg.split("=", 1)[1].split(",")
        result = write_governed(slug, level, node)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    if cmd == "query":
        slug, level, q = sys.argv[2], sys.argv[3], sys.argv[4]
        top_k = 5
        for arg in sys.argv[5:]:
            if arg.startswith("--top-k="):
                top_k = int(arg.split("=", 1)[1])
        results = query(slug, level, q, top_k=top_k)
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 0
    if cmd == "list":
        slug, level = sys.argv[2], sys.argv[3]
        filters = {}
        limit = 100
        for arg in sys.argv[4:]:
            if arg.startswith("--kind="):
                filters["kind"] = arg.split("=", 1)[1]
            elif arg.startswith("--min-importance="):
                filters["min_importance"] = float(arg.split("=", 1)[1])
            elif arg.startswith("--limit="):
                limit = int(arg.split("=", 1)[1])
        results = list_nodes(slug, level, filters=filters, limit=limit)
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 0
    if cmd == "delete":
        slug, level, nid = sys.argv[2], sys.argv[3], sys.argv[4]
        result = delete(slug, level, nid)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    if cmd == "count":
        slug, level = sys.argv[2], sys.argv[3]
        print(count(slug, level))
        return 0
    if cmd == "gc":
        slug, level = sys.argv[2], sys.argv[3]
        dry_run = "--dry-run" in sys.argv
        result = governor_gc(slug, level, dry_run=dry_run)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    if cmd == "embed":
        text = sys.argv[2] if len(sys.argv) > 2 else ""
        vec = embed_to_list(text)
        print(f"dim={len(vec)}, first 5={vec[:5]}")
        return 0
    if cmd == "cosine":
        a, b = sys.argv[2], sys.argv[3]
        print(f"{cosine_text(a, b):.4f}")
        return 0
    if cmd == "start":
        slug = sys.argv[2]
        mode = None
        for arg in sys.argv[3:]:
            if arg.startswith("--mode="):
                mode = arg.split("=", 1)[1]
        result = session_start(slug, mode=mode)
        print(result.get("greeting", ""))
        return 0
    if cmd == "continue":
        slug = sys.argv[2]
        result = session_continue(slug)
        print(result.get("greeting", ""))
        if result.get("handoff"):
            print(f"\n  Handoff encontrado: {result['handoff'].get('last_session', '?')}")
        return 0
    if cmd == "end":
        slug = sys.argv[2]
        result = session_end(slug)
        print(f"  ✓ Reflection: {result['reflection'].get('promoted', 0)} knowledge promoted")
        if result.get("compact"):
            print(f"  ✓ Compactación: {result['compact']}")
        print(f"  ✓ GUARDIAN.md: {result['guardian_md'].get('lines', 0)} líneas")
        print(f"  ✓ Handoff guardado")
        return 0
    if cmd == "reflect":
        slug = sys.argv[2]
        result = run_reflection(slug)
        print(f"  Events: {result['events']}, Clusters: {result['clusters']}, Candidates: {len(result['candidates'])}, Promoted: {result['promoted']}")
        return 0
    if cmd == "orchestrate":
        slug = sys.argv[2]
        q = sys.argv[3] if len(sys.argv) > 3 else ""
        result = orchestrate(slug, q)
        print(f"  Levels queried: {result['levels_queried']}")
        for level, nodes in result["results"].items():
            print(f"  {level}: {len(nodes)} results")
        return 0
    if cmd == "guardian":
        slug = sys.argv[2]
        content = read_guardian_md(slug)
        print(content if content else "(GUARDIAN.md no existe. Corré `regenerate-guardian` para crearlo.)")
        return 0
    if cmd == "regenerate-guardian":
        slug = sys.argv[2]
        result = regenerate_guardian_md(slug)
        print(f"  ✓ GUARDIAN.md regenerado: {result['lines']} líneas")
        return 0
    if cmd == "promote":
        if len(sys.argv) < 5:
            print("promote requires slug, level, id")
            return 1
        slug, level, nid = sys.argv[2], sys.argv[3], sys.argv[4]
        result = global_promote(slug, nid, level)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    if cmd == "auto-compact":
        slug = sys.argv[2]
        dry_run = "--dry-run" in sys.argv
        result = auto_compact(slug, dry_run=dry_run)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    print(f"Unknown command: {cmd}")
    print(USAGE)
    return 1


# ── GUARDIAN.md (cerebro esencial, siempre cargado) ─────────────────

GUARDIAN_MD_MAX_LINES = 30


def read_guardian_md(slug: str) -> str:
    gmd = schema.guardian_md_path(slug)
    if not gmd.exists():
        return ""
    return gmd.read_text(encoding="utf-8")


def write_guardian_md(slug: str, content: str) -> dict:
    lines = content.splitlines()
    truncated = False
    if len(lines) > GUARDIAN_MD_MAX_LINES:
        lines = lines[:GUARDIAN_MD_MAX_LINES]
        truncated = True
    gmd = schema.guardian_md_path(slug)
    gmd.parent.mkdir(parents=True, exist_ok=True)
    gmd.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "lines": len(lines),
        "truncated": truncated,
        "path": str(gmd),
    }


def generate_guardian_md(slug: str) -> str:
    """Generate compact GUARDIAN.md (~25 lines, estilo CLAUDE.md).

    Secciones: Objetivo, Stack, Estado actual, Decisiones activas, Últimos errores.
    No se regenera desde cero — se escribe progresivamente con append/compact.
    """
    schema.init_project(slug)
    parts = [f"# GUARDIAN — {slug}", ""]

    # Objetivo
    goal = list_nodes(slug, "semantic", filters={"kind": "goal", "min_importance": 0.7}, limit=1)
    if goal:
        parts.append(f"## Objetivo\n{goal[0]['content']}\n")
    else:
        parts.append("## Objetivo\n—\n")

    # Stack
    stack = list_nodes(slug, "semantic", filters={"kind": "stack", "min_importance": 0.5}, limit=1)
    if stack:
        parts.append(f"## Stack\n{stack[0]['content']}\n")

    # Decisiones activas (máximo 5)
    decisions = list_nodes(slug, "semantic", filters={"kind": "decision", "min_importance": 0.6}, limit=5)
    if decisions:
        parts.append("## Decisiones activas")
        for d in decisions:
            topic = d.get("tags", "")
            topic_str = f" [{topic[0]}]" if isinstance(topic, list) and topic else ""
            outcome = d.get("outcome", "")
            marker = {"success": "✅", "failure": "❌", "warning": "⚠️", "info": "ℹ️"}.get(outcome, "")
            parts.append(f"- {marker}{topic_str} {d['content'][:80]}")
        parts.append("")

    # Últimos errores
    errors = list_nodes(slug, "reflection", filters={"min_importance": 0.6}, limit=3)
    if errors:
        parts.append("## Últimos errores")
        for e in errors:
            parts.append(f"- {e['content'][:100]}")
        parts.append("")

    return "\n".join(parts)


def regenerate_guardian_md(slug: str) -> dict:
    content = generate_guardian_md(slug)
    return write_guardian_md(slug, content)


# ── Observation system (v4.1.0) ─────────────────────────────────


def write_observation(slug: str, obs_type: str, topic_key: str, content: str,
                      why: str = "", where: str = "", outcome: str = "info",
                      scope: str = "project", tags: list = None) -> dict:
    """Save an observation with full metadata.

    obs_type: decision | error | pattern | architecture | config | bugfix
    topic_key: ej. "db/migration", "auth/jwt"
    outcome: success | failure | warning | info
    scope: project | global
    why: reasoning behind the decision
    where: files/areas affected
    tags: list of keywords for search
    """
    schema.init_project(slug)
    tags = tags or []
    node = {
        "kind": obs_type,
        "topic_key": topic_key,
        "content": content,
        "why": why,
        "where": where,
        "outcome": outcome,
        "scope": scope,
        "tags": json.dumps(tags),
        "importance": 0.7 if outcome in ("success", "failure") else 0.5,
        "confidence": 1.0,
    }

    level = "reflection" if obs_type in ("error", "bugfix") else "semantic"
    result = write(slug, level, node)

    reason = why or content[:80]
    append_guardian_md_line(slug, obs_type, topic_key, outcome, reason)

    if scope == "global":
        try:
            g_node = {**node, "project_slug": slug}
            g_db = schema.brain_db_path("_global", level)
            g_conn = sqlite3.connect(str(g_db))
            g_fields = _dict_to_node_fields(g_node)
            g_fields["project_slug"] = "_global"
            g_cols = ", ".join(g_fields.keys())
            g_ph = ", ".join("?" for _ in g_fields)
            g_conn.execute(
                f"INSERT OR REPLACE INTO nodes ({g_cols}) VALUES ({g_ph})",
                list(g_fields.values()),
            )
            g_conn.commit()
            g_conn.close()
        except Exception:
            pass

    return result


def get_observations(slug: str, topic_key: str, limit: int = 5,
                     global_too: bool = True) -> list[dict]:
    """Search observations by topic_key. Searches project + global."""
    schema.init_project(slug)
    results = []

    for level in ("semantic", "reflection"):
        try:
            rows = list_nodes(slug, level, filters={"topic_key": topic_key}, limit=limit)
            results.extend(rows)
        except Exception:
            pass

    if global_too:
        for g_level in ("semantic", "reflection"):
            try:
                g_db = schema.brain_db_path("_global", g_level)
                if not g_db.exists():
                    continue
                g_conn = sqlite3.connect(str(g_db))
                g_conn.row_factory = sqlite3.Row
                rows = g_conn.execute(
                    "SELECT * FROM nodes WHERE topic_key = ? ORDER BY importance DESC LIMIT ?",
                    (topic_key, limit),
                ).fetchall()
                g_conn.close()
                for r in rows:
                    results.append(_row_to_dict(r))
            except Exception:
                pass

    results.sort(key=lambda x: x.get("importance", 0), reverse=True)
    return results[:limit]


def get_last_good(slug: str, topic_key: str) -> dict | None:
    """Get the last successful observation for a topic_key."""
    results = get_observations(slug, topic_key, limit=10)
    for r in results:
        if r.get("outcome") == "success":
            return r
    return None


def append_guardian_md_line(slug: str, obs_type: str, topic_key: str,
                            outcome: str, reason: str) -> dict:
    """Append 1 line to GUARDIAN.md. Compact if > 30 lines."""
    marker = {"success": "✅", "failure": "❌", "warning": "⚠️", "info": "ℹ️"}.get(outcome, "•")
    line = f"- {marker} [{topic_key}] {reason[:100]}"

    gmd = schema.guardian_md_path(slug)
    existing = read_guardian_md(slug)
    lines = existing.splitlines() if existing else []

    lines.append(line)

    if len(lines) > GUARDIAN_MD_MAX_LINES:
        header = []
        body = []
        in_header = True
        for l in lines:
            if in_header and l.startswith("#"):
                header.append(l)
            elif in_header and not l.strip():
                header.append(l)
            else:
                in_header = False
                body.append(l)

        keep_header = header[:4]
        keep_body = body[-(GUARDIAN_MD_MAX_LINES - len(keep_header) - 1):]
        lines = keep_header + [""] + keep_body

    return write_guardian_md(slug, "\n".join(lines))


def compact_guardian_md(slug: str) -> dict:
    """Compact GUARDIAN.md: keep header + most recent lines."""
    gmd = schema.guardian_md_path(slug)
    if not gmd.exists():
        return {"ok": True, "lines": 0, "removed": 0}

    content = read_guardian_md(slug)
    lines = content.splitlines()
    before = len(lines)

    if before <= GUARDIAN_MD_MAX_LINES:
        return {"ok": True, "lines": before, "removed": 0}

    header = []
    body = []
    in_header = True
    for l in lines:
        if in_header and l.startswith("#"):
            header.append(l)
        elif in_header and not l.strip():
            header.append(l)
        else:
            in_header = False
            body.append(l)

    keep_header = header[:4]
    keep_body = body[-(GUARDIAN_MD_MAX_LINES - len(keep_header) - 1):]
    compacted = keep_header + [""] + keep_body

    write_guardian_md(slug, "\n".join(compacted))
    return {"ok": True, "lines": len(compacted), "removed": before - len(compacted)}


# ── Working Memory ──────────────────────────────────────────────────

def _working_memory_path(slug: str) -> Path:
    return schema.brain_dir(slug) / "working_memory.json"


def read_working_memory(slug: str) -> dict:
    p = _working_memory_path(slug)
    if not p.exists():
        return {
            "goal": None, "task": None, "constraints": [],
            "progress": [], "open_questions": [], "mode": None,
            "session_started_at": None, "last_updated": None,
        }
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def write_working_memory(slug: str, wm: dict) -> dict:
    p = _working_memory_path(slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    wm["last_updated"] = _now_epoch()
    p.write_text(json.dumps(wm, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "path": str(p)}


def set_working_memory(slug: str, **kwargs) -> dict:
    wm = read_working_memory(slug)
    for k, v in kwargs.items():
        wm[k] = v
    return write_working_memory(slug, wm)


# ── Handoff ────────────────────────────────────────────────────────

def _handoff_path(slug: str) -> Path:
    return schema.brain_dir(slug) / "handoff.json"


def read_handoff(slug: str) -> dict | None:
    p = _handoff_path(slug)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def write_handoff(slug: str, handoff: dict) -> dict:
    p = _handoff_path(slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    handoff["written_at"] = _now_epoch()
    p.write_text(json.dumps(handoff, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "path": str(p)}


# ── Context Budget ─────────────────────────────────────────────────

CONTEXT_BUDGETS = {
    "read":   {"semantic": 1500, "episodic": 200,  "procedural": 500,  "reflection": 300},
    "plan":   {"semantic": 1500, "episodic": 200,  "procedural": 500,  "reflection": 300},
    "build":  {"semantic": 800,  "episodic": 100,  "procedural": 800,  "reflection": 200},
    "commit": {"semantic": 400,  "episodic": 0,    "procedural": 600,  "reflection": 100},
    "review": {"semantic": 1500, "episodic": 800,  "procedural": 500,  "reflection": 400},
}


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def build_context(slug: str, mode: str, query: str = "",
                  top_k_per_level: int = 5) -> dict:
    schema.init_project(slug)
    budget = CONTEXT_BUDGETS.get(mode, CONTEXT_BUDGETS["read"])
    result = {
        "guardian_md": read_guardian_md(slug),
        "working_memory": read_working_memory(slug),
        "levels": {},
        "budget_used": {k: 0 for k in budget},
        "truncated": [],
    }
    for level in ("semantic", "episodic", "procedural", "reflection"):
        limit = budget[level]
        if query and level in ("semantic", "procedural"):
            candidates = query(slug, level, query, top_k=top_k_per_level)
        else:
            candidates = list_nodes(slug, level, limit=top_k_per_level)
        accepted = []
        used = 0
        for node in candidates:
            content = node.get("content", "")
            size = estimate_tokens(content)
            if used + size > limit:
                result["truncated"].append(level)
                break
            accepted.append(node)
            used += size
        result["levels"][level] = accepted
        result["budget_used"][level] = used
    return result


# ── Orchestrator ──────────────────────────────────────────────────

ORCHESTRATOR_KEYWORDS = {
    "semantic":   ["qué", "cuál", "decisión", "prefer", "sabés", "config", "stack", "versión"],
    "episodic":   ["cuándo", "historial", "antes", "pasó", "ayer", "semana", "evento"],
    "procedural": ["cómo", "workflow", "deploy", "test", "build", "instalar", "comando"],
    "reflection": ["aprend", "lección", "insight", "descubrí", "error", "mejora"],
}


def orchestrate(slug: str, query_text: str, top_k: int = 3) -> dict:
    schema.init_project(slug)
    q_lower = query_text.lower()
    scores = {}
    for level, keywords in ORCHESTRATOR_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in q_lower)
        scores[level] = score
    chosen = [lvl for lvl, s in sorted(scores.items(), key=lambda x: -x[1]) if s > 0]
    if not chosen:
        chosen = ["semantic"]
    results = {}
    for level in chosen:
        nodes = query(slug, level, query_text, top_k=top_k)
        results[level] = nodes
    return {
        "levels_queried": chosen,
        "scores": scores,
        "results": results,
        "reasoning": f"Query matched keywords in: {[l for l, s in scores.items() if s > 0] or ['default: semantic']}",
    }


# ── Reflection Agent ──────────────────────────────────────────────

def run_reflection(slug: str, since_ts: float = None) -> dict:
    schema.init_project(slug)
    if since_ts is None:
        since_ts = _now_epoch() - 86400
    events = list_nodes(slug, "episodic", filters={"since": since_ts}, limit=200)
    if not events:
        return {"events": 0, "clusters": [], "candidates": [], "promoted": 0}
    clusters = _cluster_by_tokens(events)
    candidates = []
    for cluster in clusters:
        if len(cluster) < 2:
            continue
        rep = max(cluster, key=lambda n: len(n.get("content", "")))
        all_tags = []
        for n in cluster:
            t = n.get("tags") or []
            if isinstance(t, list):
                all_tags.extend(t)
        unique_tags = list(set(all_tags))[:5]
        avg_conf = sum(n.get("confidence", 0.5) for n in cluster) / len(cluster)
        size_boost = min(0.3, len(cluster) * 0.05)
        confidence = min(1.0, avg_conf + size_boost)
        importance = min(1.0, len(cluster) * 0.1 + confidence * 0.5)
        content_lower = rep.get("content", "").lower()
        if any(kw in content_lower for kw in ["workflow", "deploy", "test", "build", "comando"]):
            level = "procedural"
            kind = "workflow"
        elif any(kw in content_lower for kw in ["aprend", "lección", "insight"]):
            level = "reflection"
            kind = "learning"
        elif any(kw in content_lower for kw in ["prefiere", "le gusta", "quiere"]):
            level = "semantic"
            kind = "preference"
        else:
            level = "semantic"
            kind = "pattern"
        candidate = {
            "kind": kind, "level": level, "content": rep["content"],
            "importance": round(importance, 3), "confidence": round(confidence, 3),
            "tags": unique_tags, "source": "reflection",
            "meta": {"cluster_size": len(cluster), "cluster_ids": [n["id"] for n in cluster]},
        }
        candidates.append(candidate)
    promoted = 0
    for c in candidates:
        if c["importance"] < 0.4:
            continue
        result = write_governed(slug, c["level"], c)
        if result.get("ok") and result.get("action") in ("wrote", "merged"):
            promoted += 1
        for ev_id in c.get("meta", {}).get("cluster_ids", []):
            _mark_consolidated(slug, "episodic", ev_id)
    return {
        "events": len(events),
        "clusters": len(clusters),
        "candidates": candidates,
        "promoted": promoted,
    }


def _cluster_by_tokens(events: list, threshold: float = 0.2) -> list[list]:
    def tokens(text):
        return set(_tokenize(text))
    clusters = []
    for event in events:
        ev_tokens = tokens(event.get("content", ""))
        placed = False
        for cluster in clusters:
            rep = cluster[0]
            rep_tokens = tokens(rep.get("content", ""))
            if not ev_tokens or not rep_tokens:
                continue
            overlap = len(ev_tokens & rep_tokens)
            union = len(ev_tokens | rep_tokens)
            jaccard = overlap / union if union > 0 else 0
            if jaccard >= threshold:
                cluster.append(event)
                placed = True
                break
        if not placed:
            clusters.append([event])
    return clusters


def _mark_consolidated(slug: str, level: str, node_id: str) -> bool:
    db = schema.brain_db_path(slug, level)
    if not db.exists():
        return False
    conn = _connect(db)
    try:
        conn.execute("UPDATE nodes SET consolidated = 1 WHERE id = ?", (node_id,))
        conn.commit()
        return True
    finally:
        if str(db) not in _CONN_CACHE:
            conn.close()


# ── Auto-Compact ──────────────────────────────────────────────────

def should_compact(slug: str) -> dict:
    triggers = []
    gmd = schema.guardian_md_path(slug)
    if gmd.exists():
        lines = len(gmd.read_text(encoding="utf-8").splitlines())
        if lines >= GUARDIAN_MD_MAX_LINES:
            triggers.append(f"guardian_md_pressure ({lines} >= {GUARDIAN_MD_MAX_LINES})")
    sm_count = count(slug, "semantic")
    if sm_count > 100:
        triggers.append(f"sm_bloat ({sm_count} > 100)")
    em_count = count(slug, "episodic", filters={"needs_review": False})
    if em_count > 200:
        triggers.append(f"em_stale ({em_count} > 200)")
    return {
        "should": len(triggers) > 0,
        "triggers": triggers,
    }


def auto_compact(slug: str, dry_run: bool = False) -> dict:
    results = {}
    for level in ("semantic", "episodic", "procedural", "reflection"):
        results[f"gc_{level}"] = governor_gc(slug, level, dry_run=dry_run)
    results["reflection"] = run_reflection(slug) if not dry_run else {"skipped": "dry_run"}
    if not dry_run:
        gmd = regenerate_guardian_md(slug)
        results["guardian_md"] = {"lines": gmd.get("lines", 0)}
    return results


# ── Session lifecycle ────────────────────────────────────────────

def session_start(slug: str, mode: str = None) -> dict:
    schema.init_project(slug)
    wm = read_working_memory(slug)
    if not wm.get("session_started_at"):
        wm["session_started_at"] = _now_epoch()
    if mode:
        wm["mode"] = mode
    elif not wm.get("mode"):
        wm["mode"] = "read"
    write_working_memory(slug, wm)
    context = build_context(slug, wm["mode"])
    return {
        "slug": slug, "mode": wm["mode"],
        "guardian_md_lines": len(context["guardian_md"].splitlines()),
        "working_memory": wm,
        "levels_loaded": {k: len(v) for k, v in context["levels"].items()},
        "budget_used": context["budget_used"],
        "greeting": _format_greeting(slug, wm, context),
    }


def session_continue(slug: str) -> dict:
    schema.init_project(slug)
    handoff = read_handoff(slug)
    wm = read_working_memory(slug)
    if handoff:
        for k in ("goal", "task", "constraints", "progress", "mode"):
            if handoff.get(k) is not None:
                wm[k] = handoff[k]
        wm["resumed_from_session"] = handoff.get("written_at")
    wm["session_started_at"] = _now_epoch()
    write_working_memory(slug, wm)
    context = build_context(slug, wm.get("mode", "read"))
    return {
        "slug": slug, "mode": wm.get("mode", "read"),
        "handoff": handoff, "working_memory": wm,
        "greeting": _format_greeting(slug, wm, context, handoff=handoff),
    }


def session_end(slug: str, reason: str = "explicit") -> dict:
    schema.init_project(slug)
    wm = read_working_memory(slug)
    reflection = run_reflection(slug)
    compact_check = should_compact(slug)
    compact_result = None
    if compact_check["should"]:
        compact_result = auto_compact(slug, dry_run=False)
    gmd = regenerate_guardian_md(slug)
    handoff = {
        "last_session": _now_epoch(),
        "ended_in_mode": wm.get("mode"),
        "reason": reason,
        "goal": wm.get("goal"),
        "task": wm.get("task"),
        "constraints": wm.get("constraints", []),
        "progress": wm.get("progress", []),
        "open_questions": wm.get("open_questions", []),
        "next_suggestion": _suggest_next(slug, wm),
    }
    write_handoff(slug, handoff)
    return {
        "reflection": reflection, "compact": compact_result,
        "guardian_md": gmd, "handoff": handoff,
    }


def _format_greeting(slug: str, wm: dict, context: dict, handoff: dict = None) -> str:
    lines = [f"🛡️  Guardian v3 — {slug}", ""]
    if handoff:
        lines.append(f"👋 Hola de nuevo. Estuviste {int((_now_epoch() - handoff.get('written_at', _now_epoch())) / 86400)} días ausente.")
        lines.append("")
        if handoff.get("task"):
            lines.append(f"  Última task: {handoff['task']}")
    else:
        if not wm.get("goal"):
            lines.append("  Detecté el proyecto. Primera vez que lo veo.")
        else:
            lines.append("  Continuando.")
    if wm.get("goal"):
        lines.append(f"  Goal: {wm['goal']}")
    if wm.get("task"):
        lines.append(f"  Task: {wm['task']}")
    lines.append(f"  Modo: {wm.get('mode', 'read')}")
    if context.get("levels_loaded"):
        total = sum(context["levels_loaded"].values())
        lines.append(f"  Contexto cargado: {total} nodos esenciales")
    return "\n".join(lines)


def _suggest_next(slug: str, wm: dict) -> str:
    progress = wm.get("progress", [])
    if not progress:
        return "Definí un goal para empezar."
    for p in progress:
        if isinstance(p, str) and not p.startswith("✓"):
            return f"Continuar con: {p}"
    return "Todas las tareas marcadas como hechas. Definí un nuevo goal."


# ── Global brain operations ───────────────────────────────────────

def global_read(level: str, node_id: str) -> dict | None:
    if level not in schema.GLOBAL_LEVELS:
        raise ValueError(f"Invalid global level: {level}")
    db = schema.global_db_path(level)
    if not db.exists():
        return None
    conn = _connect(db)
    try:
        conn.execute(
            "UPDATE nodes SET last_accessed = ?, access_count = access_count + 1 WHERE id = ?",
            (_now_epoch(), node_id),
        )
        conn.commit()
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
        if row is None:
            return None
        return _row_to_dict(row)
    finally:
        conn.close()


def global_write(level: str, node: dict) -> dict:
    if level not in schema.GLOBAL_LEVELS:
        raise ValueError(f"Invalid global level: {level}")
    db = schema.global_db_path(level)
    conn = _connect(db)
    try:
        fields = _dict_to_node_fields(node)
        fields["project_slug"] = None
        cols = ", ".join(fields.keys())
        placeholders = ", ".join("?" for _ in fields)
        conn.execute(
            f"INSERT OR REPLACE INTO nodes ({cols}) VALUES ({placeholders})",
            list(fields.values()),
        )
        conn.commit()
        return {"ok": True, "id": fields["id"]}
    finally:
        if str(db) not in _CONN_CACHE:
            conn.close()


def global_query(level: str, q: str, top_k: int = 5) -> list[dict]:
    if level not in schema.GLOBAL_LEVELS:
        raise ValueError(f"Invalid global level: {level}")
    db = schema.global_db_path(level)
    if not db.exists():
        return []
    q_embed = embed(q)
    conn = _connect(db)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM nodes WHERE embedding IS NOT NULL").fetchall()
    finally:
        if str(db) not in _CONN_CACHE:
            conn.close()
    scored = []
    for row in rows:
        d = _row_with_embedding(row)
        node_emb = d.get("embedding")
        if not node_emb:
            continue
        sim = cosine(q_embed, node_emb)
        if sim > 0:
            scored.append((sim, d))
    scored.sort(key=lambda x: -x[0])
    result = []
    for sim, d in scored[:top_k]:
        if "embedding" in d:
            d["has_embedding"] = d["embedding"] is not None
            d["embedding_dim"] = EMBED_DIM if d["embedding"] else 0
            del d["embedding"]
        d["similarity"] = round(sim, 4)
        result.append(d)
    return result


def global_promote(slug: str, node_id: str, level: str = None) -> dict:
    if level is None:
        level = "semantic"
    if level not in schema.PROJECT_LEVELS:
        raise ValueError(f"Invalid project level: {level}")
    node = read(slug, level, node_id)
    if not node:
        return {"ok": False, "error": "node not found"}
    glevel_map = {"semantic": "semantic_g", "procedural": "procedural_g", "reflection": "reflection_g"}
    glevel = glevel_map.get(level)
    if not glevel:
        return {"ok": False, "error": f"project level {level} cannot be promoted"}
    new_node = {k: v for k, v in node.items() if k not in ("id", "project_slug", "embedding", "has_embedding", "embedding_dim")}
    result = global_write(glevel, new_node)
    return {
        "ok": True, "promoted_id": result["id"],
        "from_project": slug, "from_level": level, "to_global_level": glevel,
    }


def list_global_nodes(level: str, limit: int = 100, filters: dict = None) -> list[dict]:
    if level not in schema.GLOBAL_LEVELS:
        raise ValueError(f"Invalid global level: {level}")
    db = schema.global_db_path(level)
    if not db.exists():
        return []
    conn = _connect(db)
    try:
        conn.row_factory = sqlite3.Row
        where = []
        params = []
        if filters:
            if "kind" in filters:
                where.append("kind = ?")
                params.append(filters["kind"])
            if "min_importance" in filters:
                where.append("importance >= ?")
                params.append(float(filters["min_importance"]))
        sql = "SELECT * FROM nodes"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY importance DESC, created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def write_global_guardian_md(content: str) -> dict:
    gmd = schema.global_guardian_md_path()
    gmd.parent.mkdir(parents=True, exist_ok=True)
    gmd.write_text(content, encoding="utf-8")
    return {"ok": True, "path": str(gmd), "lines": len(content.splitlines())}


def read_global_guardian_md() -> str:
    gmd = schema.global_guardian_md_path()
    if not gmd.exists():
        return ""
    return gmd.read_text(encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
