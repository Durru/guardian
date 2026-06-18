#!/usr/bin/env python3
"""
Guardian Memory System — replaces Engram + CodeGraph persistence.
JSONL-based, zero deps, dedup by content hash, TTL-controlled, scope-aware.
Semantic search via built-in TF-IDF + cosine similarity (zero external deps).

Commands:
  save <slug> <type> <content> [file] [line] [scope] [ttl]
  search <slug> <query> [type_filter] [--semantic]
  search --semantic <slug> <query>
  context <slug> [scope_filter]
  index <slug> [--force]
  gc <slug>
  status <slug>
"""

import json, sys, hashlib, re, math, collections
from datetime import datetime, timezone
from pathlib import Path

import guardian_shared as shared
from guardian_shared import _

MEMORY_DIR = shared.MEMORY_DIR
TTL_BY_TYPE = {"landmark": 90, "decision": 30, "pattern": 14, "analysis": 7, "note": 30, "session": 7}
MAX_CONTEXT_LINES = 12

# ── Semantic search: built-in TF-IDF (zero deps) ──

_SEMANTIC = True  # built-in TF-IDF always available


def _tokenize(text):
    return re.findall(r'[a-záéíóúñüA-ZÁÉÍÓÚÑÜ0-9]+', text.lower())


def _compute_tf(tokens):
    if not tokens:
        return {}
    tf = collections.Counter(tokens)
    total = len(tokens)
    return {w: c / total for w, c in tf.items()}


def _compute_tfidf_index(entries):
    if not entries:
        return {}, {}
    idf = collections.Counter()
    for e in entries:
        for w in set(_tokenize(e.get("content", ""))):
            idf[w] += 1
    n = len(entries)
    idf_final = {}
    for w, c in idf.items():
        idf_final[w] = math.log((n + 1) / (c + 1)) + 1
    vocab = sorted(idf_final.keys())
    return idf_final, vocab


def _vectorize(tokens, idf, vocab):
    tf = _compute_tf(tokens)
    return [tf.get(w, 0.0) * idf.get(w, 1.0) for w in vocab]


def _cosine_sim(a, b):
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _embed_text(text, idf, vocab):
    return _vectorize(_tokenize(text), idf, vocab)


def _memory_file(slug):
    v4 = shared._v4_project_root(slug) / "brain" / "memory.jsonl"
    if v4.exists():
        return v4
    return MEMORY_DIR / slug / "memory.jsonl"


def _v4_memory_file(slug):
    return shared._v4_project_root(slug) / "brain" / "memory.jsonl"


def _ensure(slug):
    (MEMORY_DIR / slug).mkdir(parents=True, exist_ok=True)
    _memory_file(slug).touch(exist_ok=True)


def _ts():
    return shared.ts()


def _ts_epoch(ts_str):
    return shared.ts_epoch(ts_str)


def _entry_id(type_, content, file_):
    raw = f"{type_}:{content}:{file_ or ''}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def _read_entries(slug):
    mf = _memory_file(slug)
    if not mf.exists() or mf.stat().st_size == 0:
        return []
    entries = []
    with open(mf) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def _write_entries(slug, entries):
    mf = _v4_memory_file(slug)
    mf.parent.mkdir(parents=True, exist_ok=True)
    with open(mf, "w") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


# ── save ──


def cmd_save(slug, type_, content, file_="", line=0, scope="", ttl=None):
    if not slug or not type_ or not content:
        print("Faltan datos: necesito el slug, el tipo y el contenido")
        return 1
    valid_types = set(TTL_BY_TYPE.keys())
    if type_ not in valid_types:
        print(_("El tipo '{type_}' no es válido. Usá uno de: {}", ', '.join(sorted(valid_types)), type_=type_))
        return 1
    _ensure(slug)
    if ttl is None:
        ttl = TTL_BY_TYPE.get(type_, 7)

    eid = _entry_id(type_, content, file_)
    now = shared.ts()

    entries = _read_entries(slug)
    found = False
    for e in entries:
        if e.get("id") == eid:
            e["ts"] = now
            e["hits"] = e.get("hits", 1) + 1
            e["file"] = file_ or e["file"]
            e["scope"] = scope or e["scope"]
            found = True
            break

    if not found:
        entries.append({
            "id": eid,
            "ts": now,
            "type": type_,
            "scope": scope,
            "content": content,
            "file": file_,
            "line": line,
            "ttl": ttl,
            "hits": 1,
        })

    _write_entries(slug, entries)
    action = "Actualizado" if found else "Guardado"
    print(_("  🧠 {action}: {type_}", action=action, type_=type_))
    return 0


# ── index (pre-compute semantic embeddings) ──


def _embed_index_file(slug):
    v4 = shared._v4_project_root(slug) / "brain" / "memory-embeddings.json"
    if v4.parent.exists():
        return v4
    return MEMORY_DIR / slug / "memory-embeddings.json"


def _load_cached_embeddings(slug):
    f = _embed_index_file(slug)
    if f.exists():
        try:
            return json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_cached_embeddings(slug, embeddings):
    f = _embed_index_file(slug)
    f.write_text(json.dumps(embeddings))


def cmd_index(slug, force=False):
    if not slug:
        print("Falta el slug del proyecto")
        return 1
    _ensure(slug)
    entries = _read_entries(slug)
    if not entries:
        print("  La memoria está vacía")
        return 0

    cached = {} if force else _load_cached_embeddings(slug)
    if cached and not force:
        print(_("  🧬 Índice semántico: {} entrada(s) indexada(s) (usá --force para reindexar)", len(cached)))
        return 0

    idf, vocab = _compute_tfidf_index(entries)
    embeddings = {}
    for e in entries:
        eid = e.get("id") or _entry_id(e["type"], e["content"], e.get("file", ""))
        vec = _embed_text(e.get("content", ""), idf, vocab)
        if vec:
            embeddings[eid] = vec

    meta = {"idf": idf, "vocab": vocab}
    _save_cached_embeddings(slug, {"meta": meta, "entries": embeddings})
    print(_("  🧬 Índice semántico: {}/{} entrada(s) indexada(s) (TF-IDF, zero deps)", len(embeddings), len(entries)))
    return 0


# ── search ──


def cmd_search(slug, query, type_filter=None, semantic=False, json_output=False):
    if not slug or not query:
        print("Faltan datos: necesito el slug y el término de búsqueda")
        return 1
    _ensure(slug)
    entries = _read_entries(slug)
    if not entries:
        if json_output:
            print(json.dumps([], ensure_ascii=False))
            return 0
        print("  No hay nada guardado en la memoria todavía")
        return 0

    if semantic and _SEMANTIC:
        cached = _load_cached_embeddings(slug)
        meta = cached.get("meta") if isinstance(cached, dict) and "meta" in cached else None
        if not meta:
            # Build on-the-fly if no cached index
            idf, vocab = _compute_tfidf_index(entries)
        else:
            idf, vocab = meta.get("idf", {}), meta.get("vocab", [])
            cached_entries = cached.get("entries", {})

        qvec = _embed_text(query, idf, vocab)
        scored = []
        for e in entries:
            if type_filter and e.get("type") != type_filter:
                continue
            eid = e.get("id") or _entry_id(e["type"], e["content"], e.get("file", ""))
            if meta and eid in cached_entries:
                ev = cached_entries[eid]
            else:
                ev = _embed_text(e.get("content", ""), idf, vocab)
            sim = _cosine_sim(qvec, ev)
            if sim > 0.10:
                scored.append((sim, e))
        scored.sort(key=lambda x: -x[0])

        if not scored:
            if json_output:
                print(json.dumps([], ensure_ascii=False))
                return 0
            print("  No encontré nada semánticamente similar (threshold > 0.10)")
            return 0

        if json_output:
            results_data = []
            for sim, e in scored:
                results_data.append({
                    "id": e.get("id", ""),
                    "type": e.get("type", ""),
                    "content": e.get("content", ""),
                    "file": e.get("file", ""),
                    "ts": e.get("ts", ""),
                    "hits": e.get("hits", 0),
                    "ttl": e.get("ttl", 7),
                    "scope": e.get("scope", ""),
                })
            print(json.dumps(results_data, ensure_ascii=False))
            return 0

        print(_("  🔍 Búsqueda semántica: \"{query}\"", query=query))
        for sim, e in scored:
            bar = "█" * max(1, int(sim * 10))
            print(_("  {sim:.2f} {bar} [{:>8}] {}", e['type'], e.get('content',''), sim=sim, bar=bar))
            if e.get("file"):
                print(_("          archivo: {}", e['file']))
            print(_("          ttl: {}d | usos: {} | {}", e.get('ttl','?'), e.get('hits',0), e.get('ts','')))
        return 0

    # Fallback: keyword search
    q = query.lower()
    results = []
    for e in entries:
        if type_filter and e.get("type") != type_filter:
            continue
        if q not in e.get("content", "").lower() and q not in e.get("file", "").lower():
            continue
        results.append(e)

    if not results:
        if json_output:
            print(json.dumps([], ensure_ascii=False))
            return 0
        print("  No encontré nada con ese término")
        return 0

    if json_output:
        results_data = []
        for e in results:
            results_data.append({
                "id": e.get("id", ""),
                "type": e.get("type", ""),
                "content": e.get("content", ""),
                "file": e.get("file", ""),
                "ts": e.get("ts", ""),
                "hits": e.get("hits", 0),
                "ttl": e.get("ttl", 7),
                "scope": e.get("scope", ""),
            })
        print(json.dumps(results_data, ensure_ascii=False))
        return 0

    for e in results:
        print(_("  [{:>8}] {}", e['type'], e.get('content','')))
        if e.get("file"):
            print(_("          archivo: {}", e['file']))
        print(_("          ttl: {}d | usos: {} | {}", e.get('ttl','?'), e.get('hits',0), e.get('ts','')))
    return 0


# ── context (controlled injection, never >12 lines) ──


def cmd_context(slug, scope_filter=None, json_output=False):
    if not slug:
        print("Falta el slug del proyecto")
        return 1
    _ensure(slug)
    entries = _read_entries(slug)
    if not entries:
        if json_output:
            print(json.dumps({"entries": [], "total": 0}, ensure_ascii=False))
            return 0
        return 0

    # Filter expired
    now = int(datetime.now(timezone.utc).timestamp())
    valid = []
    for e in entries:
        age = (now - shared.ts_epoch(e.get("ts", ""))) // 86400
        ttl = e.get("ttl", 7)
        hits = e.get("hits", 0)
        if age <= ttl and hits > 0:
            valid.append(e)

    if not valid:
        if json_output:
            print(json.dumps({"entries": [], "total": 0}, ensure_ascii=False))
            return 0
        return 0

    if json_output:
        entries_data = []
        scope_q = scope_filter.lower() if scope_filter else ""
        for e in valid:
            if scope_q and scope_q not in e.get("scope", "").lower() and scope_q not in e.get("file", "").lower() and scope_q not in e.get("content", "").lower():
                continue
            entries_data.append({
                "id": e.get("id", ""),
                "type": e.get("type", ""),
                "content": e.get("content", ""),
                "file": e.get("file", ""),
                "scope": e.get("scope", ""),
                "ts": e.get("ts", ""),
                "hits": e.get("hits", 0),
                "ttl": e.get("ttl", 7),
            })
        print(json.dumps({"entries": entries_data, "total": len(entries_data)}, ensure_ascii=False))
        return 0

    scope_q = scope_filter.lower() if scope_filter else ""
    PREFIXES = {"landmark": "📍", "decision": "🧠", "pattern": "🔁", "note": "📝", "analysis": "📊", "skill_usage": "📈"}

    # Score each entry: landmarks auto-include, scope match boosts, hits boost
    scored = []
    for e in valid:
        score = e.get("hits", 0)
        t = e.get("type", "")
        # Landmarks get a head start
        if t == "landmark":
            score += 3
        # Scope match gives a big boost
        scope_match = (
            not scope_q
            or scope_q in e.get("scope", "").lower()
            or scope_q in e.get("file", "").lower()
            or scope_q in e.get("content", "").lower()
        )
        if scope_match:
            score += 5
        # Recent entries preferred
        age = (now - shared.ts_epoch(e.get("ts", ""))) // 3600
        recency = max(0, 2 - age // 24)  # 0-2 points
        score += recency
        scored.append((score, scope_match, e))

    # Sort: highest score first
    scored.sort(key=lambda x: -x[0])

    seen_ids = set()
    output = []
    max_items = 6

    def try_add(e):
        nonlocal seen_ids, output
        eid = e.get("id") or _entry_id(e["type"], e["content"], e.get("file", ""))
        if eid in seen_ids:
            return
        seen_ids.add(eid)
        prefix = PREFIXES.get(e.get("type", ""), "•")
        output.append(f"{prefix} {e['content']}")

    # Phase 1: landmarks + scope-matches (prioritized by score)
    for _, sm, e in scored:
        if len(output) >= max_items:
            break
        t = e.get("type", "")
        if t == "landmark" or (sm and t in ("decision", "pattern", "note", "analysis")):
            try_add(e)

    # Phase 2: fill remaining with highest scored entries not yet included
    for _, _, e in scored:
        if len(output) >= max_items:
            break
        try_add(e)

    print("─" * 40)
    print("📌 Memoria del proyecto:")
    for line in output:
        print(line)
    print("─" * 40)
    return 0


# ── gc ──


def cmd_gc(slug):
    if not slug:
        print("Falta el slug del proyecto")
        return 1
    _ensure(slug)
    entries = _read_entries(slug)
    if not entries:
        print("  La memoria está vacía, no hay nada que limpiar")
        return 0

    now = int(datetime.now(timezone.utc).timestamp())
    alive = []
    removed = 0
    for e in entries:
        age = (now - shared.ts_epoch(e.get("ts", ""))) // 86400
        ttl = e.get("ttl", 7)
        if age > ttl:
            removed += 1
        else:
            alive.append(e)

    _write_entries(slug, alive)
    print(_("  🧹 Memoria limpiada: {} vigentes, {removed} vencido(s) eliminado(s)", len(alive), removed=removed))
    return 0


# ── status ──


def cmd_status(slug, json_output=False):
    if not slug:
        print("Falta el slug del proyecto")
        return 1
    _ensure(slug)
    entries = _read_entries(slug)
    if not entries:
        if json_output:
            print(json.dumps({"total": 0, "expired": 0, "counts": {}, "active": 0}, ensure_ascii=False))
            return 0
        print("  🧠 La memoria está vacía")
        return 0

    counts = {}
    for e in entries:
        t = e.get("type", "unknown")
        counts[t] = counts.get(t, 0) + 1

    now = int(datetime.now(timezone.utc).timestamp())
    expired = 0
    for e in entries:
        age = (now - shared.ts_epoch(e.get("ts", ""))) // 86400
        if age > e.get("ttl", 7):
            expired += 1

    total = len(entries)
    if json_output:
        print(json.dumps({"total": total, "expired": expired, "counts": counts, "active": total - expired}, ensure_ascii=False))
        return 0
    print(_("  🧠 Memoria: {total} entrada(s) ({expired} vencida(s))", total=total, expired=expired))
    for t in ("landmark", "decision", "pattern", "analysis", "note"):
        c = counts.get(t, 0)
        note = ""
        if t == "landmark":
            note = "(carga automática)"
        elif t in ("decision", "pattern", "note"):
            note = "(según contexto)"
        elif t == "analysis":
            note = "(bajo demanda)"
        if c > 0:
            print(_("    {t:<10} {c:>3} {note}", t=t, c=c, note=note))
    return 0


# ── session ──


def cmd_session_save(slug, with_config=False):
    if not slug:
        print("Falta el slug del proyecto")
        return 1
    now = shared.ts()
    _ensure(slug)

    content = f"Sesión iniciada: {now}"
    config_info = ""
    if with_config:
        config_path = MEMORY_DIR / slug / "config.yaml"
        if config_path.exists():
            lines = config_path.read_text().strip().split("\n")[:10]
            config_info = " | " + "; ".join(l for l in lines if not l.startswith("#") and ":" in l)

    entries = _read_entries(slug)
    session_count = sum(1 for e in entries if e.get("type") == "session")
    content += f" (#{session_count + 1}{config_info})"

    eid = hashlib.md5(f"session:{now}:{slug}".encode()).hexdigest()[:16]
    entries.append({
        "id": eid,
        "ts": now,
        "type": "session",
        "scope": "",
        "content": content,
        "file": "",
        "line": 0,
        "ttl": 7,
        "hits": 1,
    })
    _write_entries(slug, entries)
    print(_("  🟢 Sesión guardada (#{})", session_count + 1))
    return 0


def cmd_session_status(slug, json_output=False):
    if not slug:
        print("Falta el slug del proyecto")
        return 1
    _ensure(slug)
    entries = _read_entries(slug)
    sessions = [e for e in entries if e.get("type") == "session"]

    if not sessions:
        if json_output:
            print(json.dumps({"total": 0, "active": 0, "last_hours_ago": 0, "last_content": ""}, ensure_ascii=False))
            return 0
        print("  📭 Sin sesiones registradas")
        return 0

    now_ts = int(datetime.now(timezone.utc).timestamp())
    last = sessions[-1]
    last_ts = shared.ts_epoch(last.get("ts", ""))
    hours_ago = max(0, (now_ts - last_ts) // 3600)

    # GC expired sessions
    active_sessions = 0
    for s in sessions:
        age = (now_ts - shared.ts_epoch(s.get("ts", ""))) // 86400
        if age <= 7:
            active_sessions += 1

    total = len(sessions)
    if json_output:
        print(json.dumps({"total": total, "active": active_sessions, "last_hours_ago": hours_ago, "last_content": last.get("content", "")}, ensure_ascii=False))
        return 0
    print(_("  🟢 Sesiones: {total} total · {active_sessions} activas (7d)", total=total, active_sessions=active_sessions))
    print(_("  🕐 Última: {hours_ago}h atrás", hours_ago=hours_ago))
    print(_("     {}", last.get('content', '')))
    return 0


# ── main ──


def main():
    if len(sys.argv) < 2:
        print("Sistema de memoria — cómo usarlo:")
        print(_("  {} save <slug> <tipo> <contenido> [archivo] [línea] [scope] [ttl]", sys.argv[0]))
        print(_("  {} search [--semantic] <slug> <término> [filtro_tipo]", sys.argv[0]))
        print(_("  {} context <slug> [filtro_scope]", sys.argv[0]))
        print(_("  {} index <slug> [--force]", sys.argv[0]))
        print(_("  {} session save <slug> [--with-config]", sys.argv[0]))
        print(_("  {} session status <slug>", sys.argv[0]))
        print(_("  {} gc <slug>", sys.argv[0]))
        print(_("  {} status <slug>", sys.argv[0]))
        print()
        print("Tipos: landmark (90d), decision (30d), pattern (14d), analysis (7d), note (30d), session (7d)")
        return 1

    cmd = sys.argv[1]

    if cmd == "save":
        if len(sys.argv) < 4:
            print("Faltan datos: necesito el slug, el tipo y el contenido")
            return 1
        slug = sys.argv[2]
        type_ = sys.argv[3]
        content = sys.argv[4]
        file_ = sys.argv[5] if len(sys.argv) > 5 else ""
        line = int(sys.argv[6]) if len(sys.argv) > 6 and sys.argv[6] else 0
        scope = sys.argv[7] if len(sys.argv) > 7 else ""
        ttl = int(sys.argv[8]) if len(sys.argv) > 8 and sys.argv[8] else None
        return cmd_save(slug, type_, content, file_, line, scope, ttl)

    elif cmd == "search":
        json_output = "--json" in sys.argv
        semantic = "--semantic" in sys.argv
        args = [a for a in sys.argv[2:] if a not in ("--semantic", "--json")]
        if len(args) < 2:
            print("Faltan datos: necesito el slug y el término de búsqueda")
            return 1
        slug = args[0]
        query = args[1]
        type_filter = args[2] if len(args) > 2 else None
        return cmd_search(slug, query, type_filter, semantic, json_output)

    elif cmd == "context":
        json_output = "--json" in sys.argv
        args = [a for a in sys.argv[2:] if a != "--json"]
        if len(args) < 1:
            print("Falta el slug del proyecto")
            return 1
        slug = args[0]
        scope_filter = args[1] if len(args) > 1 else None
        return cmd_context(slug, scope_filter, json_output)

    elif cmd == "index":
        if len(sys.argv) < 3:
            print("Falta el slug del proyecto")
            return 1
        slug = sys.argv[2]
        force = "--force" in sys.argv
        return cmd_index(slug, force)

    elif cmd == "gc":
        if len(sys.argv) < 3:
            print("Falta el slug del proyecto")
            return 1
        return cmd_gc(sys.argv[2])

    elif cmd == "status":
        json_output = "--json" in sys.argv
        args = [a for a in sys.argv[2:] if a != "--json"]
        if len(args) < 1:
            print("Falta el slug del proyecto")
            return 1
        return cmd_status(args[0], json_output)

    elif cmd == "session":
        if len(sys.argv) < 4:
            print("Faltan datos: necesito subcomando (save|status) y slug")
            return 1
        sub = sys.argv[2]

        # Find slug: first non-flag arg after subcommand
        slug = None
        for i in range(3, len(sys.argv)):
            if not sys.argv[i].startswith("-"):
                slug = sys.argv[i]
                break
        if not slug:
            print("Falta el slug del proyecto")
            return 1

        if sub == "save":
            with_config = "--with-config" in sys.argv
            return cmd_session_save(slug, with_config)
        elif sub == "status":
            json_output = "--json" in sys.argv
            return cmd_session_status(slug, json_output)
        else:
            print(_("No conozco el subcomando 'session {sub}'. Usá 'save' o 'status'.", sub=sub))
            return 1

    else:
        print(_("No conozco el comando '{cmd}'. Usá 'status', 'save', 'search', 'context', 'session', 'index' o 'gc'.", cmd=cmd))
        return 1


if __name__ == "__main__":
    sys.exit(main())
