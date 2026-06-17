#!/usr/bin/env python3
"""
Guardian Capability — model card and routing.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import guardian_shared as shared


CAP_DIR = shared.BACKEND_DIR / "capability"
MODEL_CARDS_DIR = CAP_DIR / "model_cards"
TASK_HISTORY_DIR = CAP_DIR / "task_history"

DEFAULT_MODEL = "guardian-default"

TASK_TYPES = (
    "code_generation", "code_review", "research", "planning",
    "debugging", "refactoring",
)

DEFAULT_METRICS = {
    "task_success_rate": {t: 0.5 for t in TASK_TYPES},
    "context_utilization": 0.5,
    "compaction_resistance": 0.5,
    "knowledge_application": 0.5,
    "mode_adherence": 0.5,
    "drift_score": 0.25,
}

DEFAULT_CTX = {
    "comfortable": 50000,
    "max_useful": 120000,
    "degraded": 180000,
}


def _ensure_dirs():
    CAP_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_CARDS_DIR.mkdir(parents=True, exist_ok=True)
    TASK_HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def _card_path(model: str = DEFAULT_MODEL) -> Path:
    _ensure_dirs()
    return MODEL_CARDS_DIR / f"{model}.json"


def load_card(model: str = DEFAULT_MODEL) -> dict:
    p = _card_path(model)
    if not p.exists():
        return {
            "model": model, "version": "1.0", "measured_at": None, "sample_size": 0,
            "metrics": json.loads(json.dumps(DEFAULT_METRICS)),
            "context_window_recommendation": dict(DEFAULT_CTX),
        }
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return load_card(model)


def save_card(card: dict) -> dict:
    p = _card_path(card["model"])
    card["measured_at"] = time.time()
    p.write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "path": str(p)}


def record_outcome(task_type: str, success: bool, drift_score: float = None,
                   context_size: int = None, model: str = DEFAULT_MODEL) -> dict:
    if task_type not in TASK_TYPES:
        return {"ok": False, "error": f"unknown task type: {task_type}"}
    card = load_card(model)
    alpha = 0.1
    old_rate = card["metrics"]["task_success_rate"].get(task_type, 0.5)
    new_rate = old_rate * (1 - alpha) + (1.0 if success else 0.0) * alpha
    card["metrics"]["task_success_rate"][task_type] = round(new_rate, 4)
    if drift_score is not None:
        old_drift = card["metrics"]["drift_score"]
        card["metrics"]["drift_score"] = round(old_drift * (1 - alpha) + drift_score * alpha, 4)
    card["sample_size"] += 1
    save_card(card)
    _log_outcome(task_type, success, drift_score, context_size, model)
    if new_rate < old_rate - 0.1:
        return {
            "ok": True, "alert": "model_degradation",
            "task_type": task_type,
            "old_rate": old_rate, "new_rate": new_rate,
        }
    return {"ok": True, "new_rate": new_rate, "sample_size": card["sample_size"]}


def _log_outcome(task_type: str, success: bool, drift: float, ctx: int, model: str):
    today = time.strftime("%Y-%m-%d")
    log_path = TASK_HISTORY_DIR / f"{today}.jsonl"
    entry = {
        "ts": time.time(), "model": model, "task_type": task_type,
        "success": success, "drift": drift, "context_size": ctx,
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def routing_decision(task_type: str, context_size: int = 0,
                      complexity: str = "medium", model: str = DEFAULT_MODEL) -> dict:
    card = load_card(model)
    success_rate = card["metrics"]["task_success_rate"].get(task_type, 0.5)
    ctx_rec = card.get("context_window_recommendation", DEFAULT_CTX)

    if success_rate < 0.5:
        if complexity == "high":
            return {
                "delegate": False,
                "reason": f"model success_rate too low ({success_rate:.2f}) for high-complexity task",
                "alternative": "ask_user_for_more_context",
            }
        return {
            "delegate": False,
            "reason": f"model success_rate too low ({success_rate:.2f})",
            "alternative": "decompose_task",
        }

    if context_size > ctx_rec["degraded"]:
        return {
            "delegate": True,
            "warning": "context_too_large",
            "recommendation": "compact_before_execution",
            "context_budget": {
                "target": ctx_rec["comfortable"],
                "degraded_at": ctx_rec["degraded"],
            },
        }

    return {
        "delegate": True,
        "context_budget": {
            "comfortable": ctx_rec["comfortable"],
            "max_useful": ctx_rec["max_useful"],
        },
    }


def benchmark(model: str = DEFAULT_MODEL) -> dict:
    card = load_card(model)
    results = {}
    for task in TASK_TYPES:
        results[task] = {
            "current_rate": card["metrics"]["task_success_rate"][task],
            "sample_size": card["sample_size"],
        }
    return {
        "ok": True, "model": model, "results": results,
        "note": "Zero-deps benchmark: returns current model card metrics",
    }


def history(model: str = DEFAULT_MODEL, days: int = 7) -> dict:
    _ensure_dirs()
    entries = []
    cutoff = time.time() - (days * 86400)
    for log_path in sorted(TASK_HISTORY_DIR.glob("*.jsonl"), reverse=True):
        try:
            for line in log_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                entry = json.loads(line)
                if entry.get("ts", 0) >= cutoff and entry.get("model") == model:
                    entries.append(entry)
        except (json.JSONDecodeError, OSError):
            continue
    return {
        "model": model, "days": days, "total": len(entries),
        "by_task": {}, "entries": entries[-50:],
    }


USAGE = """Guardian Capability — usage:
  status
  measure <task-type> [--success] [--drift=N] [--context=N]
  benchmark
  routing <task-type> [--context=N] [--complexity=low|medium|high]
  history [--days=N]
"""


def main():
    if len(sys.argv) < 2:
        print(USAGE)
        return 1
    cmd = sys.argv[1]
    if cmd == "status":
        card = load_card()
        print(json.dumps(card, indent=2, ensure_ascii=False))
        return 0
    if cmd == "measure":
        if len(sys.argv) < 3:
            print("measure requires task-type")
            return 1
        task_type = sys.argv[2]
        success = "--success" in sys.argv
        drift = None
        ctx = None
        for arg in sys.argv[3:]:
            if arg.startswith("--drift="):
                drift = float(arg.split("=", 1)[1])
            elif arg.startswith("--context="):
                ctx = int(arg.split("=", 1)[1])
        result = record_outcome(task_type, success, drift_score=drift, context_size=ctx)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    if cmd == "benchmark":
        print(json.dumps(benchmark(), indent=2, ensure_ascii=False))
        return 0
    if cmd == "routing":
        if len(sys.argv) < 3:
            print("routing requires task-type")
            return 1
        task_type = sys.argv[2]
        ctx = 0
        complexity = "medium"
        for arg in sys.argv[3:]:
            if arg.startswith("--context="):
                ctx = int(arg.split("=", 1)[1])
            elif arg.startswith("--complexity="):
                complexity = arg.split("=", 1)[1]
        decision = routing_decision(task_type, context_size=ctx, complexity=complexity)
        print(json.dumps(decision, indent=2, ensure_ascii=False))
        return 0
    if cmd == "history":
        days = 7
        for arg in sys.argv[2:]:
            if arg.startswith("--days="):
                days = int(arg.split("=", 1)[1])
        print(json.dumps(history(days=days), indent=2, ensure_ascii=False))
        return 0
    print(f"Unknown command: {cmd}")
    print(USAGE)
    return 1


if __name__ == "__main__":
    sys.exit(main())
