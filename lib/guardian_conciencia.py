from __future__ import annotations

import json
from pathlib import Path

import guardian_rag
import guardian_shared as shared
import guardian_genome


DEFAULT_THRESHOLDS = {
    "assume": 0.8,
    "ask_little_floor": 0.5,
    "ask_much_floor": 0.2,
    "advisory": True,
    "plan_assume_bonus": -0.1,
    "build_assume_bonus": 0.1,
}
THRESHOLD_KEYS = ["assume", "ask_little_floor", "ask_much_floor"]


def _conciencia_path(slug):
    """Path to conciencia cycles within the branch (fallback to legacy)."""
    new_path = shared.branch_path_for(slug, "consciousness", "cycles.json")
    if new_path.exists():
        return new_path
    legacy = shared.MEMORY_DIR / slug / "conciencia-state.json"
    if legacy.exists():
        return legacy
    return new_path


def _thresholds_path(slug):
    """Path to thresholds within the branch (fallback to legacy)."""
    new_path = shared.branch_path_for(slug, "consciousness", "thresholds.json")
    if new_path.exists():
        return new_path
    legacy = shared.MEMORY_DIR / slug / "conciencia-thresholds.json"
    if legacy.exists():
        return legacy
    return new_path


def _learnings_dir(slug):
    """Path to learnings within the branch (fallback to legacy)."""
    new_path = shared.branch_path_for(slug, "learnings")
    if new_path.exists():
        return new_path
    legacy = shared.MEMORY_DIR / slug / "learnings"
    if legacy.exists():
        return legacy
    return new_path


def read_state(slug):
    path = _conciencia_path(slug)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"cycles": [], "last_confidence": 0.0, "last_action": None}


def write_state(slug, data):
    path = _conciencia_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def read_thresholds(slug):
    path = _thresholds_path(slug)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        for k in DEFAULT_THRESHOLDS:
            data.setdefault(k, DEFAULT_THRESHOLDS[k])
        return data
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return dict(DEFAULT_THRESHOLDS)


def write_thresholds(slug, data):
    path = _thresholds_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def save_learning(slug, entry):
    d = _learnings_dir(slug)
    d.parent.mkdir(parents=True, exist_ok=True)
    d.mkdir(exist_ok=True)
    ts = shared.ts()
    fname = ts.replace(":", "-")[:19] + ".json"
    (d / fname).write_text(
        json.dumps({"ts": ts, **entry}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    existing = sorted(d.glob("*.json"))
    for p in existing[:-50]:
        p.unlink()


# ── Nivel 1: Ciclo operativo ─────────────────────────────────


def score_context(payload):
    context = payload.get("context") or {}
    query = str(payload.get("question") or payload.get("query") or "").strip()
    rag = payload.get("rag") or {}
    signals = []
    if query:
        signals.append(min(0.35, len(query) / 200.0))
    if isinstance(context, dict):
        if context.get("mode") in ("plan", "build"):
            signals.append(0.1)
        if context.get("project_root"):
            signals.append(0.1)
        if context.get("memory_count"):
            signals.append(min(0.15, context.get("memory_count", 0) / 40.0))
        if context.get("relevant_skills_count"):
            signals.append(min(0.15, context.get("relevant_skills_count", 0) / 20.0))
    results = rag.get("results") if isinstance(rag, dict) else []
    if isinstance(results, list) and results:
        top = max(float(item.get("score", 0.0)) for item in results[:5])
        signals.append(min(0.35, top))
    confidence = max(0.0, min(1.0, sum(signals)))
    return confidence


def consciousness_action(confidence, mode="plan", thresholds=None):
    if thresholds is None:
        thresholds = DEFAULT_THRESHOLDS
    bonus = thresholds.get("build_assume_bonus" if mode == "build" else "plan_assume_bonus", 0)
    adj = round(confidence + bonus, 2)
    if adj >= thresholds.get("assume", 0.8):
        return "assume"
    if adj >= thresholds.get("ask_little_floor", 0.5):
        return "ask_little"
    if adj >= thresholds.get("ask_much_floor", 0.2):
        return "ask_much"
    return "investigate"


def run_cycle(slug, question="", mode="plan", rag_results=None, context=None):
    confidence = score_context({
        "question": question,
        "mode": mode,
        "rag": {"results": rag_results} if rag_results else {},
        "context": context or {},
    })
    thresholds = read_thresholds(slug)
    action = consciousness_action(confidence, mode, thresholds)
    state = read_state(slug)
    cycle = {
        "ts": shared.ts(),
        "mode": mode,
        "confidence": round(confidence, 3),
        "action": action,
        "question": question,
    }
    if rag_results:
        cycle["rag_results"] = rag_results[:5] if isinstance(rag_results, list) else []
    state.setdefault("cycles", []).append(cycle)
    state["cycles"] = state["cycles"][-50:]
    state["last_confidence"] = confidence
    state["last_action"] = action
    state["updated"] = shared.ts()
    write_state(slug, state)
    # N2 auto
    meta = evolve(slug, state.get("cycles", []), thresholds)
    return {
        "slug": slug,
        "mode": mode,
        "confidence": round(confidence, 3),
        "action": action,
        "state": state,
        "meta": meta,
    }


# ── Nivel 2: Meta-evolución ───────────────────────────────────


def evolve(slug, cycles, thresholds):
    if len(cycles) < 5:
        return None
    recent = cycles[-20:]
    total = len(recent)
    if total < 5:
        return None

    action_counts = {}
    confidences_by_action = {}
    for c in recent:
        a = c.get("action", "unknown")
        action_counts[a] = action_counts.get(a, 0) + 1
        confidences_by_action.setdefault(a, []).append(c.get("confidence", 0.0))

    adjustments = {}
    reasons = []

    assume_confs = confidences_by_action.get("assume", [])
    if assume_confs:
        avg_assume = sum(assume_confs) / len(assume_confs)
        margin = avg_assume - thresholds["assume"]
        if margin < 0.05 and len(assume_confs) >= 3:
            adjustments["assume"] = round(thresholds["assume"] + 0.05, 2)
            reasons.append(f"assume avg {avg_assume:.2f} too close to threshold")

    investigate_confs = confidences_by_action.get("investigate", [])
    if investigate_confs:
        avg_investigate = sum(investigate_confs) / len(investigate_confs)
        if avg_investigate > thresholds["ask_much_floor"] + 0.1 and len(investigate_confs) >= 3:
            adjustments["ask_much_floor"] = round(thresholds["ask_much_floor"] + 0.05, 2)
            reasons.append(f"investigate avg {avg_investigate:.2f} above floor")

    if total >= 10:
        assume_pct = action_counts.get("assume", 0) / total
        investigate_pct = action_counts.get("investigate", 0) / total
        if assume_pct > 0.7:
            adjustments["assume"] = round(thresholds["assume"] + 0.05, 2)
            reasons.append(f"assume rate {assume_pct:.0%} too high")
        if investigate_pct > 0.4:
            adjustments["ask_much_floor"] = round(max(0.05, thresholds["ask_much_floor"] - 0.05), 2)
            reasons.append(f"investigate rate {investigate_pct:.0%} too high")

    if not adjustments:
        return None

    for k in THRESHOLD_KEYS:
        thresholds[k] = round(max(0.0, min(1.0, adjustments.get(k, thresholds[k]))), 2)

    write_thresholds(slug, thresholds)

    entry = {
        "type": "meta_evolution",
        "adjustments": adjustments,
        "thresholds": {k: thresholds[k] for k in THRESHOLD_KEYS},
        "reasons": reasons,
        "action_distribution": action_counts,
        "total_cycles_analyzed": total,
    }
    save_learning(slug, entry)
    return entry
