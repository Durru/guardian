#!/usr/bin/env python3
"""
guardian_migration_v3_layout — migra datos de v3 a v4 layout.

v3 layout:
  /var/guardian/projects/<slug>/
    config.yaml, conciencia-state.json, conciencia-thresholds.json,
    memory.jsonl, learnings/, knowledge/tomes/, skills.json

v4 layout:
  $GUARDIAN_DATA/users/<machine-id>/projects/<slug>/root/
    config.yaml, mode-state.json, brain/, lineage.json, root-link.json

CLI:
  guardian migrate <status|migrate|rollback> <slug>
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

import guardian_shared as shared


def _v3_project_dir(slug: str) -> Path:
    return shared.MEMORY_DIR / slug


def _v4_root(slug: str) -> Path:
    return shared.project_root_path(slug)


def _v4_brain_dir(slug: str) -> Path:
    return _v4_root(slug) / "brain"


def status(slug: str) -> dict:
    """Check if slug has v3 or v4 layout data."""
    v3_dir = _v3_project_dir(slug)
    v4_root = _v4_root(slug)
    v3_exists = v3_dir.exists()
    v4_config = v4_root / "config.yaml"

    v3_memory = (v3_dir / "memory.jsonl").exists()
    v3_conciencia_state = (v3_dir / "conciencia-state.json").exists()
    v3_conciencia_thresholds = (v3_dir / "conciencia-thresholds.json").exists()
    v3_learnings = (v3_dir / "learnings").exists()
    v3_tomes = (v3_dir / "knowledge" / "tomes").exists()
    v3_skills = (v3_dir / "skills.json").exists()

    v4_brain = _v4_brain_dir(slug)
    v4_has_brain = v4_brain.exists() and any(v4_brain.iterdir())

    v4_config_synced = v4_config.exists() and v4_config.stat().st_size > 0

    has_v3_data = v3_memory or v3_conciencia_state or v3_conciencia_thresholds or v3_learnings or v3_tomes
    needs_migration = has_v3_data and not v4_has_brain

    return {
        "slug": slug,
        "v3_exists": v3_exists,
        "v3_files": {
            "config": v3_exists,
            "memory": v3_memory,
            "conciencia_state": v3_conciencia_state,
            "conciencia_thresholds": v3_conciencia_thresholds,
            "learnings": v3_learnings,
            "tomes": v3_tomes,
            "skills": v3_skills,
        },
        "v4_has_brain_db": v4_has_brain,
        "v4_config_synced": v4_config_synced,
        "needs_migration": needs_migration,
        "migrated": v4_has_brain,
    }


def migrate(slug: str, dry_run: bool = False) -> dict:
    """Migrate a single project from v3 to v4 layout.

    Returns a dict with the result of each migration step.
    """
    result = {"slug": slug, "dry_run": dry_run, "steps": [], "errors": []}
    v3_dir = _v3_project_dir(slug)
    v4_root = _v4_root(slug)
    v4_brain = _v4_brain_dir(slug)

    if not v3_dir.exists():
        return {"ok": False, "error": f"v3 project '{slug}' not found at {v3_dir}"}

    # v4 root should already exist (project_root_path creates it)
    v4_root.mkdir(parents=True, exist_ok=True)
    v4_brain.mkdir(parents=True, exist_ok=True)

    # 1. Migrate config.yaml
    v3_config = v3_dir / "config.yaml"
    v4_config = v4_root / "config.yaml"
    if v3_config.exists():
        if not dry_run:
            shutil.copy2(str(v3_config), str(v4_config))
        result["steps"].append("config.yaml")

    # 2. Migrate memory.jsonl → brain/memory.jsonl
    v3_memory = v3_dir / "memory.jsonl"
    v4_memory = v4_brain / "memory.jsonl"
    if v3_memory.exists():
        if not dry_run:
            shutil.copy2(str(v3_memory), str(v4_memory))
        result["steps"].append("memory.jsonl")

    # 3. Migrate conciencia-state.json → brain/conciencia-state.json
    v3_state = v3_dir / "conciencia-state.json"
    v4_state = v4_brain / "conciencia-state.json"
    if v3_state.exists():
        if not dry_run:
            shutil.copy2(str(v3_state), str(v4_state))
        result["steps"].append("conciencia-state.json")

    # 4. Migrate conciencia-thresholds.json → brain/conciencia-thresholds.json
    v3_thresholds = v3_dir / "conciencia-thresholds.json"
    v4_thresholds = v4_brain / "conciencia-thresholds.json"
    if v3_thresholds.exists():
        if not dry_run:
            shutil.copy2(str(v3_thresholds), str(v4_thresholds))
        result["steps"].append("conciencia-thresholds.json")

    # 5. Ensure mode-state.json
    v4_mode = v4_root / "mode-state.json"
    if not v4_mode.exists() and not dry_run:
        shared.write_json(v4_mode, {"mode": "plan", "updated_at": shared.ts()})

    # 6. Migrate skills.json → brain/skills.json
    v3_skills = v3_dir / "skills.json"
    v4_skills = v4_brain / "skills.json"
    if v3_skills.exists():
        if not dry_run:
            shutil.copy2(str(v3_skills), str(v4_skills))
        result["steps"].append("skills.json")

    # 7. Migrate learnings/ → brain/learnings/
    v3_learnings = v3_dir / "learnings"
    v4_learnings = v4_brain / "learnings"
    if v3_learnings.exists():
        if not dry_run:
            if v4_learnings.exists():
                _merge_dirs(v3_learnings, v4_learnings)
            else:
                shutil.copytree(str(v3_learnings), str(v4_learnings))
        result["steps"].append("learnings/")

    # 8. Migrate knowledge/tomes/ → brain/tomes/
    v3_tomes = v3_dir / "knowledge" / "tomes"
    v4_tomes = v4_brain / "tomes"
    if v3_tomes.exists():
        if not dry_run:
            if v4_tomes.exists():
                _merge_dirs(v3_tomes, v4_tomes)
            else:
                shutil.copytree(str(v3_tomes), str(v4_tomes))
        result["steps"].append("knowledge/tomes/")

    # 9. Create root-link.json pointing to the project's actual root
    v4_link = v4_root / "root-link.json"
    if not v4_link.exists() and not dry_run:
        config_data = shared.read_json(v3_config) if v3_config.exists() else {}
        actual_root = config_data.get("project_root", str(Path.cwd()))
        shared.write_json(v4_link, {"project_root": actual_root, "linked_at": shared.ts()})

    # 10. Create/update branch.json
    branch = shared.user_branch_path()
    v4_branch_json = branch / "branch.json"
    if not v4_branch_json.exists() and not dry_run:
        shared.write_json(v4_branch_json, {
            "created_at": shared.ts(),
            "guardian_version": "4.0.0",
            "migrated_from": "v3",
            "projects": [slug],
        })

    # Run the brain schema init to create the v4 DB tables
    if not dry_run:
        try:
            import guardian_brain_schema
            guardian_brain_schema.init_project(slug)
            result["steps"].append("brain_schema_init")
        except Exception as e:
            result["errors"].append(f"brain_schema_init: {e}")

    result["ok"] = len(result["errors"]) == 0
    return result


def rollback(slug: str) -> dict:
    """Rollback a v4 migration by removing v4 layout files."""
    v4_root = _v4_root(slug)
    result = {"slug": slug, "removed": []}
    if not v4_root.exists():
        result["ok"] = True
        result["note"] = "Nothing to rollback (v4 layout does not exist)"
        return result

    items_to_remove = [
        v4_root / "root-link.json",
        v4_root / "mode-state.json",
    ]

    for item in items_to_remove:
        if item.exists():
            item.unlink()
            result["removed"].append(str(item.relative_to(v4_root.parent)))

    brain_dir = v4_root / "brain"
    if brain_dir.exists():
        shutil.rmtree(str(brain_dir))
        result["removed"].append("brain/")

    result["ok"] = True
    return result


def _merge_dirs(source: Path, dest: Path):
    """Merge source directory into dest (existing files are NOT overwritten)."""
    for src_item in source.rglob("*"):
        if src_item.is_file():
            rel = src_item.relative_to(source)
            dst_item = dest / rel
            if not dst_item.exists():
                dst_item.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src_item), str(dst_item))


def cmd_status(args: list[str]) -> int:
    if not args:
        print("Uso: guardian migration status <slug>")
        return 1
    slug = args[0]
    s = status(slug)
    print(f"\nMigration status for '{slug}':")
    print(f"  v3 exists:       {s['v3_exists']}")
    print(f"  v4 brain DB:     {s['v4_has_brain_db']}")
    print(f"  v4 config:       {s['v4_config_synced']}")
    print(f"  needs_migration: {s['needs_migration']}")
    print(f"  migrated:        {s['migrated']}")
    if s.get("v3_files"):
        print("\n  v3 files:")
        for name, exists in s["v3_files"].items():
            print(f"    {name}: {exists}")
    return 0 if s["migrated"] else 0


def cmd_migrate(args: list[str]) -> int:
    if not args:
        print("Uso: guardian migration migrate <slug> [--dry-run]")
        return 1
    dry_run = "--dry-run" in args
    slug = args[0]
    result = migrate(slug, dry_run=dry_run)
    if not result.get("ok"):
        print(f"\nMigration failed: {result.get('error', 'unknown error')}")
        return 1
    print(f"\nMigration {'(DRY RUN)' if dry_run else 'completed'} for '{slug}':")
    for step in result.get("steps", []):
        print(f"  ✓ {step}")
    for err in result.get("errors", []):
        print(f"  ✗ {err}")
    if result.get("dry_run"):
        print("\n  Run without --dry-run to apply.")
    return 0 if result["ok"] else 1


def cmd_rollback(args: list[str]) -> int:
    if not args:
        print("Uso: guardian migration rollback <slug>")
        return 1
    slug = args[0]
    result = rollback(slug)
    if not result.get("ok"):
        print(f"\nRollback failed: {result.get('error', 'unknown error')}")
        return 1
    print(f"\nRollback for '{slug}':")
    for item in result.get("removed", []):
        print(f"  ✗ removed: {item}")
    if not result.get("removed"):
        print("  Nothing to rollback.")
    return 0


def main() -> int:
    if not sys.argv[1:]:
        print("Uso: guardian migration <status|migrate|rollback> <slug> [--dry-run]")
        return 1
    sub = sys.argv[1]
    args = sys.argv[2:]
    if sub == "status":
        return cmd_status(args)
    elif sub == "migrate":
        return cmd_migrate(args)
    elif sub == "rollback":
        return cmd_rollback(args)
    else:
        print(f"Subcomando desconocido: '{sub}'. Usá: status, migrate, rollback")
        return 1


if __name__ == "__main__":
    sys.exit(main())
