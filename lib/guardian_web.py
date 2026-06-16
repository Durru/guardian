#!/usr/bin/env python3
"""
Guardian Web Dashboard — standalone read-only HTTP server.

Usage:
  python3 guardian_web.py [--port=PORT]
"""

import http.server
import json
import sys
import argparse
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime, timezone

import guardian_shared as shared
from guardian_shared import _

import guardian_rag

MEMORY_DIR = shared.MEMORY_DIR
DEFAULT_PORT = 7878
HOST = "127.0.0.1"


def _read_config(slug):
    return shared.read_config(slug)


def _read_memory(slug):
    return shared.read_memory(slug)[-50:]


def _read_audit(slug):
    data = shared.read_audit(slug)
    return data[-50:] if isinstance(data, list) else []


def _read_skills_json(slug):
    data = shared.read_skills_json(slug)
    if "classification" not in data:
        data["classification"] = {}
    return data


def _discover_projects():
    return shared.discover_projects()


def _get_brain_schema():
    import guardian_brain_schema
    return guardian_brain_schema


def _project_exists(slug):
    return shared.project_exists(slug)


def _ts_epoch(ts_str):
    return shared.ts_epoch(ts_str)


def _query_rag(slug, query, top_k=10, source_filter=None):
    config = _read_config(slug)
    if not config:
        return None
    chunks = guardian_rag._collect_chunks(slug, config, source_filter)
    if not chunks:
        return None
    contents = [c["content"] for c in chunks]
    from guardian_memory import _compute_tfidf_index, _embed_text
    idf, vocab = _compute_tfidf_index([{"content": ct} for ct in contents])
    query_vec = _embed_text(query, idf, vocab)
    if not any(query_vec):
        return None
    all_scored = guardian_rag._rerank(chunks, idf, vocab, query_vec, None)
    results = []
    for c in all_scored[:top_k]:
        r = {
            "score": c["_score"],
            "sim": c["_sim"],
            "source": c["source"],
            "content": c["content"][:300],
            "citation": guardian_rag._fmt_citation(c),
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
    return {"query": query, "slug": slug, "total_chunks": len(chunks), "results": results}


# ── HTML templates ─────────────────────────────────────────────

CSS = """
* { margin:0; padding:0; box-sizing:border-box; }
body { background:#0d1117; color:#c9d1d9; font-family:"SF Mono","Cascadia Code","Fira Code","JetBrains Mono","Consolas",monospace; font-size:14px; line-height:1.5; padding:20px; }
a { color:#58a6ff; text-decoration:none; }
a:hover { text-decoration:underline; }
h1 { font-size:24px; margin-bottom:20px; color:#f0f6fc; }
h2 { font-size:18px; margin-bottom:12px; color:#f0f6fc; }
h3 { font-size:15px; margin-bottom:8px; color:#f0f6fc; }
.dashboard { max-width:1200px; margin:0 auto; }
.grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:16px; }
.card { background:#161b22; border:1px solid #30363d; border-radius:8px; padding:16px; transition:border-color .2s; }
.card:hover { border-color:#58a6ff; }
.card h3 { margin-bottom:8px; }
.card h3 a { color:#58a6ff; }
.meta { color:#8b949e; font-size:12px; margin-top:8px; }
.meta span { display:inline-block; margin-right:12px; }
.badge { display:inline-block; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:600; margin-right:4px; }
.badge-hot { background:#da3633; color:#fff; }
.badge-warm { background:#d29922; color:#fff; }
.badge-cold { background:#21262d; color:#8b949e; border:1px solid #30363d; }
table { width:100%; border-collapse:collapse; margin:12px 0; }
th, td { text-align:left; padding:8px 12px; border-bottom:1px solid #21262d; }
th { color:#8b949e; font-weight:600; font-size:12px; text-transform:uppercase; }
td { font-size:13px; }
.section { margin-bottom:24px; }
.back { margin-bottom:16px; display:inline-block; }
pre { background:#0d1117; border:1px solid #30363d; border-radius:6px; padding:12px; overflow-x:auto; font-size:12px; }
.status-ok { color:#3fb950; }
.status-violation { color:#da3633; }
.status-blocked { color:#d29922; }
.flash { color:#58a6ff; }
.key { color:#8b949e; }
.val { color:#c9d1d9; }
.nav { margin-bottom:20px; padding-bottom:12px; border-bottom:1px solid #30363d; }
.nav a { margin-right:16px; }
input, select { background:#0d1117; border:1px solid #30363d; border-radius:6px; color:#c9d1d9; padding:8px 12px; font-size:14px; font-family:inherit; }
input:focus { outline:none; border-color:#58a6ff; }
button { background:#238636; color:#fff; border:none; border-radius:6px; padding:8px 20px; font-size:14px; cursor:pointer; }
button:hover { background:#2ea043; }
.rag-result { background:#161b22; border:1px solid #30363d; border-radius:8px; padding:16px; margin-bottom:12px; }
.rag-result .score { color:#8b949e; font-size:12px; }
.rag-result .citation { color:#58a6ff; font-size:12px; }
.rag-result .snippet { margin-top:8px; color:#c9d1d9; font-size:13px; white-space:pre-wrap; word-break:break-all; }
mark { background:#d29922; color:#0d1117; padding:0 2px; border-radius:2px; }
"""


def _page_html(title, body):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>{CSS}</style>
</head>
<body>
<div class="dashboard">
{body}
</div>
</body>
</html>"""


def _index_html(projects_data):
    cards = ""
    for p in projects_data:
        mem_count = p.get("memory_count", 0)
        skills_rel = p.get("skills_relevant", 0)
        skills_hot = p.get("skills_hot", 0)
        last_audit = p.get("last_audit_ts", "—")
        slug = p["slug"]
        cards += f"""<div class="card">
<h3><a href="/{slug}/">{slug}</a></h3>
<div class="meta">
  <span>📋 audit: {last_audit[:10] if last_audit != "—" else "—"}</span><br>
  <span>🧠 memoria: {mem_count}</span>
  <span>📦 skills: {skills_rel}</span>
  <span>🔥 hot: {skills_hot}</span>
</div>
</div>
"""

    body = f"""<h1>🛡️ Guardian Dashboard</h1>
<div class="grid">{cards}</div>
"""
    return _page_html("🛡️ Guardian Dashboard", body)


def _project_html(slug, config, skills, memory, audit):
    # Skills classification
    cls = skills.get("classification", {})
    tiers = cls.get("tiers", {})
    hot_skills = tiers.get("hot", [])
    warm_skills = tiers.get("warm", [])
    cold_skills = tiers.get("cold", [])

    skills_section = ""
    if hot_skills:
        skills_section += '<tr><th colspan="2" class="flash">🔥 Hot</th></tr>\n'
        for s in hot_skills:
            name = s.get("name", "?")
            score = s.get("score", 0)
            reasons = ", ".join(s.get("reasons", []))
            skills_section += f"<tr><td>{name}</td><td>{score} — {reasons}</td></tr>\n"
    if warm_skills:
        skills_section += '<tr><th colspan="2" class="flash">🔥 Warm</th></tr>\n'
        for s in warm_skills:
            name = s.get("name", "?")
            score = s.get("score", 0)
            reasons = ", ".join(s.get("reasons", []))
            skills_section += f"<tr><td>{name}</td><td>{score} — {reasons}</td></tr>\n"
    if cold_skills:
        skills_section += '<tr><th colspan="2" class="flash">🧊 Cold</th></tr>\n'
        for s in cold_skills:
            name = s.get("name", "?")
            score = s.get("score", 0)
            skills_section += f"<tr><td>{name}</td><td>{score}</td></tr>\n"
    if not skills_section:
        rel = skills.get("relevant", [])
        hot = skills.get("hot", [])
        scores = skills.get("scores", {})
        skills_section = f"<tr><td>Relevantes</td><td>{len(rel)}</td></tr>\n"
        skills_section += f"<tr><td>Hot</td><td>{len(hot)}</td></tr>\n"

    # Config table
    config_rows = ""
    for k, v in config.items():
        if isinstance(v, dict):
            continue
        if isinstance(v, list):
            config_rows += f"<tr><td class='key'>{k}</td><td class='val'>{', '.join(str(x) for x in v)}</td></tr>\n"
        else:
            config_rows += f"<tr><td class='key'>{k}</td><td class='val'>{v}</td></tr>\n"

    # Stack info
    stack = config.get("stack", {})
    if isinstance(stack, dict):
        for k, v in stack.items():
            if v is not None and v != "":
                config_rows += f"<tr><td class='key'>stack.{k}</td><td class='val'>{v}</td></tr>\n"

    # Audit table
    audit_rows = ""
    for e in audit:
        ts = e.get("ts", "")[:19]
        etype = e.get("type", "")
        status = e.get("status", "")
        desc = e.get("desc", e.get("details", ""))
        sclass = f"status-{status}" if status in ("ok", "violation", "blocked") else ""
        audit_rows += f"<tr><td>{ts}</td><td>{etype}</td><td class='{sclass}'>{status}</td><td>{desc[:80]}</td></tr>\n"

    # Memory table
    mem_rows = ""
    for e in memory:
        ts = e.get("ts", "")[:19]
        mtype = e.get("type", "")
        content = e.get("content", "")[:80]
        scope = e.get("scope", "")
        mem_rows += f"<tr><td>{ts}</td><td><span class='badge badge-{mtype}'>{mtype}</span></td><td>{scope}</td><td>{content}</td></tr>\n"

    body = f"""<a class="back" href="/">&larr; Dashboard</a>
<h1>🛡️ {slug}</h1>

<div class="section">
<h2>Configuración</h2>
<table>
{config_rows}
</table>
</div>

<div class="section">
<h2>Skills</h2>
<table>
{skills_section}
</table>
</div>

<div class="section">
<h2>Auditoría (últimos {len(audit)})</h2>
<table>
<tr><th>Timestamp</th><th>Tipo</th><th>Estado</th><th>Descripción</th></tr>
{audit_rows}
</table>
</div>

<div class="section">
<h2>Memoria (últimos {len(memory)})</h2>
<table>
<tr><th>Timestamp</th><th>Tipo</th><th>Scope</th><th>Contenido</th></tr>
{mem_rows}
</table>
</div>
"""
    return _page_html(f"🛡️ {slug}", body)


def _rag_search_html(slug, query, results, projects):
    slug_opts = "".join(
        f'<option value="{s}"{" selected" if s == slug else ""}>{s}</option>'
        for s in projects
    )
    results_html = ""
    if results is not None:
        if "error" in results:
            results_html = f'<p style="color:#da3633;">{results["error"]}</p>'
        elif results.get("results"):
            for r in results["results"]:
                score_pct = r["score"] * 100
                sim_pct = r["sim"] * 100
                results_html += f"""<div class="rag-result">
<div class="score">score={score_pct:.0f}% &nbsp; sim={sim_pct:.0f}%</div>
<div class="citation">{r.get("citation", "")}</div>
<div class="snippet">{r["content"]}</div>
</div>
"""
        else:
            results_html = "<p>Sin resultados.</p>"

    body = f"""<a class="back" href="/">&larr; Dashboard</a>
<h1>🔍 RAG Search</h1>
<form id="rag-form" style="margin-bottom:20px; display:flex; gap:8px; flex-wrap:wrap; align-items:center;">
<select name="slug" style="min-width:160px;">
{slug_opts}
</select>
<input type="text" name="q" placeholder="Buscar en docs, código y memoria..." value="{query or ""}" style="flex:1; min-width:200px;">
<select name="source" style="min-width:120px;">
<option value="">Todas las fuentes</option>
<option value="doc">Documentación</option>
<option value="code">Código</option>
<option value="memory">Memoria</option>
</select>
<button type="submit">Buscar</button>
</form>
<div id="rag-results">{results_html}</div>
<script>
document.getElementById('rag-form').addEventListener('submit', function(e) {{
e.preventDefault();
var slug = this.slug.value;
var q = this.q.value;
var source = this.source.value;
var url = '/' + slug + '/rag.json?q=' + encodeURIComponent(q) + '&top_k=10';
if (source) url += '&source=' + source;
window.location.href = '/rag/?slug=' + encodeURIComponent(slug) + '&q=' + encodeURIComponent(q) + (source ? '&source=' + source : '');
}});
</script>
"""
    return _page_html("🔍 RAG Search — Guardian", body)


# ── HTTP handler ───────────────────────────────────────────────

class GuardianHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        ts = datetime.now().strftime("%H:%M:%S")
        sys.stderr.write(f"[{ts}] {fmt % args}\n")

    def _respond(self, body, content_type, status=200):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        if "json" in content_type:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_json(self, data, status=200):
        body = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
        self._respond(body, "application/json; charset=utf-8", status)

    def _send_html(self, html, status=200):
        self._respond(html, "text/html; charset=utf-8", status)

    def _send_error(self, status, message):
        body = json.dumps({"error": message}, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
        self._respond(body, "application/json; charset=utf-8", status)

    def _send_404(self):
        self._send_error(404, "Not found")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_HEAD(self):
        self.do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        parts = path.strip("/").split("/")
        if len(parts) == 3 and parts[2] == "save" and parts[1] in ("guardian.md", "brain.md"):
            slug = parts[0]
            if not _project_exists(slug):
                self._send_404()
                return
            self._serve_guardian_md_save(slug, parts)
            return
        self._send_404()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        # Root: dashboard
        if path == "" or path == "/" or path == "/index.html":
            self._serve_index()
            return

        # JSON: all projects
        if path == "/projects.json":
            self._serve_projects_json()
            return

        # RAG search page
        if path == "/rag" or path == "/rag/search":
            slug = _get_param(parsed.query, "slug") or ""
            q = _get_param(parsed.query, "q") or ""
            source = _get_param(parsed.query, "source") or None
            self._serve_rag_page(slug, q, source)
            return

        # /<slug>/
        parts = path.strip("/").split("/")

        if len(parts) == 1:
            slug = parts[0]
            if _project_exists(slug):
                self._serve_project(slug)
            else:
                self._send_404()
            return

        if len(parts) == 2:
            slug = parts[0]
            endpoint = parts[1]

            if not _project_exists(slug):
                self._send_404()
                return

            if endpoint == "status.json":
                self._serve_status_json(slug)
            elif endpoint == "memory.json":
                self._serve_memory_json(slug)
            elif endpoint == "skills.json":
                self._serve_skills_json(slug)
            elif endpoint == "audit.json":
                self._serve_audit_json(slug)
            elif endpoint == "rag.json":
                self._serve_rag_json(slug, parsed.query)
            elif endpoint == "guardian.md" or endpoint == "brain.md":
                self._serve_guardian_md(slug)
            else:
                self._send_404()
            return

        if len(parts) == 3 and parts[2] == "save":
            slug = parts[0]
            if not _project_exists(slug):
                self._send_404()
                return
            self._serve_guardian_md_save(slug, parts)
            return

        self._send_404()

    # ── route handlers ──

    def _serve_index(self):
        projects = _discover_projects()
        data = []
        for slug in projects:
            config = _read_config(slug)
            skills = _read_skills_json(slug)
            mem = _read_memory(slug)
            audit = _read_audit(slug)
            last_ts = audit[-1].get("ts", "") if audit else ""
            data.append({
                "slug": slug,
                "last_audit_ts": last_ts,
                "memory_count": len(mem),
                "skills_relevant": len(skills.get("relevant", [])),
                "skills_hot": len(skills.get("hot", [])),
            })
        html = _index_html(data)
        self._send_html(html)

    def _serve_projects_json(self):
        projects = _discover_projects()
        data = []
        for slug in projects:
            config = _read_config(slug)
            skills = _read_skills_json(slug)
            mem = _read_memory(slug)
            audit = _read_audit(slug)
            last_ts = audit[-1].get("ts", "") if audit else ""
            data.append({
                "slug": slug,
                "config": config,
                "last_audit_ts": last_ts,
                "memory_count": len(mem),
                "skills_relevant": len(skills.get("relevant", [])),
                "skills_hot": len(skills.get("hot", [])),
                "audit_count": len(audit),
            })
        self._send_json({"projects": data})

    def _serve_project(self, slug):
        config = _read_config(slug)
        skills = _read_skills_json(slug)
        memory = _read_memory(slug)
        audit = _read_audit(slug)
        html = _project_html(slug, config, skills, memory, audit)
        self._send_html(html)

    def _serve_status_json(self, slug):
        config = _read_config(slug)
        skills = _read_skills_json(slug)
        mem = _read_memory(slug)
        audit = _read_audit(slug)
        violations = sum(1 for e in audit if e.get("status") == "violation")
        changes = sum(1 for e in audit if e.get("type") == "change")
        expired = sum(1 for e in mem if e.get("ttl", 7) < 999 and
                      (datetime.now(timezone.utc).timestamp() - _ts_epoch(e.get("ts", ""))) // 86400 > e.get("ttl", 7))

        data = {
            "slug": slug,
            "config": config,
            "memory": {
                "count": len(mem),
                "expired": expired,
            },
            "skills": {
                "relevant": len(skills.get("relevant", [])),
                "hot": len(skills.get("hot", [])),
                "scores": skills.get("scores", {}),
            },
            "audit": {
                "count": len(audit),
                "violations": violations,
                "changes": changes,
            },
        }
        # Only include classification tiers if present
        cls = skills.get("classification", {})
        tiers = cls.get("tiers", {})
        if tiers:
            data["skills"]["classification"] = tiers
        self._send_json(data)

    def _serve_memory_json(self, slug):
        mem = _read_memory(slug)
        # Filter out very long content strings
        for e in mem:
            if "content" in e and isinstance(e["content"], str) and len(e["content"]) > 500:
                e["content"] = e["content"][:500] + "..."
        self._send_json({"slug": slug, "memory": mem, "count": len(mem)})

    def _serve_skills_json(self, slug):
        skills = _read_skills_json(slug)
        self._send_json({"slug": slug, **skills})

    def _serve_audit_json(self, slug):
        audit = _read_audit(slug)
        self._send_json({"slug": slug, "audit": audit, "count": len(audit)})

    def _serve_guardian_md(self, slug):
        """v3: serve GUARDIAN.md as editable HTML."""
        import guardian_brain
        guardian_brain_schema = _get_brain_schema()
        guardian_brain_schema.init_project(slug)
        content = guardian_brain.read_guardian_md(slug)
        lines = content.count("\n") + (1 if content else 0)
        escaped = (content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        body = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>GUARDIAN.md — {slug}</title>
<style>
body {{ font-family: monospace; max-width: 900px; margin: 2em auto; padding: 0 1em; }}
textarea {{ width: 100%; min-height: 400px; font-family: monospace; font-size: 14px; padding: 0.5em; border: 1px solid #ccc; border-radius: 4px; }}
button {{ margin: 0.5em 0; padding: 0.5em 1em; background: #2c7; color: white; border: 0; border-radius: 4px; cursor: pointer; }}
button:hover {{ background: #1a5; }}
.meta {{ color: #666; font-size: 0.9em; margin: 1em 0; }}
#status {{ margin-left: 1em; color: #666; }}
</style></head><body>
<h1>GUARDIAN.md — <code>{slug}</code></h1>
<p class="meta">{lines} líneas · auto-loaded cada sesión</p>
<form method="POST" action="/{slug}/brain.md/save">
  <textarea name="content" id="content">{escaped}</textarea>
  <p><button type="submit">Guardar</button><span id="status"></span></p>
</form>
<script>
document.querySelector('form').onsubmit = async (e) => {{
  e.preventDefault();
  const content = document.getElementById('content').value;
  const r = await fetch('/{slug}/brain.md/save', {{
    method: 'POST', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{content}})
  }});
  const status = document.getElementById('status');
  if (r.ok) {{
    status.textContent = '✓ Guardado';
    status.style.color = '#2c7';
    setTimeout(() => status.textContent = '', 2000);
  }} else {{
    status.textContent = '✗ Error: ' + r.status;
    status.style.color = '#c33';
  }}
}};
</script>
</body></html>"""
        self._send_html(body)

    def _serve_guardian_md_save(self, slug, parts):
        """v3: save GUARDIAN.md from form data or JSON body."""
        import guardian_brain
        guardian_brain_schema = _get_brain_schema()
        guardian_brain_schema.init_project(slug)
        content_type = self.headers.get("Content-Type", "")
        content = None
        if "application/json" in content_type:
            try:
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length).decode("utf-8")
                import json as _json
                data = _json.loads(raw)
                content = data.get("content", "")
            except Exception as e:
                self._send_error(400, f"invalid JSON: {e}")
                return
        else:
            try:
                from urllib.parse import parse_qs
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length).decode("utf-8")
                data = parse_qs(raw)
                content = data.get("content", [""])[0]
            except Exception as e:
                self._send_error(400, f"invalid form: {e}")
                return
        if not isinstance(content, str):
            self._send_error(400, "content must be a string")
            return
        if len(content.splitlines()) > guardian_brain.GUARDIAN_MD_MAX_LINES:
            self._send_error(400, f"exceeds max {guardian_brain.GUARDIAN_MD_MAX_LINES} lines")
            return
        result = guardian_brain.write_guardian_md(slug, content)
        self._send_json(result)

    def _serve_rag_json(self, slug, query_string):
        from urllib.parse import parse_qs
        params = parse_qs(query_string)
        q = (params.get("q") or [None])[0]
        if not q:
            self._send_error(400, "Missing 'q' parameter")
            return
        top_k = int((params.get("top_k") or ["10"])[0])
        source_raw = params.get("source")
        source_filter = set(source_raw) if source_raw else None
        result = _query_rag(slug, q, top_k, source_filter)
        if result is None:
            self._send_json({"error": f"No se pudo ejecutar RAG para '{slug}'", "query": q})
            return
        self._send_json(result)

    def _serve_rag_page(self, slug, query, source_filter):
        projects = sorted(_discover_projects())
        result = None
        if slug and query:
            sf = {source_filter} if source_filter else None
            result = _query_rag(slug, query, 10, sf)
        html = _rag_search_html(slug, query, result, projects)
        self._send_html(html)


def _get_param(query_string, name):
    from urllib.parse import parse_qs
    params = parse_qs(query_string)
    vals = params.get(name)
    return vals[0] if vals else None


# ── CLI ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Guardian Web Dashboard")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port (default: {DEFAULT_PORT})")
    args = parser.parse_args()

    server = http.server.HTTPServer((HOST, args.port), GuardianHandler)
    print(_("  🛡️  Guardian Dashboard → http://{HOST}:{}/", args.port, HOST=HOST))
    print(_("     Projects dir: {MEMORY_DIR}", MEMORY_DIR=MEMORY_DIR))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  ✋ Shutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
