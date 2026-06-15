#!/usr/bin/env python3
"""
guardian_forja — La Forja: meta-módulo para crear, modificar, validar y eliminar
cualquier parte del core de Guardian. Uso personal — taller del arquitecto.

CLI:
  guardian forja <subcomando> [args]

Subcomandos:
  index                          Reconstruir el índice de auto-conocimiento
  module new <name> [desc]       Scaffold de nuevo guardian_*.py
  validate [module]              Validar módulo contra convenciones
  impact <change>                Análisis de impacto
  doctor                         Diagnóstico de salud del sistema
  list                           Inventario de módulos, endpoints, MCP tools
  edit <file>                    Editar archivo del core
  rm <module> [--force]          Eliminar módulo (con seguridad)
  protect <module>               Marcar módulo como protegido
  run <texto>                    Interfaz directa: interpreta pedido en lenguaje natural
"""

import ast
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import guardian_shared as shared
from guardian_shared import _


GUARDIAN_DIR = Path(__file__).resolve().parent.parent
LIB_DIR = GUARDIAN_DIR / "lib"
FORJA_DIR = Path.home() / ".forja"
INDEX_PATH = FORJA_DIR / "index.json"
BACKUP_DIR = FORJA_DIR / "backups"
AUDIT_DIR = FORJA_DIR / "audit"
AUDIT_LOG = AUDIT_DIR / "changes.jsonl"

PROTECTED_MODULES = {
    "guardian_shared", "guardian_genome", "guardian_conciencia",
    "guardian_forja", "guardian", "guardian_mcp", "guardian_backend",
}

INDEX_SNAPSHOT_PATH = FORJA_DIR / "index-snapshot.json"

MODULE_TEMPLATE = '''#!/usr/bin/env python3
"""
guardian_{name} — {desc}

CLI:
  guardian {name} <action> [args]
"""

import json
import sys
from pathlib import Path
import guardian_shared as shared
from guardian_shared import _


def main():
    if len(sys.argv) < 2:
        print(_("Uso: guardian {name} <action> [args]"))
        return 1
    action = sys.argv[1]
    args = sys.argv[2:]
    print(_("{{action}}: aún no implementado", action=action))
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


def _ts():
    return datetime.now(timezone.utc).isoformat()


def _ensure_dirs():
    FORJA_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)


def _audit_log(entry: dict):
    _ensure_dirs()
    entry["ts"] = _ts()
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _find_functions(filepath: Path) -> list[dict]:
    funcs = []
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                funcs.append({
                    "name": node.name,
                    "lineno": node.lineno,
                    "args": [a.arg for a in node.args.args],
                })
    except SyntaxError:
        pass
    return funcs


def _find_cli_commands(filepath: Path) -> list[str]:
    cmds = []
    text = filepath.read_text(encoding="utf-8")
    for m in re.finditer(r'def cmd_(\w+)\(', text):
        cmds.append(m.group(1))
    return cmds


def _find_endpoints(filepath: Path) -> list[str]:
    endpoints = []
    text = filepath.read_text(encoding="utf-8")
    for m in re.finditer(r'if parsed\.path == "([^"]+)"', text):
        endpoints.append(m.group(1))
    return endpoints


def _find_mcp_tools(filepath: Path) -> list[str]:
    tools = []
    text = filepath.read_text(encoding="utf-8")
    for m in re.finditer(r'"name":\s*"(\w+)"', text):
        tools.append(m.group(1))
    return tools


# ── auto-conocimiento ─────────────────────────────────


def scan_index() -> dict:
    _ensure_dirs()
    index = {
        "modules": [],
        "files": 0,
        "functions": 0,
        "endpoints": 0,
        "mcp_tools": 0,
        "scanned_at": _ts(),
    }
    for f in sorted(LIB_DIR.glob("guardian_*.py")):
        mod_name = f.stem
        funcs = _find_functions(f)
        cli_cmds = _find_cli_commands(f)
        endpoints = _find_endpoints(f)
        mcp_tools = _find_mcp_tools(f)
        index["modules"].append({
            "file": f.name,
            "name": mod_name,
            "loc": _count_lines(f),
            "functions": [fn["name"] for fn in funcs],
            "cli_commands": cli_cmds,
            "endpoints": endpoints,
            "mcp_tools": mcp_tools,
        })
        index["functions"] += len(funcs)
        index["endpoints"] += len(endpoints)
        index["mcp_tools"] += len(mcp_tools)

    guardian_file = LIB_DIR / "guardian.py"
    if guardian_file.exists():
        funcs = _find_functions(guardian_file)
        cli_cmds = _find_cli_commands(guardian_file)
        index["modules"].append({
            "file": "guardian.py",
            "name": "guardian",
            "loc": _count_lines(guardian_file),
            "functions": [fn["name"] for fn in funcs],
            "cli_commands": cli_cmds,
        })
        index["functions"] += len(funcs)

    index["files"] = len(index["modules"])
    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return index


def load_index() -> dict:
    if INDEX_PATH.exists():
        return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    return scan_index()


def _count_lines(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8").splitlines())
    except Exception:
        return 0


# ── scaffold ──────────────────────────────────────────


def _register_in_guardian_py(name: str, desc: str = "") -> bool:
    guardian_py = LIB_DIR / "guardian.py"
    if not guardian_py.exists():
        return False
    text = guardian_py.read_text(encoding="utf-8")
    guard = f'cmd_{name}'
    if guard in text:
        return False

    script_var = f'{name.upper()}_SCRIPT'
    module_path = f'GUARDIAN_DIR / "lib" / "guardian_{name}.py"'

    cmd_handler = f'''
def cmd_{name}(args):
    if not args:
        print("Uso: guardian {name} <sub> [args...]")
        return 1
    cmd = [sys.executable, str({script_var})] + args
    try:
        result = subprocess.run(cmd)
        return result.returncode
    except FileNotFoundError:
        return err(f"No se encontró: {{{script_var}}}")
    except Exception as e:
        return err(f"Error: {{e}}")
'''

    script_line = f'{script_var} = {module_path}'
    help_line = f'  f"  {name:<32}{desc}",'

    text = text.replace(
        'FORJA_SCRIPT = GUARDIAN_DIR / "lib" / "guardian_forja.py"',
        f'{script_line}\nFORJA_SCRIPT = GUARDIAN_DIR / "lib" / "guardian_forja.py"',
    )

    text = text.replace(
        'def cmd_forja(args):',
        cmd_handler + '\ndef cmd_forja(args):',
    )

    text = text.replace(
        '  forja <sub> [args]            La Forja: crear/validar/editar/eliminar módulos del core',
        f'  {name} <sub> [args]            {desc}\n  forja <sub> [args]            La Forja: crear/validar/editar/eliminar módulos del core',
    )

    dispatch_line = f'if cmd == "{name}":\n        return cmd_{name}(cmd_args)'
    text = text.replace(
        'if cmd == "forja":',
        f'{dispatch_line}\n    if cmd == "forja":',
    )

    guardian_py.write_text(text, encoding="utf-8")
    return True


def module_new(name: str, desc: str = "", register: bool = False) -> dict:
    if not re.match(r'^[a-z][a-z_0-9]+$', name):
        return {"ok": False, "error": _("Nombre inválido: usar snake_case (ej: auditoria)")}

    filename = f"guardian_{name}.py"
    filepath = LIB_DIR / filename
    if filepath.exists():
        return {"ok": False, "error": _("{name} ya existe", name=filename)}

    desc = desc or f"Módulo {name}"
    content = MODULE_TEMPLATE.format(name=name, desc=desc)
    filepath.write_text(content, encoding="utf-8")

    result = {"ok": True, "file": filename, "path": str(filepath), "bytes": len(content)}

    if register:
        registered_dispatch = _register_in_guardian_py(name, desc)
        if registered_dispatch:
            result["registered_in_guardian"] = True
            _audit_log({"action": "module_register", "name": name, "target": "guardian.py"})

    _audit_log({"action": "module_new", "file": filename, "name": name, "full_register": register})
    scan_index()
    return result


def function_add(module: str, func_name: str, register: bool = False) -> dict:
    filepath = _resolve_module(module)
    if not filepath:
        return {"ok": False, "error": _("Módulo {m} no encontrado", m=module)}

    guard = f"def cmd_{func_name}("
    text = filepath.read_text(encoding="utf-8")
    if guard in text:
        return {"ok": False, "error": _("La función cmd_{name} ya existe en {mod}", name=func_name, mod=module)}

    new_func = f"""

def cmd_{func_name}(args):
    print(_("cmd_{name}: implementar", name="{func_name}"))
    return 0
"""
    text += new_func
    filepath.write_text(text, encoding="utf-8")
    _audit_log({"action": "function_add", "module": module, "function": f"cmd_{func_name}"})
    scan_index()
    result = {"ok": True, "file": str(filepath), "function": f"cmd_{func_name}"}

    if register:
        guardian_py = LIB_DIR / "guardian.py"
        if guardian_py.exists():
            gp_text = guardian_py.read_text(encoding="utf-8")
            dispatch_line = f'if cmd == "{func_name}":'
            if dispatch_line not in gp_text:
                help_line = f'f"  {func_name:<32}..."'
                new_gp = gp_text.replace(
                    "def dispatch(argv):",
                    f"def cmd_{func_name}(args, slug=None):\n    from guardian_forja import function_add\n    print(_('cmd_{func_name}: delegar a forja'))\n    return 0\n\n\ndef dispatch(argv):",
                )
                new_gp = new_gp.replace(
                    'if cmd == "mode"',
                    f'if cmd == "{func_name}":\n        return cmd_{func_name}(args, slug)\n    elif cmd == "mode"',
                )
                guardian_py.write_text(new_gp, encoding="utf-8")
                result["registered_in_guardian"] = True
                _audit_log({"action": "function_register", "function": f"cmd_{func_name}"})

    return result


# ── endpoint scaffold ──────────────────────────────────


def cmd_endpoint(method: str, path: str, module: str = "") -> dict:
    backend_py = LIB_DIR / "guardian_backend.py"
    if not backend_py.exists():
        return {"ok": False, "error": _("guardian_backend.py no encontrado")}

    if method.upper() not in ("GET", "POST"):
        return {"ok": False, "error": _("Método debe ser GET o POST")}

    text = backend_py.read_text(encoding="utf-8")
    route_check = f'if parsed.path == "{path}"'
    if route_check in text:
        return {"ok": False, "error": _("El endpoint {p} ya existe", p=path)}

    method_lower = method.lower()

    handler = f"""
    elif parsed.path == "{path}":
        slug = params.get("slug", [None])[0]
        return {{"ok": True, "endpoint": "{path}", "slug": slug}}
"""

    method_marker = f'def do_{method_lower}'
    insert_pos = text.rfind(method_marker)
    if insert_pos == -1:
        return {"ok": False, "error": _("No se encontró método do_{m} en backend", m=method_lower)}

    route_start = text.find(f'if parsed.path == "', insert_pos)
    if route_start == -1:
        route_start = text.find(f'if parsed.path.startswith(', insert_pos)

    if route_start == -1:
        text_last = text.rfind("\n", insert_pos)
        text = text[:text_last] + handler + text[text_last:]
    else:
        text = text[:route_start] + handler + "\n" + " " * 4 + text[route_start:]

    backend_py.write_text(text, encoding="utf-8")

    _audit_log({"action": "endpoint_add", "method": method, "path": path, "module": module})
    scan_index()
    return {"ok": True, "path": path, "method": method, "module": module or "?"}


# ── MCP tool scaffold ─────────────────────────────────


def cmd_mcp_tool(name: str, module: str = "guardian_forja") -> dict:
    mcp_py = LIB_DIR / "guardian_mcp.py"
    if not mcp_py.exists():
        return {"ok": False, "error": _("guardian_mcp.py no encontrado")}

    text = mcp_py.read_text(encoding="utf-8")
    if f'"{name}"' in text:
        return {"ok": False, "error": _("La tool {n} ya existe en mcp.py", n=name)}

    mod_import = f"import {module} as {module.replace('guardian_', 'g_')}"
    if mod_import not in text:
        import_end = text.find("\n\n")
        if import_end == -1:
            import_end = text.find("\n", text.find("import "))
        text = text[:import_end] + "\n" + mod_import + text[import_end:]

    tool_def = f'''    {{
        "name": "{name}",
        "description": "Tool {name}",
        "input_schema": {{{{}}}}
    }},
'''

    tools_insert = text.find('"name": "')
    if tools_insert > 0:
        text = text[:tools_insert] + tool_def + text[tools_insert:]

    handler_def = f'''
def handle_{name}(params: dict) -> dict:
    return {{"ok": True, "tool": "{name}"}}
'''
    text += handler_def

    mcp_py.write_text(text, encoding="utf-8")

    _audit_log({"action": "mcp_tool_add", "name": name, "module": module})
    scan_index()
    return {"ok": True, "name": name, "module": module}


# ── diff (index snapshot) ──────────────────────────────


def diff_snapshot() -> dict:
    current = load_index()
    current_by_name = {m["name"]: m for m in current["modules"]}

    if INDEX_SNAPSHOT_PATH.exists():
        old = json.loads(INDEX_SNAPSHOT_PATH.read_text(encoding="utf-8"))
        old_by_name = {m["name"]: m for m in old["modules"]}
    else:
        old = {"modules": [], "files": 0, "functions": 0}
        old_by_name = {}

    added = []
    removed = []
    changed = []

    for name, mod in current_by_name.items():
        if name not in old_by_name:
            added.append(mod)
        elif mod.get("loc", 0) != old_by_name[name].get("loc", 0) or \
             mod.get("functions", []) != old_by_name[name].get("functions", []):
            changed.append({"name": name, "before": old_by_name[name], "after": mod})

    for name, mod in old_by_name.items():
        if name not in current_by_name:
            removed.append(mod)

    INDEX_SNAPSHOT_PATH.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "ok": True,
        "snapshot_saved": True,
        "added": [m["name"] for m in added],
        "removed": [m["name"] for m in removed],
        "changed": [(c["name"], c["after"].get("loc", 0) - c["before"].get("loc", 0)) for c in changed],
        "scanned_at": current.get("scanned_at", ""),
    }


# ── graph (ASCII dependencias) ─────────────────────────


def graph_deps() -> dict:
    import_map: dict[str, list[str]] = {}
    for f in sorted(LIB_DIR.glob("guardian_*.py")) + [LIB_DIR / "guardian.py"]:
        if not f.exists():
            continue
        name = f.stem
        import_map[name] = []
        text = f.read_text(encoding="utf-8")
        for m in re.finditer(r'^import (\S+)|^from (\S+) import', text, re.MULTILINE):
            mod = m.group(1) or m.group(2)
            if mod.startswith("guardian_") and mod != name:
                import_map[name].append(mod)

    lines = []
    for mod, deps in sorted(import_map.items()):
        if deps:
            for dep in deps:
                lines.append(f"  {mod} ──> {dep}")
        else:
            lines.append(f"  {mod}")

    ascii_lines = []
    for mod, deps in sorted(import_map.items()):
        if deps:
            for i, dep in enumerate(deps):
                prefix = "├── " if i < len(deps) - 1 else "└── "
                ascii_lines.append(f"  {mod}")
                ascii_lines.append(f"{prefix}{dep}")
        else:
            ascii_lines.append(f"  {mod}")

    return {
        "ok": True,
        "nodes": list(import_map.keys()),
        "edges": [(m, d) for m, deps in import_map.items() for d in deps],
        "ascii": "\n".join(ascii_lines),
    }


# ── patch (edición parcial) ────────────────────────────


def patch_file(rel_path: str, old_text: str, new_text: str) -> dict:
    full_path = LIB_DIR / rel_path
    if not full_path.exists():
        full_path = GUARDIAN_DIR / rel_path
    if not full_path.exists():
        return {"ok": False, "error": _("Archivo no encontrado: {p}", p=rel_path)}

    content = full_path.read_text(encoding="utf-8")
    if old_text not in content:
        return {"ok": False, "error": _("Texto a reemplazar no encontrado en {p}", p=rel_path)}

    count = content.count(old_text)
    if count > 1:
        return {"ok": False, "error": _("Se encontraron {n} ocurrencias. Usá un contexto más específico", n=count)}

    new_content = content.replace(old_text, new_text)
    backup_path = BACKUP_DIR / f"{full_path.name}.{int(datetime.now().timestamp())}.bak"
    shutil.copy2(full_path, backup_path)

    full_path.write_text(new_content, encoding="utf-8")
    _audit_log({
        "action": "patch",
        "file": str(full_path),
        "backup": str(backup_path),
        "old_len": len(old_text),
        "new_len": len(new_text),
    })
    return {"ok": True, "file": str(full_path), "backup": str(backup_path), "lines_changed": len(new_content.splitlines()) - len(content.splitlines())}


# ── validate ──────────────────────────────────────────


def validate_module(module_name: str = "") -> dict:
    rules = {
        "naming": {"pass": 0, "fail": 0, "items": []},
        "imports": {"pass": 0, "fail": 0, "items": []},
        "i18n": {"pass": 0, "fail": 0, "items": []},
        "headers": {"pass": 0, "fail": 0, "items": []},
        "error_handling": {"pass": 0, "fail": 0, "items": []},
    }

    targets = [LIB_DIR / f"{module_name}.py"] if module_name else sorted(LIB_DIR.glob("*.py"))
    for fp in targets:
        if not fp.exists():
            continue
        text = fp.read_text(encoding="utf-8")
        name = fp.stem

        lines = text.splitlines()
        has_cmd = any(line.strip().startswith("def cmd_") for line in lines)
        if has_cmd:
            rules["naming"]["pass"] += 1
        else:
            rules["naming"]["items"].append(f"{name}: sin funciones cmd_")
            rules["naming"]["fail"] += 1

        if "guardian_shared as shared" in text:
            rules["imports"]["pass"] += 1
        else:
            rules["imports"]["items"].append(f"{name}: falta 'import guardian_shared as shared'")
            rules["imports"]["fail"] += 1

        if "from guardian_shared import _" in text or "from guardian_shared import" in text:
            rules["i18n"]["pass"] += 1
        else:
            rules["i18n"]["items"].append(f"{name}: falta 'from guardian_shared import _'")
            rules["i18n"]["fail"] += 1

        has_section_headers = bool(re.search(r'# ──.+──', text))
        if has_section_headers:
            rules["headers"]["pass"] += 1
        else:
            rules["headers"]["items"].append(f"{name}: sin secciones # ── ──")
            rules["headers"]["fail"] += 1

        has_try = "try:" in text
        has_except = "except" in text
        if has_try or has_except:
            rules["error_handling"]["pass"] += 1
        else:
            rules["error_handling"]["items"].append(f"{name}: sin try/except")
            rules["error_handling"]["fail"] += 1

    total_pass = sum(r["pass"] for r in rules.values())
    total_fail = sum(r["fail"] for r in rules.values())
    return {
        "ok": total_fail == 0,
        "total_pass": total_pass,
        "total_fail": total_fail,
        "rules": rules,
        "target": module_name or "all",
    }


# ── impact ────────────────────────────────────────────


IMPACT_MATRIX = {
    "cli": {"files": ["guardian.py"], "docs": ["REFERENCIA.md"], "msg": "Nuevo CLI command: tocar guardian.py + docs"},
    "endpoint": {"files": ["guardian_backend.py"], "lib": True, "docs": ["REFERENCIA.md"], "msg": "Nuevo endpoint: tocar backend.py + lib + docs"},
    "mcp": {"files": ["guardian_mcp.py"], "plugin": True, "docs": ["REFERENCIA.md"], "msg": "Nueva MCP tool: tocar mcp.py + plugin + backend + docs"},
    "module": {"files": [], "new_file": True, "guardian": True, "docs": ["REFERENCIA.md", "AGENTS.md", "MODULOS.md"], "msg": "Nuevo módulo: crear archivo + guardian.py + docs"},
    "edit": {"files": [], "msg": "Editar archivo existente del core"},
    "delete": {"files": [], "backup": True, "audit": True, "msg": "Eliminar módulo: backup + limpiar registros"},
}


def impact_analysis(change: str) -> dict:
    change = change.strip().lower()
    result = {"change": change, "impacted_files": [], "notes": []}

    if change.startswith("cli ") or change == "cli":
        info = IMPACT_MATRIX["cli"]
        result["impacted_files"].extend(info["files"])
        result["notes"].append(info["msg"])

    elif change.startswith("endpoint ") or change == "endpoint":
        info = IMPACT_MATRIX["endpoint"]
        result["impacted_files"].extend(info["files"])
        result["notes"].append(info["msg"])

    elif change.startswith("mcp ") or change == "mcp":
        info = IMPACT_MATRIX["mcp"]
        result["impacted_files"].extend(info["files"])
        result["impacted_files"].append("guardian_backend.py")
        result["notes"].append(info["msg"])

    elif change.startswith("module ") or change == "module":
        info = IMPACT_MATRIX["module"]
        result["impacted_files"].append(f"lib/guardian_{change.split()[-1] if len(change.split()) > 1 else '<name>'}.py (nuevo)")
        result["impacted_files"].extend(info["docs"])
        result["notes"].append(info["msg"])

    elif change.startswith("edit "):
        target = change.split(maxsplit=1)[1]
        result["impacted_files"].append(target)
        result["notes"].append(f"Editar {target}")

    elif change.startswith("rm ") or change == "delete":
        info = IMPACT_MATRIX["delete"]
        result["notes"].append(info["msg"])

    else:
        result["notes"].append(_("No se pudo determinar el cambio. Usá: cli, endpoint, mcp, module <name>, edit <file>, rm <module>"))

    return result


# ── doctor ─────────────────────────────────────────────


def doctor_check() -> dict:
    issues = []
    checks = {"passed": 0, "failed": 0, "warnings": 0}

    for f in sorted(LIB_DIR.glob("guardian_*.py")):
        if not f.exists():
            issues.append({"severity": "error", "msg": f"Falta: {f.name}"})
            checks["failed"] += 1
            continue
        try:
            compile(f.read_text(encoding="utf-8"), f.name, "exec")
            checks["passed"] += 1
        except SyntaxError as e:
            issues.append({"severity": "error", "msg": f"Error sintaxis en {f.name}: {e}"})
            checks["failed"] += 1

    guardian_main = LIB_DIR / "guardian.py"
    if guardian_main.exists():
        text = guardian_main.read_text(encoding="utf-8")
        for mod_file in LIB_DIR.glob("guardian_*.py"):
            mod_name = mod_file.stem
            if mod_name == "guardian_shared":
                continue
            if mod_name not in text:
                issues.append({"severity": "warning", "msg": f"Módulo {mod_name} no referenciado en guardian.py"})
                checks["warnings"] += 1

    imports_ok = True
    for f in sorted(LIB_DIR.glob("*.py")):
        text = f.read_text(encoding="utf-8")
        for im in re.finditer(r'^import (\S+)|^from (\S+) import', text, re.MULTILINE):
            mod = im.group(1) or im.group(2)
            if mod.startswith("guardian_") and mod != f.stem:
                target = LIB_DIR / f"{mod}.py"
                if not target.exists():
                    issues.append({"severity": "error", "msg": f"Import {mod} en {f.name} no resuelve"})
                    checks["failed"] += 1
                    imports_ok = False

    if imports_ok:
        checks["passed"] += 1

    index = load_index()
    checks["modules"] = index["files"]
    checks["functions"] = index["functions"]

    return {
        "ok": checks["failed"] == 0,
        "checks": checks,
        "issues": issues,
        "index": {"files": index["files"], "functions": index["functions"]},
    }


# ── list ───────────────────────────────────────────────


def list_inventory() -> dict:
    index = load_index()
    result = {
        "modules": [],
        "endpoints": set(),
        "mcp_tools": set(),
        "cli_commands": [],
    }

    for mod in index["modules"]:
        result["modules"].append({
            "file": mod["file"],
            "name": mod["name"],
            "loc": mod.get("loc", 0),
            "functions": len(mod.get("functions", [])),
            "cli_commands": mod.get("cli_commands", []),
        })
        for ep in mod.get("endpoints", []):
            result["endpoints"].add(ep)
        for tool in mod.get("mcp_tools", []):
            result["mcp_tools"].add(tool)
        for cmd in mod.get("cli_commands", []):
            result["cli_commands"].append(cmd)

    result["endpoints"] = sorted(result["endpoints"])
    result["mcp_tools"] = sorted(result["mcp_tools"])
    result["total_modules"] = len(result["modules"])
    result["total_endpoints"] = len(result["endpoints"])
    result["total_mcp_tools"] = len(result["mcp_tools"])
    return result


# ── edit ───────────────────────────────────────────────


def edit_file(rel_path: str) -> dict:
    full_path = LIB_DIR / rel_path
    if not full_path.exists():
        full_path = GUARDIAN_DIR / rel_path
    if not full_path.exists():
        return {"ok": False, "error": _("Archivo no encontrado: {p}", p=rel_path)}

    content = full_path.read_text(encoding="utf-8")
    return {
        "ok": True,
        "file": str(full_path),
        "content": content,
        "lines": len(content.splitlines()),
    }


def write_file_content(rel_path: str, content: str) -> dict:
    full_path = LIB_DIR / rel_path
    if not full_path.exists():
        full_path = GUARDIAN_DIR / rel_path
    if not full_path.exists():
        return {"ok": False, "error": _("Archivo no encontrado: {p}", p=rel_path)}

    full_path.write_text(content, encoding="utf-8")
    _audit_log({"action": "edit", "file": str(full_path), "bytes": len(content)})
    return {"ok": True, "file": str(full_path), "bytes": len(content)}


# ── delete ─────────────────────────────────────────────


def _resolve_module(name: str) -> Path | None:
    for f in LIB_DIR.glob("guardian_*.py"):
        if f.stem == name or f.stem == f"guardian_{name}":
            return f
    g = LIB_DIR / "guardian.py"
    if name in ("guardian", "guardian.py"):
        return g
    return None


def delete_module(name: str, force: bool = False, dry_run: bool = False, interactive: bool = True) -> dict:
    filepath = _resolve_module(name)
    if not filepath:
        return {"ok": False, "error": _("Módulo {n} no encontrado", n=name)}

    mod_key = filepath.stem if filepath.stem != "guardian" else "guardian"

    if mod_key in PROTECTED_MODULES and not force:
        return {"ok": False, "error": _("{m} es un módulo protegido. Usá --force para eliminarlo (no recomendado)", m=mod_key)}

    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "file": filepath.name,
            "protected": mod_key in PROTECTED_MODULES,
            "backup_target": str(BACKUP_DIR / f"{filepath.name}.<timestamp>.bak"),
            "audit_entry": {"action": "delete", "module": mod_key},
            "message": _("Dry-run: esto es lo que pasaría. Pasá --no-confirm para saltar la confirmación interactiva."),
        }

    if interactive and not force and sys.stdin.isatty():
        print(_("¿Eliminar {f}? (s/N): ", f=filepath.name), end="", flush=True)
        try:
            respuesta = sys.stdin.readline().strip().lower()
            if respuesta not in ("s", "si", "y", "yes"):
                return {"ok": False, "error": _("Operación cancelada por el usuario")}
        except (EOFError, KeyboardInterrupt):
            return {"ok": False, "error": _("Operación cancelada")}

    backup_path = BACKUP_DIR / f"{filepath.name}.{int(datetime.now().timestamp())}.bak"
    shutil.copy2(filepath, backup_path)

    filepath.unlink()

    _audit_log({
        "action": "delete",
        "module": mod_key,
        "file": filepath.name,
        "backup": str(backup_path),
        "force": force,
    })

    scan_index()
    return {
        "ok": True,
        "deleted": filepath.name,
        "backup": str(backup_path),
    }


# ── protect ────────────────────────────────────────────


def protect_module(name: str) -> dict:
    filepath = _resolve_module(name)
    if not filepath:
        return {"ok": False, "error": _("Módulo {n} no encontrado", n=name)}

    mod_key = filepath.stem if filepath.stem != "guardian" else "guardian"
    PROTECTED_MODULES.add(mod_key)
    _audit_log({"action": "protect", "module": mod_key})
    return {"ok": True, "module": mod_key, "protected": True}


# ── run (interfaz directa) ────────────────────────────


def run_direct(text: str) -> dict:
    text_lower = text.lower()
    result = {"input": text, "interpretation": "", "action": "", "result": {}}

    mod_match = re.search(r'(?:crea|crear|nuevo|new|scaffold)\s+(?:un\s+)?(?:m[oó]dulo|module)\s+(?:llamado\s+|que\s+)?([a-z_][a-z0-9_]*)', text_lower)
    if mod_match:
        mod_name = mod_match.group(1)
        full = "registralo completo" in text_lower or "full" in text_lower or "registra" in text_lower
        result["interpretation"] = f"Crear módulo {mod_name}" + (" (full register)" if full else "")
        result["action"] = "module_new"
        result["result"] = module_new(mod_name, register=full)
        return result

    rm_match = re.search(r'(?:elimina|borra|rm|delete|remove)\s+(?:el\s+)?(?:m[oó]dulo\s+|module\s+)?([a-z_][a-z0-9_]*)', text_lower)
    if rm_match:
        mod_name = rm_match.group(1)
        dry = "simula" in text_lower or "dry" in text_lower or "simul" in text_lower
        result["interpretation"] = f"Eliminar módulo {mod_name}" + (" (dry-run)" if dry else "")
        result["action"] = "delete"
        result["result"] = delete_module(mod_name, dry_run=dry)
        return result

    validate_match = re.search(r'(?:valida|validate|verifica|check)\s+(?:el\s+)?(?:m[oó]dulo\s+|module\s+)?([a-z_][a-z0-9_]*)', text_lower)
    if validate_match:
        mod_name = validate_match.group(1)
        result["interpretation"] = f"Validar módulo {mod_name}"
        result["action"] = "validate"
        result["result"] = validate_module(mod_name)
        return result

    if any(w in text_lower for w in ["doctor", "diagnóstico", "diagnostico", "salud", "health"]):
        result["interpretation"] = "Diagnóstico del sistema"
        result["action"] = "doctor"
        result["result"] = doctor_check()
        return result

    if any(w in text_lower for w in ["index", "reconstruir", "escane", "scan"]):
        result["interpretation"] = "Reconstruir índice de auto-conocimiento"
        result["action"] = "index"
        result["result"] = scan_index()
        return result

    if any(w in text_lower for w in ["lista", "list", "inventario", "inventory"]):
        result["interpretation"] = "Listar inventario del sistema"
        result["action"] = "list"
        result["result"] = list_inventory()
        return result

    endpoint_match = re.search(r'(?:endpoint|ruta|route)\s+(?:get|post|put|delete)\s+[/]?(\S+)', text_lower)
    if endpoint_match:
        ep_path = endpoint_match.group(1)
        ep_method = re.search(r'(get|post|put|delete)', text_lower).group(1).upper()
        mod_name = re.search(r'(?:en\s+)?(\S+)(?:\s+module|\s*módulo)', text_lower)
        result["interpretation"] = f"Crear endpoint {ep_method} /{ep_path}"
        result["action"] = "endpoint"
        result["result"] = cmd_endpoint(ep_method, "/" + ep_path.lstrip("/"))
        return result

    graph_match = re.search(r'(?:graph|grafo|dependencia|deps)', text_lower)
    if graph_match:
        result["interpretation"] = "Grafo de dependencias"
        result["action"] = "graph"
        result["result"] = graph_deps()
        return result

    diff_match = re.search(r'(?:diff|cambio|cambios|cambiate|snapshot)', text_lower)
    if diff_match:
        result["interpretation"] = "Diff de snapshot del índice"
        result["action"] = "diff"
        result["result"] = diff_snapshot()
        return result

    if any(w in text_lower for w in ["parche", "patch", "reemplaza", "reemplazar", "replace"]):
        result["interpretation"] = "Edición parcial (usá forja patch <file> directamente)"
        result["action"] = "unknown"
        result["result"] = {"error": _("Usá: guardian forja patch <file> con old y new")}
        return result

    result["interpretation"] = _("No se pudo interpretar. Usá: crear módulo, eliminar, validar, doctor, index, list, endpoint, graph, diff, patch")
    result["action"] = "unknown"
    return result


# ── CLI handler ────────────────────────────────────────


def main():
    if len(sys.argv) < 2:
        print(_("Uso: guardian forja <subcomando> [args]"))
        print()
        print(_("Subcomandos:"))
        print("  index                          Reconstruir el índice de auto-conocimiento")
        print("  module new <name> [desc]       Scaffold de nuevo guardian_*.py [--register]")
        print("  validate [module]              Validar módulo contra convenciones")
        print("  impact <change>                Mostrar qué archivos tocar")
        print("  doctor                         Diagnóstico de salud del sistema")
        print("  list                           Inventario de módulos, endpoints, MCP tools")
        print("  edit <file>                    Editar archivo del core")
        print("  rm <module> [--force|--dry-run|--no-confirm]  Eliminar módulo (con seguridad)")
        print("  protect <module>               Marcar módulo como protegido")
        print("  endpoint <method> <path>       Scaffold de nuevo endpoint REST")
        print("  mcp-tool <name>                Scaffold de nueva tool MCP")
        print("  function <name> [--register]   Agregar cmd_<name> a un módulo")
        print("  diff                           Snapshot diff del índice")
        print("  graph                          Grafo ASCII de dependencias")
        print("  patch <file> <old> <new>       Edición parcial (find+replace)")
        print("  run <texto>                    Interfaz directa en lenguaje natural")
        return 1

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd == "index":
        result = scan_index()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    elif cmd == "module":
        if not args or args[0] != "new":
            print("Uso: guardian forja module new <name> [desc] [--register]")
            return 1
        register = "--register" in args
        clean_args = [a for a in args if a != "--register"]
        name = clean_args[1] if len(clean_args) > 1 else ""
        desc = " ".join(clean_args[2:]) if len(clean_args) > 2 else ""
        if not name:
            print("Error: nombre del módulo requerido")
            return 1
        result = module_new(name, desc, register=register)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1

    elif cmd == "validate":
        mod = args[0] if args else ""
        result = validate_module(mod)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1

    elif cmd == "impact":
        if not args:
            print("Uso: guardian forja impact <change>")
            print("Ej: guardian forja impact 'cli new-command'")
            return 1
        result = impact_analysis(" ".join(args))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    elif cmd == "doctor":
        result = doctor_check()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1

    elif cmd == "list":
        result = list_inventory()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    elif cmd == "edit":
        if not args:
            print("Uso: guardian forja edit <file>")
            print("Ej: guardian forja edit guardian_forja.py")
            return 1
        result = edit_file(args[0])
        if not result.get("ok"):
            print(result.get("error", "Error"))
            return 1
        print(result["content"])
        print(_("\n--- {file} | {lines} líneas ---", file=result["file"], lines=result["lines"]))
        return 0

    elif cmd == "rm":
        if not args:
            print("Uso: guardian forja rm <module> [--force] [--dry-run] [--no-confirm]")
            print("Ej: guardian forja rm guardian_viejo")
            return 1
        force = "--force" in args
        dry_run = "--dry-run" in args
        no_confirm = "--no-confirm" in args
        clean_args = [a for a in args if a not in ("--force", "--dry-run", "--no-confirm")]
        mod = clean_args[0] if clean_args else ""
        if not mod:
            print("Error: nombre del módulo requerido")
            return 1
        result = delete_module(mod, force=force, dry_run=dry_run, interactive=not no_confirm)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1

    elif cmd == "protect":
        if not args:
            print("Uso: guardian forja protect <module>")
            return 1
        result = protect_module(args[0])
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1

    elif cmd == "endpoint":
        if len(args) < 2:
            print("Uso: guardian forja endpoint <GET|POST> <path> [module]")
            print("Ej: guardian forja endpoint GET /api/health")
            return 1
        method = args[0].upper()
        path = args[1]
        module = args[2] if len(args) > 2 else ""
        result = cmd_endpoint(method, path, module)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1

    elif cmd in ("mcp-tool", "mcptool", "mcp_tool"):
        if len(args) < 1:
            print("Uso: guardian forja mcp-tool <name> [module]")
            print("Ej: guardian forja mcp-tool guardian_health")
            return 1
        name = args[0]
        module = args[1] if len(args) > 1 else ""
        result = cmd_mcp_tool(name, module)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1

    elif cmd == "function":
        if not args:
            print("Uso: guardian forja function <name> [--register]")
            print("Ej: guardian forja function health --register")
            print("Nota: agrega cmd_<name> al módulo guardian_forja.py")
            return 1
        register = "--register" in args
        clean_args = [a for a in args if a != "--register"]
        func_name = clean_args[0] if clean_args else ""
        if not func_name:
            print("Error: nombre de función requerido")
            return 1
        result = function_add("guardian_forja", func_name, register=register)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1

    elif cmd == "diff":
        result = diff_snapshot()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    elif cmd == "graph":
        result = graph_deps()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    elif cmd == "patch":
        if len(args) < 3:
            print("Uso: guardian forja patch <rel_path> <old> <new>")
            print("Ej: guardian forja patch guardian_forja.py 'texto_viejo' 'texto_nuevo'")
            return 1
        result = patch_file(args[0], args[1], args[2])
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1

    elif cmd == "run":
        if not args:
            print("Uso: guardian forja run <texto>")
            print("Ej: guardian forja run 'creá un módulo de auditoría'")
            return 1
        result = run_direct(" ".join(args))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    else:
        print(_("Subcomando no válido: '{cmd}'", cmd=cmd))
        return 1


if __name__ == "__main__":
    sys.exit(main())
