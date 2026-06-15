from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import guardian_absorb
import guardian_conciencia
import guardian_evolution
import guardian_genome
import guardian_rag
import guardian_shared as shared
from guardian_shared import _


HOST = "127.0.0.1"
DEFAULT_PORT = 9787
PID_FILE = shared.BACKEND_DIR / "guardian-backend.pid"
LOG_FILE = shared.BACKEND_DIR / "guardian-backend.log"


def _json_response(handler, code, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_body(handler):
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    if not raw:
        return {}
    try:
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _project_slug(params, body=None):
    body = body or {}
    for key in ("slug",):
        if body.get(key):
            return body[key]
        values = params.get(key)
        if values:
            return values[0]
    return None


def _rag_query(slug, query, mode="plan", top_k=5):
    config = shared.read_config(slug)
    if not config:
        return None
    source_filter = {"memory", "knowledge"}
    if mode == "build":
        source_filter.update({"code", "doc"})
    else:
        source_filter.update({"doc"})
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
        results.append({
            "score": c.get("_score", 0.0),
            "sim": c.get("_sim", 0.0),
            "source": c.get("source"),
            "content": c.get("content", "")[:300],
            "citation": guardian_rag._fmt_citation(c),
        })
    return {"query": query, "slug": slug, "mode": mode, "total_chunks": len(chunks), "results": results}


class GuardianBackendHandler(BaseHTTPRequestHandler):
    server_version = "GuardianBackend/2.0"

    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path == "/health":
            return _json_response(self, 200, {"ok": True, "service": "guardian-backend", "pid": os.getpid()})

        if parsed.path == "/metrics":
            branch = shared.get_branch_dir()
            projects = []
            if branch.exists():
                state_file = branch / "state.json"
                if state_file.exists():
                    try:
                        state = json.loads(state_file.read_text(encoding="utf-8"))
                        projects = list(state.get("projects", {}).keys())
                    except (json.JSONDecodeError, OSError):
                        pass
            return _json_response(self, 200, {
                "projects": len(projects),
                "project_list": projects,
                "pid": os.getpid(),
                "uptime": 0,
            })

        if parsed.path == "/mode":
            slug = _project_slug(params)
            if not slug:
                return _json_response(self, 400, {"error": "slug required"})
            return _json_response(self, 200, shared.read_mode_state(slug))

        if parsed.path == "/genome":
            genome = guardian_genome.load_genome()
            branches = guardian_genome.list_branches()
            return _json_response(self, 200, {
                "genome": genome,
                "branches": branches,
            })

        if parsed.path == "/branch":
            slug = _project_slug(params)
            if slug:
                info = guardian_genome.branch_status(slug)
                if info is None:
                    return _json_response(self, 404, {"error": "branch not found"})
                return _json_response(self, 200, info)
            branches = guardian_genome.list_branches()
            return _json_response(self, 200, {"branches": branches})

        if parsed.path == "/conciencia/state":
            slug = _project_slug(params)
            if not slug:
                return _json_response(self, 400, {"error": "slug required"})
            state = guardian_conciencia.read_state(slug)
            return _json_response(self, 200, state)

        if parsed.path == "/conciencia/percentiles":
            slug = _project_slug(params)
            if not slug:
                return _json_response(self, 400, {"error": "slug required"})
            thresholds = guardian_conciencia.read_thresholds(slug)
            return _json_response(self, 200, {"slug": slug, "thresholds": thresholds})

        if parsed.path == "/rag":
            slug = _project_slug(params)
            query = params.get("q", [""])[0]
            mode = params.get("mode", [shared.DEFAULT_MODE])[0]
            if not slug or not query:
                return _json_response(self, 400, {"error": "slug and q required"})
            result = _rag_query(slug, query, mode=mode)
            if result is None:
                return _json_response(self, 404, {"error": "no results"})
            return _json_response(self, 200, result)

        if parsed.path in ("/knowledge/status", "/conocimiento/status"):
            slug = _project_slug(params)
            if not slug:
                return _json_response(self, 400, {"error": "slug required"})
            index = shared.read_knowledge_index(slug)
            return _json_response(self, 200, {"slug": slug, "index": index, "tomes": index.get("tomes", [])})

        if parsed.path == "/knowledge/tomes":
            slug = _project_slug(params)
            if not slug:
                return _json_response(self, 400, {"error": "slug required"})
            tomes_dir = shared.branch_path_for(slug, "knowledge", "tomes")
            if not tomes_dir.exists():
                tomes_dir = shared.MEMORY_DIR / slug / "knowledge" / "tomes"
            tomes = []
            if tomes_dir.exists():
                for p in sorted(tomes_dir.iterdir()):
                    if p.is_file():
                        content = p.read_text(encoding="utf-8")[:500]
                        tomes.append({"name": p.name, "preview": content})
            return _json_response(self, 200, {"slug": slug, "tomes": tomes})

        if parsed.path == "/knowledge/search":
            slug = _project_slug(params)
            query = params.get("q", [""])[0]
            if not slug or not query:
                return _json_response(self, 400, {"error": "slug and q required"})
            config = shared.read_config(slug)
            if not config:
                return _json_response(self, 404, {"error": "project not found"})
            chunks = guardian_rag._collect_chunks(slug, config, {"knowledge"})
            if not chunks:
                return _json_response(self, 200, {"results": []})
            contents = [c["content"] for c in chunks]
            from guardian_memory import _compute_tfidf_index, _embed_text
            idf, vocab = _compute_tfidf_index([{"content": ct} for ct in contents])
            query_vec = _embed_text(query, idf, vocab)
            results = []
            if any(query_vec):
                all_scored = guardian_rag._rerank(chunks, idf, vocab, query_vec, None)
                for c in all_scored[:5]:
                    results.append({
                        "score": c.get("_score", 0.0),
                        "source": c.get("source"),
                        "content": c.get("content", "")[:300],
                    })
            return _json_response(self, 200, {"results": results})

        if parsed.path == "/forja/index":
            import guardian_forja
            index = guardian_forja.scan_index()
            return _json_response(self, 200, index)

        if parsed.path == "/forja/list":
            import guardian_forja
            inventory = guardian_forja.list_inventory()
            return _json_response(self, 200, inventory)

        if parsed.path == "/forja/doctor":
            import guardian_forja
            result = guardian_forja.doctor_check()
            return _json_response(self, 200, result)

        if parsed.path == "/forja/validate":
            slug = _project_slug(params)
            mod = params.get("module", [""])[0]
            import guardian_forja
            result = guardian_forja.validate_module(mod)
            return _json_response(self, 200, result)

        if parsed.path == "/mcp/tools":
            import guardian_mcp
            return _json_response(self, 200, {"tools": guardian_mcp.TOOLS})

        return _json_response(self, 404, {"error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        body = _read_body(self)
        params = parse_qs(parsed.query)

        if parsed.path == "/mode":
            slug = _project_slug(params, body)
            mode = str(body.get("mode") or params.get("mode", [""])[0]).strip().lower()
            if not slug or mode not in {"plan", "build"}:
                return _json_response(self, 400, {"error": "slug and mode(plan/build) required"})
            state = shared.append_mode_history(slug, mode, str(body.get("reason") or ""))
            return _json_response(self, 200, state)

        if parsed.path == "/branch/fork":
            slug = _project_slug(params, body)
            if not slug:
                return _json_response(self, 400, {"error": "slug required"})
            state, path = guardian_genome.fork_branch(slug)
            return _json_response(self, 200, {"slug": slug, "path": str(path), "branch_hash": guardian_genome._branch_hash()})

        if parsed.path == "/conciencia/cycle":
            slug = _project_slug(params, body)
            if not slug:
                return _json_response(self, 400, {"error": "slug required"})
            mode = str(body.get("mode") or shared.read_mode_state(slug).get("mode", shared.DEFAULT_MODE))
            query = str(body.get("question") or body.get("query") or "").strip()
            rag = _rag_query(slug, query, mode=mode) if query else None
            result = guardian_conciencia.run_cycle(
                slug, question=query, mode=mode,
                rag_results=rag.get("results") if rag else None,
                context=body.get("context"),
            )
            if rag:
                result["rag"] = rag
            return _json_response(self, 200, result)

        if parsed.path == "/conciencia/meta":
            slug = _project_slug(params, body)
            if not slug:
                return _json_response(self, 400, {"error": "slug required"})
            state = guardian_conciencia.read_state(slug)
            thresholds = guardian_conciencia.read_thresholds(slug)
            meta = guardian_conciencia.evolve(slug, state.get("cycles", []), thresholds)
            if meta is None:
                return _json_response(self, 200, {"slug": slug, "meta": None, "reason": "insufficient cycles or no adjustments needed"})
            return _json_response(self, 200, {"slug": slug, "meta": meta, "thresholds": {k: thresholds[k] for k in guardian_conciencia.THRESHOLD_KEYS}})

        if parsed.path == "/evolve":
            slug = _project_slug(params, body)
            if not slug:
                return _json_response(self, 400, {"error": "slug required"})
            meta = guardian_evolution.evolve_branch(slug)
            return _json_response(self, 200, {"slug": slug, "meta": meta})

        if parsed.path == "/consolidate":
            slug = _project_slug(params, body)
            if not slug:
                return _json_response(self, 400, {"error": "slug required"})
            result = guardian_evolution.consolidate(slug)
            return _json_response(self, 200, result)

        if parsed.path == "/absorb/ingest":
            slug = _project_slug(params, body)
            if not slug:
                return _json_response(self, 400, {"error": "slug required"})
            rc = guardian_absorb.cmd_ingest(slug, rebuild=bool(body.get("rebuild", False)))
            return _json_response(self, 200 if rc == 0 else 400, {"slug": slug, "rc": rc})

        if parsed.path == "/absorb/scan":
            slug = _project_slug(params, body)
            if not slug:
                return _json_response(self, 400, {"error": "slug required"})
            result = _run_cli([sys.executable, str(Path(__file__).with_name("guardian_absorb.py")), "scan", slug])
            return _json_response(self, 200 if result["rc"] == 0 else 400, {"slug": slug, **result})

        if parsed.path == "/absorb/classify":
            slug = _project_slug(params, body)
            if not slug:
                return _json_response(self, 400, {"error": "slug required"})
            result = _run_cli([sys.executable, str(Path(__file__).with_name("guardian_absorb.py")), "classify", slug])
            return _json_response(self, 200 if result["rc"] == 0 else 400, {"slug": slug, **result})

        if parsed.path == "/docs/scan":
            slug = _project_slug(params, body)
            if not slug:
                return _json_response(self, 400, {"error": "slug required"})
            result = _run_cli([sys.executable, str(Path(__file__).with_name("guardian.py")), "docs", "scan", slug])
            return _json_response(self, 200 if result["rc"] == 0 else 400, {"slug": slug, **result})

        if parsed.path == "/permission/check":
            slug = _project_slug(params, body)
            if not slug:
                return _json_response(self, 400, {"error": "slug required"})
            path = str(body.get("path", "") or "")
            operation = str(body.get("operation", "edit"))
            mode_state = shared.read_mode_state(slug)
            mode = str(body.get("mode") or mode_state.get("mode", shared.DEFAULT_MODE))
            query = f"{operation}: {path}" if path else f"{operation}"
            rag = _rag_query(slug, query, mode=mode) if query else None
            result = guardian_conciencia.quick_check(
                slug, path=path, operation_type=operation, mode=mode,
                rag_results=rag.get("results") if rag else None,
            )
            if rag:
                result["rag_score"] = max((r.get("score", 0.0) for r in rag.get("results", [])), default=0.0)
            return _json_response(self, 200, result)

        if parsed.path == "/mcp/call":
            import guardian_mcp
            tool_name = body.get("tool", "")
            args = body.get("args", {})
            slug = _project_slug(body)
            if slug:
                args["slug"] = slug
            guardian_mcp._handle_call(tool_name, args, "api")
            return _json_response(self, 200, {"ok": True})

        if parsed.path == "/forja/module/new":
            slug = _project_slug(params, body)
            name = str(body.get("name", ""))
            desc = str(body.get("desc", ""))
            if not name:
                return _json_response(self, 400, {"error": "name required"})
            import guardian_forja
            result = guardian_forja.module_new(name, desc)
            return _json_response(self, 200 if result.get("ok") else 400, result)

        if parsed.path == "/forja/rm":
            slug = _project_slug(params, body)
            mod = str(body.get("module", ""))
            force = bool(body.get("force", False))
            if not mod:
                return _json_response(self, 400, {"error": "module required"})
            import guardian_forja
            result = guardian_forja.delete_module(mod, force=force)
            return _json_response(self, 200 if result.get("ok") else 400, result)

        if parsed.path == "/forja/edit":
            slug = _project_slug(params, body)
            file_path = str(body.get("file", ""))
            content = body.get("content")
            if not file_path:
                return _json_response(self, 400, {"error": "file required"})
            import guardian_forja
            if content is not None:
                result = guardian_forja.write_file_content(file_path, content)
            else:
                result = guardian_forja.edit_file(file_path)
            return _json_response(self, 200 if result.get("ok") else 400, result)

        if parsed.path == "/forja/run":
            slug = _project_slug(params, body)
            text = str(body.get("text", ""))
            if not text:
                return _json_response(self, 400, {"error": "text required"})
            import guardian_forja
            result = guardian_forja.run_direct(text)
            return _json_response(self, 200, result)

        if parsed.path == "/forja/protect":
            slug = _project_slug(params, body)
            mod = str(body.get("module", ""))
            if not mod:
                return _json_response(self, 400, {"error": "module required"})
            import guardian_forja
            result = guardian_forja.protect_module(mod)
            return _json_response(self, 200 if result.get("ok") else 400, result)

        if parsed.path == "/forja/endpoint":
            slug = _project_slug(params, body)
            method = str(body.get("method", "GET")).upper()
            path = str(body.get("path", ""))
            module = str(body.get("module", ""))
            if not path:
                return _json_response(self, 400, {"error": "path required"})
            import guardian_forja
            result = guardian_forja.cmd_endpoint(method, path, module)
            return _json_response(self, 201 if result.get("ok") else 400, result)

        if parsed.path == "/forja/mcp-tool":
            slug = _project_slug(params, body)
            name = str(body.get("name", ""))
            module = str(body.get("module", ""))
            if not name:
                return _json_response(self, 400, {"error": "name required"})
            import guardian_forja
            result = guardian_forja.cmd_mcp_tool(name, module)
            return _json_response(self, 201 if result.get("ok") else 400, result)

        if parsed.path == "/forja/function":
            slug = _project_slug(params, body)
            func_name = str(body.get("function", ""))
            register = body.get("register", False)
            module = str(body.get("module", "guardian_forja"))
            if not func_name:
                return _json_response(self, 400, {"error": "function name required"})
            import guardian_forja
            result = guardian_forja.function_add(module, func_name, register=bool(register))
            return _json_response(self, 201 if result.get("ok") else 400, result)

        if parsed.path == "/forja/diff":
            slug = _project_slug(params, body)
            import guardian_forja
            result = guardian_forja.diff_snapshot()
            return _json_response(self, 200, result)

        if parsed.path == "/forja/graph":
            slug = _project_slug(params, body)
            import guardian_forja
            result = guardian_forja.graph_deps()
            return _json_response(self, 200, result)

        if parsed.path == "/forja/patch":
            slug = _project_slug(params, body)
            rel_path = str(body.get("file", ""))
            old_text = str(body.get("old", ""))
            new_text = str(body.get("new", ""))
            if not rel_path or not old_text or not new_text:
                return _json_response(self, 400, {"error": "file, old, and new required"})
            import guardian_forja
            result = guardian_forja.patch_file(rel_path, old_text, new_text)
            return _json_response(self, 200 if result.get("ok") else 400, result)

        if parsed.path == "/activate":
            slug = _project_slug(params, body)
            if not slug:
                cwd = os.getcwd()
                slug = os.path.basename(cwd).lower().replace(" ", "-").replace("_", "-")
            result = {"slug": slug, "steps": []}
            config = shared.read_config(slug)
            if not config:
                guardian_setup = Path(__file__).with_name("guardian.py")
                proc = subprocess.run(
                    [sys.executable, str(guardian_setup), "setup", slug, "--auto"],
                    capture_output=True, text=True, timeout=120,
                )
                result["steps"].append({"step": "setup", "rc": proc.returncode})
            config = shared.read_config(slug) or {}
            state, path = guardian_genome.fork_branch(slug)
            result["steps"].append({"step": "branch_fork", "path": str(path)})
            absorb_script = Path(__file__).with_name("guardian_absorb.py")
            proc = subprocess.run(
                [sys.executable, str(absorb_script), "scan"],
                capture_output=True, text=True, timeout=60,
            )
            result["steps"].append({"step": "absorb_scan", "rc": proc.returncode})
            proc = subprocess.run(
                [sys.executable, str(absorb_script), "match", slug],
                capture_output=True, text=True, timeout=60,
            )
            result["steps"].append({"step": "absorb_match", "rc": proc.returncode})
            rc = guardian_absorb.cmd_ingest(slug)
            result["steps"].append({"step": "absorb_ingest", "rc": rc})
            guardian_setup = Path(__file__).with_name("guardian.py")
            proc = subprocess.run(
                [sys.executable, str(guardian_setup), "docs", "scan", slug],
                capture_output=True, text=True, timeout=60,
            )
            result["steps"].append({"step": "docs_scan", "rc": proc.returncode})
            mode_state = shared.read_mode_state(slug)
            mode = mode_state.get("mode", shared.DEFAULT_MODE)
            plantilla = f"SOY: activar guardian en {slug}"
            conciencia_result = guardian_conciencia.run_cycle(slug, question=plantilla, mode=mode)
            result["steps"].append({
                "step": "conciencia_cycle",
                "action": conciencia_result.get("action"),
                "confidence": conciencia_result.get("confidence"),
            })
            result["status"] = "ok"
            return _json_response(self, 200, result)

        return _json_response(self, 404, {"error": "not found"})


def _run_cli(cmd):
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return {"rc": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}


def serve(host=HOST, port=DEFAULT_PORT):
    server = ThreadingHTTPServer((host, port), GuardianBackendHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def start(host=HOST, port=DEFAULT_PORT):
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)
            return 0
        except Exception:
            PID_FILE.unlink(missing_ok=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(Path(__file__).resolve()), "serve", "--host", host, "--port", str(port)]
    with open(LOG_FILE, "a", encoding="utf-8") as log:
        proc = subprocess.Popen(cmd, stdout=log, stderr=log, start_new_session=True)
    PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    return 0


def stop():
    if not PID_FILE.exists():
        return 0
    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, signal.SIGTERM)
    except Exception:
        pass
    PID_FILE.unlink(missing_ok=True)
    return 0


def status(host=HOST, port=DEFAULT_PORT):
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)
            return {"running": True, "pid": pid, "host": host, "port": port}
        except Exception:
            PID_FILE.unlink(missing_ok=True)
    return {"running": False, "host": host, "port": port}


def main(argv=None):
    argv = list(argv or sys.argv[1:])
    parser = argparse.ArgumentParser(prog="guardian_backend.py")
    sub = parser.add_subparsers(dest="cmd", required=True)

    serve_p = sub.add_parser("serve")
    serve_p.add_argument("--host", default=HOST)
    serve_p.add_argument("--port", type=int, default=DEFAULT_PORT)

    start_p = sub.add_parser("start")
    start_p.add_argument("--host", default=HOST)
    start_p.add_argument("--port", type=int, default=DEFAULT_PORT)

    stop_p = sub.add_parser("stop")

    status_p = sub.add_parser("status")

    args = parser.parse_args(argv)
    if args.cmd == "serve":
        serve(args.host, args.port)
        return 0
    if args.cmd == "start":
        return start(args.host, args.port)
    if args.cmd == "stop":
        return stop()
    if args.cmd == "status":
        print(json.dumps(status(args.host, args.port), ensure_ascii=False))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
