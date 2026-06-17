#!/usr/bin/env python3
"""
Guardian Lineage — track the genealogical tree of branches and projects.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import guardian_brain_schema
import guardian_shared as shared


def lineage_path(slug: str) -> Path:
    return guardian_brain_schema.brain_dir(slug) / "lineage.json"


def read_lineage(slug: str) -> dict:
    p = lineage_path(slug)
    if not p.exists():
        return {
            "slug": slug, "parent": None,
            "templates_cloned": [], "forks_made": [],
            "clones_made": [], "published_templates": [],
        }
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return read_lineage(slug)


def write_lineage(slug: str, lineage: dict) -> dict:
    p = lineage_path(slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(lineage, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "path": str(p)}


def record_parent(slug: str, parent: str) -> dict:
    lineage = read_lineage(slug)
    lineage["parent"] = parent
    return write_lineage(slug, lineage)


def record_template_cloned(slug: str, template_name: str, version: str) -> dict:
    lineage = read_lineage(slug)
    tpl_entry = f"{template_name}@{version}"
    if tpl_entry not in lineage.get("templates_cloned", []):
        lineage.setdefault("templates_cloned", []).append(tpl_entry)
    return write_lineage(slug, lineage)


def record_fork(slug: str, child: str) -> dict:
    lineage = read_lineage(slug)
    if child not in lineage.get("forks_made", []):
        lineage.setdefault("forks_made", []).append(child)
    return write_lineage(slug, lineage)


def format_tree(slug: str, indent: int = 0) -> str:
    lineage = read_lineage(slug)
    prefix = "  " * indent
    lines = [f"{prefix}🌳 {slug}"]
    if lineage.get("parent"):
        lines.append(f"{prefix}  ↑ forked from: {lineage['parent']}")
    if lineage.get("templates_cloned"):
        for t in lineage["templates_cloned"]:
            lines.append(f"{prefix}  📦 template: {t}")
    if lineage.get("forks_made"):
        for f in lineage["forks_made"]:
            lines.append(f"{prefix}  ⤴  fork: {f}")
    if lineage.get("clones_made"):
        for c in lineage["clones_made"]:
            lines.append(f"{prefix}  📋 clone: {c}")
    if lineage.get("published_templates"):
        for p in lineage["published_templates"]:
            lines.append(f"{prefix}  📤 published: {p}")
    return "\n".join(lines)


USAGE = """Guardian Lineage — usage:
  show <slug> [--tree]
  record-parent <slug> <parent-slug>
  record-template <slug> <template-name> <version>
  record-fork <slug> <child-slug>
"""


def main():
    if len(sys.argv) < 2:
        print(USAGE)
        return 1
    cmd = sys.argv[1]
    if cmd == "show":
        if len(sys.argv) < 3:
            print("show requires slug")
            return 1
        slug = sys.argv[2]
        tree = "--tree" in sys.argv
        lineage = read_lineage(slug)
        if tree:
            print(format_tree(slug))
        else:
            print(json.dumps(lineage, indent=2, ensure_ascii=False))
        return 0
    if cmd == "record-parent":
        if len(sys.argv) < 4:
            print("record-parent requires slug and parent")
            return 1
        result = record_parent(sys.argv[2], sys.argv[3])
        return 0 if result.get("ok") else 1
    if cmd == "record-template":
        if len(sys.argv) < 5:
            print("record-template requires slug, name, version")
            return 1
        result = record_template_cloned(sys.argv[2], sys.argv[3], sys.argv[4])
        return 0 if result.get("ok") else 1
    if cmd == "record-fork":
        if len(sys.argv) < 4:
            print("record-fork requires slug and child")
            return 1
        result = record_fork(sys.argv[2], sys.argv[3])
        return 0 if result.get("ok") else 1
    print(f"Unknown command: {cmd}")
    print(USAGE)
    return 1


if __name__ == "__main__":
    sys.exit(main())
