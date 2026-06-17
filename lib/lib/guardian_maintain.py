#!/usr/bin/env python3
"""
Guardian Maintain — drift detection and project health reports.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import guardian_brain
import guardian_brain_schema
import guardian_knowledge
import guardian_shared as shared


def detect_drift(slug: str, project_root: str = None) -> dict:
    guardian_brain_schema.init_project(slug)
    drifts = []
    decisions = guardian_brain.list_nodes(slug, "semantic", filters={"kind": "decision"}, limit=50)
    if project_root:
        root = Path(project_root)
        for d in decisions:
            content = d.get("content", "").lower()
            contradicting = None
            if "sqlite" in content or "sql lite" in content:
                for f in root.rglob("*.py"):
                    try:
                        fcontent = f.read_text(encoding="utf-8", errors="ignore").lower()
                        if "psycopg" in fcontent or "asyncpg" in fcontent or "postgresql" in fcontent:
                            contradicting = f"decision says SQLite but code uses Postgres in {f.name}"
                            break
                    except (OSError, UnicodeDecodeError):
                        continue
            elif "postgres" in content or "postgresql" in content:
                for f in root.rglob("*.py"):
                    try:
                        fcontent = f.read_text(encoding="utf-8", errors="ignore").lower()
                        if "sqlite3" in fcontent and "psycopg" not in fcontent:
                            contradicting = f"decision says Postgres but code uses SQLite in {f.name}"
                            break
                    except (OSError, UnicodeDecodeError):
                        continue
            if contradicting:
                drifts.append({
                    "type": "decision_drift",
                    "node_id": d["id"],
                    "sm_says": d["content"],
                    "code_evidence": contradicting,
                    "severity": "medium" if d.get("importance", 0.5) > 0.7 else "low",
                })
    return {"drifts": drifts, "count": len(drifts)}


def health_report(slug: str, project_root: str = None) -> dict:
    guardian_brain_schema.init_project(slug)
    brain_status = guardian_brain.status(slug)
    drift = detect_drift(slug, project_root=project_root)
    stale = guardian_knowledge.detect_stale(slug)
    wm = guardian_brain.read_working_memory(slug)
    wm_age_days = None
    if wm.get("last_updated"):
        wm_age_days = (time.time() - wm["last_updated"]) / 86400
    from guardian_plan import list_plans
    active_plans = [p for p in list_plans(slug) if p.get("state") not in ("archived",)]
    from guardian_specialization import list_enabled
    enabled_specs = list_enabled(slug)
    from guardian_shared import read_mode_state
    mode = read_mode_state(slug).get("mode", "plan")
    health = 100
    issues = []
    if brain_status.get("totals", {}).get("nodes", 0) == 0:
        health -= 30
        issues.append("Brain is empty")
    if drift.get("count", 0) > 0:
        health -= min(30, drift["count"] * 10)
        issues.append(f"{drift['count']} drift(s) detected")
    if len(stale) > 5:
        health -= min(20, len(stale) * 2)
        issues.append(f"{len(stale)} stale knowledge node(s)")
    if wm_age_days and wm_age_days > 30:
        health -= 10
        issues.append(f"Working memory is {int(wm_age_days)} days stale")
    if active_plans:
        applying = [p for p in active_plans if p.get("state") == "applying"]
        if len(applying) > 3:
            issues.append(f"{len(applying)} plans in 'applying' state")
    health = max(0, health)
    return {
        "slug": slug, "health_score": health, "issues": issues, "mode": mode,
        "brain": {
            "total_nodes": brain_status.get("totals", {}).get("nodes", 0),
            "by_kind": brain_status.get("totals", {}).get("by_kind", {}),
            "guardian_md_lines": brain_status.get("guardian_md", {}).get("lines", 0),
        },
        "drift": drift, "stale_knowledge_count": len(stale),
        "working_memory": {
            "goal": wm.get("goal"), "task": wm.get("task"),
            "mode": wm.get("mode"),
            "age_days": round(wm_age_days, 1) if wm_age_days is not None else None,
        },
        "active_plans": len(active_plans),
        "enabled_specializations": enabled_specs,
    }


def format_report(report: dict) -> str:
    lines = [
        f"📊 Health report: {report['slug']}", "",
        f"  Health: {report['health_score']}/100",
        f"  Mode:   {report['mode']}",
    ]
    if report.get("issues"):
        lines.append("")
        lines.append("  Issues:")
        for issue in report["issues"]:
            lines.append(f"    ⚠ {issue}")
    lines.append("")
    lines.append("  Brain:")
    b = report["brain"]
    lines.append(f"    Total nodes: {b['total_nodes']}")
    if b.get("by_kind"):
        kinds = ", ".join(f"{k}={v}" for k, v in b["by_kind"].items())
        lines.append(f"    By kind: {kinds}")
    if b.get("guardian_md_lines"):
        lines.append(f"    GUARDIAN.md: {b['guardian_md_lines']} lines")
    lines.append("")
    lines.append(f"  Drift: {report['drift']['count']} issue(s)")
    for d in report["drift"].get("drifts", [])[:3]:
        lines.append(f"    [{d['severity']}] {d['sm_says'][:60]}")
        lines.append(f"        → {d['code_evidence'][:60]}")
    if report["stale_knowledge_count"]:
        lines.append(f"  Stale knowledge: {report['stale_knowledge_count']} node(s)")
    wm = report["working_memory"]
    if wm.get("goal"):
        lines.append(f"  Working memory: goal='{wm['goal'][:50]}'")
    if wm.get("age_days") is not None:
        lines.append(f"  Working memory age: {wm['age_days']} days")
    if report.get("active_plans"):
        lines.append(f"  Active plans: {report['active_plans']}")
    if report.get("enabled_specializations"):
        lines.append(f"  Specializations: {', '.join(report['enabled_specializations'])}")
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Uso: guardian maintain report <slug> [--project-root=PATH]")
        return 1
    cmd = sys.argv[1]
    if cmd == "report":
        slug = sys.argv[2]
        project_root = None
        for arg in sys.argv[3:]:
            if arg.startswith("--project-root="):
                project_root = arg.split("=", 1)[1]
        report = health_report(slug, project_root=project_root)
        print(format_report(report))
        return 0
    print(f"Unknown command: {cmd}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
