#!/usr/bin/env python3
"""
Guardian RAG — context enrichment pipeline for LLMs.
Three-phase: 1) Chunk docs, code, memory. 2) TF-IDF retrieval + rerank.
3) Format enriched context with citations.

Subcommands:
  <query>       Run a RAG query (default)
  index         Precompute and cache chunks
"""
import sys
import json
import re
import hashlib
from pathlib import Path
from datetime import datetime, timezone

import guardian_shared as shared
from guardian_shared import _
from guardian_memory import (
    _tokenize,
    _compute_tfidf_index,
    _embed_text,
    _cosine_sim,
    _read_entries,
)

MEMORY_DIR = shared.MEMORY_DIR

CODE_EXTS = {".py", ".js", ".ts", ".tsx", ".md", ".json", ".yaml", ".yml"}

TYPE_WEIGHTS = {
    "doc": 0.6,
    "tome": 0.9,
    "code": 0.7,
    "landmark": 1.0,
    "decision": 0.8,
    "pattern": 0.7,
    "note": 0.5,
    "analysis": 0.4,
    "memory": 0.5,
}

MAX_CHUNK_LINES = 50
CHUNK_OVERLAP = 10

# Rough token estimation: ~4 chars per token
CHARS_PER_TOKEN = 4


def _slugify(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def _auto_slug():
    cwd = Path.cwd()
    slug = _slugify(cwd.name)
    if (MEMORY_DIR / slug / "config.yaml").exists():
        return slug
    for parent in cwd.parents:
        s = _slugify(parent.name)
        if (MEMORY_DIR / s / "config.yaml").exists():
            return s
    return None


def _highlight(text, query_tokens):
    if not query_tokens:
        return text
    for tok in query_tokens:
        if len(tok) < 2:
            continue
        pattern = re.compile(re.escape(tok), re.IGNORECASE)
        text = pattern.sub(lambda m: f"\033[1;33m{m.group(0)}\033[0m", text)
    return text


# ── Chunking ──

def _chunk_docs(slug, config):
    chunks = []
    routes = shared.get_docs_routes(config)
    root = Path(config.get("project_root", "."))
    for pattern, doc_name in routes.items():
        doc_path = root / doc_name
        if not doc_path.exists() or not doc_path.is_file():
            continue
        text = doc_path.read_text(encoding="utf-8", errors="replace")
        sections = re.split(r'\n(?=#{1,3}\s)', text)
        for sec in sections:
            lines = sec.strip().splitlines()
            if not lines:
                continue
            header = lines[0] if lines[0].startswith("#") else doc_name
            content = "\n".join(lines).strip()
            if len(content) < 20:
                continue
            chunks.append({
                "source": "doc",
                "doc_name": doc_name,
                "section": header.lstrip("#").strip(),
                "content": content[:800],
                "type_weight": TYPE_WEIGHTS["doc"],
            })
    return chunks


def _chunk_code(project_root):
    chunks = []
    root = Path(project_root)
    if not root.exists():
        return chunks
    for f in sorted(root.rglob("*")):
        if f.is_dir() or f.suffix not in CODE_EXTS:
            continue
        rel = f.relative_to(root)
        parts = rel.parts
        if any(p.startswith(".") or p in ("__pycache__", "node_modules", "venv", ".venv")
               for p in parts):
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        lines = text.splitlines()
        if not lines:
            continue
        if len(lines) <= MAX_CHUNK_LINES:
            chunks.append({
                "source": "code",
                "file": str(rel),
                "line_start": 1,
                "line_end": len(lines),
                "content": "\n".join(lines),
                "type_weight": TYPE_WEIGHTS["code"],
            })
        else:
            for start in range(0, len(lines), MAX_CHUNK_LINES - CHUNK_OVERLAP):
                end = min(start + MAX_CHUNK_LINES, len(lines))
                chunk_lines = lines[start:end]
                chunks.append({
                    "source": "code",
                    "file": str(rel),
                    "line_start": start + 1,
                    "line_end": end,
                    "content": "\n".join(chunk_lines),
                    "type_weight": TYPE_WEIGHTS["code"],
                })
    return chunks


def _chunk_memory(slug):
    chunks = []
    entries = _read_entries(slug)
    now = int(datetime.now(timezone.utc).timestamp())
    for e in entries:
        ts = shared.ts_epoch(e.get("ts", ""))
        age_days = (now - ts) / 86400 if ts else 999
        ttl = e.get("ttl", 30)
        if age_days > ttl:
            continue
        content = (e.get("content") or "").strip()
        if not content:
            continue
        type_ = e.get("type", "note")
        chunks.append({
            "source": "memory",
            "type": type_,
            "id": e.get("id", ""),
            "content": content[:400],
            "ts": e.get("ts", ""),
            "hits": e.get("hits", 0),
            "scope": e.get("scope", ""),
            "age_days": age_days,
            "type_weight": TYPE_WEIGHTS.get(type_, TYPE_WEIGHTS["memory"]),
        })
    return chunks


def _chunk_knowledge(slug):
    chunks = []
    base = MEMORY_DIR / slug / "knowledge" / "tomes"
    if not base.exists():
        return chunks
    for path in sorted(base.rglob("*")):
        if path.is_dir() or path.suffix not in {".md", ".markdown", ".json", ".txt"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if not text.strip():
            continue
        rel = path.relative_to(base.parent.parent)
        chunks.append({
            "source": "knowledge",
            "kind": "tome",
            "file": str(rel),
            "content": text[:800],
            "type_weight": TYPE_WEIGHTS["tome"],
        })
    return chunks


def _collect_chunks(slug, config, source_filter=None):
    chunks = []
    sources = source_filter or {"doc", "code", "memory", "knowledge"}
    if "doc" in sources:
        chunks.extend(_chunk_docs(slug, config))
    if "code" in sources:
        chunks.extend(_chunk_code(config.get("project_root", ".")))
    if "memory" in sources:
        chunks.extend(_chunk_memory(slug))
    if "knowledge" in sources:
        chunks.extend(_chunk_knowledge(slug))
    return chunks


# ── Retrieval + Reranking ──

def _rerank(chunks, idf, vocab, query_vec, scope_filter):
    """Rerank chunks with hybrid TF-IDF + embedding scoring. v4.6.0."""
    try:
        import guardian_brain as brain
        q_emb = brain.embed(" ".join(query_vec[:20])) if query_vec else None
        embs = [brain.embed(c["content"][:200]) for c in chunks] if q_emb else []
        emb_sims = brain.cosine_bulk(q_emb, embs) if q_emb and embs else []
    except Exception:
        emb_sims = []

    scored = []
    for i, c in enumerate(chunks):
        c_vec = _embed_text(c["content"], idf, vocab)
        sim = _cosine_sim(query_vec, c_vec)
        emb_sim = emb_sims[i] if i < len(emb_sims) else 0.0

        recency = max(0.0, 1.0 - c.get("age_days", 999) / 90.0)
        type_w = c.get("type_weight", 0.5)
        hits = min(c.get("hits", 0) / 10.0, 1.0)
        scope = 1.0 if (scope_filter and c.get("scope", "") and
                        scope_filter in c["scope"]) else 0.0

        score = sim * 0.30 + emb_sim * 0.30 + recency * 0.15 + type_w * 0.10 + hits * 0.10 + scope * 0.05
        c["_score"] = round(score, 4)
        c["_sim"] = round(sim, 4)
        c["_emb_sim"] = round(emb_sim, 4)
        scored.append(c)

    scored.sort(key=lambda x: x["_score"], reverse=True)
    return scored


def _fmt_citation(c):
    src = c["source"]
    if src == "doc":
        return _("📄 {doc_name} § {section}", doc_name=c["doc_name"], section=c["section"])
    elif src == "code":
        return _("📁 {file}:{line_start}-{line_end}", file=c["file"],
                 line_start=c["line_start"], line_end=c["line_end"])
    elif src == "memory":
        return _("🧠 {type}: {content}", type=c["type"],
                 content=c["content"][:80])
    elif src == "knowledge":
        return _("📚 {file}", file=c.get("file", "tome"))
    return src


# ── Index subcommand ──

def _chunks_file(slug):
    path = MEMORY_DIR / slug / "rag-chunks.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def cmd_index(slug, force=False):
    config = shared.read_config(slug)
    if not config:
        print(_("  ❌ Proyecto '{slug}' no encontrado.", slug=slug))
        return 1

    cache_path = _chunks_file(slug)
    if cache_path.exists() and not force:
        print(_("  Chunks ya cacheados ({n}). Usá --force para reindexar.",
                n=len(json.loads(cache_path.read_text()))))
        return 0

    chunks = _collect_chunks(slug, config)
    if not chunks:
        print(_("  Sin fuentes disponibles para indexar."))
        return 0

    flat = []
    for c in chunks:
        entry = {k: v for k, v in c.items() if k != "content"}
        entry["content_hash"] = hashlib.md5(c["content"].encode()).hexdigest()[:16]
        flat.append(entry)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(flat, ensure_ascii=False, indent=2))
    print(_("  ✅ {n} fragmentos indexados para {slug}", n=len(flat), slug=slug))
    return 0


# ── Query command ──

def cmd_rag(slug, query, top_k=10, scope_filter=None, json_output=False,
            source_filter=None, max_tokens=None, highlight=True):
    config = shared.read_config(slug)
    if not config:
        print(_("  ❌ Proyecto '{slug}' no encontrado.", slug=slug))
        return 1

    chunks = _collect_chunks(slug, config, source_filter)
    if not chunks:
        print(_("  Sin fuentes disponibles para RAG."))
        return 0

    contents = [c["content"] for c in chunks]
    idf, vocab = _compute_tfidf_index([{"content": ct} for ct in contents])

    query_vec = _embed_text(query, idf, vocab)
    if not any(query_vec):
        print(_("  La consulta no generó términos de búsqueda."))
        return 0

    all_scored = _rerank(chunks, idf, vocab, query_vec, scope_filter)

    if max_tokens:
        budget = max_tokens
        top = []
        for c in all_scored:
            cost = max(1, len(c["content"]) // CHARS_PER_TOKEN)
            if cost <= budget:
                top.append(c)
                budget -= cost
            if budget <= 0:
                break
    else:
        top = all_scored[:top_k]

    query_tokens = _tokenize(query) if highlight else []

    if json_output:
        results = []
        for c in top:
            r = {
                "score": c["_score"],
                "sim": c["_sim"],
                "source": c["source"],
                "content": c["content"][:300],
                "citation": _fmt_citation(c),
            }
            if c["source"] == "doc":
                r["doc_name"] = c.get("doc_name", "")
                r["section"] = c.get("section", "")
            elif c["source"] == "code":
                r["file"] = c.get("file", "")
                r["line_start"] = c.get("line_start", 0)
                r["line_end"] = c.get("line_end", 0)
            elif c["source"] == "memory":
                r["memory_type"] = c.get("type", "")
            results.append(r)
        print(json.dumps({"query": query, "slug": slug,
                          "total_chunks": len(chunks), "results": results},
                         ensure_ascii=False, indent=2))
    else:
        print(_("\n  🔍 RAG: \"{query}\"", query=query))
        print(_("  Proyecto: {slug}  |  {n} fragmentos analizados",
                slug=slug, n=len(chunks)))
        print()
        for i, c in enumerate(top, 1):
            sim_pct = c["_sim"] * 100
            score_pct = c["_score"] * 100
            citation = _fmt_citation(c)
            print(_("  [{i}] score={score_pct:.0f}%  sim={sim_pct:.0f}%",
                    i=i, score_pct=score_pct, sim_pct=sim_pct))
            print(_("      {citation}", citation=citation))
            snippet = c["content"][:200].replace("\n", " ")
            if query_tokens:
                snippet = _highlight(snippet, query_tokens)
            print(_("      {snippet}", snippet=snippet))
            print()

    return 0


# ── CLI ──

def main():
    if len(sys.argv) < 2:
        print(_("Uso: {cmd} <comando> [args...]", cmd=sys.argv[0]))
        print()
        print(_("Comandos:"))
        print(_("  <query>             Ejecutar búsqueda RAG"))
        print(_("  index [--slug]      Precomputar y cachear fragmentos"))
        print()
        print(_("Opciones de búsqueda:"))
        print(_("  --slug <slug>       Proyecto (auto-detect si no se especifica)"))
        print(_("  --top-k <n>         Cantidad de resultados (default: 10)"))
        print(_("  --json              Salida en JSON"))
        print(_("  --scope <path>      Filtrar por scope/path"))
        print(_("  --source <tipo>     Fuente: doc, code, memory (default: todas)"))
        print(_("  --max-tokens <n>    Límite de tokens en la respuesta"))
        print(_("  --no-highlight      Desactivar resaltado de términos"))
        return 1

    cmd = sys.argv[1]

    if cmd == "index":
        args = sys.argv[2:]
        slug = None
        force = "--force" in args
        for i, a in enumerate(args):
            if a == "--slug" and i + 1 < len(args):
                slug = args[i + 1]
        if not slug:
            slug = _auto_slug()
        if not slug:
            print(_("  No se pudo detectar el proyecto. Usá --slug <nombre>."))
            return 1
        return cmd_index(slug, force)

    if cmd == "serve":
        print(_("  El servidor RAG ahora está integrado en el dashboard web."))
        print(_("  Usá: guardian web"))
        print(_("  Luego: http://127.0.0.1:7878/rag/?q=...&slug=..."))
        return 0

    # Default: query
    args = sys.argv[1:]
    query = None
    slug = None
    top_k = 10
    json_output = False
    scope_filter = None
    source_filter = None
    max_tokens = None
    no_highlight = False

    i = 0
    source_list = []
    while i < len(args):
        if args[i] == "--slug" and i + 1 < len(args):
            slug = args[i + 1]
            i += 2
        elif args[i] == "--top-k" and i + 1 < len(args):
            top_k = int(args[i + 1])
            i += 2
        elif args[i] == "--json":
            json_output = True
            i += 1
        elif args[i] == "--scope" and i + 1 < len(args):
            scope_filter = args[i + 1]
            i += 2
        elif args[i] == "--source" and i + 1 < len(args):
            source_list.append(args[i + 1])
            i += 2
        elif args[i] == "--max-tokens" and i + 1 < len(args):
            max_tokens = int(args[i + 1])
            i += 2
        elif args[i] == "--no-highlight":
            no_highlight = True
            i += 1
        elif args[i].startswith("--"):
            i += 1
        else:
            if query is None:
                query = args[i]
            i += 1

    if source_list:
        source_filter = set()
        for s in source_list:
            for part in s.split(","):
                part = part.strip()
                if part in ("doc", "code", "memory"):
                    source_filter.add(part)

    if not query:
        print(_("  Falta la consulta de búsqueda."))
        return 1

    if not slug:
        slug = _auto_slug()
    if not slug:
        print(_("  No se pudo detectar el proyecto. Usá --slug <nombre>."))
        return 1

    return cmd_rag(slug, query, top_k, scope_filter, json_output,
                   source_filter, max_tokens, highlight=not no_highlight)


if __name__ == "__main__":
    sys.exit(main())
