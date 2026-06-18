#!/usr/bin/env python3
"""
guardian_migration_v45 — migra datos de v4 split-brain a v4.5 unificado.

v4 (antes):
  genome/branches/<hash>/projects/<slug>/brain/  ← DBs, GUARDIAN.md
  users/<machine-id>/projects/<slug>/root/       ← state, thresholds
  projects/<slug>/                               ← config, audit, skills

v4.5 (después):
  projects/<slug>/                               ← TODO del proyecto
  projects/<slug>/brain/                         ← DBs, GUARDIAN.md, state
"""

import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import guardian_shared as shared
import guardian_brain_schema as schema


def _old_genome_brain(slug: str) -> Path:
    """Old genome/branches/<hash>/projects/<slug>/brain/"""
    _guess_hash()
    return shared.BACKEND_DIR / "genome" / "branches" / _old_hash / "projects" / slug / "brain"


def _old_genome_knowledge(slug: str) -> Path:
    return shared.BACKEND_DIR / "genome" / "branches" / _old_hash / "projects" / slug / "knowledge"


_old_hash = "70d8f57c85b0da5b"  # hardcoded from this machine's old branch


def _guess_hash():
    global _old_hash
    branches = shared.BACKEND_DIR / "genome" / "branches"
    if branches.exists():
        for d in branches.iterdir():
            if d.is_dir():
                _old_hash = d.name
                return


def status(slug: str) -> dict:
    old_brain = _old_genome_brain(slug)
    new_brain = schema.brain_dir(slug)
    return {
        "slug": slug,
        "old_brain_exists": old_brain.exists(),
        "old_brain_files": [f.name for f in old_brain.iterdir()] if old_brain.exists() else [],
        "new_brain_exists": new_brain.exists(),
        "new_brain_files": [f.name for f in new_brain.iterdir()] if new_brain.exists() else [],
        "needs_migration": old_brain.exists() and (not new_brain.exists() or len(list(new_brain.iterdir())) == 0),
    }


def migrate(slug: str, dry_run: bool = False) -> dict:
    result = {"slug": slug, "steps": [], "errors": [], "dry_run": dry_run}

    # 1. Migrate brain/ (DBs, GUARDIAN.md, working_memory, handoff)
    old_brain = _old_genome_brain(slug)
    new_brain = schema.brain_dir(slug)
    if old_brain.exists():
        if not dry_run:
            new_brain.mkdir(parents=True, exist_ok=True)
            for f in old_brain.iterdir():
                if f.is_file():
                    shutil.copy2(str(f), str(new_brain / f.name))
        result["steps"].append(f"brain/ ({len(list(old_brain.iterdir()))} files)")

    # 2. Migrate knowledge/
    old_knowledge = _old_genome_knowledge(slug)
    if old_knowledge.exists():
        new_knowledge = shared.project_dir(slug) / "knowledge"
        if not dry_run:
            for f in old_knowledge.rglob("*"):
                if f.is_file():
                    rel = f.relative_to(old_knowledge)
                    dst = new_knowledge / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    # Don't overwrite existing files
                    if not dst.exists():
                        shutil.copy2(str(f), str(dst))
        result["steps"].append("knowledge/")

    # 3. Ensure branch.json exists
    branch_json = shared.project_dir(slug) / "branch.json"
    if not branch_json.exists() and not dry_run:
        shared.project_dir(slug).mkdir(parents=True, exist_ok=True)
        branch_json.write_text(json.dumps({
            "slug": slug,
            "genome_version": 4,
            "migrated_at": shared.ts(),
            "version": "4.5.0",
        }, indent=2), encoding="utf-8")
        result["steps"].append("branch.json")

    result["ok"] = len(result["errors"]) == 0
    return result


def cmd_status(args):
    slug = args[0] if args else ""
    if slug:
        s = status(slug)
        print(f"\nMigration v4.5 status for '{slug}':")
        print(f"  Old brain: {'EXISTS (' + ', '.join(s['old_brain_files']) + ')' if s['old_brain_exists'] else '—'}")
        print(f"  New brain: {'EXISTS (' + ', '.join(s['new_brain_files']) + ')' if s['new_brain_exists'] else '—'}")
        print(f"  Needs migration: {s['needs_migration']}")
    else:
        for d in sorted(shared.MEMORY_DIR.iterdir()):
            if d.is_dir():
                ns = d.name
                s = status(ns)
                if s["needs_migration"]:
                    print(f"  {ns}: needs migration ({len(s['old_brain_files'])} files in old brain)")
    return 0


def cmd_migrate(args):
    slug = args[0] if args else ""
    dry_run = "--dry-run" in args
    if not slug:
        # Migrate all
        ok = True
        for d in sorted(shared.MEMORY_DIR.iterdir()):
            if d.is_dir():
                ns = d.name
                s = status(ns)
                if s["needs_migration"]:
                    r = migrate(ns, dry_run=dry_run)
                    if r["ok"]:
                        print(f"  {ns}: migrated ({', '.join(r['steps'])})")
                    else:
                        print(f"  {ns}: FAILED ({', '.join(r['errors'])})")
                        ok = False
        return 0 if ok else 1
    r = migrate(slug, dry_run=dry_run)
    if r["ok"]:
        print(f"  {slug}: migrated ({', '.join(r['steps'])})")
    else:
        print(f"  {slug}: FAILED ({', '.join(r['errors'])})")
    return 0 if r["ok"] else 1


def main():
    if len(sys.argv) < 2:
        print("Uso: guardian migrate-v45 <status|migrate> [slug] [--dry-run]")
        return 1
    cmd = sys.argv[1]
    args = sys.argv[2:]
    if cmd == "status":
        return cmd_status(args)
    elif cmd == "migrate":
        return cmd_migrate(args)
    else:
        print(f"Subcomando desconocido: '{cmd}'. Usá: status, migrate")
        return 1


if __name__ == "__main__":
    sys.exit(main())
