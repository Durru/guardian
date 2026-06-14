#!/usr/bin/env python3
"""
Guardian CLI — unified command interface for Nexxoria Guardian.

Usage:
  guardian status [slug]
  guardian check [slug]
  guardian report [slug]
  guardian detect
  guardian protect <path> [slug]
  guardian snapshot <path> [slug]
  guardian diff [path] [slug]
  guardian rollback [slug]
  guardian hooks [slug]
  guardian docs scan [slug]
  guardian docs route <path> [slug]
  guardian setup [slug]
  guardian context [--brief|--check|--full|--json] [--since-last|--since=<ts>] [--scope=<path>] [slug]
  guardian mode <plan|build|status> [reason...]
  guardian backend <start|stop|restart|status>
  guardian prompt <step> [--scope=<path>] [--type=<tipo>] [--files=<paths>] [slug]
  guardian pre-change <files...> [--auto] [slug]
  guardian post-change [files...] [--auto] [--no-tests] [--no-lint] [slug]
  guardian pre-deploy [--auto] [slug]
  guardian post-deploy [--auto] [slug]
  guardian memory <args>...
  guardian absorb <args>...
  guardian knowledge <status|tomes|search> [args...]
  guardian pr <create|status|comment|approve|merge|list|checkout> [args]
  guardian issue <list|create|close|comment> [args]
  guardian projects <list|status|gc|absorb>
  guardian build|dev|test|lint|typecheck|deploy|logs [slug]
"""

import builtins
import json
import sys
import os
import hashlib
import re
import subprocess
import shlex
import shutil
import fnmatch
from datetime import datetime, timezone
from pathlib import Path
import guardian_shared as shared
import guardian_genome
import guardian_evolution
from guardian_shared import _

_builtin_print = builtins.print
_builtin_input = builtins.input

def _print(*args, **kwargs):
    args = tuple(shared._(a) if isinstance(a, str) else a for a in args)
    _builtin_print(*args, **kwargs)

def _input(prompt=""):
    return _builtin_input(shared._(prompt))

builtins.print = _print
builtins.input = _input

GUARDIAN_DIR = Path(__file__).resolve().parent.parent
MEMORY_DIR = shared.MEMORY_DIR
SKILLS_GLOBAL = Path("/var/guardian/skills-global.json")
TEMPLATE_DIR = GUARDIAN_DIR / "templates"
PROMPT_DIR = GUARDIAN_DIR / "prompts"
MEMORY_SCRIPT = GUARDIAN_DIR / "lib" / "guardian_memory.py"
ABSORB_SCRIPT = GUARDIAN_DIR / "lib" / "guardian_absorb.py"
RAG_SCRIPT = GUARDIAN_DIR / "lib" / "guardian_rag.py"
WEB_SCRIPT = GUARDIAN_DIR / "lib" / "guardian_web.py"
BACKEND_SCRIPT = GUARDIAN_DIR / "lib" / "guardian_backend.py"
DEFAULT_WEB_PORT = 7878
INSTALL_SCRIPT = GUARDIAN_DIR / "install.sh"

HOOKS = ["pre-change", "post-change", "pre-deploy", "post-deploy"]
STACK_COMMANDS = ["build", "dev", "test", "lint", "typecheck", "deploy", "logs"]

# ── helpers ─────────────────────────────────────────────────────

def _ts():
    return shared.ts()

def _slugify(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')

def _find_slug():
    cwd = Path.cwd()
    slug = _slugify(cwd.name)
    if (MEMORY_DIR / slug / "config.yaml").exists():
        return slug
    for parent in cwd.parents:
        s = _slugify(parent.name)
        if (MEMORY_DIR / s / "config.yaml").exists():
            return s
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, cwd=cwd, timeout=5
        )
        if result.returncode == 0:
            remote = result.stdout.strip()
            repo_name = Path(remote).stem
            s = _slugify(repo_name)
            if (MEMORY_DIR / s / "config.yaml").exists():
                return s
    except Exception:
        pass
    return None

def _resolve_slug(args):
    if args and not args[0].startswith("-"):
        slug = _slugify(args[0])
        if not slug:
            print("  El slug especificado no es válido.")
            sys.exit(1)
        return slug, args[1:]
    slug = _find_slug()
    if not slug:
        print("  No se pudo detectar el proyecto. Especificá un slug o ejecutá 'guardian setup'.")
        sys.exit(1)
    return slug, args

def _prompt_yes_no(prompt):
    try:
        result = input(f"{prompt} [s/N] ")
        return result.strip().lower() in ("s", "si", "y", "yes", "")
    except (EOFError, KeyboardInterrupt):
        return False

def warn(msg):
    print(f"  ⚠ {shared._(msg)}")
    return 0

def err(msg):
    print(f"  ❌ {shared._(msg)}")
    return 1

def info(msg):
    print(f"  {msg}")
    return 0

def _sep(title=""):
    if title:
        print(_("\n─── {title} ───", title=title))
    else:
        print("─" * 50)

# ── wrapper functions for shared ────────────────────────────────

def _read_config(slug):
    return shared.read_config(slug)

def _write_config(slug, config):
    shared.write_config(slug, config)

def _read_audit(slug):
    return shared.read_audit(slug)

def _write_audit(slug, entries):
    shared.write_audit(slug, entries)

def _read_memory(slug):
    return shared.read_memory(slug)

def _read_skills_json(slug):
    data = shared.read_skills_json(slug)
    if "scores" not in data:
        data["scores"] = {}
    if "hot" not in data:
        data["hot"] = []
    if "last_match" not in data:
        data["last_match"] = None
    return data

def _write_skills_json(slug, data):
    shared.write_skills_json(slug, data)

def _get_docs_routes(config):
    return shared.get_docs_routes(config)

def _get_docs_available(config):
    return shared.get_docs_available(config)

def _get_docs_last_scan(config):
    return shared.get_docs_last_scan(config)

def _discover_projects():
    return shared.discover_projects()

def _project_exists(slug):
    return shared.project_exists(slug)

def _read_json(path, default=None):
    return shared.read_json(path, default)

def _ts_epoch(ts_str):
    return shared.ts_epoch(ts_str)

def _read_memory_raw(slug):
    entries = shared.read_memory(slug)
    return entries if isinstance(entries, list) else []

# ── audit & route helpers ──────────────────────────────────────

def _run_audit_record(slug, hook, files, status, desc):
    if isinstance(files, str):
        files = [files]
    audit = _read_audit(slug)
    audit.append({
        "ts": _ts(),
        "type": hook,
        "files": files,
        "status": status,
        "desc": desc,
    })
    _write_audit(slug, audit)

def _match_route(path, routes):
    if not routes:
        return None
    path_str = str(path)
    if path_str in routes:
        return routes[path_str]
    best_score = -1
    best_match = None
    for pattern, doc in routes.items():
        if fnmatch.fnmatch(path_str, pattern):
            score = len(pattern)
            if score > best_score:
                best_score = score
                best_match = doc
    return best_match

# ── template inference helpers ─────────────────────────────────

def _infer_frontend_tools(framework):
    tools = {
        "next": {"state": "Zustand", "server_state": "React Query", "api": "fetch/axios"},
        "react": {"state": "Zustand", "server_state": "React Query", "api": "fetch/axios"},
        "vue": {"state": "Pinia", "server_state": "TanStack Query", "api": "axios"},
        "svelte": {"state": "Svelte Stores", "server_state": "TanStack Query", "api": "fetch/axios"},
        "angular": {"state": "NgRx", "server_state": "Angular Services", "api": "HttpClient"},
    }
    return tools.get(framework.lower(), {"state": "—", "server_state": "—", "api": "—"})

def _infer_backend_tools(framework):
    tools = {
        "django": {"validator": "Django Serializers", "orm": "Django ORM"},
        "fastapi": {"validator": "Pydantic", "orm": "SQLAlchemy"},
        "flask": {"validator": "Marshmallow", "orm": "SQLAlchemy"},
        "express": {"validator": "express-validator", "orm": "Prisma/Mongoose"},
        "next": {"validator": "Zod", "orm": "Prisma"},
        "actix": {"validator": "Serde", "orm": "Diesel"},
        "axum": {"validator": "Serde", "orm": "SQLx"},
        "rocket": {"validator": "Serde", "orm": "Diesel"},
    }
    return tools.get(framework.lower(), {"validator": "—", "orm": "—"})

def _infer_forbidden_deps(framework):
    deps = {
        "next": ["lodash", "moment", "jquery"],
        "react": ["lodash", "jquery"],
        "vue": ["lodash", "jquery"],
        "django": ["mock"],
        "fastapi": ["mock"],
    }
    return deps.get(framework.lower(), [])

def _render_template(template_text, variables):
    result = template_text
    for key, value in variables.items():
        placeholder = "{{" + key + "}}"
        if placeholder in result:
            result = result.replace(placeholder, str(value) if value is not None else "")
    return result

# ── cmd_setup ───────────────────────────────────────────────────

def _setup_check_memory(slug):
    """Return True if memory has no recent session entry."""
    try:
        result = subprocess.run(
            [sys.executable, str(MEMORY_SCRIPT), "session", "status", slug],
            capture_output=True, text=True, timeout=15
        )
        output = result.stdout.strip()
        # if output contains session info, memory exists
        return "Sin sesiones" in output or "no hay" in output.lower()
    except Exception:
        return True


def _setup_check_docs(config):
    """Return True if docs are stale or missing."""
    if not config or not config.get("project_root"):
        return True
    root = Path(config["project_root"])
    docs_dir = root / "docs"
    if not docs_dir.exists():
        return True
    last_scan = shared.get_docs_last_scan(config)
    if not last_scan:
        return True
    return shared.is_stale(last_scan, max_age_days=7)


def _setup_check_skills(slug):
    """Return True if skills are stale or missing."""
    global_path = Path("/var/guardian/skills-global.json")
    if not global_path.exists():
        return True
    global_data = shared.read_json(global_path, {})
    last_absorb = global_data.get("last_absorb")
    if not last_absorb:
        return True
    skills_data = shared.read_skills_json(slug)
    last_match = skills_data.get("last_match")
    if not last_match:
        return True
    return shared.ts_epoch(last_absorb) > shared.ts_epoch(last_match)


def cmd_setup(slug=None, auto=False):
    if not auto:
        print("  🛡️  Nexxoria Guardian — Configuración")
        print()

    if not slug:
        cwd = Path.cwd()
        default_slug = _slugify(cwd.name)
        if auto:
            slug = default_slug
        else:
            try:
                slug_input = input(f"  Nombre del proyecto [{default_slug}]: ").strip()
            except (EOFError, KeyboardInterrupt):
                return 1
            slug = slug_input if slug_input else default_slug

    slug = _slugify(slug)
    if not slug:
        return err("El slug no es válido.")

    existing_config = _read_config(slug)
    is_reconfigure = bool(existing_config)

    if is_reconfigure:
        if auto:
            return 0
        created = existing_config.get("created_at", "?")[:10]
        stack = existing_config.get("stack", {})
        if isinstance(stack, str):
            stack = {}
        detected = stack.get("detected", "?")
        print(shared._("setup_already_exists", slug=slug, created=created))
        print(shared._("setup_stack", stack=detected))
        print()
        if not _prompt_yes_no(shared._("setup_reconfigure")):
            return 0

    config = existing_config or {}

    project_root = config.get("project_root", "")
    if not project_root:
        if auto:
            project_root = str(Path.cwd())
        else:
            try:
                root_input = input(f"  Ruta del proyecto [{Path.cwd()}]: ").strip()
            except (EOFError, KeyboardInterrupt):
                return 1
            project_root = root_input if root_input else str(Path.cwd())

    project_root = str(Path(project_root).resolve())

    if not auto:
        print(_("\n  Detectando stack..."))
    detected = _detect_stack(project_root)
    stack_type = detected.get("type", "unknown")
    framework = detected.get("framework", "")
    runtime = detected.get("runtime", "python" if stack_type == "python" else "node")

    if not auto:
        print(_("    Stack detectado: {stack_type} / {framework}", stack_type=stack_type, framework=framework))

    stack_config = config.get("stack", {})
    if isinstance(stack_config, str):
        stack_config = {}
    if not stack_config.get("test"):
        if auto:
            test_cmd = detected.get("test_cmd", "")
        else:
            try:
                test_input = input(f"  Comando de tests [{detected.get('test_cmd', '')}]: ").strip()
            except (EOFError, KeyboardInterrupt):
                return 1
            test_cmd = test_input if test_input else detected.get("test_cmd", "")
    else:
        test_cmd = stack_config["test"]

    if not stack_config.get("lint"):
        if auto:
            lint_cmd = detected.get("lint_cmd", "")
        else:
            try:
                lint_input = input(f"  Comando de lint [{detected.get('lint_cmd', '')}]: ").strip()
            except (EOFError, KeyboardInterrupt):
                return 1
            lint_cmd = lint_input if lint_input else detected.get("lint_cmd", "")
    else:
        lint_cmd = stack_config["lint"]

    if not stack_config.get("build"):
        build_cmd = detected.get("build_cmd", "")
    else:
        build_cmd = stack_config["build"]

    if not stack_config.get("dev"):
        dev_cmd = detected.get("dev_cmd", "")
    else:
        dev_cmd = stack_config["dev"]

    if not stack_config.get("deploy"):
        deploy_cmd = ""
    else:
        deploy_cmd = stack_config["deploy"]

    if not stack_config.get("logs"):
        logs_cmd = ""
    else:
        logs_cmd = stack_config["logs"]

    project_type = config.get("project", {}).get("type", "")
    if not project_type:
        project_type = "webapp"

    config_data = {
        "slug": slug,
        "project_root": project_root,
        "project": {
            "type": project_type,
            "description": config.get("project", {}).get("description", ""),
        },
        "stack": {
            "detected": stack_type,
            "framework": framework,
            "runtime": runtime,
            "test": test_cmd,
            "lint": lint_cmd,
            "build": build_cmd,
            "dev": dev_cmd,
            "deploy": deploy_cmd,
            "logs": logs_cmd,
        },
        "docs": config.get("docs", {}),
        "rules": config.get("rules", []),
        "protected_paths": config.get("protected_paths", []),
        "created_at": config.get("created_at", _ts()),
        "updated_at": _ts(),
    }

    _write_config(slug, config_data)

    if not auto:
        print(_("\n  ✓ Proyecto '{slug}' configurado en {}", MEMORY_DIR / slug / 'config.yaml', slug=slug))

    if _setup_check_memory(slug):
        if auto:
            session_args = [str(MEMORY_SCRIPT), "session", "save", slug, "--with-config"]
            subprocess.run([sys.executable] + session_args, timeout=30)
        elif _prompt_yes_no(shared._("setup_memory_needed")):
            session_args = [str(MEMORY_SCRIPT), "session", "save", slug, "--with-config"]
            subprocess.run([sys.executable] + session_args, timeout=30)
    elif not auto:
        print(shared._("setup_skip_memory"))

    if _setup_check_docs(config_data):
        if auto:
            cmd_docs_scan(slug)
        elif _prompt_yes_no(shared._("setup_docs_needed")):
            cmd_docs_scan(slug)
    elif not auto:
        print(shared._("setup_skip_docs"))

    if _setup_check_skills(slug):
        if auto:
            try:
                subprocess.run([sys.executable, str(ABSORB_SCRIPT), "scan"], timeout=60)
                subprocess.run([sys.executable, str(ABSORB_SCRIPT), "match", slug], timeout=60)
            except Exception:
                pass
        elif _prompt_yes_no(shared._("setup_skills_needed")):
            try:
                subprocess.run([sys.executable, str(ABSORB_SCRIPT), "scan"], timeout=60)
                subprocess.run([sys.executable, str(ABSORB_SCRIPT), "match", slug], timeout=60)
            except Exception as e:
                print(_("  ⚠ Error en scan/match: {e}", e=e))
    elif not auto:
        print(shared._("setup_skip_skills"))

    audit = _read_audit(slug)
    audit.append({"ts": _ts(), "type": "setup", "desc": f"Proyecto '{slug}' configurado", "status": "ok"})
    _write_audit(slug, audit)

    if not auto:
        print(_("\n  ✅ Guardian listo para '{slug}'", slug=slug))
    return 0

def _detect_stack(project_root):
    root = Path(project_root)
    info = {"type": "unknown", "framework": "", "runtime": "python",
            "test_cmd": "", "lint_cmd": "", "build_cmd": "", "dev_cmd": ""}

    pkg = root / "package.json"
    if pkg.exists():
        info["type"] = "node"
        info["runtime"] = "node"
        try:
            data = json.loads(pkg.read_text())
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            for dep in deps:
                dl = dep.lower()
                if "next" in dl:
                    info["framework"] = "next"
                    info["dev_cmd"] = "npm run dev"
                    info["build_cmd"] = "npm run build"
                elif not info["framework"] and "react" in dl:
                    info["framework"] = "react"
                elif not info["framework"] and "vue" in dl:
                    info["framework"] = "vue"
            scripts = data.get("scripts", {})
            if scripts.get("test"):
                info["test_cmd"] = "npm test"
            elif (root / "vitest.config.ts").exists() or (root / "vitest.config.js").exists():
                info["test_cmd"] = "npx vitest run"
            elif (root / "jest.config.ts").exists() or (root / "jest.config.js").exists():
                info["test_cmd"] = "npx jest"
            if scripts.get("lint"):
                info["lint_cmd"] = "npm run lint"
            elif (root / ".eslintrc.js").exists() or (root / ".eslintrc.json").exists():
                info["lint_cmd"] = "npx eslint ."
            if scripts.get("dev"):
                info["dev_cmd"] = "npm run dev"
            if scripts.get("build"):
                info["build_cmd"] = "npm run build"
            if scripts.get("start"):
                info["deploy_cmd"] = "npm start"
        except (json.JSONDecodeError, OSError):
            pass
        return info

    pyproj = root / "pyproject.toml"
    if pyproj.exists():
        info["type"] = "python"
        info["runtime"] = "python"
        content = pyproj.read_text().lower()
        if "django" in content:
            info["framework"] = "django"
            info["test_cmd"] = "python manage.py test"
            info["lint_cmd"] = "ruff check ."
            info["dev_cmd"] = "python manage.py runserver"
        elif "fastapi" in content:
            info["framework"] = "fastapi"
            info["test_cmd"] = "pytest"
            info["lint_cmd"] = "ruff check ."
            info["dev_cmd"] = "uvicorn main:app --reload"
        elif "flask" in content:
            info["framework"] = "flask"
            info["test_cmd"] = "pytest"
            info["lint_cmd"] = "ruff check ."
        if "pytest" in content:
            info["test_cmd"] = "pytest"
        if "ruff" in content:
            info["lint_cmd"] = "ruff check ."
        return info

    req = root / "requirements.txt"
    if req.exists():
        info["type"] = "python"
        info["runtime"] = "python"
        info["test_cmd"] = "python -m pytest"
        info["lint_cmd"] = "ruff check ."
        return info

    cargo = root / "Cargo.toml"
    if cargo.exists():
        info["type"] = "rust"
        info["runtime"] = "rust"
        content = cargo.read_text().lower()
        if "actix" in content:
            info["framework"] = "actix"
        elif "axum" in content:
            info["framework"] = "axum"
        elif "rocket" in content:
            info["framework"] = "rocket"
        info["test_cmd"] = "cargo test"
        info["lint_cmd"] = "cargo clippy"
        info["build_cmd"] = "cargo build"
        info["dev_cmd"] = "cargo run"
        return info

    if (root / "go.mod").exists():
        info["type"] = "go"
        info["runtime"] = "go"
        info["test_cmd"] = "go test ./..."
        info["lint_cmd"] = "golangci-lint run"
        info["build_cmd"] = "go build"
        return info

    if list(root.glob("*.csproj")):
        info["type"] = "csharp"
        info["runtime"] = "dotnet"
        info["test_cmd"] = "dotnet test"
        info["build_cmd"] = "dotnet build"
        return info

    if (root / "composer.json").exists():
        info["type"] = "php"
        info["runtime"] = "php"
        info["test_cmd"] = "php vendor/bin/phpunit"
        info["lint_cmd"] = "php vendor/bin/phpcs"
        return info

    return info

# ── cmd_detect ──────────────────────────────────────────────────

def cmd_detect():
    slug = _find_slug()
    if not slug:
        print("  No se detectó ningún proyecto registrado en este directorio.")
        print("  Ejecutá 'guardian setup' para crear uno nuevo.")
        return 1
    config = _read_config(slug)
    stack = config.get("stack", {})
    if isinstance(stack, str):
        stack = {}
    detected = stack.get("detected", "?")
    framework = stack.get("framework", "?")
    root = config.get("project_root", "?")
    print(_("  Proyecto: {slug}", slug=slug))
    print(_("  Stack: {detected} / {framework}", detected=detected, framework=framework))
    print(_("  Ruta: {root}", root=root))
    mem = _read_memory(slug)
    print(_("  Memoria: {} entrada(s)", len(mem)))
    skills = _read_skills_json(slug)
    print(_("  Skills: {} relevante(s)", len(skills.get('relevant', []))))
    audit = _read_audit(slug)
    print(_("  Auditoría: {} entrada(s)", len(audit)))
    return 0

# ── cmd_status ──────────────────────────────────────────────────

def cmd_status(slug):
    config = _read_config(slug)
    if not config:
        return err(f"Proyecto '{slug}' no encontrado.")

    _sep(_("📊 {slug}", slug=slug))
    stack = config.get("stack", {})
    if isinstance(stack, str):
        stack = {}
    detected = stack.get("detected", "—")
    framework = stack.get("framework", "—")
    root = config.get("project_root", "—")
    print(_("  Stack:       {detected} / {framework}", detected=detected, framework=framework))
    print(_("  Ruta:        {root}", root=root))

    protected = config.get("protected_paths", [])
    if isinstance(protected, list):
        print(_("  Paths protegidos: {}", len(protected)))

    rules = config.get("rules", [])
    if isinstance(rules, list):
        print(_("  Reglas:      {}", len(rules)))

    docs_avail = _get_docs_available(config)
    if docs_avail:
        avail_str = ", ".join(k for k, v in docs_avail.items() if v)
        print(_("  Docs activos: {avail_str}", avail_str=avail_str))
    last_scan = _get_docs_last_scan(config)
    if last_scan:
        print(_("  Último scan docs: {}", last_scan[:19]))

    print()
    _sep("Hook status")
    for h in HOOKS:
        print(_("  {h}", h=h))

    print()
    _sep("Cambios recientes")
    audit = _read_audit(slug)
    recent = [e for e in audit if e.get("type") not in ("setup",)][-5:]
    for e in recent:
        ts = e.get("ts", "")[:19]
        etype = e.get("type", "")
        desc = e.get("desc", e.get("details", ""))
        status = e.get("status", "")
        icon = "✓" if status == "ok" else "✗" if status in ("violation", "blocked") else "•"
        print(_("  {icon} [{ts}] {etype}: {}", desc[:80], icon=icon, ts=ts, etype=etype))

    print()
    mem = _read_memory(slug)
    if mem:
        types = {}
        for e in mem:
            t = e.get("type", "unknown")
            types[t] = types.get(t, 0) + 1
        type_str = ", ".join(f"{k}:{v}" for k, v in sorted(types.items()))
        print(_("  🧠 Memoria: {} entrada(s) [{type_str}]", len(mem), type_str=type_str))
    else:
        print(_("  🧠 Memoria: vacía"))

    skills = _read_skills_json(slug)
    if skills.get("hot"):
        print(_("  🔥 Skills hot: {}", ', '.join(skills['hot'][:5])))
    else:
        print(_("  📦 Skills: {} relevante(s)", len(skills.get('relevant', []))))

    return 0

# ── cmd_check ───────────────────────────────────────────────────

def cmd_check(slug):
    config = _read_config(slug)
    if not config:
        return err(f"Proyecto '{slug}' no encontrado.")

    issues = 0
    _sep(_("🔍 Verificando: {slug}", slug=slug))

    protected = config.get("protected_paths", [])
    if isinstance(protected, list) and protected:
        root = Path(config.get("project_root", "."))
        for p in protected:
            target = root / p
            if target.exists():
                print(_("  ✓ Protegido: {p}", p=p))
            else:
                print(_("  ⚠ No existe: {p}", p=p))
    else:
        print(_("  • Sin paths protegidos"))

    rules = config.get("rules", [])
    if isinstance(rules, list) and rules:
        print(_("  ✓ Reglas: {} definidas", len(rules)))
    else:
        print(_("  • Sin reglas"))

    stack = config.get("stack", {})
    if isinstance(stack, dict):
        framework = stack.get("framework", "")
        if framework:
            forbidden = _infer_forbidden_deps(framework)
            if forbidden:
                print(_("  ✓ Dependencias prohibidas: {}", ', '.join(forbidden)))

    docs_avail = _get_docs_available(config)
    if docs_avail:
        avail_count = sum(1 for v in docs_avail.values() if v)
        stale = False
        last_scan = _get_docs_last_scan(config)
        if last_scan:
            try:
                scan_ts = datetime.strptime(last_scan[:19], "%Y-%m-%dT%H:%M:%S")
                age = (datetime.now() - scan_ts).days
                if age > 7:
                    print(_("  ⚠ Docs desactualizados: {age} días desde último scan", age=age))
                    stale = True
            except ValueError:
                pass
        print(_("  ✓ Docs: {avail_count}/4 disponibles" if not stale else "  ⚠ Docs: {avail_count}/4 (stale)", avail_count=avail_count))

    skills = _read_skills_json(slug)
    if skills.get("hot"):
        print(_("  ✓ Skills cargados: {} hot", len(skills['hot'])))
    elif skills.get("relevant"):
        print(_("  ✓ Skills: {} relevante(s)", len(skills['relevant'])))
    else:
        print(_("  ⚠ Sin skills — ejecutá 'guardian absorb match {slug}'", slug=slug))

    mem = _read_memory(slug)
    if mem:
        expired = 0
        now_ts = int(datetime.now(timezone.utc).timestamp())
        for e in mem:
            age = (now_ts - _ts_epoch(e.get("ts", ""))) // 86400
            if age > e.get("ttl", 7):
                expired += 1
        if expired:
            print(_("  ⚠ {expired}/{} entradas de memoria vencidas", len(mem), expired=expired))

    print()
    if issues == 0:
        print(_("  ✅ Todo en orden para '{slug}'", slug=slug))
    else:
        print(_("  ⚠ {issues} problema(s) encontrado(s)", issues=issues))
    return issues

# ── cmd_report ──────────────────────────────────────────────────

def cmd_report(slug):
    config = _read_config(slug)
    if not config:
        return err(f"Proyecto '{slug}' no encontrado.")

    audit = _read_audit(slug)
    if not audit:
        print(_("  No hay auditoría para '{slug}'.", slug=slug))
        return 0

    _sep(_("📋 Reporte: {slug}", slug=slug))

    total = len(audit)
    violations = sum(1 for e in audit if e.get("status") == "violation")
    blocked = sum(1 for e in audit if e.get("status") == "blocked")
    ok_count = sum(1 for e in audit if e.get("status") == "ok")
    changes = sum(1 for e in audit if e.get("type") in ("change", "pre-change", "post-change"))
    snapshots = sum(1 for e in audit if e.get("type") == "snapshot")
    hooks_run = sum(1 for e in audit if e.get("type") in HOOKS)

    print(_("  Total eventos:  {total}", total=total))
    print(_("  ✓ OK:           {ok_count}", ok_count=ok_count))
    print(_("  ⚠ Violaciones:  {violations}", violations=violations))
    print(_("  ✗ Bloqueos:     {blocked}", blocked=blocked))
    print(_("  Cambios:        {changes}", changes=changes))
    print(_("  Snapshots:      {snapshots}", snapshots=snapshots))
    print(_("  Hooks:          {hooks_run}", hooks_run=hooks_run))

    thirty_days_ago = int(datetime.now(timezone.utc).timestamp()) - 30 * 86400
    recent = [e for e in audit if _ts_epoch(e.get("ts", "")) >= thirty_days_ago]
    if recent:
        compliance = sum(1 for e in recent if e.get("status") == "ok") / len(recent) * 100
        print(_("\n  Tendencia 30d:"))
        print(_("    Eventos:     {}", len(recent)))
        print(_("    Compliance:  {compliance:.0f}%", compliance=compliance))

    file_changes = {}
    for e in audit:
        files = e.get("files", [])
        if isinstance(files, list):
            for f in files:
                file_changes[f] = file_changes.get(f, 0) + 1
        elif isinstance(files, str):
            file_changes[files] = file_changes.get(files, 0) + 1

    if file_changes:
        sorted_files = sorted(file_changes.items(), key=lambda x: -x[1])[:5]
        print(_("\n  Archivos más modificados:"))
        for f, c in sorted_files:
            print(_("    {f:<50} {c}x", f=f, c=c))

    hooks_config = config.get("hooks", {})
    if hooks_config:
        print(_("\n  Hooks configurados: {}", len(hooks_config)))

    print(_("\n  ✅ Reporte generado para '{slug}'", slug=slug))
    return 0

# ── cmd_protect ─────────────────────────────────────────────────

def cmd_protect(path, slug):
    if not path:
        return err("Especificá un path para proteger.")
    config = _read_config(slug)
    protected = config.get("protected_paths", [])
    if not isinstance(protected, list):
        protected = []
    if path in protected:
        return warn(f"'{path}' ya está protegido.")
    protected.append(path)
    config["protected_paths"] = protected
    _write_config(slug, config)

    root = Path(config.get("project_root", "."))
    constraints_file = root / "CONSTRAINTS.md"
    if constraints_file.exists():
        content = constraints_file.read_text(encoding="utf-8", errors="replace")
        new_line = f"- {path}"
        if new_line not in content:
            content += f"\n{new_line}\n"
            constraints_file.write_text(content, encoding="utf-8")

    _run_audit_record(slug, "protect", [path], "ok", f"Path protegido: {path}")
    print(_("  🔒 Path protegido: {path}", path=path))
    print(_("     Config: {}", MEMORY_DIR / slug / 'config.yaml'))
    return 0

# ── cmd_snapshot ────────────────────────────────────────────────

def cmd_snapshot(path, slug):
    if not path:
        return err("Especificá un archivo para hacer snapshot.")
    src = Path(path)
    if not src.exists():
        return err(f"El archivo no existe: {path}")
    ts_str = _ts().replace(":", "-")
    dest = src.parent / f"{src.name}.guardian-snapshot-{ts_str}"
    shutil.copy2(src, dest)
    print(_("  📸 Snapshot: {}", dest.name))
    print(_("     Backup creado en: {dest}", dest=dest))
    audit = _read_audit(slug)
    audit.append({"ts": _ts(), "type": "snapshot", "file": str(dest), "desc": f"Snapshot: {path}", "status": "ok"})
    _write_audit(slug, audit)
    return 0

# ── cmd_diff ────────────────────────────────────────────────────

def cmd_diff(path, slug):
    config = _read_config(slug)
    root = config.get("project_root", ".")

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True, text=True, cwd=root, timeout=5
        )
        has_git = result.returncode == 0
    except Exception:
        has_git = False

    if has_git:
        if path:
            cmd = ["git", "diff", "--", path]
        else:
            cmd = ["git", "diff", "--stat"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=root, timeout=30)
            output = result.stdout.strip()
            if output:
                print(output)
            else:
                print("  No hay cambios sin commit.")
        except subprocess.TimeoutExpired:
            return err("Diff excedió el tiempo de espera.")
    else:
        audit = _read_audit(slug)
        snapshots = [e for e in audit if e.get("type") == "snapshot"]
        if not snapshots:
            print("  No hay git ni snapshots disponibles.")
            return 0
        print(_("  Snapshots disponibles ({}):", len(snapshots)))
        for e in snapshots[-10:]:
            ts = e.get("ts", "")[:19]
            f = e.get("file", e.get("desc", ""))
            print(_("    {ts}  {f}", ts=ts, f=f))
    return 0

# ── cmd_prompt ──────────────────────────────────────────────────

WORKFLOW_STEPS = ["identify", "consult", "analyze", "evaluate", "execute"]

def _read_workflow_state(slug):
    wf = MEMORY_DIR / slug / "workflow-state.json"
    if wf.exists():
        try:
            return json.loads(wf.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"step": None, "last_scope": None, "next_step": "identify", "history": []}

def _write_workflow_state(slug, state):
    wf = MEMORY_DIR / slug / "workflow-state.json"
    wf.parent.mkdir(parents=True, exist_ok=True)
    wf.write_text(json.dumps(state, indent=2, ensure_ascii=False))

def cmd_prompt(slug, cmd_args):
    config = _read_config(slug)
    if not config:
        return err(f"Proyecto '{slug}' no encontrado.")

    if not cmd_args or cmd_args[0] == "status":
        state = _read_workflow_state(slug)
        _sep(_("📋 Workflow: {slug}", slug=slug))
        print(_("  Paso actual:     {}", state.get('step', '—')))
        print(_("  Último scope:    {}", state.get('last_scope', '—')))
        print(_("  Próximo paso:    {}", state.get('next_step', 'identify')))
        if state.get("history"):
            print(_("  Historial:"))
            for h in state["history"][-5:]:
                print(_("    {} @ {} scope={}", h.get('step', '?'), h.get('ts', '?'), h.get('scope', '—')))
        return 0

    step = cmd_args[0]
    force = "--force" in cmd_args
    # filter out flags for further processing
    cmd_args = [a for a in cmd_args if not a.startswith("--") or a == step]

    if step not in WORKFLOW_STEPS:
        return err(f"Paso no válido: '{step}'. Usá: {', '.join(WORKFLOW_STEPS)}")

    # Workflow gate: enforce step ordering
    state = _read_workflow_state(slug)
    last_step = state.get("step")
    if last_step and last_step in WORKFLOW_STEPS and not force:
        last_idx = WORKFLOW_STEPS.index(last_step)
        requested_idx = WORKFLOW_STEPS.index(step)
        if requested_idx > last_idx + 1:
            expected = WORKFLOW_STEPS[last_idx + 1]
            return err(
                f"No se puede saltar de '{last_step}' a '{step}'. "
                f"El siguiente paso debería ser '{expected}'. "
                f"Usá --force para saltar esta verificación."
            )
        if requested_idx < last_idx:
            print(
                f"  ⚠ Atención: estás yendo de '{last_step}' a '{step}' "
                f"(retrocediendo en el workflow)"
            )

    scope = None
    change_type = None
    files = None
    for arg in cmd_args[1:]:
        if arg.startswith("--scope="):
            scope = arg.split("=", 1)[1]
        elif arg.startswith("--type="):
            change_type = arg.split("=", 1)[1]
        elif arg.startswith("--files="):
            files = arg.split("=", 1)[1]

    template_file = PROMPT_DIR / f"{step}.md"
    if not template_file.exists():
        return err(f"Template no encontrado: {template_file}")

    stack = config.get("stack", {})
    if isinstance(stack, str):
        stack = {}
    detected = stack.get("detected", "—")
    framework = stack.get("framework", "—")

    docs_section = ""
    docs_avail = _get_docs_available(config)
    if docs_avail:
        avail = [k for k, v in docs_avail.items() if v]
        if avail:
            docs_section = "Docs disponibles: " + ", ".join(avail)

    memory_section = ""
    mem = _read_memory(slug)
    if mem:
        recent = mem[-3:]
        for e in recent:
            t = e.get("type", "?")
            c = e.get("content", "")[:100]
            memory_section += f"- [{t}] {c}\n"

    constraints_section = ""
    rules = config.get("rules", [])
    if isinstance(rules, list) and rules:
        constraints_section = "Reglas:\n" + "\n".join(f"- {r}" for r in rules[:5])

    variables = {
        "slug": slug,
        "stack": detected,
        "framework": framework,
        "scope": scope or ".",
        "change_type": change_type or "—",
        "files": files or "—",
        "docs_section": docs_section.strip(),
        "memory_section": memory_section.strip(),
        "constraints_section": constraints_section.strip(),
    }

    template_text = template_file.read_text(encoding="utf-8", errors="replace")
    rendered = _render_template(template_text, variables)
    print(rendered)

    state = _read_workflow_state(slug)
    state["step"] = step
    state["last_scope"] = scope or "."
    idx = WORKFLOW_STEPS.index(step)
    state["next_step"] = WORKFLOW_STEPS[idx + 1] if idx + 1 < len(WORKFLOW_STEPS) else None
    if "history" not in state:
        state["history"] = []
    state["history"].append({"step": step, "ts": _ts(), "scope": scope or "."})
    if len(state["history"]) > 20:
        state["history"] = state["history"][-20:]
    _write_workflow_state(slug, state)

    return 0

# ── cmd_rollback ────────────────────────────────────────────────

def cmd_rollback(slug):
    audit = _read_audit(slug)
    changes = [e for e in audit if e.get("type") in ("change", "post-change") and e.get("status") == "ok"]
    if not changes:
        return err("No hay cambios para revertir.")

    last = changes[-1]
    ts = last.get("ts", "")[:19]
    desc = last.get("desc", "Cambio sin descripción")
    files = last.get("files", [])

    _sep("⏪ Revertir último cambio")
    print(_("  ❗ Esta acción es destructiva: los cambios se perderán."))
    print(_("  Fecha: {ts}", ts=ts))
    print(_("  Desc: {desc}", desc=desc))
    if isinstance(files, list) and files:
        print(_("  Archivos:"))
        for f in files[:5]:
            print(_("    - {f}", f=f))
    print()

    try:
        confirm = input("  Escribí 'revertir' para confirmar: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return info("Cancelado.")
    if confirm != "revertir":
        return info("Cancelado.")

    config = _read_config(slug)
    root = config.get("project_root", ".")
    try:
        result = subprocess.run(
            ["git", "checkout", "HEAD", "--"] + (files if isinstance(files, list) else []),
            capture_output=True, text=True, cwd=root, timeout=30
        )
        if result.returncode == 0:
            _run_audit_record(slug, "rollback", files, "ok", f"Revertido: {desc[:60]}")
            print(_("  ✅ Cambio revertido."))
        else:
            if result.stderr:
                return err(result.stderr.strip())
            return err("No se pudo revertir (git checkout falló).")
    except subprocess.TimeoutExpired:
        return err("Revertir excedió el tiempo de espera.")
    except Exception as e:
        return err(f"Error al revertir: {e}")
    return 0

# ── cmd_hooks ──────────────────────────────────────────────────

def cmd_hooks(slug):
    config = _read_config(slug)
    _sep(_("🔌 Hooks: {slug}", slug=slug))

    hooks_config = config.get("hooks", {})
    if isinstance(hooks_config, str):
        hooks_config = {}
    hook_steps = {
        "pre-change": ["snapshot", "scope match", "memory context", "protected check", "delete check"],
        "post-change": ["diff", "tests", "lint", "memory save", "audit write"],
        "pre-deploy": ["build check", "SDD verify"],
        "post-deploy": ["smoke test", "audit write", "memory save"],
    }
    for hook in HOOKS:
        enabled = hooks_config.get(hook, {}).get("enabled", True) if isinstance(hooks_config.get(hook), dict) else True
        status = "✅" if enabled else "⏸"
        steps = hook_steps.get(hook, [])
        print(_("  {status} {hook}:", status=status, hook=hook))
        for step in steps:
            print(_("       → {step}", step=step))

    audit = _read_audit(slug)
    hook_events = [e for e in audit if e.get("type") in HOOKS]
    if hook_events:
        print()
        last_hooks = hook_events[-5:]
        for e in last_hooks:
            ts = e.get("ts", "")[:19]
            etype = e.get("type", "")
            status = e.get("status", "")
            desc = e.get("desc", "")[:60]
            icon = "✓" if status == "ok" else "✗"
            print(_("  {icon} [{ts}] {etype}: {desc}", icon=icon, ts=ts, etype=etype, desc=desc))

    return 0

# ── cmd_pre_change ──────────────────────────────────────────────

def cmd_pre_change(slug, files=None, auto=False):
    config = _read_config(slug)
    if not config:
        return err(f"Proyecto '{slug}' no encontrado.")

    _sep(_("🔄 Pre-change: {slug}", slug=slug))
    root = Path(config.get("project_root", "."))

    if files:
        if isinstance(files, str):
            files = [files]
    else:
        files = []

    if files:
        snapshots_taken = 0
        for f in files:
            target = root / f
            if target.exists():
                content_hash = hashlib.sha256(target.read_bytes()).hexdigest()
                existing = sorted(target.parent.glob(f"{target.name}.guardian-snapshot-*"))
                already_backed_up = any(
                    shared.hash_file(snap) == content_hash for snap in existing
                )
                if already_backed_up:
                    print(shared._("snapshot_identical", file=f))
                    continue
                ts_str = _ts().replace(":", "-")
                dest = target.parent / f"{target.name}.guardian-snapshot-{ts_str}"
                shutil.copy2(target, dest)
                snapshots_taken += 1
                print(_("  📸 Snapshot: {}", dest.name))
            else:
                print(_("  ⚠ No existe: {f}", f=f))

    protected = config.get("protected_paths", [])
    if isinstance(protected, list) and protected:
        for p in protected:
            target = root / p
            if target.exists():
                print(_("  🔒 Path protegido: {p}", p=p))
                if not auto and not _prompt_yes_no(f"  ¿Modificar '{p}' de todas formas?"):
                    _run_audit_record(slug, "pre-change", files or [p], "blocked", f"Path protegido: {p}")
                    return err(f"Operación bloqueada: '{p}' está protegido.")

    _run_audit_record(slug, "pre-change", files or [], "ok", "Pre-change completado")
    print(_("  ✅ Pre-change completado"))
    return 0

# ── cmd_post_change ─────────────────────────────────────────────

def cmd_post_change(slug, files=None, auto=False, skip_tests=False, skip_lint=False):
    config = _read_config(slug)
    if not config:
        return err(f"Proyecto '{slug}' no encontrado.")

    _sep(_("🔄 Post-change: {slug}", slug=slug))
    issues = 0
    cwd = Path(config.get("project_root", "."))

    if not skip_tests:
        test_cmd = config.get("stack", {}).get("test", "") if isinstance(config.get("stack"), dict) else ""
        if test_cmd:
            print(_("  🔬 Ejecutando tests: {test_cmd}", test_cmd=test_cmd))
            try:
                result = subprocess.run(
                    shlex.split(test_cmd), capture_output=True, text=True, timeout=120, cwd=cwd
                )
                if result.returncode == 0:
                    print(_("  ✅ Tests pasaron"))
                else:
                    print(_("  ❌ Tests fallaron (código: {})", result.returncode))
                    if result.stdout:
                        for line in result.stdout.strip().split("\n")[-5:]:
                            print(_("     {line}", line=line))
                    if result.stderr:
                        for line in result.stderr.strip().split("\n")[-5:]:
                            print(_("     {line}", line=line))
                    issues += 1
            except subprocess.TimeoutExpired:
                print(_("  ⚠ Tests excedieron tiempo límite"))
                issues += 1
            except FileNotFoundError:
                print(_("  ⚠ Comando no encontrado: {test_cmd}", test_cmd=test_cmd))
        else:
            print(_("  • Sin comando de tests configurado"))
    else:
        print(_("  • Tests omitidos"))

    if not skip_lint:
        lint_cmd = config.get("stack", {}).get("lint", "") if isinstance(config.get("stack"), dict) else ""
        if lint_cmd:
            print(_("  🔍 Ejecutando lint: {lint_cmd}", lint_cmd=lint_cmd))
            try:
                result = subprocess.run(
                    shlex.split(lint_cmd), capture_output=True, text=True, timeout=60, cwd=cwd
                )
                if result.returncode == 0:
                    print(_("  ✅ Lint pasó"))
                else:
                    print(_("  ⚠ Lint encontró problemas (código: {})", result.returncode))
                    if result.stdout:
                        for line in result.stdout.strip().split("\n")[:10]:
                            print(_("     {line}", line=line))
                    issues += 1
            except subprocess.TimeoutExpired:
                print(_("  ⚠ Lint excedió tiempo límite"))
            except FileNotFoundError:
                print(_("  ⚠ Comando no encontrado: {lint_cmd}", lint_cmd=lint_cmd))
        else:
            print(_("  • Sin comando de lint configurado"))
    else:
        print(_("  • Lint omitido"))

    content = f"Post-change: {', '.join(files) if files else 'cambios'} | issues: {issues}"
    try:
        mem_args = [sys.executable, str(MEMORY_SCRIPT), "save", slug, "analysis", content]
        subprocess.run(mem_args, capture_output=True, timeout=10)
        mem_args2 = [sys.executable, str(MEMORY_SCRIPT), "save", slug, "decision", f"Cambio aplicado: {content[:80]}"]
        subprocess.run(mem_args2, capture_output=True, timeout=10)
    except Exception:
        pass

    _run_audit_record(slug, "post-change", files or [], "ok" if issues == 0 else "violation",
                      f"Post-change: {issues} issue(s)")

    if issues == 0:
        print(_("\n  ✅ Post-change completado sin issues"))
    else:
        print(_("\n  ⚠ Post-change completado con {issues} issue(s)", issues=issues))
    return issues

# ── cmd_pre_deploy ─────────────────────────────────────────────

def cmd_pre_deploy(slug, auto=False):
    config = _read_config(slug)
    if not config:
        return err(f"Proyecto '{slug}' no encontrado.")

    _sep(_("🚀 Pre-deploy: {slug}", slug=slug))
    issues = 0
    cwd = Path(config.get("project_root", "."))

    build_cmd = config.get("stack", {}).get("build", "") if isinstance(config.get("stack"), dict) else ""
    if build_cmd:
        print(_("  🔨 Build: {build_cmd}", build_cmd=build_cmd))
        try:
            result = subprocess.run(
                shlex.split(build_cmd), capture_output=True, text=True, timeout=180, cwd=cwd
            )
            if result.returncode == 0:
                print(_("  ✅ Build exitoso"))
            else:
                print(_("  ❌ Build falló (código: {})", result.returncode))
                if result.stdout:
                    for line in result.stdout.strip().split("\n")[-5:]:
                        print(_("     {line}", line=line))
                if result.stderr:
                    for line in result.stderr.strip().split("\n")[-5:]:
                        print(_("     {line}", line=line))
                issues += 1
        except subprocess.TimeoutExpired:
            print(_("  ❌ Build excedió tiempo límite"))
            issues += 1
        except FileNotFoundError:
            print(_("  ❌ Comando no encontrado: {build_cmd}", build_cmd=build_cmd))
            issues += 1
    else:
        print(_("  • Sin comando de build configurado"))

    _run_audit_record(slug, "pre-deploy", [], "ok" if issues == 0 else "violation",
                      f"Pre-deploy: {issues} issue(s)")

    if issues == 0:
        print(_("\n  ✅ Pre-deploy: listo para desplegar"))
    else:
        print(_("\n  ❌ Pre-deploy: {issues} issue(s) - corregí antes de desplegar", issues=issues))
    return issues

# ── cmd_post_deploy ─────────────────────────────────────────────

def cmd_post_deploy(slug, auto=False):
    config = _read_config(slug)
    if not config:
        return err(f"Proyecto '{slug}' no encontrado.")

    _sep(_("✅ Post-deploy: {slug}", slug=slug))
    issues = 0
    cwd = Path(config.get("project_root", "."))

    deploy_cmd = config.get("stack", {}).get("deploy", "") if isinstance(config.get("stack"), dict) else ""
    if not deploy_cmd:
        deploy_cmd = config.get("stack", {}).get("start", "")

    if deploy_cmd:
        print(_("  🌐 Smoke test: {deploy_cmd}", deploy_cmd=deploy_cmd))
        try:
            result = subprocess.run(
                shlex.split(deploy_cmd), capture_output=True, text=True, timeout=30, cwd=cwd
            )
            if result.returncode == 0:
                print(_("  ✅ Smoke test pasó"))
            else:
                print(_("  ⚠ Smoke test falló (código: {})", result.returncode))
                issues += 1
        except subprocess.TimeoutExpired:
            print(_("  ⚠ Smoke test excedió tiempo límite"))
        except FileNotFoundError:
            print(_("  ⚠ Comando no encontrado: {deploy_cmd}", deploy_cmd=deploy_cmd))
    else:
        if not auto:
            url = config.get("url", "")
            if url:
                try:
                    import urllib.request as _ur
                    req = _ur.Request(url, method="GET")
                    resp = _ur.urlopen(req, timeout=10)
                    if resp.status == 200:
                        print(_("  ✅ Smoke test: {url} → {}", resp.status, url=url))
                    else:
                        print(_("  ⚠ Smoke test: {url} → {}", resp.status, url=url))
                        issues += 1
                except Exception as e:
                    print(_("  ⚠ Smoke test falló: {e}", e=e))
                    issues += 1
            else:
                print(_("  • Sin URL ni comando de deploy configurados"))

    content = f"Deploy completado: {slug}"
    try:
        mem_args = [sys.executable, str(MEMORY_SCRIPT), "save", slug, "analysis", content]
        subprocess.run(mem_args, capture_output=True, timeout=10)
    except Exception:
        pass

    _run_audit_record(slug, "post-deploy", [], "ok" if issues == 0 else "violation",
                      f"Post-deploy completado con {issues} issue(s)")

    if issues == 0:
        print(_("\n  ✅ Post-deploy completado"))
    else:
        print(_("\n  ⚠ Post-deploy completado con {issues} issue(s)", issues=issues))
    return issues

# ── cmd_docs_scan ──────────────────────────────────────────────

DOC_TEMPLATES = {
    "AGENTS.md": "AGENTS.md.template",
    "BACKEND.md": "BACKEND.md.template",
    "FRONTEND.md": "FRONTEND.md.template",
    "FEATURES.md": "FEATURES.md.template",
    "UI.md": "UI.md.template",
    "CONSTRAINTS.md": "CONSTRAINTS.md.template",
}

def _render_and_maybe_write(content, dest, generated):
    """Write content to dest only if different from current file content."""
    new_hash = hashlib.sha256(content.encode()).hexdigest()
    existing_hash = shared.hash_file(dest)
    if existing_hash == new_hash:
        print(shared._("docs_unchanged", name=dest.name))
        return
    dest.write_text(content, encoding="utf-8")
    print(shared._("docs_generated", name=dest.name))
    generated.append(str(dest.relative_to(dest.parents[1]) if len(dest.parents) > 1 else dest.name))


def cmd_docs_scan(slug):
    config = _read_config(slug)
    if not config:
        return err(f"Proyecto '{slug}' no encontrado.")

    root = Path(config.get("project_root", "."))
    docs_dir = root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    stack = config.get("stack", {})
    if isinstance(stack, str):
        stack = {}
    detected = stack.get("detected", "python")
    framework = stack.get("framework", "")
    runtime = stack.get("runtime", "python")
    test_cmd = stack.get("test", "")
    lint_cmd = stack.get("lint", "")
    build_cmd = stack.get("build", "")
    dev_cmd = stack.get("dev", "")

    docs_avail = _get_docs_available(config)
    if not docs_avail:
        docs_avail = {"frontend": False, "backend": False, "ui": False, "features": False}

    frontend_template = docs_avail.get("frontend", False)
    backend_template = docs_avail.get("backend", False)
    ui_template = docs_avail.get("ui", False)
    features_template = docs_avail.get("features", False)

    generated = []

    fe_tools = _infer_frontend_tools(framework)
    be_tools = _infer_backend_tools(framework)
    forbidden_deps = _infer_forbidden_deps(framework)

    protected = config.get("protected_paths", [])
    if not isinstance(protected, list):
        protected = []
    rules = config.get("rules", [])
    if not isinstance(rules, list):
        rules = []

    for doc_name, template_name in DOC_TEMPLATES.items():
        if doc_name == "AGENTS.md":
            template_path = TEMPLATE_DIR / template_name
            if template_path.exists():
                variables = {
                    "slug": slug,
                    "project_type": config.get("project", {}).get("type", "webapp"),
                    "runtime": runtime,
                    "framework": framework if framework else "—",
                    "db": config.get("project", {}).get("database", "—"),
                    "dev_cmd": dev_cmd or "—",
                    "test_cmd": test_cmd or "—",
                    "lint_cmd": lint_cmd or "—",
                    "build_cmd": build_cmd or "—",
                    "docs_list": "",
                }
                docs_list = []
                for d in ["BACKEND.md", "FRONTEND.md", "FEATURES.md", "UI.md", "CONSTRAINTS.md"]:
                    if (docs_dir / d).exists() or d == "CONSTRAINTS.md":
                        docs_list.append(f"- [{d}](docs/{d})")
                variables["docs_list"] = "\n".join(docs_list)
                content = _render_template(template_path.read_text(encoding="utf-8", errors="replace"), variables)
                dest = root / doc_name
                _render_and_maybe_write(content, dest, generated)

        elif doc_name == "CONSTRAINTS.md":
            template_path = TEMPLATE_DIR / template_name
            if template_path.exists():
                variables = {
                    "scope_paths": "\n".join(f"- {r}" for r in rules[:10]) if rules else "- (ninguno)",
                    "protected_paths": "\n".join(f"- {p}" for p in protected) if protected else "- (ninguno)",
                    "forbidden_deps": "\n".join(f"- {d}" for d in forbidden_deps) if forbidden_deps else "- (ninguna)",
                    "forbidden_patterns": "",
                    "tech_debt_items": "- (ninguno)",
                }
                content = _render_template(template_path.read_text(encoding="utf-8", errors="replace"), variables)
                dest = docs_dir / doc_name
                _render_and_maybe_write(content, dest, generated)

        elif doc_name == "BACKEND.md" and backend_template:
            template_path = TEMPLATE_DIR / template_name
            if template_path.exists():
                variables = {
                    "runtime": runtime,
                    "framework": framework if framework else "—",
                    "db": config.get("project", {}).get("database", "PostgreSQL"),
                    "validator": be_tools.get("validator", "—"),
                    "orm": be_tools.get("orm", "—"),
                }
                content = _render_template(template_path.read_text(encoding="utf-8", errors="replace"), variables)
                dest = docs_dir / doc_name
                _render_and_maybe_write(content, dest, generated)

        elif doc_name == "FRONTEND.md" and frontend_template:
            template_path = TEMPLATE_DIR / template_name
            if template_path.exists():
                variables = {
                    "runtime": runtime,
                    "framework": framework if framework else "—",
                    "state_library": fe_tools.get("state", "—"),
                    "server_state_library": fe_tools.get("server_state", "—"),
                    "api_client": fe_tools.get("api", "—"),
                }
                content = _render_template(template_path.read_text(encoding="utf-8", errors="replace"), variables)
                dest = docs_dir / doc_name
                _render_and_maybe_write(content, dest, generated)

        elif doc_name == "FEATURES.md" and features_template:
            template_path = TEMPLATE_DIR / template_name
            if template_path.exists():
                variables = {
                    "framework": framework if framework else "—",
                }
                content = _render_template(template_path.read_text(encoding="utf-8", errors="replace"), variables)
                dest = docs_dir / doc_name
                _render_and_maybe_write(content, dest, generated)

        elif doc_name == "UI.md" and ui_template:
            template_path = TEMPLATE_DIR / template_name
            if template_path.exists():
                variables = {
                    "framework": framework if framework else "—",
                }
                content = _render_template(template_path.read_text(encoding="utf-8", errors="replace"), variables)
                dest = docs_dir / doc_name
                _render_and_maybe_write(content, dest, generated)

    docs_config = config.get("docs", {})
    if not isinstance(docs_config, dict):
        docs_config = {}
    docs_config["last_scan"] = _ts()
    docs_config["frontend"] = frontend_template
    docs_config["backend"] = backend_template
    docs_config["ui"] = ui_template
    docs_config["features"] = features_template
    config["docs"] = docs_config
    _write_config(slug, config)

    if generated:
        print(_("  📄 Documentos generados ({}):", len(generated)))
        for g in generated:
            print(_("     ✓ {g}", g=g))
    else:
        print(shared._("docs_up_to_date"))

    _run_audit_record(slug, "docs_scan", generated, "ok", f"Docs scan: {len(generated)} archivo(s)")
    try:
        subprocess.run([sys.executable, str(RAG_SCRIPT), "index", "--slug", slug, "--force"], capture_output=True, text=True, timeout=60)
    except Exception:
        pass
    return 0

# ── cmd_docs_route ─────────────────────────────────────────────

def cmd_docs_route(path, slug):
    if not path:
        return err("Especificá un path para ruteo.")

    config = _read_config(slug)
    if not config:
        return err(f"Proyecto '{slug}' no encontrado.")

    routes = _get_docs_routes(config)
    if not routes:
        print(_("  No hay rutas de docs configuradas. Ejecutá 'guardian docs scan {slug}'.", slug=slug))
        return 0

    _sep(_("🗺️  Ruteo de docs: {slug}", slug=slug))

    match = _match_route(path, routes)
    if match:
        root = Path(config.get("project_root", "."))
        doc_path = root / match if isinstance(match, str) else match
        doc_file = Path(str(doc_path))
        exists = doc_file.exists()
        status = "✓" if exists else "✗"
        print(_("  Path:        {path}", path=path))
        print(_("  Match:       {match}", match=match))
        print(_("  Archivo:     {doc_file}", doc_file=doc_file))
        print(_("  Estado:      {status} {}", 'existe' if exists else 'no encontrado', status=status))
    else:
        print(_("  Path:        {path}", path=path))
        print(_("  Match:       (ninguno)"))

    print(_("\n  Rutas configuradas ({}):", len(routes)))
    for pattern, doc in sorted(routes.items()):
        active = "← match" if match and pattern in [k for k, v in routes.items() if v == match] else ""
        print(_("    {pattern:<40} → {doc:<20} {active}", pattern=pattern, doc=doc, active=active))

    return 0

# ── cmd_context ─────────────────────────────────────────────────

def _read_context_state(slug):
    cs = MEMORY_DIR / slug / "context-state.json"
    if cs.exists():
        try:
            return json.loads(cs.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"last_query": None, "last_output_hash": None, "queries": []}

def _write_context_state(slug, state):
    cs = MEMORY_DIR / slug / "context-state.json"
    cs.parent.mkdir(parents=True, exist_ok=True)
    cs.write_text(json.dumps(state, indent=2, ensure_ascii=False))

def cmd_context(slug, cmd_args):
    config = _read_config(slug)
    if not config:
        return err(f"Proyecto '{slug}' no encontrado.")

    mode = "normal"
    scope_filter = None
    since_ts = None
    json_output = False
    rag_query = None

    i = 0
    while i < len(cmd_args):
        arg = cmd_args[i]
        if arg == "--brief":
            mode = "brief"
        elif arg == "--check":
            mode = "check"
        elif arg == "--full":
            mode = "full"
        elif arg == "--json":
            json_output = True
        elif arg == "--since-last":
            state = _read_context_state(slug)
            since_ts = state.get("last_query")
        elif arg.startswith("--since="):
            since_ts = arg.split("=", 1)[1]
        elif arg.startswith("--scope="):
            scope_filter = arg.split("=", 1)[1]
        elif arg == "--rag":
            if i + 1 < len(cmd_args):
                rag_query = cmd_args[i + 1]
                i += 1
        i += 1

    stack = config.get("stack", {})
    if isinstance(stack, str):
        stack = {}
    detected = stack.get("detected", "—")
    framework = stack.get("framework", "—")
    root = config.get("project_root", ".")

    if json_output:
        ctx = {
            "slug": slug,
            "project_root": root,
            "stack": detected,
            "framework": framework,
            "mode": mode,
        }

        if mode in ("normal", "full"):
            docs_avail = _get_docs_available(config)
            ctx["docs"] = {k: v for k, v in docs_avail.items()}
            routes = _get_docs_routes(config)
            if routes:
                ctx["doc_routes"] = {k: v for k, v in list(routes.items())[:10]}

            mem = _read_memory(slug)
            if mem:
                now_ts = int(datetime.now(timezone.utc).timestamp())
                valid = []
                for e in mem:
                    age = (now_ts - _ts_epoch(e.get("ts", ""))) // 86400
                    if age <= e.get("ttl", 7):
                        valid.append(e)
                ctx["memory_count"] = len(valid)
                ctx["memory"] = [{"type": e.get("type"), "content": e.get("content", "")[:120],
                                  "scope": e.get("scope", ""), "ts": e.get("ts", "")[:19]}
                                 for e in valid[:10]]

            skills = _read_skills_json(slug)
            if skills.get("hot"):
                ctx["hot_skills"] = skills["hot"]
            if skills.get("relevant"):
                ctx["relevant_skills_count"] = len(skills["relevant"])

            protected = config.get("protected_paths", [])
            if isinstance(protected, list) and protected:
                ctx["protected_paths"] = protected

        if mode in ("check", "full"):
            rules = config.get("rules", [])
            if isinstance(rules, list) and rules:
                ctx["rules"] = rules[:10]

        if mode == "full":
            audit = _read_audit(slug)
            ctx["audit_count"] = len(audit)
            ctx["recent_audit"] = [{"ts": e.get("ts", "")[:19], "type": e.get("type", ""),
                                    "status": e.get("status", ""), "desc": (e.get("desc") or "")[:80]}
                                   for e in audit[-5:]]

        if rag_query:
            try:
                rag_args = [rag_query, "--slug", slug, "--json", "--top-k", "5"]
                rag_out = subprocess.run(
                    [sys.executable, str(RAG_SCRIPT)] + rag_args,
                    capture_output=True, text=True, timeout=15
                )
                if rag_out.returncode == 0 and rag_out.stdout.strip():
                    rag_data = json.loads(rag_out.stdout)
                    ctx["rag_query"] = rag_query
                    ctx["rag_results"] = rag_data.get("results", [])
                    ctx["rag_total_chunks"] = rag_data.get("total_chunks", 0)
                else:
                    ctx["rag_error"] = rag_out.stderr.strip() or "RAG subprocess failed"
            except Exception as e:
                ctx["rag_error"] = str(e)

        print(json.dumps(ctx, indent=2, ensure_ascii=False))
        _write_context_state(slug, {"last_query": _ts(), "last_output_hash": hashlib.md5(json.dumps(ctx).encode()).hexdigest()[:16]})
        return 0

    if since_ts:
        audit = _read_audit(slug)
        changes_since = [e for e in audit if e.get("ts", "") > since_ts]
        if not changes_since:
            print("  No hay cambios desde la última consulta.")
            print("  (contexto omitido para evitar repetición)")
            return 0

    _sep(_("📌 Contexto: {slug}", slug=slug))

    if mode == "check":
        rules = config.get("rules", [])
        if isinstance(rules, list) and rules:
            print(_("  Reglas activas ({}):", len(rules)))
            for r in rules[:10]:
                print(_("    • {r}", r=r))
        protected = config.get("protected_paths", [])
        if isinstance(protected, list) and protected:
            print(_("  Paths protegidos ({}):", len(protected)))
            for p in protected:
                print(_("    🔒 {p}", p=p))
        return 0

    print(_("  Proyecto:    {slug}", slug=slug))
    print(_("  Stack:       {detected} / {framework}", detected=detected, framework=framework))
    print(_("  Ruta:        {root}", root=root))

    if mode in ("normal", "full"):
        docs_avail = _get_docs_available(config)
        if docs_avail:
            avail = [k for k, v in docs_avail.items() if v]
            if avail:
                print(_("  Docs:        {}", ', '.join(avail)))

        routes = _get_docs_routes(config)
        if routes and scope_filter:
            matched = _match_route(scope_filter, routes)
            if matched:
                print(_("  Doc scope:   {scope_filter} → {matched}", scope_filter=scope_filter, matched=matched))

        mem = _read_memory(slug)
        if mem:
            now_ts = int(datetime.now(timezone.utc).timestamp())
            if scope_filter:
                scope_q = scope_filter.lower()
                relevant = []
                scope_words = scope_q.replace("/", " ").replace("-", " ").split()
                for e in mem:
                    age = (now_ts - _ts_epoch(e.get("ts", ""))) // 86400
                    if age > e.get("ttl", 7):
                        continue
                    content = e.get("content", "").lower()
                    file = e.get("file", "").lower()
                    scope = e.get("scope", "").lower()
                    for w in scope_words:
                        if w and w in content or w in file or w in scope:
                            relevant.append(e)
                            break
                show_mem = relevant[:6]
            else:
                scored = []
                for e in mem:
                    age = (now_ts - _ts_epoch(e.get("ts", ""))) // 86400
                    if age > e.get("ttl", 7):
                        continue
                    score = e.get("hits", 0) + (3 if e.get("type") == "landmark" else 0)
                    recency = max(0, 2 - age // 24)
                    score += recency
                    scored.append((score, e))
                scored.sort(key=lambda x: -x[0])
                show_mem = [e for _, e in scored[:6]]

            if show_mem:
                PREFIXES = {"landmark": "📍", "decision": "🧠", "pattern": "🔁", "note": "📝", "analysis": "📊"}
                print(_("\n  Memoria relevante ({}):", len(show_mem)))
                for e in show_mem:
                    prefix = PREFIXES.get(e.get("type", ""), "•")
                    content = e.get("content", "")[:120]
                    print(_("    {prefix} {content}", prefix=prefix, content=content))

        skills = _read_skills_json(slug)
        if skills.get("hot"):
            print(_("\n  🔥 Skills: {}", ', '.join(skills['hot'][:5])))

        if mode == "full":
            audit = _read_audit(slug)
            recent = audit[-5:] if audit else []
            if recent:
                print(_("\n  Últimos cambios:"))
                for e in recent:
                    ts = e.get("ts", "")[:19]
                    etype = e.get("type", "")
                    desc = (e.get("desc") or "")[:80]
                    print(_("    [{ts}] {etype}: {desc}", ts=ts, etype=etype, desc=desc))

    _write_context_state(slug, {"last_query": _ts(), "last_output_hash": "dummy"})
    return 0


# ── cmd_mode ───────────────────────────────────────────────────

def cmd_mode(slug, cmd_args):
    config = _read_config(slug)
    if not config:
        return err(f"Proyecto '{slug}' no encontrado.")

    mode_state = shared.read_mode_state(slug)
    if not cmd_args or cmd_args[0] == "status":
        _sep(_("🧠 Modo: {slug}", slug=slug))
        print(_("  Modo actual:   {mode}", mode=mode_state.get("mode", shared.DEFAULT_MODE)))
        print(_("  Actualizado:   {updated}", updated=mode_state.get("updated", "—")))
        history = mode_state.get("history", [])
        if history:
            print(_("  Historial:"))
            for entry in history[-5:]:
                print(_("    {ts}  {mode}  {reason}", ts=entry.get("ts", "—")[:19], mode=entry.get("mode", "—"), reason=entry.get("reason", "")))
        return 0

    mode = cmd_args[0].strip().lower()
    if mode not in ("plan", "build"):
        return err("Modo no válido. Usá: plan, build, status")

    reason = " ".join(cmd_args[1:]).strip()
    state = shared.append_mode_history(slug, mode, reason)
    print(_("  ✅ Modo actualizado a {mode}", mode=state.get("mode", mode)))
    return 0


# ── cmd_backend ────────────────────────────────────────────────

def cmd_backend(cmd_args):
    if not cmd_args or cmd_args[0] == "status":
        result = subprocess.run([sys.executable, str(BACKEND_SCRIPT), "status"], capture_output=True, text=True)
        if result.stdout.strip():
            print(result.stdout.strip())
        elif result.stderr.strip():
            print(result.stderr.strip())
        return result.returncode

    sub = cmd_args[0]
    if sub not in ("start", "stop", "restart", "serve"):
        return err("Uso: guardian backend <start|stop|restart|status>")

    if sub == "restart":
        subprocess.run([sys.executable, str(BACKEND_SCRIPT), "stop"], capture_output=True, text=True)
        result = subprocess.run([sys.executable, str(BACKEND_SCRIPT), "start"], capture_output=True, text=True)
    else:
        result = subprocess.run([sys.executable, str(BACKEND_SCRIPT), sub], capture_output=True, text=True)

    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())
    return result.returncode


# ── cmd_knowledge ──────────────────────────────────────────────

def cmd_knowledge(slug, cmd_args):
    config = _read_config(slug)
    if not config:
        return err(f"Proyecto '{slug}' no encontrado.")

    index = shared.read_knowledge_index(slug)
    tomes_dir = shared.MEMORY_DIR / slug / "knowledge" / "tomes"


# ── cmd_conciencia ─────────────────────────────────────────────

def cmd_conciencia(slug, cmd_args):
    config = _read_config(slug)
    if not config:
        return err(f"Proyecto '{slug}' no encontrado.")

    sub = cmd_args[0] if cmd_args else "status"

    if sub == "status":
        state = _read_state_json(slug, "conciencia-state.json")
        thresholds = _read_state_json(slug, "conciencia-thresholds.json")
        _sep(_("🧠 Conciencia: {slug}", slug=slug))
        print(_("  Última acción:    {action}", action=state.get("last_action", "—")))
        print(_("  Última confianza: {confidence}", confidence=state.get("last_confidence", 0.0)))
        print(_("  Ciclos totales:   {n}", n=len(state.get("cycles", []))))
        print(_("  Umbral assume:    {t}", t=thresholds.get("assume", 0.8)))
        print(_("  Umbral ask_little: {t}", t=thresholds.get("ask_little_floor", 0.5)))
        print(_("  Umbral ask_much:  {t}", t=thresholds.get("ask_much_floor", 0.2)))
        return 0

    if sub == "history":
        state = _read_state_json(slug, "conciencia-state.json")
        cycles = state.get("cycles", [])
        if not cycles:
            print("  No hay ciclos todavía.")
            return 0
        _sep(_("📜 Historial de conciencia: {slug}", slug=slug))
        for c in cycles[-10:]:
            print(_("  {ts}  {action:12}  conf={confidence:.2f}  {question}", **c))
        return 0

    if sub == "cycle":
        question = " ".join(cmd_args[1:]).strip()
        return _conciencia_cycle(slug, question)

    if sub == "meta":
        return _conciencia_meta(slug)

    return err("Uso: guardian conciencia <status|history|cycle [question]|meta>")


def _read_state_json(slug, name):
    path = shared.MEMORY_DIR / slug / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _conciencia_cycle(slug, question=""):
    """N1: ejecutar un ciclo de conciencia via backend."""
    backend = subprocess.run(
        [sys.executable, str(BACKEND_SCRIPT), "serve", "--port", "9787"],
        capture_output=True, text=True, timeout=5,
    )
    # if backend isn't running, execute cycle locally
    try:
        import urllib.request
        import urllib.parse
        data = json.dumps({"slug": slug, "question": question, "mode": shared.read_mode_state(slug).get("mode", shared.DEFAULT_MODE)}).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:9787/conciencia/cycle",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read())
        _sep(_("🧠 Ciclo de conciencia: {slug}", slug=slug))
        print(_("  Acción:      {action}", action=result.get("action", "—")))
        print(_("  Confianza:   {confidence}", confidence=result.get("confidence", 0.0)))
        if result.get("meta"):
            print(_("  ⚡ Meta-evolución: {reasons}", reasons="; ".join(result["meta"].get("reasons", []))))
        return 0
    except Exception:
        # fallback: local computation
        pass
    # local fallback
    conf = 0.5
    action = "ask_little"
    print(_("  ⚠ No se pudo contactar el backend, usando fallback local."))
    print(_("  Acción: {action} (confianza {confidence})", action=action, confidence=conf))
    return 0


def _conciencia_meta(slug):
    """N2: disparar meta-evolución."""
    try:
        import urllib.request
        data = json.dumps({"slug": slug}).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:9787/conciencia/meta",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read())
        meta = result.get("meta")
        if meta is None:
            print("  Meta-evolución: no se requieren ajustes todavía (necesita ≥5 ciclos).")
            return 0
        _sep(_("⚡ Meta-evolución: {slug}", slug=slug))
        for r in meta.get("reasons", []):
            print(_("  • {r}", r=r))
        print(_("  Ajustes: {adjustments}", adjustments=meta.get("adjustments", {})))
        return 0
    except Exception as e:
        return err(f"Error al conectar con backend: {e}")


# ── cmd_genome ─────────────────────────────────────────────────

def cmd_genome(slug, cmd_args):
    sub = cmd_args[0] if cmd_args else "status"
    if sub == "status":
        genome = guardian_genome.load_genome()
        identity = genome.get("identity", {})
        _sep(_("🧬 Genoma"))
        print(_("  Nombre:    {name}", name=identity.get("name", "—")))
        print(_("  Propósito: {purpose}", purpose=identity.get("purpose", "—")))
        print(_("  Creador:   {creator}", creator=genome.get("creator", "—")))
        print(_("  Versión:   {version}", version=genome.get("version", "—")))
        return 0
    if sub == "diff":
        diffs = guardian_genome.branch_diff()
        if not diffs:
            print("  Sin diferencias entre genoma y rama.")
            return 0
        _sep(_("\U0001f9ec Diff genoma vs rama"))
        for d in diffs:
            print(_("  \u2022 {key}: genoma={genome} \u2192 rama={branch}", **d))
        return 0
    return err("Uso: guardian genome <status|diff> [slug]")


# ── cmd_branch ─────────────────────────────────────────────────

def cmd_branch(slug, cmd_args):
    sub = cmd_args[0] if cmd_args else "list"
    if sub == "list":
        branches = guardian_genome.list_branches()
        if not branches:
            print("  No hay rama en esta máquina.")
            return 0
        _sep(_("🌱 Rama única"))
        b = branches[0]
        print(_("  Hash:           {hash}", hash=b["hash"]))
        print(_("  Creador:        {creator}", creator=b.get("creator", "?")))
        print(_("  Desde genoma:   {forked}", forked=b.get("forked_from_genome", "?")))
        print(_("  Sesiones:       {n}", n=b.get("session_count", 0)))
        print(_("  Evoluciones:    {v}", v=b.get("evolution_version", 0)))
        if b.get("projects"):
            print(_("  Proyectos:      {projects}", projects=", ".join(b["projects"])))
        else:
            print(_("  Proyectos:      (ninguno)"))
        return 0
    if sub == "status":
        info = guardian_genome.branch_status(slug)
        if info is None:
            return err("Rama no encontrada. Ejecutá 'guardian branch fork' primero.")
        _sep(_("🌱 Rama"))
        print(_("  Hash:      {hash}", hash=info.get("hash", "?")[:16]))
        state = info.get("state", {})
        meta = state.get("branch_meta", {})
        print(_("  Sesiones:  {n}", n=meta.get("session_count", 0)))
        print(_("  Plan:      {n}  Build: {m}", n=meta.get("plan_sessions", 0), m=meta.get("build_sessions", 0)))
        print(_("  Versión evo: {v}", v=state.get("evolution", {}).get("current_version", 0)))
        if slug:
            pdata = info.get("project", {})
            print(_("  Proyecto:  {slug}", slug=pdata.get("slug", slug)))
            print(_("  Sesiones:  {n}", n=pdata.get("session_count", 0)))
        if info.get("projects"):
            print(_("  Todos los proyectos: {projects}", projects=", ".join(info["projects"])))
        return 0
    if sub == "fork":
        state, path = guardian_genome.fork_branch(slug)
        print(_("  ✅ Rama única lista: {path}", path=str(path)))
        return 0
    if sub == "diff":
        diffs = guardian_genome.branch_diff()
        if not diffs:
            print("  Sin diferencias entre genoma y rama.")
            return 0
        for d in diffs:
            print(_("  • {key}: {genome} → {branch}", **d))
        return 0
    return err("Uso: guardian branch <list|status|fork|diff> [slug]")


# ── cmd_evolve ─────────────────────────────────────────────────

def cmd_evolve(slug, cmd_args):
    config = _read_config(slug)
    if not config:
        return err(f"Proyecto '{slug}' no encontrado.")
    meta = guardian_evolution.evolve_branch(slug)
    if meta is None:
        print("  Evolución: no se requieren ajustes (necesita ≥5 ciclos de conciencia).")
        return 0
    _sep(_("⚡ Evolución: {slug}", slug=slug))
    for r in meta.get("reasons", []):
        print(_("  • {r}", r=r))
    print(_("  Ajustes: {adjustments}", adjustments=meta.get("adjustments", {})))
    return 0


# ── cmd_consolidate ────────────────────────────────────────────

# ── cmd_activate ───────────────────────────────────────────────

def cmd_activate(slug=None):
    """Activar Guardian en un proyecto: setup → branch → absorb → docs → conciencia."""
    slug = slug or _find_slug()
    if not slug:
        cwd = Path.cwd()
        slug = _slugify(cwd.name)
    print(_("  🛡️  Activando Guardian en '{slug}'...", slug=slug))
    print()

    config = _read_config(slug)
    if not config:
        print(_("  Configurando proyecto '{slug}'...", slug=slug))
        cmd_setup(slug)
        config = _read_config(slug)

    print(_("  Creando rama de evolución..."))
    state, path = guardian_genome.fork_branch(slug)
    print(_("    Rama: {path}", path=str(path)))

    print(_("  Escaneando skills globales..."))
    subprocess.run([sys.executable, str(ABSORB_SCRIPT), "scan"], capture_output=True, text=True, timeout=60)

    print(_("  Matcheando skills al proyecto..."))
    subprocess.run([sys.executable, str(ABSORB_SCRIPT), "match", slug], capture_output=True, text=True, timeout=60)

    print(_("  Ingestando skills como tomos de conocimiento..."))
    rc = subprocess.run([sys.executable, str(ABSORB_SCRIPT), "ingest", slug], capture_output=True, text=True, timeout=60)
    if rc.returncode == 0:
        print(_("    ✓ Tomos generados"))

    print(_("  Escaneando docs..."))
    subprocess.run([sys.executable, str(Path(__file__).resolve()), "docs", "scan", slug],
                   capture_output=True, text=True, timeout=60)

    print(_("  Ciclo de conciencia inicial..."))
    mode_state = shared.read_mode_state(slug)
    mode = mode_state.get("mode", shared.DEFAULT_MODE)
    try:
        import urllib.request
        import urllib.parse
        data = json.dumps({"slug": slug, "question": f"SOY: activar guardian en {slug}", "mode": mode}).encode()
        req = urllib.request.Request("http://127.0.0.1:9787/conciencia/cycle", data=data,
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read())
        print(_("    Acción: {action} (confianza {confidence})", action=result.get("action", "—"), confidence=result.get("confidence", 0.0)))
    except Exception:
        result = guardian_conciencia.run_cycle(slug, question=f"SOY: activar guardian en {slug}", mode=mode)
        print(_("    Acción: {action} (confianza {confidence})", action=result.get("action", "—"), confidence=result.get("confidence", 0.0)))

    print()
    print(_("  ✅ Guardian activado para '{slug}'", slug=slug))
    print(_("  Proyecto: {slug}", slug=slug))
    print(_("  Rama:     {hash}", hash=guardian_genome._slug_hash(slug)[:16]))
    print(_("  Modo:     {mode}", mode=mode))
    print()
    return 0


def cmd_consolidate(slug, cmd_args):
    config = _read_config(slug)
    if not config:
        return err(f"Proyecto '{slug}' no encontrado.")
    result = guardian_evolution.consolidate(slug)
    if not result.get("ok"):
        return err(f"Error: {result.get('error', 'unknown')}")
    mem = result.get("memory_gc", {})
    if mem:
        print(_("  🧹 Memoria GC: {removed} expirados eliminados", removed=mem.get("removed", 0)))
    if result.get("rag_reindex", {}).get("rc") == 0:
        print("  ✅ RAG re-indexado")
    learn = result.get("learnings_consolidated", {})
    if learn:
        print(_("  📚 Learnings: {before} → {after}", **learn))
    return 0


    if not cmd_args or cmd_args[0] == "status":
        _sep(_("📚 Conocimiento: {slug}", slug=slug))
        print(_("  Tomos:       {n}", n=len(index.get("tomes", []))))
        print(_("  Actualizado: {updated}", updated=index.get("updated", "—")))
        return 0

    sub = cmd_args[0]
    if sub == "tomes":
        if not tomes_dir.exists():
            print("  No hay tomos todavía.")
            return 0
        _sep(_("📚 Tomos: {slug}", slug=slug))
        for path in sorted(tomes_dir.glob("*")):
            if path.is_file():
                print(_("  • {name}", name=path.name))
        return 0

    if sub == "search":
        if len(cmd_args) < 2:
            return err("Uso: guardian knowledge search <slug> <query>")
        query = " ".join(cmd_args[1:])
        return cmd_rag([query, "--slug", slug, "--top-k", "5", "--source", "knowledge", "--json"])

    return err("Uso: guardian knowledge <status|tomes|search>")

# ── cmd_pr ──────────────────────────────────────────────────────

def cmd_pr(slug, subcmd, subargs):
    config = _read_config(slug)
    root = config.get("project_root", ".") if config else "."

    if subcmd == "create":
        title = subargs[0] if subargs else ""
        body = subargs[1] if len(subargs) > 1 else ""
        if not title:
            return err("Falta el título del PR.")
        cmd = ["gh", "pr", "create", "--title", title, "--body", body or "(sin descripción)"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=root, timeout=60)
            if result.returncode == 0:
                url = result.stdout.strip()
                print(_("  ✅ PR creado: {url}", url=url))
                _run_audit_record(slug, "pr_create", [], "ok", f"PR creado: {title[:60]}")
            else:
                return err(result.stderr.strip() or "Error al crear PR")
        except subprocess.TimeoutExpired:
            return err("Creación de PR excedió el tiempo de espera.")
        except FileNotFoundError:
            return err("gh CLI no encontrado. Instalá GitHub CLI: https://cli.github.com/")

    elif subcmd == "status":
        cmd = ["gh", "pr", "status"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=root, timeout=30)
            print(result.stdout.strip() or "Sin PRs activos.")
            if result.stderr:
                print(result.stderr.strip())
        except subprocess.TimeoutExpired:
            return err("Status de PR excedió el tiempo de espera.")
        except FileNotFoundError:
            return err("gh CLI no encontrado.")

    elif subcmd == "list":
        cmd = ["gh", "pr", "list"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=root, timeout=30)
            print(result.stdout.strip() or "Sin PRs.")
            if result.stderr:
                print(result.stderr.strip())
        except subprocess.TimeoutExpired:
            return err("Listado de PRs excedió el tiempo de espera.")
        except FileNotFoundError:
            return err("gh CLI no encontrado.")

    elif subcmd == "comment":
        if len(subargs) < 2:
            return err("Uso: guardian pr comment <número> <cuerpo>")
        number = subargs[0]
        body = subargs[1]
        cmd = ["gh", "pr", "comment", number, "--body", body]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=root, timeout=30)
            if result.returncode == 0:
                print(_("  ✅ Comentario agregado a PR #{number}", number=number))
            else:
                return err(result.stderr.strip() or "Error al comentar")
        except subprocess.TimeoutExpired:
            return err("Comentario excedió el tiempo de espera.")
        except FileNotFoundError:
            return err("gh CLI no encontrado.")

    elif subcmd == "approve":
        if not subargs:
            return err("Falta el número de PR.")
        number = subargs[0]
        cmd = ["gh", "pr", "review", number, "--approve"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=root, timeout=30)
            if result.returncode == 0:
                print(_("  ✅ PR #{number} aprobado", number=number))
                _run_audit_record(slug, "pr_approve", [], "ok", f"PR #{number} aprobado")
            else:
                return err(result.stderr.strip() or "Error al aprobar")
        except subprocess.TimeoutExpired:
            return err("Approve excedió el tiempo de espera.")
        except FileNotFoundError:
            return err("gh CLI no encontrado.")

    elif subcmd == "merge":
        if not subargs:
            return err("Falta el número de PR.")
        number = subargs[0]
        cmd = ["gh", "pr", "merge", number]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=root, timeout=60)
            if result.returncode == 0:
                print(_("  ✅ PR #{number} mergeado", number=number))
                _run_audit_record(slug, "pr_merge", [], "ok", f"PR #{number} mergeado")
            else:
                return err(result.stderr.strip() or "Error al mergear")
        except subprocess.TimeoutExpired:
            return err("Merge excedió el tiempo de espera.")
        except FileNotFoundError:
            return err("gh CLI no encontrado.")

    elif subcmd == "checkout":
        if not subargs:
            return err("Falta el número de PR.")
        number = subargs[0]
        cmd = ["gh", "pr", "checkout", number]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=root, timeout=30)
            if result.returncode == 0:
                print(_("  ✅ PR #{number} checkout realizado", number=number))
            else:
                return err(result.stderr.strip() or "Error al checkout")
        except subprocess.TimeoutExpired:
            return err("Checkout excedió el tiempo de espera.")
        except FileNotFoundError:
            return err("gh CLI no encontrado.")

    else:
        return err(f"Subcomando de PR no válido: '{subcmd}'. Usá: create, status, comment, approve, merge, list, checkout")

    return 0

# ── cmd_issue ───────────────────────────────────────────────────

def cmd_issue(slug, subcmd, subargs):
    config = _read_config(slug)
    root = config.get("project_root", ".") if config else "."

    if subcmd == "list":
        cmd = ["gh", "issue", "list"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=root, timeout=30)
            print(result.stdout.strip() or "Sin issues.")
            if result.stderr:
                print(result.stderr.strip())
        except subprocess.TimeoutExpired:
            return err("Listado de issues excedió el tiempo de espera.")
        except FileNotFoundError:
            return err("gh CLI no encontrado.")

    elif subcmd == "create":
        if len(subargs) < 1:
            return err("Falta el título del issue.")
        title = subargs[0]
        body = subargs[1] if len(subargs) > 1 else ""
        cmd = ["gh", "issue", "create", "--title", title, "--body", body or "(sin descripción)"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=root, timeout=60)
            if result.returncode == 0:
                url = result.stdout.strip()
                print(_("  ✅ Issue creado: {url}", url=url))
                _run_audit_record(slug, "issue_create", [], "ok", f"Issue: {title[:60]}")
            else:
                return err(result.stderr.strip() or "Error al crear issue")
        except subprocess.TimeoutExpired:
            return err("Creación de issue excedió el tiempo de espera.")
        except FileNotFoundError:
            return err("gh CLI no encontrado.")

    elif subcmd == "close":
        if not subargs:
            return err("Falta el número de issue.")
        number = subargs[0]
        cmd = ["gh", "issue", "close", number]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=root, timeout=30)
            if result.returncode == 0:
                print(_("  ✅ Issue #{number} cerrado", number=number))
            else:
                return err(result.stderr.strip() or "Error al cerrar issue")
        except subprocess.TimeoutExpired:
            return err("Cierre de issue excedió el tiempo de espera.")
        except FileNotFoundError:
            return err("gh CLI no encontrado.")

    elif subcmd == "comment":
        if len(subargs) < 2:
            return err("Uso: guardian issue comment <número> <cuerpo>")
        number = subargs[0]
        body = subargs[1]
        cmd = ["gh", "issue", "comment", number, "--body", body]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=root, timeout=30)
            if result.returncode == 0:
                print(_("  ✅ Comentario agregado a issue #{number}", number=number))
            else:
                return err(result.stderr.strip() or "Error al comentar")
        except subprocess.TimeoutExpired:
            return err("Comentario excedió el tiempo de espera.")
        except FileNotFoundError:
            return err("gh CLI no encontrado.")

    else:
        return err(f"Subcomando de issue no válido: '{subcmd}'. Usá: list, create, close, comment")

    return 0

# ── cmd_projects ────────────────────────────────────────────────

def cmd_projects(subcmd, subargs):
    projects = _discover_projects()

    if subcmd == "list":
        if not projects:
            print("  No hay proyectos registrados.")
            return 0
        _sep("📋 Proyectos")
        for slug in projects:
            config = _read_config(slug)
            stack = config.get("stack", {})
            if isinstance(stack, str):
                stack = {}
            detected = stack.get("detected", "?")
            framework = stack.get("framework", "?")
            mem = _read_memory(slug)
            skills = _read_skills_json(slug)
            hot = skills.get("hot", [])
            hot_str = f"🔥 {', '.join(hot[:3])}" if hot else ""
            print(_("  {slug:<30} {detected:<8} {framework:<12} 🧠{:>3}  📦{:>3}  {hot_str}", len(mem), len(skills.get('relevant', [])), slug=slug, detected=detected, framework=framework, hot_str=hot_str))
        return 0

    elif subcmd == "status":
        if not projects:
            print("  No hay proyectos registrados.")
            return 0
        total_mem = 0
        total_hot = 0
        total_skills = 0
        active = 0
        for slug in projects:
            config = _read_config(slug)
            mem = _read_memory(slug)
            skills = _read_skills_json(slug)
            total_mem += len(mem)
            total_hot += len(skills.get("hot", []))
            total_skills += len(skills.get("relevant", []))
            if mem:
                now_ts = int(datetime.now(timezone.utc).timestamp())
                recent = sum(1 for e in mem if (now_ts - _ts_epoch(e.get("ts", ""))) // 86400 <= e.get("ttl", 7))
                if recent > 0:
                    active += 1
        _sep("📊 Proyectos — Estadísticas")
        print(_("  Total:       {}", len(projects)))
        print(_("  Activos:     {active}", active=active))
        print(_("  Memoria:     {total_mem} entrada(s)", total_mem=total_mem))
        print(_("  Skills:      {total_skills} relevante(s)", total_skills=total_skills))
        print(_("  Hot skills:  {total_hot}", total_hot=total_hot))
        return 0

    elif subcmd == "gc":
        if not projects:
            print("  No hay proyectos registrados.")
            return 0
        total_removed = 0
        total_skipped = 0
        now_ts = int(datetime.now(timezone.utc).timestamp())
        for slug in projects:
            mem = _read_memory(slug)
            if not mem:
                total_skipped += 1
                continue
            has_expired = any(
                (now_ts - _ts_epoch(e.get("ts", ""))) // 86400 > e.get("ttl", 7)
                for e in mem[:10]
            )
            if not has_expired:
                total_skipped += 1
                continue
            try:
                mem_args = [sys.executable, str(MEMORY_SCRIPT), "gc", slug]
                result = subprocess.run(mem_args, capture_output=True, text=True, timeout=30)
                output = result.stdout.strip()
                if output:
                    print(_("  {slug}: {output}", slug=slug, output=output))
                    m = re.search(r"(\d+) vencido", output)
                    if m:
                        total_removed += int(m.group(1))
            except Exception as e:
                print(_("  ⚠ {slug}: {e}", slug=slug, e=e))
        skip_str = shared._("projects_skipped", skipped=total_skipped) if total_skipped else ""
        print(shared._("projects_gc_done", total=len(projects), extra=skip_str))
        return 0

    elif subcmd == "absorb":
        subsub = subargs[0] if subargs else ""
        if subsub == "match":
            if not projects:
                print("  No hay proyectos registrados.")
                return 0
            now_ts = int(datetime.now(timezone.utc).timestamp())
            total_skipped = 0
            total_run = 0
            for slug in projects:
                skills_data = _read_skills_json(slug)
                last_match = skills_data.get("last_match")
                if last_match:
                    age_days = (now_ts - _ts_epoch(last_match)) // 86400
                    if age_days < 1:
                        total_skipped += 1
                        continue
                total_run += 1
                try:
                    result = subprocess.run(
                        [sys.executable, str(ABSORB_SCRIPT), "match", slug],
                        capture_output=True, text=True, timeout=60
                    )
                    output = result.stdout.strip()
                    if output:
                        last_line = output.strip().split("\n")[-1]
                        print(_("  {slug}: {}", last_line[:80], slug=slug))
                except Exception as e:
                    print(_("  ⚠ {slug}: {e}", slug=slug, e=e))
            skip_str = shared._("projects_skipped_run", skipped=total_skipped, ran=total_run) if total_skipped else ""
            print(shared._("projects_absorb_done", total=len(projects), extra=skip_str))
            return 0
        else:
            return err("Uso: guardian projects absorb match")

    else:
        return err(f"Subcomando no válido: '{subcmd}'. Usá: list, status, gc, absorb")

    return 0

# ── cmd_memory, cmd_absorb, cmd_stack ───────────────────────────

def cmd_memory(args):
    if not args:
        print("Uso: guardian memory <save|search|context|gc|status|index|session> [args...]")
        return 1
    cmd = [sys.executable, str(MEMORY_SCRIPT)] + args
    try:
        result = subprocess.run(cmd)
        return result.returncode
    except FileNotFoundError:
        return err(f"No se encontró: {MEMORY_SCRIPT}")
    except Exception as e:
        return err(f"Error: {e}")

def cmd_absorb(args):
    if not args:
        print("Uso: guardian absorb <scan|match|classify|ingest|learn|suggest|status> [args...]")
        return 1
    cmd = [sys.executable, str(ABSORB_SCRIPT)] + args
    try:
        result = subprocess.run(cmd)
        return result.returncode
    except FileNotFoundError:
        return err(f"No se encontró: {ABSORB_SCRIPT}")
    except Exception as e:
        return err(f"Error: {e}")

def cmd_rag(args):
    if not args:
        print("Uso: guardian rag <query> [--slug <slug>] [--top-k <n>] [--json] [--scope <path>]")
        return 1
    cmd = [sys.executable, str(RAG_SCRIPT)] + args
    try:
        result = subprocess.run(cmd)
        return result.returncode
    except FileNotFoundError:
        return err(f"No se encontró: {RAG_SCRIPT}")
    except Exception as e:
        return err(f"Error: {e}")

def cmd_web(args):
    extra = []
    port = DEFAULT_WEB_PORT
    skip_next = False
    for i, a in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if a == "--port" and i + 1 < len(args):
            port = int(args[i + 1])
            skip_next = True
        else:
            extra.append(a)
    cmd = [sys.executable, str(WEB_SCRIPT), "--port", str(port)] + extra
    try:
        result = subprocess.run(cmd)
        return result.returncode
    except FileNotFoundError:
        return err(f"No se encontró: {WEB_SCRIPT}")
    except Exception as e:
        return err(f"Error: {e}")

def cmd_stack(action, slug):
    config = _read_config(slug)
    if not config:
        return err(f"Proyecto '{slug}' no encontrado.")
    stack = config.get("stack", {})
    if isinstance(stack, str):
        stack = {}
    cmd = stack.get(action, "")
    if not cmd:
        return err(f"No hay comando configurado para '{action}'. Usá 'guardian setup' para configurarlo.")
    root = config.get("project_root", "")
    print(_("  ⚡ {cmd}", cmd=cmd))
    try:
        result = subprocess.run(shlex.split(cmd), cwd=root or ".", timeout=120)
        if result.returncode == 0:
            print(_("  ✓ {action} completado", action=action))
        else:
            print(_("  ❌ {action} falló (código: {})", result.returncode, action=action))
        return result.returncode
    except subprocess.TimeoutExpired:
        return err(f"{action} excedió el tiempo de espera")
    except Exception as e:
        return err(f"Error al ejecutar {action}: {e}")

# ── main ────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("--help", "-h"):
        print("🛡️  Nexxoria Guardian")
        print()
        print("Uso: guardian <comando> [args...]")
        print()
        print("Proyecto:")
        print("  activate [slug]              Activar Guardian (setup + branch + absorb + docs + conciencia)")
        print("  detect                       Detectar proyecto actual")
        print("  status [slug]                Dashboard del proyecto")
        print("  check [slug]                 Verificar reglas y paths protegidos")
        print("  report [slug]                Violaciones, tendencias, cumplimiento")
        print("  setup [slug]                 Configurar proyecto")
        print()
        print("Cambios:")
        print("  protect <path> [slug]        Proteger un path")
        print("  snapshot <path> [slug]       Backup de archivo")
        print("  diff [path] [slug]           Mostrar diff (git o snapshot)")
        print("  rollback [slug]              Revertir último cambio")
        print("  hooks [slug]                 Estado de hooks")
        print()
        print("Workflow AI:")
        print("  context [opts] [slug]        Contexto del proyecto para AI")
        print("                                --rag <query> añade búsqueda RAG (solo --json)")
        print("  rag <query> [--slug] [opts]  Búsqueda RAG en docs + código + memoria")
        print()
        print("Web:")
        print("  web [--port <n>]              Dashboard web con RAG search")
        print()
        print("Documentación:")
        print("  docs scan [slug]             Generar docs desde templates")
        print("  docs route <path> [slug]     Ver qué doc se sirve para un path")
        print()
        print("Hooks:")
        print("  pre-change <files...> [--auto] [slug]")
        print("  post-change [files...] [--auto] [slug]")
        print("  pre-deploy [--auto] [slug]")
        print("  post-deploy [--auto] [slug]")
        print()
        print("Sistemas:")
        print("  mode <plan|build|status>     Modo de operación")
        print("  backend <start|stop|restart|status>  Backend persistente")
        print("  conciencia <cycle|status|history|meta>  Conciencia + meta-evolución")
        print("  knowledge <args>             Conocimiento (tomes/RAG)")
        print("  genome <status|diff>         ADN del ser")
        print("  branch <list|fork|status|diff>  Ramas de evolución")
        print("  evolve [slug]                Disparar evolución de rama")
        print("  consolidate [slug]           Consolidar memoria + RAG")
        print("  memory <args>                Sistema de memoria persistente")
        print("  absorb <args>                Sistema de skills")
        print("  pr <sub> [args]              GitHub PR integration")
        print("  issue <sub> [args]           GitHub Issues integration")
        print("  projects <sub> [args]        Gestión multi-proyecto")
        print()
        print("Stack:")
        print("  build|dev|test|lint|typecheck|deploy|logs [slug]")
        return 0

    args = sys.argv[1:]
    cmd = args[0]
    cmd_args = args[1:]

    # ── commands that take slug from args or auto-detect ──

    if cmd == "detect":
        return cmd_detect()

    if cmd == "activate":
        slug = cmd_args[0] if cmd_args else None
        return cmd_activate(slug)

    if cmd in ("status", "check", "report"):
        slug, rest = _resolve_slug(cmd_args)
        if cmd == "status":
            return cmd_status(slug)
        elif cmd == "check":
            return cmd_check(slug)
        elif cmd == "report":
            return cmd_report(slug)

    if cmd == "protect":
        if not cmd_args:
            print("Uso: guardian protect <path> [slug]")
            return 1
        path = cmd_args[0]
        slug, _ = _resolve_slug(cmd_args[1:])
        return cmd_protect(path, slug)

    if cmd == "snapshot":
        if not cmd_args:
            print("Uso: guardian snapshot <path> [slug]")
            return 1
        path = cmd_args[0]
        slug, _ = _resolve_slug(cmd_args[1:])
        return cmd_snapshot(path, slug)

    if cmd == "diff":
        path_arg = cmd_args[0] if cmd_args and not cmd_args[0].startswith("-") else None
        rest = cmd_args[1:] if path_arg else cmd_args
        slug, _ = _resolve_slug(rest)
        return cmd_diff(path_arg, slug)

    if cmd == "rollback":
        slug, _ = _resolve_slug(cmd_args)
        return cmd_rollback(slug)

    if cmd == "hooks":
        slug, _ = _resolve_slug(cmd_args)
        return cmd_hooks(slug)

    if cmd == "setup":
        auto = "--auto" in cmd_args
        filtered = [a for a in cmd_args if a != "--auto"]
        slug = filtered[0] if filtered else None
        return cmd_setup(slug, auto=auto)

    if cmd == "docs":
        if not cmd_args:
            print("Uso: guardian docs <scan|route> [args...]")
            return 1
        sub = cmd_args[0]
        subargs = cmd_args[1:]
        if sub == "scan":
            slug, _ = _resolve_slug(subargs)
            return cmd_docs_scan(slug)
        elif sub == "route":
            if not subargs:
                return err("Uso: guardian docs route <path> [slug]")
            path = subargs[0]
            slug, _ = _resolve_slug(subargs[1:])
            return cmd_docs_route(path, slug)
        else:
            return err(f"Subcomando docs no válido: '{sub}'. Usá: scan, route")

    if cmd == "context":
        slug, rest = _resolve_slug(cmd_args)
        return cmd_context(slug, rest)

    if cmd == "mode":
        slug, rest = _resolve_slug(cmd_args)
        return cmd_mode(slug, rest)

    if cmd == "backend":
        return cmd_backend(cmd_args)

    if cmd == "knowledge":
        slug, rest = _resolve_slug(cmd_args)
        return cmd_knowledge(slug, rest)

    if cmd == "conciencia":
        slug, rest = _resolve_slug(cmd_args)
        return cmd_conciencia(slug, rest)

    if cmd == "genome":
        slug, rest = _resolve_slug(cmd_args)
        return cmd_genome(slug, rest)

    if cmd == "branch":
        slug, rest = _resolve_slug(cmd_args)
        return cmd_branch(slug, rest)

    if cmd == "evolve":
        slug, rest = _resolve_slug(cmd_args)
        return cmd_evolve(slug, rest)

    if cmd == "consolidate":
        slug, rest = _resolve_slug(cmd_args)
        return cmd_consolidate(slug, rest)

    if cmd == "prompt":
        if not cmd_args:
            return err("Uso: guardian prompt <paso> [--scope=...] [--type=...] [--files=...] [slug]")
        step = cmd_args[0]
        rest = cmd_args[1:]
        slug, rest2 = _resolve_slug(rest)
        return cmd_prompt(slug, [step] + rest2)

    # ── hooks ──

    if cmd in HOOKS:
        auto = "--auto" in cmd_args
        no_tests = "--no-tests" in cmd_args
        no_lint = "--no-lint" in cmd_args
        filtered = [a for a in cmd_args if not a.startswith("--")]
        slug, files_rest = _resolve_slug(filtered)

        if cmd == "pre-change":
            return cmd_pre_change(slug, files_rest, auto=auto)
        elif cmd == "post-change":
            return cmd_post_change(slug, files=files_rest, auto=auto, skip_tests=no_tests, skip_lint=no_lint)
        elif cmd == "pre-deploy":
            return cmd_pre_deploy(slug, auto=auto)
        elif cmd == "post-deploy":
            return cmd_post_deploy(slug, auto=auto)

    # ── subcommands that delegate ──

    if cmd == "memory":
        return cmd_memory(cmd_args)

    if cmd == "absorb":
        return cmd_absorb(cmd_args)

    if cmd == "rag":
        return cmd_rag(cmd_args)

    if cmd == "web":
        return cmd_web(cmd_args)

    if cmd == "pr":
        if not cmd_args:
            return err("Uso: guardian pr <create|status|comment|approve|merge|list|checkout> [args]")
        sub = cmd_args[0]
        subargs = cmd_args[1:]
        slug, rest = _resolve_slug(subargs)
        return cmd_pr(slug, sub, rest)

    if cmd == "issue":
        if not cmd_args:
            return err("Uso: guardian issue <list|create|close|comment> [args]")
        sub = cmd_args[0]
        subargs = cmd_args[1:]
        slug, rest = _resolve_slug(subargs)
        return cmd_issue(slug, sub, rest)

    if cmd == "projects":
        if not cmd_args:
            return err("Uso: guardian projects <list|status|gc|absorb> [args]")
        sub = cmd_args[0]
        subargs = cmd_args[1:]
        return cmd_projects(sub, subargs)

    # ── stack commands ──

    if cmd in STACK_COMMANDS:
        slug, _ = _resolve_slug(cmd_args)
        return cmd_stack(cmd, slug)

    # ── unknown ──

    return err(f"Comando desconocido: '{cmd}'. Ejecutá 'guardian' sin argumentos para ver la ayuda.")

if __name__ == "__main__":
    sys.exit(main())
