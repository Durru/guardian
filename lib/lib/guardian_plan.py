#!/usr/bin/env python3
"""
Guardian Plan — lifecycle of structured plans (OpenSpec-style + ad-hoc).
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import guardian_brain
import guardian_brain_schema
import guardian_shared as shared


PLAN_STATES = [
    "draft", "specs", "designed", "tasks",
    "applying", "verifying", "archived",
]

TRANSITIONS = {
    "draft":      ["specs", "applying", "archived"],
    "specs":      ["designed", "applying", "archived"],
    "designed":   ["tasks", "applying", "archived"],
    "tasks":      ["applying", "archived"],
    "applying":   ["verifying", "archived"],
    "verifying":  ["archived"],
    "archived":   [],
}


def _plan_id(title: str) -> str:
    raw = f"{title}:{int(time.time())}"
    h = hashlib.md5(raw.encode()).hexdigest()[:10]
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:30]
    return f"{slug}-{h}"


def _plan_dir(slug: str, plan_id: str) -> Path:
    return guardian_brain_schema.plans_dir(slug) / plan_id


def _read_plan(slug: str, plan_id: str) -> dict | None:
    pd = _plan_dir(slug, plan_id)
    if not pd.exists():
        return None
    status_file = pd / "status.json"
    if not status_file.exists():
        return None
    try:
        status = json.loads(status_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    files = {}
    for f in pd.glob("*.md"):
        files[f.name] = f.read_text(encoding="utf-8")
    status["files"] = files
    return status


def _write_status(slug: str, plan_id: str, status: dict):
    pd = _plan_dir(slug, plan_id)
    pd.mkdir(parents=True, exist_ok=True)
    (pd / "status.json").write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")


def _transition(plan: dict, new_state: str) -> dict:
    current = plan.get("state", "draft")
    valid = TRANSITIONS.get(current, [])
    if new_state not in valid:
        return {
            "ok": False, "error": f"invalid transition: {current} → {new_state}",
            "valid_next": valid,
        }
    return {"ok": True}


def new_plan(slug: str, title: str, plan_type: str = "full", description: str = "") -> dict:
    guardian_brain_schema.init_project(slug)
    if plan_type not in ("full", "quick"):
        plan_type = "full"
    plan_id = _plan_id(title)
    pd = _plan_dir(slug, plan_id)
    pd.mkdir(parents=True, exist_ok=True)
    now_iso = datetime.now(timezone.utc).isoformat()
    proposal = f"""# {title}

**Plan ID:** {plan_id}
**Type:** {plan_type}
**Created:** {now_iso}
**State:** draft

## What
{description or "[FILL: what is changing and why]"}

## Why
[FILL: motivation, business value, problem being solved]

## Scope
- In: [FILL]
- Out: [FILL]
"""
    if plan_type == "full":
        proposal += """
## Acceptance
[FILL: how we'll know this is done]
"""
    (pd / "proposal.md").write_text(proposal, encoding="utf-8")
    status = {
        "plan_id": plan_id, "slug": slug, "title": title, "type": plan_type,
        "state": "draft", "created_at": now_iso, "updated_at": now_iso,
        "history": [{"state": "draft", "ts": now_iso}],
    }
    _write_status(slug, plan_id, status)
    return {"ok": True, "plan_id": plan_id, "type": plan_type, "path": str(pd)}


def list_plans(slug: str, state: str = None) -> list[dict]:
    plans_dir = guardian_brain_schema.plans_dir(slug)
    if not plans_dir.exists():
        return []
    result = []
    for pd in sorted(plans_dir.iterdir()):
        if not pd.is_dir():
            continue
        status_file = pd / "status.json"
        if not status_file.exists():
            continue
        try:
            status = json.loads(status_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if state and status.get("state") != state:
            continue
        result.append({
            "plan_id": status["plan_id"], "title": status["title"],
            "type": status.get("type", "full"), "state": status.get("state", "draft"),
            "created_at": status.get("created_at"), "updated_at": status.get("updated_at"),
        })
    return result


def transition(slug: str, plan_id: str, new_state: str) -> dict:
    plan = _read_plan(slug, plan_id)
    if not plan:
        return {"ok": False, "error": f"plan not found: {plan_id}"}
    tcheck = _transition(plan, new_state)
    if not tcheck["ok"]:
        return tcheck
    now_iso = datetime.now(timezone.utc).isoformat()
    plan["state"] = new_state
    plan["updated_at"] = now_iso
    plan.setdefault("history", []).append({"state": new_state, "ts": now_iso})
    _write_status(slug, plan_id, plan)
    return {"ok": True, "plan_id": plan_id, "new_state": new_state}


def verify(slug: str, plan_id: str, results: dict = None) -> dict:
    plan = _read_plan(slug, plan_id)
    if not plan:
        return {"ok": False, "error": "plan not found"}
    if plan.get("state") != "verifying":
        return {"ok": False, "error": f"plan must be in 'verifying' state, is: {plan.get('state')}"}
    if results is None:
        results = {}
    all_ok = all(r.get("ok", False) for r in results.values()) if results else True
    plan["verify_results"] = results
    plan["verify_passed"] = all_ok
    plan["updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_status(slug, plan_id, plan)
    return {"ok": True, "plan_id": plan_id, "verify_passed": all_ok, "results": results}


def archive(slug: str, plan_id: str) -> dict:
    plan = _read_plan(slug, plan_id)
    if not plan:
        return {"ok": False, "error": "plan not found"}
    if plan.get("state") == "archived":
        return {"ok": False, "error": "already archived"}
    pd = _plan_dir(slug, plan_id)
    archive_dir = guardian_brain_schema.brain_dir(slug) / "plans" / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    target = archive_dir / plan_id
    if target.exists():
        shutil.rmtree(target)
    shutil.move(str(pd), str(target))
    learnings_count = 0
    title = plan.get("title", "")
    if title and plan.get("verify_passed") is not False:
        result = guardian_brain.write_governed(slug, "reflection", {
            "kind": "learning",
            "content": f"Plan '{title}' completed successfully",
            "importance": 0.5, "tags": ["plan", plan_id],
            "source": "plan_archive",
        })
        if result.get("ok"):
            learnings_count += 1
    return {
        "ok": True, "plan_id": plan_id,
        "archived_path": str(target), "learnings_extracted": learnings_count,
    }


USAGE = """Guardian Plan — usage:
  new <slug> <title> [--type=full|quick]
  list <slug> [--state=applying|archived|...]
  show <slug> <plan-id>
  specify <slug> <plan-id>
  design <slug> <plan-id>
  tasks <slug> <plan-id>
  apply <slug> <plan-id>
  verify <slug> <plan-id>
  archive <slug> <plan-id>
"""


def main():
    if len(sys.argv) < 2:
        print(USAGE)
        return 1
    cmd = sys.argv[1]
    if cmd == "new":
        if len(sys.argv) < 4:
            print("new requires slug and title")
            return 1
        slug = sys.argv[2]
        title = " ".join(sys.argv[3:])
        plan_type = "full"
        if "--type=full" in sys.argv: plan_type = "full"
        if "--type=quick" in sys.argv: plan_type = "quick"
        result = new_plan(slug, title, plan_type=plan_type)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    if cmd == "list":
        if len(sys.argv) < 3:
            print("list requires slug")
            return 1
        slug = sys.argv[2]
        state = None
        for arg in sys.argv[3:]:
            if arg.startswith("--state="):
                state = arg.split("=", 1)[1]
        result = list_plans(slug, state=state)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    if cmd == "show":
        if len(sys.argv) < 4:
            print("show requires slug and plan-id")
            return 1
        slug, plan_id = sys.argv[2], sys.argv[3]
        result = _read_plan(slug, plan_id)
        print(json.dumps(result, indent=2, ensure_ascii=False) if result else "null")
        return 0
    state_map = {
        "specify": "specs", "design": "designed", "tasks": "tasks",
        "apply": "applying", "verify": "verifying",
    }
    if cmd in state_map:
        if len(sys.argv) < 4:
            print(f"{cmd} requires slug and plan-id")
            return 1
        slug, plan_id = sys.argv[2], sys.argv[3]
        result = transition(slug, plan_id, state_map[cmd])
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    if cmd == "archive":
        if len(sys.argv) < 4:
            print("archive requires slug and plan-id")
            return 1
        slug, plan_id = sys.argv[2], sys.argv[3]
        result = archive(slug, plan_id)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    print(f"Unknown command: {cmd}")
    print(USAGE)
    return 1


if __name__ == "__main__":
    sys.exit(main())
