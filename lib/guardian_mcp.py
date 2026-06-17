from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

import guardian_brain
import guardian_brain_advisor
import guardian_brain_symbols
import guardian_capability
import guardian_conciencia
import guardian_genome
import guardian_knowledge
import guardian_observer
import guardian_publish
import guardian_rag
import guardian_shared as shared
import guardian_specialization

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
    {
        "name": "forja_doctor",
        "description": "Diagnóstico de salud del sistema Guardian",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "forja_validate",
        "description": "Validar módulo contra convenciones de Guardian",
        "inputSchema": {
            "type": "object",
            "properties": {
                "module": {"type": "string", "description": "Nombre del módulo (opcional, valida todos si se omite)"},
            },
        },
    },
    {
        "name": "forja_index",
        "description": "Reconstruir el índice de auto-conocimiento de la Forja",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "forja_list",
        "description": "Listar inventario de módulos, endpoints y MCP tools",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "forja_scaffold",
        "description": "Scaffoldear nuevo módulo guardian_*.py",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nombre del módulo (snake_case)"},
                "desc": {"type": "string", "description": "Descripción breve"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "forja_endpoint",
        "description": "Scaffoldear nuevo endpoint REST en guardian_backend.py",
        "inputSchema": {
            "type": "object",
            "properties": {
                "method": {"type": "string", "description": "GET o POST"},
                "path": {"type": "string", "description": "Ruta del endpoint, ej: /api/health"},
                "module": {"type": "string", "description": "Módulo backend asociado (opcional)"},
            },
            "required": ["method", "path"],
        },
    },
    {
        "name": "forja_mcp_tool",
        "description": "Scaffoldear nueva tool MCP en guardian_mcp.py",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nombre de la tool (snake_case)"},
                "module": {"type": "string", "description": "Módulo Python asociado (opcional)"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "forja_function",
        "description": "Agregar cmd_<name> a un módulo, opcionalmente registrándolo en dispatch",
        "inputSchema": {
            "type": "object",
            "properties": {
                "function": {"type": "string", "description": "Nombre de la función cmd_"},
                "module": {"type": "string", "description": "Módulo destino (default: guardian_forja)"},
                "register": {"type": "boolean", "description": "Registrar también en guardian.py dispatch"},
            },
            "required": ["function"],
        },
    },
    {
        "name": "forja_diff",
        "description": "Snapshot diff del índice de auto-conocimiento",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "forja_graph",
        "description": "Grafo ASCII de dependencias entre módulos Guardian",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "forja_patch",
        "description": "Edición parcial find+replace en archivos del core",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "Ruta relativa al archivo (ej: guardian_forja.py)"},
                "old": {"type": "string", "description": "Texto a reemplazar"},
                "new": {"type": "string", "description": "Texto nuevo"},
            },
            "required": ["file", "old", "new"],
        },
    },
    {
        "name": "forja_run",
        "description": "Interfaz directa: interpreta un pedido en lenguaje natural y ejecuta la acción correspondiente",
        "inputSchema": {
            "type": "object",
            "properties": {
                 "text": {"type": "string", "description": "Pedido en lenguaje natural"},
             },
             "required": ["text"],
         },
     },
    {
        "name": "brain_read",
        "description": "Lee el GUARDIAN.md esencial (cerebro siempre cargado)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "Slug del proyecto"},
            },
            "required": ["slug"],
        },
    },
    {
        "name": "brain_query",
        "description": "Búsqueda vectorial en un nivel del cerebro",
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string"},
                "level": {"type": "string", "enum": ["semantic", "episodic", "procedural", "reflection"]},
                "q": {"type": "string", "description": "Consulta"},
                "top_k": {"type": "number"},
            },
            "required": ["slug", "level", "q"],
        },
    },
    {
        "name": "brain_write",
        "description": "Escribe un nodo en el cerebro (pasa por el Governor)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string"},
                "level": {"type": "string", "enum": ["semantic", "episodic", "procedural", "reflection"]},
                "kind": {"type": "string"},
                "content": {"type": "string"},
                "importance": {"type": "number"},
                "tags": {"type": "string", "description": "Comma-separated"},
            },
            "required": ["slug", "level", "kind", "content"],
        },
    },
    {
        "name": "brain_reflect",
        "description": "Dispara el Reflection Agent (post-sesión)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string"},
            },
            "required": ["slug"],
        },
    },
    {
        "name": "session_end",
        "description": "Cierra sesión: reflection + GUARDIAN.md regen + handoff",
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["slug"],
        },
    },
    {
        "name": "knowledge_research",
        "description": "Investiga un tema y devuelve un plan de research",
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string"},
                "query": {"type": "string"},
                "depth": {"type": "string", "enum": ["quick", "deep"]},
            },
            "required": ["slug", "query"],
        },
    },
    {
        "name": "specialization_enable",
        "description": "Activa una especialización (odoo, nextjs, etc.) en el proyecto",
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string"},
                "name": {"type": "string"},
            },
            "required": ["slug", "name"],
        },
    },
    {
        "name": "maintain",
        "description": "Diagnóstico completo del proyecto (drift, stale, salud)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string"},
                "project_root": {"type": "string"},
            },
            "required": ["slug"],
        },
    },
    {
        "name": "publish",
        "description": "Publica un proyecto como template sanitizado",
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string"},
                "version": {"type": "string"},
                "to": {"type": "string", "enum": ["template", "production"]},
            },
            "required": ["slug"],
        },
    },
    {
        "name": "clone",
        "description": "Crea un nuevo proyecto a partir de un template",
        "inputSchema": {
            "type": "object",
            "properties": {
                "template": {"type": "string"},
                "new": {"type": "string"},
            },
            "required": ["template", "new"],
        },
    },
    {
        "name": "capability_status",
        "description": "Estado del model card (success_rate por tipo de tarea)",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "capability_routing",
        "description": "Decide si delegar una tarea al LLM o no",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_type": {"type": "string"},
                "context_size": {"type": "number"},
                "complexity": {"type": "string", "enum": ["low", "medium", "high"]},
            },
            "required": ["task_type"],
        },
    },
    {
        "name": "compact_now",
        "description": "Dispara compactación automática del cerebro",
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string"},
            },
            "required": ["slug"],
        },
    },
    {
        "name": "codegraph_lookup",
        "description": "v4: CodeGraph — busca símbolos en el mapa del proyecto (AST indexado con tree-sitter). 1 tool = 40 calls.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string"},
                "query": {"type": "string"},
                "top_k": {"type": "number", "default": 5},
                "max_tokens": {"type": "number", "default": 2000},
            },
            "required": ["slug", "query"],
        },
    },
    {
        "name": "advisor_context",
        "description": "v4: Advisor — inyecta contexto dinámico para el LLM. Retorna vacío si nada relevante.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string"},
                "prompt": {"type": "string"},
                "max_tokens": {"type": "number", "default": 500},
            },
            "required": ["slug"],
        },
    },
    {
        "name": "advisor_warn_action",
        "description": "v4: Advisor — advierte si una acción del LLM es riesgosa.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string"},
                "tool": {"type": "string"},
                "args": {"type": "string"},
                "file": {"type": "string"},
            },
            "required": ["slug"],
        },
    },
    {
        "name": "observer_log_prompt",
        "description": "Log de prompt de usuario via Observer",
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string"},
                "prompt": {"type": "string"},
                "mode": {"type": "string"},
            },
            "required": ["slug", "prompt"],
        },
    },
    {
        "name": "analyze_intent",
        "description": "Analiza el intent del usuario, extrae topic_key y clasifica importancia",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Mensaje del usuario"},
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "save_observation",
        "description": "Guarda una observación con metadata completa en el brain",
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string"},
                "type": {"type": "string", "enum": ["decision", "error", "pattern", "architecture", "config", "bugfix"]},
                "topic_key": {"type": "string"},
                "content": {"type": "string"},
                "why": {"type": "string"},
                "where": {"type": "string"},
                "outcome": {"type": "string", "enum": ["success", "failure", "warning", "info"]},
                "scope": {"type": "string", "enum": ["project", "global"]},
                "tags": {"type": "string"},
            },
            "required": ["slug", "type", "topic_key", "content"],
        },
    },
    {
        "name": "get_observation",
        "description": "Busca observaciones por topic_key en el brain (proyecto + global)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string"},
                "topic_key": {"type": "string"},
                "limit": {"type": "number"},
                "global": {"type": "boolean"},
            },
            "required": ["slug", "topic_key"],
        },
    },
    {
        "name": "get_last_good",
        "description": "Obtiene la última observación exitosa para un topic_key",
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string"},
                "topic_key": {"type": "string"},
            },
            "required": ["slug", "topic_key"],
        },
    },
    {
        "name": "plan_or_act",
        "description": "Evalúa si una request necesita plan complejo o va directo",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "slug": {"type": "string"},
                "confidence": {"type": "number"},
            },
            "required": ["question"],
        },
    },
    {
        "name": "compact_memory",
        "description": "Compacta GUARDIAN.md: borra líneas viejas manteniendo las más importantes",
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string"},
            },
            "required": ["slug"],
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

    elif tool_name == "forja_doctor":
        import guardian_forja
        result = guardian_forja.doctor_check()
        _respond(id_val, result)

    elif tool_name == "forja_validate":
        import guardian_forja
        mod = args.get("module", "")
        result = guardian_forja.validate_module(mod)
        _respond(id_val, result)

    elif tool_name == "forja_index":
        import guardian_forja
        result = guardian_forja.scan_index()
        _respond(id_val, result)

    elif tool_name == "forja_list":
        import guardian_forja
        result = guardian_forja.list_inventory()
        _respond(id_val, result)

    elif tool_name == "forja_scaffold":
        import guardian_forja
        name = args.get("name", "")
        desc = args.get("desc", "")
        result = guardian_forja.module_new(name, desc)
        _respond(id_val, result)

    elif tool_name == "forja_run":
        import guardian_forja
        text = args.get("text", "")
        result = guardian_forja.run_direct(text)
        _respond(id_val, result)

    elif tool_name == "forja_endpoint":
        import guardian_forja
        method = args.get("method", "GET").upper()
        path = args.get("path", "")
        module = args.get("module", "")
        if not path:
            _respond(id_val, error={"code": -32602, "message": "path required"})
            return
        result = guardian_forja.cmd_endpoint(method, path, module)
        _respond(id_val, result)

    elif tool_name == "forja_mcp_tool":
        import guardian_forja
        name = args.get("name", "")
        module = args.get("module", "")
        if not name:
            _respond(id_val, error={"code": -32602, "message": "name required"})
            return
        result = guardian_forja.cmd_mcp_tool(name, module)
        _respond(id_val, result)

    elif tool_name == "forja_function":
        import guardian_forja
        func_name = args.get("function", "")
        module = args.get("module", "guardian_forja")
        register = args.get("register", False)
        if not func_name:
            _respond(id_val, error={"code": -32602, "message": "function name required"})
            return
        result = guardian_forja.function_add(module, func_name, register=bool(register))
        _respond(id_val, result)

    elif tool_name == "forja_diff":
        import guardian_forja
        result = guardian_forja.diff_snapshot()
        _respond(id_val, result)

    elif tool_name == "forja_graph":
        import guardian_forja
        result = guardian_forja.graph_deps()
        _respond(id_val, result)

    elif tool_name == "forja_patch":
        import guardian_forja
        rel_path = args.get("file", "")
        old_text = args.get("old", "")
        new_text = args.get("new", "")
        if not rel_path or not old_text or not new_text:
            _respond(id_val, error={"code": -32602, "message": "file, old, and new required"})
            return
        result = guardian_forja.patch_file(rel_path, old_text, new_text)
        _respond(id_val, result)

    elif tool_name == "brain_read":
        slug = args.get("slug", "")
        if not slug:
            _respond(id_val, error={"code": -32602, "message": "slug required"})
            return
        text = guardian_brain.read_guardian_md(slug)
        _respond(id_val, {"slug": slug, "guardian_md": text, "lines": text.count("\n") + 1 if text else 0})

    elif tool_name == "brain_query":
        slug = args.get("slug", "")
        level = args.get("level", "semantic")
        q = args.get("q", "")
        top_k = int(args.get("top_k", 5))
        if not slug or not q:
            _respond(id_val, error={"code": -32602, "message": "slug and q required"})
            return
        results = guardian_brain.query(slug, level, q, top_k=top_k)
        _respond(id_val, {"slug": slug, "level": level, "q": q, "results": results})

    elif tool_name == "brain_write":
        slug = args.get("slug", "")
        level = args.get("level", "semantic")
        kind = args.get("kind", "note")
        content = args.get("content", "")
        importance = float(args.get("importance", 0.6))
        tags = args.get("tags", "")
        if not slug or not content:
            _respond(id_val, error={"code": -32602, "message": "slug and content required"})
            return
        node = {"kind": kind, "content": content, "importance": importance}
        if tags:
            node["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
        result = guardian_brain.write_governed(slug, level, node)
        _respond(id_val, result)

    elif tool_name == "brain_reflect":
        slug = args.get("slug", "")
        if not slug:
            _respond(id_val, error={"code": -32602, "message": "slug required"})
            return
        _respond(id_val, guardian_brain.run_reflection(slug))

    elif tool_name == "session_end":
        slug = args.get("slug", "")
        reason = args.get("reason", "explicit")
        if not slug:
            _respond(id_val, error={"code": -32602, "message": "slug required"})
            return
        _respond(id_val, guardian_brain.session_end(slug, reason=reason))

    elif tool_name == "knowledge_research":
        slug = args.get("slug", "")
        query = args.get("query", "")
        depth = args.get("depth", "quick")
        if not slug or not query:
            _respond(id_val, error={"code": -32602, "message": "slug and query required"})
            return
        _respond(id_val, guardian_knowledge.research(slug, query, depth=depth))

    elif tool_name == "specialization_enable":
        slug = args.get("slug", "")
        name = args.get("name", "")
        if not slug or not name:
            _respond(id_val, error={"code": -32602, "message": "slug and name required"})
            return
        _respond(id_val, guardian_specialization.enable(slug, name))

    elif tool_name == "maintain":
        slug = args.get("slug", "")
        project_root = args.get("project_root", "")
        if not slug:
            _respond(id_val, error={"code": -32602, "message": "slug required"})
            return
        import guardian_maintain
        _respond(id_val, guardian_maintain.health_report(slug, project_root=project_root or None))

    elif tool_name == "publish":
        slug = args.get("slug", "")
        version = args.get("version", "1.0.0")
        to = args.get("to", "template")
        if not slug:
            _respond(id_val, error={"code": -32602, "message": "slug required"})
            return
        _respond(id_val, guardian_publish.publish(slug, version=version, to=to))

    elif tool_name == "clone":
        template = args.get("template", "")
        new_slug = args.get("new", "")
        if not template or not new_slug:
            _respond(id_val, error={"code": -32602, "message": "template and new required"})
            return
        _respond(id_val, guardian_publish.clone(template, new_slug))

    elif tool_name == "capability_status":
        card = guardian_capability.load_card()
        metrics = card.get("metrics", {}) if isinstance(card, dict) else {}
        _respond(id_val, {"model": card.get("model", "guardian-default") if isinstance(card, dict) else "guardian-default", "metrics": metrics, "card": card})

    elif tool_name == "capability_routing":
        task_type = args.get("task_type", "")
        ctx = int(args.get("context_size", 0))
        complexity = args.get("complexity", "medium")
        if not task_type:
            _respond(id_val, error={"code": -32602, "message": "task_type required"})
            return
        _respond(id_val, guardian_capability.routing_decision(
            task_type, context_size=ctx, complexity=complexity
        ))

    elif tool_name == "compact_now":
        slug = args.get("slug", "")
        if not slug:
            _respond(id_val, error={"code": -32602, "message": "slug required"})
            return
        _respond(id_val, guardian_brain.auto_compact(slug, dry_run=False))

    elif tool_name == "codegraph_lookup":
        slug = args.get("slug", "")
        query = args.get("query", "")
        top_k = int(args.get("top_k", 5))
        max_tokens = int(args.get("max_tokens", 2000))
        if not slug or not query:
            _respond(id_val, error={"code": -32602, "message": "slug and query required"})
            return
        result = guardian_brain_symbols.query_smart(slug, query, top_k=top_k, max_tokens=max_tokens)
        _respond(id_val, {"slug": slug, "query": query, "result": result})

    elif tool_name == "advisor_context":
        slug = args.get("slug", "")
        prompt = args.get("prompt", "")
        max_tokens = int(args.get("max_tokens", 500))
        if not slug:
            _respond(id_val, error={"code": -32602, "message": "slug required"})
            return
        advisor = guardian_brain_advisor.Advisor(slug)
        ctx = advisor.build_context(prompt, max_tokens=max_tokens)
        _respond(id_val, {"slug": slug, "context": ctx, "injected": bool(ctx)})

    elif tool_name == "advisor_warn_action":
        slug = args.get("slug", "")
        tool_name_arg = args.get("tool", "")
        tool_args = args.get("args", "")
        tool_file = args.get("file", "")
        if not slug:
            _respond(id_val, error={"code": -32602, "message": "slug required"})
            return
        advisor = guardian_brain_advisor.Advisor(slug)
        result = advisor.advise_on_action({"tool": tool_name_arg, "args": tool_args, "file": tool_file})
        _respond(id_val, {"slug": slug, "warn": result.get("warn") if result else None, "risk": result.get("risk") if result else None})

    elif tool_name == "analyze_intent":
        prompt = args.get("prompt", "")
        if not prompt:
            _respond(id_val, error={"code": -32602, "message": "prompt required"})
            return
        topic_key = guardian_observer.extract_topic_key(prompt)
        importance = guardian_observer.classify_importance(prompt, "chat.message")
        _respond(id_val, {
            "topic_key": topic_key,
            "importance": round(importance, 2),
            "has_context": bool(topic_key),
        })

    elif tool_name == "save_observation":
        slug = args.get("slug", "")
        obs_type = args.get("type", "decision")
        topic_key = args.get("topic_key", "general")
        content = args.get("content", "")
        why = args.get("why", "")
        where = args.get("where", "")
        outcome = args.get("outcome", "info")
        scope = args.get("scope", "project")
        tags = args.get("tags", "")
        if not slug or not content:
            _respond(id_val, error={"code": -32602, "message": "slug and content required"})
            return
        tags_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        result = guardian_brain.write_observation(
            slug, obs_type, topic_key, content,
            why=why, where=where, outcome=outcome, scope=scope, tags=tags_list,
        )
        _respond(id_val, result)

    elif tool_name == "get_observation":
        slug = args.get("slug", "")
        topic_key = args.get("topic_key", "")
        limit = int(args.get("limit", 5))
        global_too = args.get("global", True)
        if not slug or not topic_key:
            _respond(id_val, error={"code": -32602, "message": "slug and topic_key required"})
            return
        results = guardian_brain.get_observations(slug, topic_key, limit=limit, global_too=bool(global_too))
        _respond(id_val, {"slug": slug, "topic_key": topic_key, "observations": results})

    elif tool_name == "get_last_good":
        slug = args.get("slug", "")
        topic_key = args.get("topic_key", "")
        if not slug or not topic_key:
            _respond(id_val, error={"code": -32602, "message": "slug and topic_key required"})
            return
        result = guardian_brain.get_last_good(slug, topic_key)
        _respond(id_val, {"slug": slug, "topic_key": topic_key, "observation": result})

    elif tool_name == "plan_or_act":
        question = args.get("question", "")
        slug = args.get("slug", "")
        confidence = float(args.get("confidence", 0.5))
        if not question:
            _respond(id_val, error={"code": -32602, "message": "question required"})
            return
        q = question.lower()
        complexity = "high" if len(question) > 150 or any(k in q for k in (
            "migr", "refactor", "arquitectur", "reestructur",
        )) else "low"
        if confidence >= 0.8 and complexity == "low":
            action = "assume"
            plan_type = "direct"
            reason = "Confianza alta + simple → ejecutar directo"
        elif confidence >= 0.5 and complexity == "low":
            action = "ask_little"
            plan_type = "direct"
            reason = "Confianza media + simple → preguntar y ejecutar"
        elif complexity == "high" and confidence >= 0.6:
            action = "plan"
            plan_type = "openspec"
            reason = "Tarea compleja → planificar con OpenSpec"
        else:
            action = "investigate"
            plan_type = "research"
            reason = "Confianza baja o tarea ambigua → investigar primero"
        _respond(id_val, {"action": action, "plan_type": plan_type, "reason": reason})

    elif tool_name == "compact_memory":
        slug = args.get("slug", "")
        if not slug:
            _respond(id_val, error={"code": -32602, "message": "slug required"})
            return
        result = guardian_brain.compact_guardian_md(slug)
        _respond(id_val, result)

    elif tool_name == "observer_log_prompt":
        slug = args.get("slug", "")
        prompt = args.get("prompt", "")
        mode = args.get("mode", "build")
        if not slug or not prompt:
            _respond(id_val, error={"code": -32602, "message": "slug and prompt required"})
            return
        reason = guardian_observer.infer_reason_from_prompt(prompt)
        eid = guardian_observer.log_prompt(slug, prompt, reason, mode)
        _respond(id_val, {"slug": slug, "id": eid, "reason": reason})

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
