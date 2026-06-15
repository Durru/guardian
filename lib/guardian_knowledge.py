#!/usr/bin/env python3
"""
Guardian Knowledge — research, refresh, scrape for the project's cognitive memory.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import guardian_brain
import guardian_brain_schema
import guardian_shared as shared


TTL_BY_KIND = {
    "research": 30,
    "docs": 90,
    "known_issues": 14,
    "best_practices": 60,
}

CLASSIFY_KEYWORDS = {
    "known_issues": [
        "error", "bug", "issue", "fail", "broken", "problema", "falla",
        "exception", "crash", "warning",
    ],
    "best_practices": [
        "best practice", "recomend", "patrón", "pattern", "convention",
        "style guide", "approach", "idiomatic", "should", "conviene",
    ],
    "docs": [
        "api", "reference", "documentation", "method", "function", "class",
        "parameter", "signature", "endpoint", "module", "import",
    ],
}


def _classify_kind(content: str, hint: str = None) -> str:
    if hint and hint in TTL_BY_KIND:
        return hint
    content_lower = content.lower()
    scores = {}
    for kind, keywords in CLASSIFY_KEYWORDS.items():
        scores[kind] = sum(1 for kw in keywords if kw in content_lower)
    best = max(scores, key=scores.get) if max(scores.values()) > 0 else "research"
    return best


def _detect_stack(content: str) -> list[str]:
    stacks = []
    content_lower = content.lower()
    stack_keywords = {
        "odoo": ["odoo", "openerp", "__manifest__", "res.partner", "res.users"],
        "nextjs": ["nextjs", "next.js", "app router", "server component", "getServerSideProps"],
        "fastapi": ["fastapi", "pydantic", "uvicorn", "starlette"],
        "postgres": ["postgres", "postgresql", "psql", "pg_dump"],
        "python": ["python", "pip", "pypi", "venv", "pyproject"],
        "react": ["react", "jsx", "usestate", "useeffect", "component"],
        "vue": ["vue", "vuex", "pinia", "composition api"],
        "rust": ["rust", "cargo", "rustc", "crate"],
        "typescript": ["typescript", "tsc", "tsx", "type:"],
        "docker": ["docker", "dockerfile", "compose"],
    }
    for stack, keywords in stack_keywords.items():
        if any(kw in content_lower for kw in keywords):
            stacks.append(stack)
    return stacks


def _extract_tags(content: str) -> list[str]:
    tags = set()
    for m in re.findall(r"#(\w+)", content):
        tags.add(m.lower())
    for m in re.findall(r"\b(?:v|version\s*)(\d+(?:\.\d+)*)\b", content, re.IGNORECASE):
        tags.add(f"v{m}")
    return list(tags)[:10]


def _url_checksum(url: str) -> str:
    raw = f"{url}:{int(time.time() // 3600)}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def _scrape_url(url: str) -> dict:
    try:
        result = subprocess.run(
            ["curl", "-sL", "--max-time", "15", "-A", "Guardian-Brain/1.0", url],
            capture_output=True, text=True, timeout=20,
        )
        if result.returncode != 0:
            return {"ok": False, "error": f"curl rc={result.returncode}"}
        content = result.stdout
        text = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return {"ok": True, "content": text, "raw_bytes": len(content), "text_chars": len(text)}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "scrape timeout"}
    except FileNotFoundError:
        return {"ok": False, "error": "curl not installed"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _summarize_scraped(text: str, max_chars: int = 4000) -> str:
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return text[:half] + "\n\n[... elided ...]\n\n" + text[-half:]


def research(slug: str, query: str, depth: str = "quick", context: dict = None) -> dict:
    guardian_brain_schema.init_project(slug)
    existing = guardian_brain.query(slug, "semantic", query, top_k=5)
    stacks = _detect_stack(query)
    kind = _classify_kind(query)
    ttl = TTL_BY_KIND.get(kind, 30)
    tags = _extract_tags(query)
    return {
        "slug": slug, "query": query, "kind": kind, "ttl_days": ttl,
        "stacks_detected": stacks, "tags_suggested": tags,
        "existing_knowledge": [
            {"id": n["id"], "content": n["content"], "similarity": n.get("similarity", 0)}
            for n in existing if n.get("similarity", 0) > 0.3
        ],
        "search_suggestions": _build_search_suggestions(query, stacks),
        "node_templates": [
            {
                "kind": kind, "level": "semantic",
                "content": f"[FILL: synthesized answer about: {query}]",
                "importance": 0.7, "confidence": 0.7, "ttl": ttl,
                "tags": tags, "stack": stacks, "source": "research",
            }
        ],
        "depth": depth,
    }


def _build_search_suggestions(query: str, stacks: list[str]) -> list[str]:
    base = [query]
    if stacks:
        for s in stacks:
            base.append(f"{s} {query}")
            base.append(f"{query} {s} best practices")
            base.append(f"{s} {query} common issues")
    base.append(f"{query} changelog")
    return list(dict.fromkeys(base))[:6]


def write_research(slug: str, kind: str, content: str, tags: list[str] = None,
                   stack: list[str] = None, importance: float = 0.7,
                   confidence: float = 0.7, url: str = None) -> dict:
    if kind not in TTL_BY_KIND:
        kind = "research"
    node = {
        "kind": kind, "content": content, "importance": importance,
        "confidence": confidence, "ttl": TTL_BY_KIND[kind],
        "tags": tags or [], "stack": stack or [],
        "source": "research" if kind != "docs" else "scrape",
    }
    if url:
        node["url"] = url
        node["source_checksum"] = _url_checksum(url)
    return guardian_brain.write_governed(slug, "semantic", node)


def scrape(slug: str, url: str, tags: list[str] = None) -> dict:
    guardian_brain_schema.init_project(slug)
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return {"ok": False, "error": "invalid URL"}
    except Exception as e:
        return {"ok": False, "error": f"URL parse failed: {e}"}
    scraped = _scrape_url(url)
    if not scraped["ok"]:
        return scraped
    text = _summarize_scraped(scraped["content"])
    detected_tags = _extract_tags(text)
    detected_stacks = _detect_stack(text)
    all_tags = list(set((tags or []) + detected_tags))
    node = {
        "kind": "docs", "content": text, "importance": 0.7,
        "confidence": 0.8, "ttl": TTL_BY_KIND["docs"],
        "tags": all_tags, "stack": detected_stacks, "source": "scrape",
        "url": url, "source_checksum": _url_checksum(url),
        "meta": {
            "raw_bytes": scraped.get("raw_bytes", 0),
            "text_chars": scraped.get("text_chars", 0),
            "scraped_at": time.time(),
        },
    }
    result = guardian_brain.write_governed(slug, "semantic", node)
    result["url"] = url
    result["scraped_chars"] = scraped.get("text_chars", 0)
    return result


def detect_stale(slug: str) -> list[dict]:
    guardian_brain_schema.init_project(slug)
    all_nodes = guardian_brain.list_nodes(slug, "semantic", limit=500)
    stale = []
    now = time.time()
    for node in all_nodes:
        if node.get("kind") not in TTL_BY_KIND:
            continue
        reasons = []
        ttl = node.get("ttl")
        if ttl:
            age_days = (now - node.get("created_at", now)) / 86400
            if age_days > ttl:
                reasons.append(f"ttl_expired ({age_days:.0f}d > {ttl}d)")
        last_acc = node.get("last_accessed", node.get("created_at", now))
        idle_days = (now - last_acc) / 86400
        if idle_days > 60 and ttl:
            reasons.append(f"idle ({idle_days:.0f}d)")
        if reasons:
            stale.append({
                "id": node["id"], "kind": node["kind"],
                "content": node["content"][:80], "reasons": reasons,
            })
    return stale


def refresh(slug: str, topic: str = None, force: bool = False) -> dict:
    guardian_brain_schema.init_project(slug)
    stale = detect_stale(slug)
    if topic:
        stale = [s for s in stale if topic.lower() in s["content"].lower()]
    refreshed = []
    for s in stale:
        node = guardian_brain.read(slug, "semantic", s["id"])
        if node:
            node["ttl"] = TTL_BY_KIND.get(node.get("kind", "research"), 30)
            node["importance"] = max(node.get("importance", 0.5), 0.6)
            result = guardian_brain.write_governed(slug, "semantic", node)
            if result.get("ok"):
                refreshed.append(s["id"])
    return {
        "ok": True, "stale_found": len(stale),
        "refreshed": len(refreshed), "topic": topic, "force": force,
    }


def list_knowledge(slug: str, kind: str = None, limit: int = 50) -> list[dict]:
    guardian_brain_schema.init_project(slug)
    filters = {"min_importance": 0.0}
    if kind:
        filters["kind"] = kind
    all_nodes = guardian_brain.list_nodes(slug, "semantic", filters=filters, limit=500)
    knowledge = [n for n in all_nodes if n.get("kind") in TTL_BY_KIND]
    return knowledge[:limit]


def show(slug: str, node_id: str) -> dict | None:
    return guardian_brain.read(slug, "semantic", node_id)


USAGE = """Guardian Knowledge — usage:
  research <slug> <query> [--depth=quick|deep]
  refresh <slug> [topic] [--force]
  scrape <slug> <url> [--tag=X,Y]
  stale <slug>
  list <slug> [--kind=research|docs|known_issues|best_practices] [--limit=N]
  show <slug> <node-id>
  write <slug> <kind> <content> [--tags=a,b] [--importance=N] [--url=...]
"""


def main():
    if len(sys.argv) < 2:
        print(USAGE)
        return 1
    cmd = sys.argv[1]
    if cmd == "research":
        if len(sys.argv) < 4:
            print("research requires slug and query")
            return 1
        slug = sys.argv[2]
        query = sys.argv[3]
        depth = "quick"
        for arg in sys.argv[4:]:
            if arg.startswith("--depth="):
                depth = arg.split("=", 1)[1]
        result = research(slug, query, depth=depth)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    if cmd == "write":
        if len(sys.argv) < 5:
            print("write requires slug, kind, content")
            return 1
        slug = sys.argv[2]
        kind = sys.argv[3]
        content = sys.argv[4]
        tags = None; stack = None; importance = 0.7; url = None
        for arg in sys.argv[5:]:
            if arg.startswith("--tags="):
                tags = arg.split("=", 1)[1].split(",")
            elif arg.startswith("--importance="):
                importance = float(arg.split("=", 1)[1])
            elif arg.startswith("--url="):
                url = arg.split("=", 1)[1]
            elif arg.startswith("--stack="):
                stack = arg.split("=", 1)[1].split(",")
        result = write_research(slug, kind, content, tags=tags, stack=stack, importance=importance, url=url)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    if cmd == "refresh":
        if len(sys.argv) < 3:
            print("refresh requires slug")
            return 1
        slug = sys.argv[2]
        topic = sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith("--") else None
        force = "--force" in sys.argv
        result = refresh(slug, topic=topic, force=force)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    if cmd == "scrape":
        if len(sys.argv) < 4:
            print("scrape requires slug and url")
            return 1
        slug = sys.argv[2]
        url = sys.argv[3]
        tags = None
        for arg in sys.argv[4:]:
            if arg.startswith("--tag="):
                tags = arg.split("=", 1)[1].split(",")
        result = scrape(slug, url, tags=tags)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    if cmd == "stale":
        if len(sys.argv) < 3:
            print("stale requires slug")
            return 1
        slug = sys.argv[2]
        result = detect_stale(slug)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    if cmd == "list":
        if len(sys.argv) < 3:
            print("list requires slug")
            return 1
        slug = sys.argv[2]
        kind = None; limit = 50
        for arg in sys.argv[3:]:
            if arg.startswith("--kind="):
                kind = arg.split("=", 1)[1]
            elif arg.startswith("--limit="):
                limit = int(arg.split("=", 1)[1])
        result = list_knowledge(slug, kind=kind, limit=limit)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    if cmd == "show":
        if len(sys.argv) < 4:
            print("show requires slug and node-id")
            return 1
        slug = sys.argv[2]
        nid = sys.argv[3]
        result = show(slug, nid)
        print(json.dumps(result, indent=2, ensure_ascii=False) if result else "null")
        return 0
    print(f"Unknown command: {cmd}")
    print(USAGE)
    return 1


if __name__ == "__main__":
    sys.exit(main())
