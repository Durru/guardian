from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

import guardian_conciencia
import guardian_genome
import guardian_rag
import guardian_shared as shared

TOOLS = [
    {
        "name": "read_file",
        "description": "Leer contenido de un archivo",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Ruta absoluta al archivo"}
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Escribir contenido en un archivo (solo modo build)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Ruta absoluta al archivo"},
                "content": {"type": "string", "description": "Contenido a escribir"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "run_command",
        "description": "Ejecutar un comando bash",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Comando a ejecutar"},
                "timeout": {"type": "number", "description": "Timeout en ms"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "rag_query",
        "description": "Consultar la base de conocimiento RAG",
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "Slug del proyecto"},
                "query": {"type": "string", "description": "Consulta"},
                "mode": {"type": "string", "enum": ["plan", "build"]},
                "top_k": {"type": "number"},
            },
            "required": ["slug", "query"],
        },
    },
    {
        "name": "conciencia_cycle",
        "description": "Ejecutar un ciclo de conciencia",
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "Slug del proyecto"},
                "question": {"type": "string"},
                "mode": {"type": "string", "enum": ["plan", "build"]},
            },
            "required": ["slug"],
        },
    },
    {
        "name": "mode_switch",
        "description": "Cambiar modo plan/build",
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string"},
                "mode": {"type": "string", "enum": ["plan", "build"]},
                "reason": {"type": "string"},
            },
            "required": ["slug", "mode"],
        },
    },
    {
        "name": "knowledge_search",
        "description": "Buscar en tomos de conocimiento",
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string"},
                "query": {"type": "string"},
                "top_k": {"type": "number"},
            },
            "required": ["slug", "query"],
        },
    },
    {
        "name": "genome_status",
        "description": "Ver identidad y estado del genoma",
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string"},
            },
            "required": ["slug"],
        },
    },
    {
        "name": "branch_fork",
        "description": "Crear una rama para un usuario",
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string"},
            },
            "required": ["slug"],
        },
    },
    {
        "name": "activate_guardian",
        "description": "Activar Guardian en un proyecto — setup, fork, absorb, docs, conciencia",
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "Slug del proyecto (opcional, auto-detecta)"},
            },
        },
    },
]


def _respond(id_val, result=None, error=None):
    body = {"jsonrpc": "2.0", "id": id_val}
    if error:
        body["error"] = {"code": error.get("code", -1), "message": error.get("message", "Error")}
    else:
        body["result"] = result or {}
    sys.stdout.write(json.dumps(body, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _handle_call(tool_name, args, id_val):
    if tool_name == "read_file":
        path = args.get("path", "")
        try:
            content = Path(path).read_text(encoding="utf-8")
            _respond(id_val, {"content": content, "path": path})
        except Exception as e:
            _respond(id_val, error={"code": -1, "message": str(e)})

    elif tool_name == "write_file":
        path = args.get("path", "")
        content = args.get("content", "")
        slug = args.get("slug", "")
        if slug:
            mode_state = shared.read_mode_state(slug)
            if mode_state.get("mode") != "build":
                _respond(id_val, error={"code": -2, "message": "Solo se puede escribir en modo build"})
                return
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(content, encoding="utf-8")
            _respond(id_val, {"ok": True, "path": path, "bytes": len(content)})
        except Exception as e:
            _respond(id_val, error={"code": -1, "message": str(e)})

    elif tool_name == "run_command":
        import subprocess
        command = args.get("command", "")
        timeout = args.get("timeout", 30000)
        try:
            proc = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                timeout=timeout / 1000 if timeout else None,
            )
            _respond(id_val, {
                "rc": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            })
        except subprocess.TimeoutExpired:
            _respond(id_val, error={"code": -3, "message": "Command timed out"})
        except Exception as e:
            _respond(id_val, error={"code": -1, "message": str(e)})

    elif tool_name == "rag_query":
        slug = args.get("slug", "")
        query = args.get("query", "")
        mode = args.get("mode", shared.DEFAULT_MODE)
        top_k = args.get("top_k", 5)
        config = shared.read_config(slug)
        if not config:
            _respond(id_val, error={"code": -1, "message": f"Proyecto '{slug}' no encontrado"})
            return
        source_filter = {"memory", "knowledge"}
        if mode == "build":
            source_filter.update({"code", "doc"})
        else:
            source_filter.update({"doc"})
        chunks = guardian_rag._collect_chunks(slug, config, source_filter)
        if not chunks:
            _respond(id_val, {"results": [], "query": query, "slug": slug})
            return
        contents = [c["content"] for c in chunks]
        from guardian_memory import _compute_tfidf_index, _embed_text
        idf, vocab = _compute_tfidf_index([{"content": ct} for ct in contents])
        query_vec = _embed_text(query, idf, vocab)
        results = []
        if any(query_vec):
            all_scored = guardian_rag._rerank(chunks, idf, vocab, query_vec, None)
            for c in all_scored[:top_k]:
                results.append({
                    "score": c.get("_score", 0.0),
                    "source": c.get("source"),
                    "content": c.get("content", "")[:300],
                })
        _respond(id_val, {"results": results, "query": query, "slug": slug, "total": len(results)})

    elif tool_name == "conciencia_cycle":
        slug = args.get("slug", "")
        question = args.get("question", "")
        mode = args.get("mode", shared.DEFAULT_MODE)
        result = guardian_conciencia.run_cycle(slug, question=question, mode=mode)
        _respond(id_val, result)

    elif tool_name == "mode_switch":
        slug = args.get("slug", "")
        mode = args.get("mode", "plan")
        reason = args.get("reason", "")
        if mode not in ("plan", "build"):
            _respond(id_val, error={"code": -1, "message": "Modo debe ser plan o build"})
            return
        state = shared.append_mode_history(slug, mode, reason)
        _respond(id_val, {"slug": slug, "mode": mode, "state": state})

    elif tool_name == "knowledge_search":
        slug = args.get("slug", "")
        query = args.get("query", "")
        top_k = args.get("top_k", 5)
        config = shared.read_config(slug)
        if not config:
            _respond(id_val, error={"code": -1, "message": f"Proyecto '{slug}' no encontrado"})
            return
        chunks = guardian_rag._collect_chunks(slug, config, {"knowledge"})
        if not chunks:
            _respond(id_val, {"results": [], "query": query, "slug": slug})
            return
        contents = [c["content"] for c in chunks]
        from guardian_memory import _compute_tfidf_index, _embed_text
        idf, vocab = _compute_tfidf_index([{"content": ct} for ct in contents])
        query_vec = _embed_text(query, idf, vocab)
        results = []
        if any(query_vec):
            all_scored = guardian_rag._rerank(chunks, idf, vocab, query_vec, None)
            for c in all_scored[:top_k]:
                results.append({
                    "score": c.get("_score", 0.0),
                    "source": c.get("source"),
                    "content": c.get("content", "")[:300],
                })
        _respond(id_val, {"results": results, "query": query, "slug": slug})

    elif tool_name == "genome_status":
        slug = args.get("slug", "")
        genome = guardian_genome.load_genome()
        branch_info = guardian_genome.branch_status(slug)
        _respond(id_val, {
            "genome": genome.get("identity", {}),
            "branch": branch_info,
        })

    elif tool_name == "branch_fork":
        slug = args.get("slug", "")
        state, path = guardian_genome.fork_branch(slug)
        _respond(id_val, {"slug": slug, "path": str(path), "branch_hash": guardian_genome._branch_hash()})

    elif tool_name == "activate_guardian":
        slug = args.get("slug", "")
        if not slug:
            import os as _os
            slug = _os.path.basename(_os.getcwd()).lower().replace(" ", "-").replace("_", "-")
        import subprocess as _sp
        import sys as _sys
        config = shared.read_config(slug)
        if not config:
            setup_script = Path(__file__).with_name("guardian.py")
            _sp.run([_sys.executable, str(setup_script), "setup", slug, "--auto"],
                    capture_output=True, text=True, timeout=120)
        state, path = guardian_genome.fork_branch(slug)
        absorb_script = Path(__file__).with_name("guardian_absorb.py")
        _sp.run([_sys.executable, str(absorb_script), "scan"], capture_output=True, text=True, timeout=60)
        _sp.run([_sys.executable, str(absorb_script), "match", slug], capture_output=True, text=True, timeout=60)
        import guardian_absorb as _ga
        _ga.cmd_ingest(slug)
        docs_script = Path(__file__).with_name("guardian.py")
        _sp.run([_sys.executable, str(docs_script), "docs", "scan", slug],
                capture_output=True, text=True, timeout=60)
        mode_state = shared.read_mode_state(slug)
        mode = mode_state.get("mode", shared.DEFAULT_MODE)
        conciencia_result = guardian_conciencia.run_cycle(slug, question=f"SOY: activar guardian en {slug}", mode=mode)
        _respond(id_val, {
            "slug": slug,
            "branch_path": str(path),
            "action": conciencia_result.get("action"),
            "confidence": conciencia_result.get("confidence"),
            "status": "ok",
        })

    else:
        _respond(id_val, error={"code": -32601, "message": f"Tool not found: {tool_name}"})


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg_id = msg.get("id")
        method = msg.get("method", "")

        if method == "initialize":
            _respond(msg_id, {
                "protocolVersion": "2025-03-26",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "guardian-mcp", "version": "2.0.0"},
            })
        elif method in ("list_tools", "tools/list"):
            _respond(msg_id, {"tools": TOOLS})
        elif method in ("call_tool", "tools/call"):
            _handle_call(msg.get("params", {}).get("name", ""), msg.get("params", {}).get("arguments", {}), msg_id)
        elif method == "ping":
            _respond(msg_id, {})
        elif method == "logging/setLevel":
            _respond(msg_id, {})
        elif method in ("notifications/initialized", "notifications/cancelled", "notifications/progress"):
            pass
        else:
            _respond(msg_id, error={"code": -32601, "message": f"Method not found: {method}"})


if __name__ == "__main__":
    main()
