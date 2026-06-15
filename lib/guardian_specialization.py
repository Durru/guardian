#!/usr/bin/env python3
"""
Guardian Specialization — stack-specific knowledge and procedures.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import guardian_brain
import guardian_brain_schema
import guardian_shared as shared


SPEC_DIR = Path.home() / ".guardian" / "specializations"


BUILTIN_SPECS = {
    "odoo": {
        "name": "odoo", "version": "1.0.0",
        "description": "Especialización para proyectos Odoo (ERP)",
        "stack_patterns": ["**/__manifest__.py", "**/__openerp__.py"],
        "applies_to_versions": ">=14.0", "kind": "best_practices",
        "seed_knowledge": [
            "En Odoo 17 los @api.depends soportan campos computed almacenados.",
            "Odoo 17 reemplazó message_post() por message_post_with_source() en el chatter.",
            "Para heredar un modelo usar _inherit = 'model.name' (no _name).",
            "Los campos relacionales usan comodel_name en lugar de relation.",
            "Para campos selection: selection_add en herencias, no selection.",
        ],
        "seed_procedures": [
            "odoo_module_test: odoo-bin --test-enable --stop-after-init -d <db> -i <module>",
            "odoo_module_update: odoo-bin -u <module> --stop-after-init -d <db>",
        ],
        "seed_known_issues": [
            "AttributeError 'res.partner' has no attribute X → campo custom no migrado.",
            "psycopg2.errors.UndefinedColumn → columna agregada al modelo pero no a la DB, correr odoo-bin -u.",
        ],
    },
    "nextjs": {
        "name": "nextjs", "version": "1.0.0",
        "description": "Especialización para proyectos Next.js",
        "stack_patterns": ["**/next.config.js", "**/next.config.mjs", "**/app/page.tsx", "**/pages/_app.tsx"],
        "applies_to_versions": ">=13.0", "kind": "best_practices",
        "seed_knowledge": [
            "Next.js 13+ usa App Router por defecto (app/ directory).",
            "Server Components por default; usar 'use client' solo cuando necesites interactividad.",
            "Server Actions permiten mutaciones sin API routes (Next 14+).",
            "Para data fetching en server components: usar fetch nativo o RSC.",
        ],
        "seed_procedures": [
            "nextjs_dev: next dev",
            "nextjs_build: next build",
            "nextjs_deploy_vercel: vercel --prod",
        ],
        "seed_known_issues": [
            "Hydration mismatch → componente server/client inconsistente, revisar 'use client' boundaries.",
            "'use client' directive must be at top of file → mover imports condicionales fuera del componente.",
        ],
    },
    "fastapi": {
        "name": "fastapi", "version": "1.0.0",
        "description": "Especialización para proyectos FastAPI",
        "stack_patterns": ["**/main.py", "**/app.py", "**/pyproject.toml"],
        "applies_to_versions": ">=0.100.0", "kind": "best_practices",
        "seed_knowledge": [
            "FastAPI es async-first; usar async def para endpoints.",
            "Pydantic v2 es el default; usar BaseModel + Field validators.",
            "Dependency injection con Depends() para db sessions, auth, etc.",
            "OpenAPI auto-generado en /docs y /redoc.",
        ],
        "seed_procedures": [
            "fastapi_dev: uvicorn main:app --reload",
            "fastapi_test: pytest",
        ],
    },
    "postgres": {
        "name": "postgres", "version": "1.0.0",
        "description": "Especialización para PostgreSQL",
        "stack_patterns": ["**/postgres.conf", "**/pg_hba.conf"],
        "applies_to_versions": ">=14", "kind": "best_practices",
        "seed_knowledge": [
            "Usar índices B-tree en columnas de filtro y orden.",
            "JSONB es preferible sobre JSON para datos semi-estructurados.",
            "EXPLAIN ANALYZE antes de optimizar queries.",
            "Connection pooling con PgBouncer para alta concurrencia.",
        ],
    },
    "python": {
        "name": "python", "version": "1.0.0",
        "description": "Especialización Python general",
        "stack_patterns": ["**/pyproject.toml", "**/setup.py", "**/requirements.txt"],
        "applies_to_versions": ">=3.10", "kind": "best_practices",
        "seed_knowledge": [
            "Type hints everywhere; usar mypy en CI.",
            "Ruff para lint (reemplaza flake8 + isort + black).",
            "Poetry o uv para dependency management.",
            "pytest con fixtures y parametrize para tests.",
        ],
    },
}


def _ensure_spec_dir():
    SPEC_DIR.mkdir(parents=True, exist_ok=True)
    return SPEC_DIR


def install_builtin(name: str) -> dict:
    if name not in BUILTIN_SPECS:
        return {"ok": False, "error": f"unknown built-in: {name}"}
    _ensure_spec_dir()
    target = SPEC_DIR / name
    target.mkdir(parents=True, exist_ok=True)
    manifest = BUILTIN_SPECS[name]
    (target / "manifest.yaml").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8",
    )
    if manifest.get("seed_knowledge"):
        (target / "knowledge.json").write_text(
            json.dumps(manifest["seed_knowledge"], indent=2, ensure_ascii=False), encoding="utf-8",
        )
    if manifest.get("seed_procedures"):
        (target / "procedures.json").write_text(
            json.dumps(manifest["seed_procedures"], indent=2, ensure_ascii=False), encoding="utf-8",
        )
    if manifest.get("seed_known_issues"):
        (target / "known_issues.json").write_text(
            json.dumps(manifest["seed_known_issues"], indent=2, ensure_ascii=False), encoding="utf-8",
        )
    return {"ok": True, "installed": str(target), "name": name}


def list_available() -> list[dict]:
    _ensure_spec_dir()
    installed = set()
    for d in SPEC_DIR.iterdir():
        if d.is_dir() and (d / "manifest.yaml").exists():
            installed.add(d.name)
    builtin = set(BUILTIN_SPECS.keys())
    result = []
    for name in sorted(builtin | installed):
        is_builtin = name in builtin
        manifest = BUILTIN_SPECS.get(name) or _load_manifest(name)
        result.append({
            "name": name, "version": manifest.get("version", "?"),
            "description": manifest.get("description", ""),
            "is_builtin": is_builtin, "installed": name in installed,
        })
    return result


def _load_manifest(name: str) -> dict:
    path = SPEC_DIR / name / "manifest.yaml"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def show(name: str) -> dict:
    _ensure_spec_dir()
    manifest = _load_manifest(name)
    builtin = BUILTIN_SPECS.get(name, {})
    if not manifest and not builtin:
        return {"ok": False, "error": f"not found: {name}"}
    full = {**builtin, **manifest} if manifest else builtin
    extra_files = ["knowledge.json", "procedures.json", "known_issues.json"]
    for f in extra_files:
        path = SPEC_DIR / name / f
        if path.exists():
            try:
                full[f.replace(".json", "")] = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
    return {"ok": True, "name": name, "spec": full}


def enable(slug: str, name: str) -> dict:
    guardian_brain_schema.init_project(slug)
    spec_path = SPEC_DIR / name / "manifest.yaml"
    if not spec_path.exists():
        install_result = install_builtin(name)
        if not install_result.get("ok"):
            return install_result
    spec = show(name)
    if not spec.get("ok"):
        return spec
    data = spec["spec"]
    written = {"semantic": 0, "procedural": 0, "skipped": 0}
    for content in data.get("knowledge", []):
        result = guardian_brain.write_governed(slug, "semantic", {
            "kind": "best_practices", "content": content,
            "importance": 0.7, "confidence": 0.8,
            "tags": [name] + data.get("tags", []),
            "stack": [name], "source": f"specialization:{name}",
        })
        if result.get("ok"):
            written["semantic"] += 1
        else:
            written["skipped"] += 1
    for proc in data.get("procedures", []):
        result = guardian_brain.write_governed(slug, "procedural", {
            "kind": "workflow", "content": proc, "importance": 0.8,
            "confidence": 0.9, "tags": [name], "stack": [name],
            "source": f"specialization:{name}",
        })
        if result.get("ok"):
            written["procedural"] += 1
        else:
            written["skipped"] += 1
    for issue in data.get("known_issues", []):
        result = guardian_brain.write_governed(slug, "semantic", {
            "kind": "known_issues", "content": issue, "importance": 0.6,
            "confidence": 0.7, "tags": [name], "stack": [name],
            "source": f"specialization:{name}",
        })
        if result.get("ok"):
            written["semantic"] += 1
    _mark_enabled(slug, name)
    return {"ok": True, "slug": slug, "spec_name": name, "written": written}


def disable(slug: str, name: str) -> dict:
    guardian_brain_schema.init_project(slug)
    _mark_disabled(slug, name)
    return {"ok": True, "slug": slug, "spec_name": name, "disabled": True}


def list_enabled(slug: str) -> list[str]:
    return _read_spec_state(slug).get("enabled", [])


def _spec_state_path(slug: str) -> Path:
    return guardian_brain_schema.brain_dir(slug) / "specializations.json"


def _read_spec_state(slug: str) -> dict:
    p = _spec_state_path(slug)
    if not p.exists():
        return {"enabled": [], "disabled": []}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"enabled": [], "disabled": []}


def _write_spec_state(slug: str, state: dict):
    p = _spec_state_path(slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def _mark_enabled(slug: str, name: str):
    state = _read_spec_state(slug)
    if name not in state.get("enabled", []):
        state.setdefault("enabled", []).append(name)
    if name in state.get("disabled", []):
        state["disabled"].remove(name)
    _write_spec_state(slug, state)


def _mark_disabled(slug: str, name: str):
    state = _read_spec_state(slug)
    if name in state.get("enabled", []):
        state["enabled"].remove(name)
    if name not in state.get("disabled", []):
        state.setdefault("disabled", []).append(name)
    _write_spec_state(slug, state)


def detect_stack(project_root: str) -> list[str]:
    detected = []
    root = Path(project_root)
    if not root.exists():
        return detected
    if list(root.rglob("__manifest__.py")) or list(root.rglob("__openerp__.py")):
        detected.append("odoo")
    if (root / "next.config.js").exists() or (root / "next.config.mjs").exists():
        if "odoo" not in detected:
            detected.append("nextjs")
    if list(root.rglob("app/page.tsx")) or list(root.rglob("pages/_app.tsx")):
        if "nextjs" not in detected:
            detected.append("nextjs")
    for f in root.rglob("*.py"):
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
            if "fastapi" in content and "FastAPI" in content:
                detected.append("fastapi")
                break
        except (OSError, UnicodeDecodeError):
            continue
    if (root / "postgres.conf").exists() or list(root.rglob("pg_dump")):
        detected.append("postgres")
    if (root / "pyproject.toml").exists() or (root / "setup.py").exists() or (root / "requirements.txt").exists():
        detected.append("python")
    return detected


USAGE = """Guardian Specialization — usage:
  list
  show <name>
  enable <slug> <name>
  disable <slug> <name>
  install <name>          install a built-in
  detect <project-root>   detect stacks in a project
"""


def main():
    if len(sys.argv) < 2:
        print(USAGE)
        return 1
    cmd = sys.argv[1]
    if cmd == "list":
        result = list_available()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    if cmd == "show":
        if len(sys.argv) < 3:
            print("show requires name")
            return 1
        name = sys.argv[2]
        result = show(name)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    if cmd == "enable":
        if len(sys.argv) < 4:
            print("enable requires slug and name")
            return 1
        slug, name = sys.argv[2], sys.argv[3]
        result = enable(slug, name)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    if cmd == "disable":
        if len(sys.argv) < 4:
            print("disable requires slug and name")
            return 1
        slug, name = sys.argv[2], sys.argv[3]
        result = disable(slug, name)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    if cmd == "install":
        if len(sys.argv) < 3:
            print("install requires name")
            return 1
        name = sys.argv[2]
        result = install_builtin(name)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    if cmd == "detect":
        if len(sys.argv) < 3:
            print("detect requires project-root")
            return 1
        root = sys.argv[2]
        result = detect_stack(root)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    print(f"Unknown command: {cmd}")
    print(USAGE)
    return 1


if __name__ == "__main__":
    sys.exit(main())
