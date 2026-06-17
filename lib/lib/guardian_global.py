#!/usr/bin/env python3
"""
Guardian Global — cross-project shared memory.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import guardian_brain
import guardian_brain_schema
import guardian_shared as shared


GLOBAL_STACKS = {
    "odoo", "nextjs", "fastapi", "postgres", "python",
    "react", "vue", "rust", "typescript", "docker",
    "kubernetes", "aws", "gcp", "azure", "redis", "kafka",
}

USER_PATTERNS = {"preference", "user_pattern"}


def classify_for_global(node: dict, project_ctx: dict, global_ctx: dict) -> dict:
    score_global = 0
    score_project = 0
    tags = set(node.get("tags") or [])
    stack = set(node.get("stack") or [])
    kind = node.get("kind", "")

    if stack & GLOBAL_STACKS:
        score_global += 4
    if tags & GLOBAL_STACKS:
        score_global += 2
    if kind in USER_PATTERNS:
        score_global += 5
    if _exists_similar_in_global(node, global_ctx):
        score_global += 3
    project_name = project_ctx.get("project_name") or project_ctx.get("slug", "")
    if project_name and project_name.lower() in node.get("content", "").lower():
        score_project += 5
    if kind == "decision" and project_name and project_name.lower() in node.get("content", "").lower():
        score_project += 3

    glevel = None
    if score_global > score_project:
        if kind in ("decision", "preference", "skill", "best_practices", "research", "docs"):
            glevel = "semantic_g"
        elif kind in ("workflow",):
            glevel = "procedural_g"
        elif kind in ("learning", "insight"):
            glevel = "reflection_g"
        return {"scope": "global", "glevel": glevel, "score": score_global}
    return {"scope": "project", "score": score_project}


def _exists_similar_in_global(node: dict, global_ctx: dict) -> bool:
    glevel = "semantic_g" if node.get("kind") != "workflow" else "procedural_g"
    existing = guardian_brain.global_query(glevel, node.get("content", ""), top_k=3)
    return any(e.get("similarity", 0) > 0.7 for e in existing)


def read_global_guardian_md() -> str:
    return guardian_brain.read_global_guardian_md()


def regenerate_global_guardian_md() -> dict:
    parts = ["# GUARDIAN — GLOBAL", "", "## Cross-project essentials", ""]
    sm_nodes = []
    for node in guardian_brain.list_global_nodes("semantic_g", limit=10):
        sm_nodes.append(node)
    if sm_nodes:
        parts.append("### Semantic (knowledge)")
        for n in sm_nodes[:5]:
            parts.append(f"- [{n['kind']}] {n['content']}")
        parts.append("")
    pm_nodes = guardian_brain.list_global_nodes("procedural_g", limit=5)
    if pm_nodes:
        parts.append("### Procedural (workflows)")
        for n in pm_nodes[:5]:
            parts.append(f"- {n['content']}")
        parts.append("")
    rm_nodes = guardian_brain.list_global_nodes("reflection_g", limit=5)
    if rm_nodes:
        parts.append("### User profile")
        for n in rm_nodes:
            parts.append(f"- {n['content']}")
        parts.append("")
    content = "\n".join(parts)
    return guardian_brain.write_global_guardian_md(content)


def list_stacks() -> list[dict]:
    from guardian_specialization import list_available
    specs = list_available()
    stacks = []
    for s in specs:
        if s.get("is_builtin"):
            stacks.append({
                "name": s["name"], "version": s["version"],
                "description": s["description"], "type": "specialization",
            })
    try:
        from guardian_specialization import SPEC_DIR
        if SPEC_DIR.exists():
            for d in SPEC_DIR.iterdir():
                if d.is_dir() and (d / "manifest.yaml").exists():
                    name = d.name
                    if not any(s["name"] == name for s in stacks):
                        stacks.append({"name": name, "type": "installed"})
    except Exception:
        pass
    return stacks


def show_stack(name: str) -> dict:
    from guardian_specialization import show as spec_show
    return spec_show(name)


def user_profile() -> dict:
    nodes = guardian_brain.list_global_nodes("reflection_g", limit=50)
    prefs = [n for n in nodes if n.get("kind") in ("preference", "user_pattern", "learning")]
    return {
        "total_reflections": len(nodes),
        "preferences": [n["content"] for n in prefs if n.get("kind") == "preference"],
        "patterns": [n["content"] for n in prefs if n.get("kind") == "user_pattern"],
        "learnings": [n["content"] for n in prefs if n.get("kind") == "learning"],
    }


USAGE = """Guardian Global — usage:
  status
  read
  search <query>
  promote <slug> <node-id>
  stacks list
  stacks show <stack>
  user profile
"""


def main():
    if len(sys.argv) < 2:
        print(USAGE)
        return 1
    cmd = sys.argv[1]
    if cmd == "status":
        result = guardian_brain_schema.status(None)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    if cmd == "read":
        content = read_global_guardian_md()
        print(content if content else "(global GUARDIAN.md does not exist)")
        return 0
    if cmd == "search":
        if len(sys.argv) < 3:
            print("search requires query")
            return 1
        query = " ".join(sys.argv[2:])
        results = guardian_brain.global_query("semantic_g", query, top_k=5)
        for r in results:
            print(f"  {r.get('similarity', 0):.2f} {r['content'][:80]}")
        return 0
    if cmd == "promote":
        if len(sys.argv) < 4:
            print("promote requires slug and node-id")
            return 1
        slug, nid = sys.argv[2], sys.argv[3]
        result = guardian_brain.global_promote(slug, nid)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    if cmd == "stacks":
        if len(sys.argv) < 3:
            print("stacks requires subcommand")
            return 1
        sub = sys.argv[2]
        if sub == "list":
            print(json.dumps(list_stacks(), indent=2, ensure_ascii=False))
            return 0
        if sub == "show":
            if len(sys.argv) < 4:
                print("stacks show requires name")
                return 1
            name = sys.argv[3]
            print(json.dumps(show_stack(name), indent=2, ensure_ascii=False))
            return 0
    if cmd == "user":
        if len(sys.argv) < 3:
            print("user requires subcommand")
            return 1
        sub = sys.argv[2]
        if sub == "profile":
            print(json.dumps(user_profile(), indent=2, ensure_ascii=False))
            return 0
    print(f"Unknown command: {cmd}")
    print(USAGE)
    return 1


if __name__ == "__main__":
    sys.exit(main())
