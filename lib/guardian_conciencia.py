#!/usr/bin/env python3
"""Guardian Conciencia — motor de razonamiento trazable.

La Conciencia es el sistema de razonamiento de Guardian. NO es un LLM.
Lee del brain, no inventa. Cada decisión tiene sources trazables.

Reglas inmutables:
1. Razona en base a lo que sabe, no a lo que se imagina
2. Si no hay datos, INVESTIGA (auto), no ASSUME
3. Si la decisión es riesgosa, WARN con la fuente
4. ASSUME solo con confidence >= threshold Y al menos 1 source
5. El genoma es quien es; el creator es quien lo hizo; el usuario es quien lo usa
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import guardian_brain_advisor as advisor_mod
import guardian_genome
import guardian_shared as shared


VALID_MODES = ("read", "plan", "build", "commit", "review")
DEFAULT_THRESHOLDS = {"assume": 0.8, "ask_little_floor": 0.5, "ask_much_floor": 0.2}
THRESHOLD_KEYS = ["assume", "ask_little_floor", "ask_much_floor"]


class Percept:
    """Lo que la Conciencia percibe de un evento.

    Solo datos reales del brain/genoma/rama. NUNCA inventado.
    """
    def __init__(self, event: dict, who_i_am: str, who_created_me: str, who_is_user: dict,
                 what_i_know: dict, sources: list[str] = None):
        self.event = event
        self.who_i_am = who_i_am
        self.who_created_me = who_created_me
        self.who_is_user = who_is_user
        self.what_i_know = what_i_know
        self.sources = sources or []

    def to_dict(self) -> dict:
        return {
            "event": self.event,
            "who_i_am": self.who_i_am,
            "who_created_me": self.who_created_me,
            "who_is_user": self.who_is_user,
            "what_i_know": self.what_i_know,
            "sources": self.sources,
        }


class Decision:
    """Decisión trazable. Cada decisión tiene sources, reason, confidence."""
    def __init__(self, action: str, reason: str, confidence: float,
                 sources: list[str], mode: str = "plan", risk: str = "low",
                 assumptions: list[str] = None, alternatives: list[str] = None):
        self.action = action
        self.reason = reason
        self.confidence = confidence
        self.sources = sources
        self.mode = mode
        self.risk = risk
        self.assumptions = assumptions or []
        self.alternatives = alternatives or []

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "reason": self.reason,
            "confidence": self.confidence,
            "sources": self.sources,
            "mode": self.mode,
            "risk": self.risk,
            "assumptions": self.assumptions,
            "alternatives": self.alternatives,
        }


class Conciencia:
    """Motor de razonamiento trazable de Guardian.

    Sabe quién es (del genoma), quién lo creó (del genoma), quién es el
    usuario actual (de la rama), y razona con la raíz del proyecto.
    """

    def __init__(self, slug: str = None):
        self.slug = slug
        self.genome = guardian_genome.load_genome()
        self.identity = self.genome.get("identity", {})
        self.creator = self.genome.get("creator") or self.identity.get("creator", "unknown")
        self.who_i_am = self.identity.get("name", "Nexxoria Guardian")
        self.principles = self.identity.get("principles", [])
        # Thresholds from consciousness.yaml (v4) or identity.yaml (v2 fallback)
        cons = self.genome.get("consciousness", {})
        self.thresholds = cons.get("thresholds", self.genome.get("consciousness", {}).get("default_thresholds", {
            "assume": 0.8, "ask_little_floor": 0.5, "ask_much_floor": 0.2
        }))
        # Tracability config (v4)
        self.tracability = cons.get("tracability", {"require_sources_for_assume": True})
        # Identify the user
        self.user = self._identify_user()
        # Current mode
        if slug:
            mode_state = shared.read_mode_state(slug)
            self.mode = mode_state.get("mode", cons.get("default_mode", "plan"))
        else:
            self.mode = cons.get("default_mode", "plan")

    def _identify_user(self) -> dict:
        """Identifica al usuario actual. NO asume si no sabe."""
        import subprocess
        user = {"name": "unknown", "email": "unknown", "source": "none"}
        try:
            r = subprocess.run(["git", "config", "user.email"],
                               capture_output=True, text=True, timeout=2)
            if r.returncode == 0 and r.stdout.strip():
                user["email"] = r.stdout.strip()
                user["source"] = "git"
        except (OSError, subprocess.TimeoutExpired):
            pass
        if user["email"] == "unknown":
            env_user = os.environ.get("USER") or os.environ.get("USERNAME")
            if env_user:
                user["name"] = env_user
                user["source"] = "env"
        return user

    def perceive(self, event: dict) -> Percept:
        """Percibe un evento. Solo lee, no inventa.

        v4 D15: Integra Advisor.build_context() para enriquecer percepción
        con contexto dinámico del brain del proyecto.
        """
        what_i_know = {}
        sources = []
        question = event.get("question", "")
        if self.slug:
            try:
                state = read_state(self.slug)
                what_i_know["conciencia_state"] = {
                    "cycles": len(state.get("cycles", [])),
                    "last_action": state.get("last_action"),
                    "last_confidence": state.get("last_confidence"),
                }
                sources.append(f"conciencia_state:{self.slug}")
            except Exception:
                pass
            # v4 D15: enrich perception with Advisor context (if relevant)
            try:
                adv = advisor_mod.Advisor(self.slug, conciencia=self)
                advisor_ctx = adv.build_context(question, max_tokens=500)
                if advisor_ctx:
                    what_i_know["advisor_context"] = advisor_ctx
                    sources.append(f"advisor:{self.slug}")
            except Exception:
                pass
        return Percept(
            event=event,
            who_i_am=self.who_i_am,
            who_created_me=str(self.creator),
            who_is_user=self.user,
            what_i_know=what_i_know,
            sources=sources,
        )

    def decide(self, percept: Percept) -> Decision:
        """Decide trazable. Si no hay datos suficientes, INVESTIGA."""
        confidence = self._compute_confidence(percept)
        sources = list(percept.sources)
        require_sources = self.tracability.get("require_sources_for_assume", True)
        # ASSUME: only if confidence >= threshold AND has sources (if required)
        if confidence >= self.thresholds.get("assume", 0.8):
            if require_sources and not sources:
                # We have high confidence but no sources: INVESTIGATE
                return Decision(
                    action="investigate",
                    reason=f"High confidence ({confidence:.2f}) but no traceable sources; will auto-explore.",
                    confidence=confidence,
                    sources=sources,
                    mode=self.mode,
                    risk="medium",
                )
            return Decision(
                action="assume",
                reason=f"Confidence {confidence:.2f} >= assume threshold {self.thresholds.get('assume', 0.8)} with traceable sources.",
                confidence=confidence,
                sources=sources,
                mode=self.mode,
                risk="low",
            )
        # ASK_LITTLE: between thresholds
        if confidence >= self.thresholds.get("ask_little_floor", 0.5):
            return Decision(
                action="ask_little",
                reason=f"Confidence {confidence:.2f} in range [ask_little, assume). Will confirm with user.",
                confidence=confidence,
                sources=sources,
                mode=self.mode,
                risk="medium",
            )
        # ASK_MUCH: between thresholds
        if confidence >= self.thresholds.get("ask_much_floor", 0.2):
            return Decision(
                action="ask_much",
                reason=f"Confidence {confidence:.2f} in range [ask_much, ask_little). Will ask user with options.",
                confidence=confidence,
                sources=sources,
                mode=self.mode,
                risk="high",
            )
        # INVESTIGATE: very low confidence
        return Decision(
            action="investigate",
            reason=f"Confidence {confidence:.2f} below ask_much threshold. Will auto-explore to gather more data.",
            confidence=confidence,
            sources=sources,
            mode=self.mode,
            risk="high",
        )

    def _compute_confidence(self, percept: Percept) -> float:
        """Compute confidence based on available data. Heuristic, not LLM.

        Incorporates kNN prediction from past cycles if available.
        """
        score = 0.5  # base
        wk = percept.what_i_know
        if wk.get("conciencia_state", {}).get("cycles", 0) > 0:
            score += 0.1
        if percept.sources:
            score += 0.1
        if wk.get("advisor_context"):
            score += 0.1
        if percept.event.get("context"):
            score += 0.05
        if percept.event.get("explicit_question"):
            score += 0.1

        # v4.5.1: kNN prediction boost
        if self.slug:
            question = percept.event.get("question", "")
            pred = predict_action(self.slug, question, self.mode, score)
            if pred.get("method") == "knn":
                score = pred["confidence"]
                if pred.get("predicted"):
                    percept.sources.append(f"prediction:{pred['predicted']}(sim={len(pred.get('scores', {}))})")

        return min(0.99, max(0.0, score))

    def who_am_i(self) -> dict:
        """Identity block for the Advisor to inject in session.created."""
        return {
            "who_i_am": self.who_i_am,
            "who_created_me": str(self.creator),
            "principles": self.principles[:3] if self.principles else [],
            "user": self.user,
        }

    def run_cycle(self, slug: str, question: str = "", mode: str = None, rag_results=None,
                  context=None, use_brain: bool = True) -> dict:
        """Legacy API kept for backward compatibility.

        Uses Percept + decide() internally and writes state.
        """
        if not slug:
            slug = self.slug
        if slug:
            self.slug = slug
        if mode and mode in VALID_MODES:
            self.mode = mode
        if self.mode not in VALID_MODES:
            self.mode = "plan"
        if use_brain and slug:
            brain_ctx = _load_brain_context(slug, self.mode, question)
            if brain_ctx:
                merged = dict(context) if context else {}
                merged.update(brain_ctx)
                context = merged
        event = {
            "question": question,
            "context": context or {},
            "rag_results": rag_results,
            "mode": self.mode,
        }
        percept = self.perceive(event)
        if context:
            percept.what_i_know["context"] = context
        if rag_results:
            percept.what_i_know["rag"] = {"results": rag_results}
        decision = self.decide(percept)
        if percept.sources:
            for s in percept.sources:
                if s not in decision.sources:
                    decision.sources.append(s)
        # Write state (legacy format)
        state = read_state(slug) if slug else {"cycles": [], "last_action": None, "last_confidence": 0.0}
        cycle = {
            "ts": shared.ts() if hasattr(shared, "ts") else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "mode": self.mode,
            "confidence": round(decision.confidence, 3),
            "action": decision.action,
            "question": question,
        }
        if rag_results:
            cycle["rag_results"] = rag_results[:5] if isinstance(rag_results, list) else []
        if context:
            slim = {k: v for k, v in context.items()
                    if k in ("guardian_md_lines", "has_goal", "has_task", "mode", "project_root")}
            cycle["context_used"] = slim
        state.setdefault("cycles", []).append(cycle)
        state["cycles"] = state["cycles"][-50:]
        state["last_confidence"] = decision.confidence
        state["last_action"] = decision.action
        if hasattr(shared, "ts"):
            state["updated"] = shared.ts()
        if slug:
            write_state(slug, state)
            try:
                save_cycle_as_observation(slug, cycle)
            except Exception:
                pass
        meta = _evolve(slug, state.get("cycles", []), self.thresholds) if slug else None
        prediction = predict_action(slug, question, self.mode, decision.confidence) if slug else {}
        return {
            "slug": slug,
            "mode": self.mode,
            "confidence": round(decision.confidence, 3),
            "action": decision.action,
            "prediction": prediction,
            "state": state,
            "meta": meta,
            "decision": decision.to_dict(),
            "percept": percept.to_dict(),
            "tracable": bool(decision.sources),
        }


# ── State / thresholds ──


def _brain_path(slug: str, *parts: str) -> Path:
    import guardian_brain_schema as schema
    return schema.brain_dir(slug) / "/".join(parts)


DEFAULT_STATE = {"cycles": [], "last_action": None, "last_confidence": 0.0}
DEFAULT_THRESHOLDS = {"assume": 0.8, "ask_little_floor": 0.5, "ask_much_floor": 0.2}


def read_state(slug):
    p = _brain_path(slug, "conciencia-state.json")
    if not p.exists():
        return dict(DEFAULT_STATE)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_STATE)


def write_state(slug, data):
    p = _brain_path(slug, "conciencia-state.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def read_thresholds(slug):
    p = _brain_path(slug, "conciencia-thresholds.json")
    if not p.exists():
        return dict(DEFAULT_THRESHOLDS)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_THRESHOLDS)


def write_thresholds(slug, data):
    p = _brain_path(slug, "conciencia-thresholds.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def save_learning(slug, entry):
    """Save a learning entry to projects/<slug>/learnings/"""
    learn_dir = shared.project_dir(slug) / "learnings"
    learn_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time() * 1000)
    learn_file = learn_dir / f"{ts}.json"
    learn_file.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "path": str(learn_file)}


def score_context(payload):
    question = payload.get("question", "") or ""
    context = payload.get("context") or {}
    rag = payload.get("rag") or {}
    score = 0.5
    if question:
        score += 0.1
    if context.get("has_goal"):
        score += 0.1
    if context.get("has_task"):
        score += 0.1
    if rag.get("results"):
        score += 0.1
    if context.get("guardian_md_lines", 0) > 0:
        score += 0.1
    return min(0.99, max(0.0, score))


def consciousness_action(confidence, mode="plan", thresholds=None):
    th = thresholds or {"assume": 0.8, "ask_little_floor": 0.5, "ask_much_floor": 0.2}
    bonus = th.get(f"{mode}_assume_bonus", 0) or 0
    if confidence + bonus >= th.get("assume", 0.8):
        return "assume"
    if confidence >= th.get("ask_little_floor", 0.5):
        return "ask_little"
    if confidence >= th.get("ask_much_floor", 0.2):
        return "ask_much"
    return "investigate"


def _load_brain_context(slug: str, mode: str, question: str = "") -> dict:
    """Load brain context for the conciencia. Safe import."""
    try:
        import guardian_brain
        return guardian_brain.build_context_for_cycle(slug, mode, question) or {}
    except Exception:
        return {}


def quick_check(slug: str, path: str = "", operation_type: str = "edit",
                mode: str = "plan", rag_results: list = None) -> dict:
    """Quick permission check. Used by backend and CLI.

    Returns dict with allowed, action, confidence, sources.
    """
    try:
        c = Conciencia(slug=slug)
        event = {
            "question": f"permission: {operation_type} {path}",
            "context": {"path": path, "operation": operation_type},
            "explicit_question": True,
        }
        p = c.perceive(event)
        if rag_results:
            p.sources.append(f"rag:{len(rag_results)}_results")
        d = c.decide(p)
        allowed = d.action == "assume" or (d.action == "ask_little" and mode == "build")
        return {
            "allowed": allowed,
            "action": d.action,
            "confidence": round(d.confidence, 2),
            "sources": d.sources,
            "risk": d.risk,
        }
    except Exception:
        return {"allowed": False, "action": "investigate", "confidence": 0.0, "sources": [], "risk": "high"}


def _evolve(slug, cycles, thresholds):
    """Meta-evolution. Returns dict or None."""
    if len(cycles) < 5:
        return None
    last = cycles[-5:]
    avg_conf = sum(c.get("confidence", 0) for c in last) / 5
    if avg_conf < 0.5:
        return {"reasons": ["low avg confidence, lowering assume threshold"], "adjustments": {"assume": -0.05}}
    return None


# Alias for backward compat
evolve = _evolve


# ═══════════════════════════════════════════════════════════════════
# E: Conciencia Predictiva — kNN sobre ciclos pasados (v4.5.1)
# ═══════════════════════════════════════════════════════════════════

def _cycle_to_query_text(cycle: dict) -> str:
    """Convert a cycle to a searchable text for embedding similarity."""
    parts = [
        cycle.get("action", ""),
        cycle.get("mode", ""),
        cycle.get("question", ""),
    ]
    return " | ".join(parts)


def predict_action(slug: str, question: str, mode: str = "plan",
                   confidence: float = 0.5) -> dict:
    """Predict the best action using kNN over past cycles stored in brain.

    Returns dict with predicted_action, confidence, similar_cycles.
    Falls back to consciousness_action() if not enough data.
    """
    try:
        import guardian_brain as brain

        query_text = f"cycle: {mode} {question}"
        q_emb = brain.embed(query_text)

        # Search in semantic DB for past cycles stored as observations
        similar = brain.query(slug, "semantic", query_text, top_k=5,
                              min_similarity=0.15)

        if not similar:
            return {"predicted": None, "confidence": confidence,
                    "similar": 0, "method": "fallback"}

        # Weight action predictions by similarity
        action_scores = {}
        for n in similar:
            sim = n.get("similarity", 0)
            action = n.get("content", "").split(" | ")[0] if " | " in n.get("content", "") else ""
            if action and sim > 0.2:
                action_scores[action] = action_scores.get(action, 0) + sim

        if not action_scores:
            return {"predicted": None, "confidence": confidence,
                    "similar": len(similar), "method": "fallback"}

        best_action = max(action_scores, key=action_scores.get)
        best_score = action_scores[best_action]
        # Scale prediction influence: more similar cycles = stronger signal
        prediction_boost = min(0.15, best_score * 0.1)

        return {
            "predicted": best_action,
            "confidence": min(0.99, confidence + prediction_boost),
            "similar": len(similar),
            "scores": action_scores,
            "method": "knn",
        }
    except Exception:
        return {"predicted": None, "confidence": confidence,
                "similar": 0, "method": "fallback"}


def save_cycle_as_observation(slug: str, cycle: dict) -> None:
    """Store a cycle in the brain for future predictions."""
    try:
        import guardian_brain as brain
        content = _cycle_to_query_text(cycle)
        brain.write_observation(
            slug=slug,
            obs_type="cycle",
            topic_key=f"cycle/{cycle.get('action', 'unknown')}",
            content=content[:200],
            why=f"auto: conciencia cycle in {cycle.get('mode', 'plan')} mode",
            outcome="info",
            scope="project",
            tags=["conciencia_cycle", cycle.get("action", ""), cycle.get("mode", "")],
        )
    except Exception:
        pass


# ── Module-level API (backward compat) ────────────────────────────


def run_cycle(slug, question="", mode="plan", rag_results=None, context=None, use_brain=True):
    """Backward compat: module-level function. Creates a Conciencia and runs cycle."""
    con = Conciencia(slug=slug)
    if mode and mode in VALID_MODES:
        con.mode = mode
    return con.run_cycle(slug, question=question, mode=mode, rag_results=rag_results,
                          context=context, use_brain=use_brain)
