#!/usr/bin/env python3
"""
Guardian Publish — publish, clone, fork, and template management.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path

import guardian_brain
import guardian_brain_schema
import guardian_genome
import guardian_shared as shared


TEMPLATES_DIR = Path.home() / ".guardian" / "templates"


SECRET_PATTERNS = [
    (re.compile(r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*[\w\-\.]+"), "[REDACTED_KEY]"),
    (re.compile(r"https?://[^\s]*:[^\s]*@"), "[REDACTED_URL]"),
    (re.compile(r"\bsk-[a-zA-Z0-9]+\b"), "[REDACTED_KEY]"),
    (re.compile(r"/Users/[^/\s]+/"), "/Users/[USER]/"),
    (re.compile(r"/home/[^/\s]+/"), "/home/[USER]/"),
    (re.compile(r"postgres://[^@\s]+@"), "postgres://[USER]@"),
    (re.compile(r"postgresql://[^@\s]+@"), "postgresql://[USER]@"),
]


def sanitize_text(text: str) -> str:
    if not text:
        return text
    for pat, repl in SECRET_PATTERNS:
        text = pat.sub(repl, text)
    return text


def build_manifest(slug: str, version: str) -> dict:
    now_iso = datetime.now(timezone.utc).isoformat()
    config_path = (shared.BACKEND_DIR / "genome" / "branches" / shared._branch_hash()
                   / "projects" / slug / "config.yaml")
    config = {}
    if config_path.exists():
        try:
            import yaml
            config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except Exception:
            pass
    return {
        "name": slug, "version": version, "created": now_iso,
        "author": config.get("creator", "unknown"),
        "description": config.get("description", ""),
        "clonable": True, "production_ready": True,
        "inherits": {
            "semantic": ["decisions", "preferences", "skills", "dependencies"],
            "procedural": ["workflows", "deployment", "testing"],
            "reflection": ["learnings", "patterns"],
        },
        "excludes": {"episodic": True, "working": True, "identity": True},
        "stack": config.get("stack", {}),
    }


def publish(slug: str, version: str = "1.0.0", to: str = "template") -> dict:
    guardian_brain_schema.init_project(slug)
    if to == "template":
        target_dir = TEMPLATES_DIR / slug / version
    else:
        target_dir = guardian_brain_schema.production_dir(slug) / version
    target_dir.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(slug, version)
    (target_dir / "manifest.yaml").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    snapshot = {"nodes": {}, "edges": {}}
    for level in ("semantic", "procedural", "reflection"):
        db = guardian_brain_schema.brain_db_path(slug, level)
        if not db.exists():
            continue
        nodes = guardian_brain.list_nodes(slug, level, limit=1000)
        sanitized_nodes = []
        for n in nodes:
            sanitized = dict(n)
            if "content" in sanitized:
                sanitized["content"] = sanitize_text(sanitized["content"])
            if "tags" in sanitized and isinstance(sanitized["tags"], list):
                sanitized["tags"] = [sanitize_text(t) for t in sanitized["tags"]]
            sanitized_nodes.append(sanitized)
        snapshot["nodes"][level] = sanitized_nodes
    (target_dir / "snapshot.json").write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    checksums = {}
    for f in target_dir.iterdir():
        if f.is_file():
            checksums[f.name] = hashlib.sha256(f.read_bytes()).hexdigest()[:16]
    (target_dir / "checksums.json").write_text(
        json.dumps(checksums, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return {
        "ok": True, "slug": slug, "version": version,
        "target": str(target_dir),
        "nodes_count": sum(len(v) for v in snapshot["nodes"].values()),
    }


def clone(template_slug: str, new_slug: str) -> dict:
    tpl_dir = TEMPLATES_DIR / template_slug
    if not tpl_dir.exists():
        return {"ok": False, "error": f"template not found: {template_slug}"}
    versions = [d.name for d in tpl_dir.iterdir() if d.is_dir()]
    if not versions:
        return {"ok": False, "error": "no versions found"}
    version = sorted(versions)[-1]
    tpl_version_dir = tpl_dir / version
    snapshot_path = tpl_version_dir / "snapshot.json"
    if not snapshot_path.exists():
        return {"ok": False, "error": "snapshot.json missing"}
    try:
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return {"ok": False, "error": f"snapshot load failed: {e}"}
    guardian_brain_schema.init_project(new_slug)
    written = {"semantic": 0, "procedural": 0, "reflection": 0, "skipped": 0}
    for level, nodes in snapshot.get("nodes", {}).items():
        for node in nodes:
            clean = {k: v for k, v in node.items()
                     if k not in ("id", "project_slug", "embedding", "has_embedding", "embedding_dim", "access_count", "last_accessed", "created_at")}
            result = guardian_brain.write_governed(new_slug, level, clean)
            if result.get("ok"):
                written[level] = written.get(level, 0) + 1
            else:
                written["skipped"] += 1
    guardian_brain.regenerate_guardian_md(new_slug)
    return {
        "ok": True, "new_slug": new_slug, "from_template": template_slug,
        "from_version": version, "written": written,
    }


def fork(parent_slug: str, child_slug: str) -> dict:
    guardian_brain_schema.init_project(parent_slug)
    guardian_brain_schema.init_project(child_slug)
    written = {}
    for level in ("semantic", "episodic", "procedural", "reflection"):
        nodes = guardian_brain.list_nodes(parent_slug, level, limit=10000)
        count = 0
        for n in nodes:
            clean = {k: v for k, v in n.items()
                     if k not in ("id", "project_slug", "embedding", "has_embedding", "embedding_dim", "access_count", "last_accessed", "created_at")}
            clean["meta"] = clean.get("meta") or {}
            if isinstance(clean["meta"], str):
                try:
                    clean["meta"] = json.loads(clean["meta"])
                except Exception:
                    clean["meta"] = {}
            clean["meta"]["forked_from"] = parent_slug
            result = guardian_brain.write_governed(child_slug, level, clean)
            if result.get("ok"):
                count += 1
        written[level] = count
    parent_wm = guardian_brain.read_working_memory(parent_slug)
    if parent_wm:
        parent_wm["meta"] = parent_wm.get("meta") or {}
        if isinstance(parent_wm.get("meta"), dict):
            parent_wm["meta"]["forked_from"] = parent_slug
        guardian_brain.write_working_memory(child_slug, parent_wm)
    guardian_brain.regenerate_guardian_md(child_slug)
    return {
        "ok": True, "child_slug": child_slug, "parent_slug": parent_slug, "written": written,
    }


def list_templates() -> list[dict]:
    if not TEMPLATES_DIR.exists():
        return []
    result = []
    for d in sorted(TEMPLATES_DIR.iterdir()):
        if not d.is_dir():
            continue
        versions = [v.name for v in d.iterdir() if v.is_dir()]
        if not versions:
            continue
        latest = sorted(versions)[-1]
        manifest_path = d / latest / "manifest.yaml"
        manifest = {}
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        result.append({
            "name": d.name, "versions": versions, "latest": latest,
            "description": manifest.get("description", ""),
        })
    return result


def show_template(slug: str) -> dict | None:
    d = TEMPLATES_DIR / slug
    if not d.exists():
        return None
    versions = [v.name for v in d.iterdir() if v.is_dir()]
    if not versions:
        return None
    latest = sorted(versions)[-1]
    manifest_path = d / latest / "manifest.yaml"
    manifest = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"name": slug, "versions": versions, "latest": latest, "manifest": manifest, "path": str(d)}


def export_template(slug: str, target_path: str = None) -> dict:
    d = TEMPLATES_DIR / slug
    if not d.exists():
        return {"ok": False, "error": f"template not found: {slug}"}
    if target_path is None:
        target_path = str(Path.cwd() / f"{slug}.tar.gz")
    try:
        with tarfile.open(target_path, "w:gz") as tar:
            tar.add(str(d), arcname=slug)
        return {"ok": True, "path": target_path}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def import_template(archive_path: str) -> dict:
    if not Path(archive_path).exists():
        return {"ok": False, "error": "file not found"}
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(TEMPLATES_DIR)
        return {"ok": True, "extracted_to": str(TEMPLATES_DIR)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


USAGE = """Guardian Publish — usage:
  publish <slug> [--to=template|production] [--version=X.Y.Z]
  clone <template-slug> <new-slug>
  fork <parent-slug> <child-slug>
  templates list
  templates show <slug>
  templates export <slug> [target-path]
  templates import <archive.tar.gz>
"""


def main():
    if len(sys.argv) < 2:
        print(USAGE)
        return 1
    cmd = sys.argv[1]
    if cmd == "publish":
        if len(sys.argv) < 3:
            print("publish requires slug")
            return 1
        slug = sys.argv[2]
        to = "template"
        version = f"1.0.{int(time.time()) % 1000}"
        for arg in sys.argv[3:]:
            if arg.startswith("--to="):
                to = arg.split("=", 1)[1]
            elif arg.startswith("--version="):
                version = arg.split("=", 1)[1]
        result = publish(slug, version=version, to=to)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    if cmd == "clone":
        if len(sys.argv) < 4:
            print("clone requires template-slug and new-slug")
            return 1
        result = clone(sys.argv[2], sys.argv[3])
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    if cmd == "fork":
        if len(sys.argv) < 4:
            print("fork requires parent-slug and child-slug")
            return 1
        result = fork(sys.argv[2], sys.argv[3])
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    if cmd == "templates":
        if len(sys.argv) < 3:
            print("templates requires subcommand")
            return 1
        sub = sys.argv[2]
        if sub == "list":
            print(json.dumps(list_templates(), indent=2, ensure_ascii=False))
            return 0
        if sub == "show":
            if len(sys.argv) < 4:
                print("templates show requires slug")
                return 1
            result = show_template(sys.argv[3])
            print(json.dumps(result, indent=2, ensure_ascii=False) if result else "null")
            return 0
        if sub == "export":
            if len(sys.argv) < 4:
                print("templates export requires slug")
                return 1
            slug = sys.argv[3]
            target = sys.argv[4] if len(sys.argv) > 4 else None
            result = export_template(slug, target)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result.get("ok") else 1
        if sub == "import":
            if len(sys.argv) < 4:
                print("templates import requires archive path")
                return 1
            result = import_template(sys.argv[3])
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result.get("ok") else 1
    print(f"Unknown command: {cmd}")
    print(USAGE)
    return 1


if __name__ == "__main__":
    sys.exit(main())
