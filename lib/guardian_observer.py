#!/usr/bin/env python3
"""Guardian Observer — captura eventos y los procesa.

Regla: cada cosa guardada se procesa. NO se acumula raw.
Procesa y guarda en el brain del proyecto (la raíz).
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from pathlib import Path

import guardian_brain_schema as schema
import guardian_shared as shared


# ── Secret sanitizer (v4) ────────────────────────────────────────

_SECRET_PATTERNS = [
    (re.compile(r'(?i)(api[_-]?key|secret|token|password|passwd|pwd)["\s:=]+["\']?([A-Za-z0-9+/=_\-]{16,})'), "[REDACTED]"),
    (re.compile(r'(?i)(sk-[A-Za-z0-9]{20,})'), "[REDACTED]"),
    (re.compile(r'(?i)(ghp_[A-Za-z0-9]{20,})'), "[REDACTED]"),
    (re.compile(r'(?i)(xox[abp]-[A-Za-z0-9-]{10,})'), "[REDACTED]"),
    (re.compile(r'eyJ[A-Za-z0-9_=]+\.eyJ[A-Za-z0-9_=]+\.?[A-Za-z0-9_.+/=]*'), "[REDACTED_JWT]"),
    (re.compile(r'(?i)bearer\s+[A-Za-z0-9._\-]{20,}'), "Bearer [REDACTED]"),
    (re.compile(r'(?i)postgres://[^:]+:[^@]+@'), "postgres://[REDACTED]@"),
    (re.compile(r'(?i)mysql://[^:]+:[^@]+@'), "mysql://[REDACTED]@"),
]


def sanitize(text: str) -> str:
    """Remove secrets from text using regex patterns. Conservative."""
    if not text:
        return text
    out = text
    for pat, repl in _SECRET_PATTERNS:
        out = pat.sub(repl, out)
    return out


# ── Event bus (in-process pub/sub) ────────────────────────────────

_subscribers: dict[str, list] = {}


def subscribe(event_type: str, handler):
    """Subscribe a handler to an event type."""
    _subscribers.setdefault(event_type, []).append(handler)


def publish(event_type: str, payload: dict) -> None:
    """Publish an event. All subscribers are called."""
    for handler in _subscribers.get(event_type, []):
        try:
            handler(event_type, payload)
        except Exception:
            pass


def reset_subscribers() -> None:
    """Reset all subscribers (for tests)."""
    _subscribers.clear()


# ── Event classification ─────────────────────────────────────────

def classify_event(event: dict) -> str:
    """Classify an event into a brain level. Returns 'data' or 'pattern'."""
    etype = event.get("type", "")
    if etype in ("chat.message", "tool.execute.after", "file.change", "test.run",
                 "git.commit", "stack.change"):
        return "data"
    if etype in ("pattern.detected", "new.capability", "new.model"):
        return "pattern"
    return "data"


def infer_reason_from_prompt(prompt: str) -> str:
    """Infer why the user is asking this. Heuristic."""
    p = prompt.lower().strip()
    if any(p.startswith(k) or f" {k}" in p for k in ("agreg", "creá", "crear", "implement", "implementá",
                                                        "construí", "construir", "hacé", "hacer",
                                                        "add ", "create ", "build ", "implement ")):
        return "add_feature"
    if any(k in p for k in ("fix", "bug", "error", "no funciona", "broken", "arreglá", "arreglar")):
        return "fix_bug"
    if any(k in p for k in ("refactor", "clean", "improve", "mejorá", "mejorar")):
        return "refactor"
    if any(k in p for k in ("borrá", "borrar", "eliminá", "eliminar", "delete ", "remove ")):
        return "destructive"
    if p.endswith("?"):
        return "question"
    return "other"


TOPIC_PATTERNS = [
    # (keywords, topic_key)
    (["migr", "db", "database", "base de datos", "postgres", "mysql", "sql"], "db/migration"),
    (["auth", "jwt", "login", "sesión", "token", "oauth"], "auth/jwt"),
    (["api", "endpoint", "route", "rest"], "api/endpoint"),
    (["deploy", "ci", "cd", "release", "desplieg"], "deploy/ci"),
    (["test", "pytest", "testing"], "test/testing"),
    (["docker", "container", "imagen"], "deploy/docker"),
    (["error", "bug", "fallo", "crash"], "bugfix/general"),
    (["refactor", "clean", "mejor"], "refactor/general"),
    (["security", "seguridad", "vuln"], "security/general"),
    (["config", "configuraci", "setup"], "config/setup"),
    (["cache", "redis", "memcach"], "performance/cache"),
    (["search", "búsqueda", "buscar", "find"], "feature/search"),
]


def extract_topic_key(prompt: str, slug: str = None) -> str:
    """Extrae topic_key del prompt. Usa kNN neural si hay data, fallback heurística."""
    if slug:
        neural = classify_topic_neural(prompt, slug)
        if neural:
            return neural
    p = prompt.lower()
    scores = []
    for keywords, topic in TOPIC_PATTERNS:
        score = 0
        for k in keywords:
            if len(k) <= 2:
                if k in p.split():
                    score += 1
            else:
                if k in p:
                    score += 1
        if score > 0:
            scores.append((score, topic))
    if not scores:
        return ""
    scores.sort(reverse=True)
    return scores[0][1]


def _heuristic_importance(prompt: str, event_type: str = "chat.message") -> float:
    """Heurística de importancia (base, sin neural)."""
    score = 0.3
    if event_type == "tool.execute.after":
        return 0.6
    if event_type == "chat.message":
        length = len(prompt.strip())
        if length > 200:
            score += 0.2
        elif length > 80:
            score += 0.1
        p = prompt.lower()
        high_impact = ["migr", "deploy", "security", "arquitectur", "refactor",
                       "reestructur", "cambi", "change", "architecture"]
        medium_impact = ["agreg", "crear", "fix", "error", "bug", "test", "config",
                         "implement", "añad", "feature", "nuev"]
        for kw in high_impact:
            if kw in p:
                score += 0.15
                break
        for kw in medium_impact:
            if kw in p:
                score += 0.08
                break
        if extract_topic_key(prompt):
            score += 0.05
    return min(1.0, max(0.0, score))


def classify_importance(prompt: str, event_type: str = "chat.message", slug: str = None) -> float:
    """Clasifica importancia de un evento (0.0 - 1.0).

    Usa kNN neural si hay datos, fallback heurística.
    """
    if slug:
        return classify_importance_neural(prompt, event_type, slug)
    return _heuristic_importance(prompt, event_type)


# ── Storage helpers ───────────────────────────────────────────────

def _event_log_db(slug: str) -> Path:
    return schema.brain_db_path(slug, "semantic")


def log_event(slug: str, event_type: str, payload: dict) -> int:
    """Persist an event to event_log table. Returns id."""
    db = _event_log_db(slug)
    if not db.exists():
        schema.init_project(slug)
    con = sqlite3.connect(str(db))
    try:
        cur = con.execute(
            "INSERT INTO event_log (ts, event_type, payload, project_slug) VALUES (?, ?, ?, ?)",
            (time.time(), event_type, json.dumps(payload, ensure_ascii=False, default=str), slug),
        )
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


def log_prompt(slug: str, prompt: str, reason: str, mode: str, files: list = None) -> int:
    """Persist a user prompt to prompt_log. Sanitized."""
    db = _event_log_db(slug)
    if not db.exists():
        schema.init_project(slug)
    safe = sanitize(prompt)
    safe_reason = sanitize(reason)
    con = sqlite3.connect(str(db))
    try:
        cur = con.execute(
            "INSERT INTO prompt_log (ts, prompt, reason_inferred, mode, files_in_context, outcome) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (time.time(), safe, safe_reason, mode, json.dumps(files or []), None),
        )
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


def log_decision(slug: str, decision: str, why: str, alternatives: list = None) -> int:
    """Persist a technical decision."""
    db = _event_log_db(slug)
    if not db.exists():
        schema.init_project(slug)
    safe_decision = sanitize(decision)
    safe_why = sanitize(why)
    con = sqlite3.connect(str(db))
    try:
        cur = con.execute(
            "INSERT INTO decision_log (ts, decision, why, alternatives, project_slug) "
            "VALUES (?, ?, ?, ?, ?)",
            (time.time(), safe_decision, safe_why,
             json.dumps(alternatives or []), slug),
        )
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


def log_stack_change(slug: str, runner: str, packages: dict) -> int:
    """Persist a stack change (from pyproject.toml, package.json, etc.)."""
    db = _event_log_db(slug)
    if not db.exists():
        schema.init_project(slug)
    safe_runner = sanitize(runner)
    con = sqlite3.connect(str(db))
    try:
        cur = con.execute(
            "INSERT INTO stack_history (ts, runner, packages, project_slug) VALUES (?, ?, ?, ?)",
            (time.time(), safe_runner, json.dumps(packages, default=str), slug),
        )
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


def log_test_result(slug: str, runner: str, passed: int, failed: int,
                    duration_s: float, output: str = "") -> int:
    """Persist a test run result."""
    db = _event_log_db(slug)
    if not db.exists():
        schema.init_project(slug)
    safe_output = sanitize(output or "")[:5000]
    con = sqlite3.connect(str(db))
    try:
        cur = con.execute(
            "INSERT INTO test_results (ts, runner, passed, failed, duration_s, output, project_slug) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (time.time(), runner, passed, failed, duration_s, safe_output, slug),
        )
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


# ── Observer class ───────────────────────────────────────────────

class Observer:
    """Captura eventos y los procesa. Lo que es dato va al brain. Lo que es pattern se propone al genoma."""

    def __init__(self, slug: str):
        self.slug = slug
        self.events_seen = 0

    def observe(self, event: dict) -> None:
        """Main entry point. Process and route the event."""
        etype = event.get("type", "")
        kind = classify_event(event)
        # Always log raw event
        log_event(self.slug, etype, event)
        self.events_seen += 1
        # Route to specific handler
        if etype == "chat.message":
            self._on_prompt(event)
        elif etype == "tool.execute.after":
            self._on_tool_after(event)
        elif etype == "test.run":
            self._on_test_run(event)
        elif etype == "stack.change":
            self._on_stack_change(event)
        elif etype == "file.change":
            self._on_file_change(event)
        elif etype in ("pattern.detected", "new.capability", "new.model"):
            # Pattern: propose to genome (NOT to the user branch directly)
            self._propose_pattern(event)
        # Publish to subscribers
        publish(etype, event)

    def _on_prompt(self, event: dict) -> None:
        prompt = event.get("prompt", "")
        reason = infer_reason_from_prompt(prompt)
        files = event.get("files_in_context") or []
        log_prompt(self.slug, prompt, reason, event.get("mode", ""),
                   files=files)
        imp = classify_importance(prompt, "chat.message", slug=self.slug)
        if imp > 0.5:
            try:
                import guardian_brain as brain
                topic_key = extract_topic_key(prompt, slug=self.slug)
                brain.write_observation(
                    slug=self.slug,
                    obs_type="pattern" if topic_key else "note",
                    topic_key=topic_key or "general",
                    content=prompt[:200],
                    why=reason,
                    where=", ".join(files) if files else "",
                    outcome="info",
                    scope="project",
                    tags=[reason] if reason else [],
                )
            except Exception:
                pass

    def _on_tool_after(self, event: dict) -> None:
        tool = event.get("tool", "")
        if tool in ("Edit", "Write"):
            self._on_file_change(event)
        elif tool == "Bash":
            args = event.get("args", "") or ""
            if any(k in args for k in ("pytest", "npm test", "jest", "go test", "vitest")):
                self._on_test_run(event)
            elif any(k in args for k in ("pip install", "npm install", "go get", "cargo add")):
                self._on_stack_change(event)

    def _on_file_change(self, event: dict) -> None:
        file_path = event.get("file", "")
        if not file_path:
            return
        # Detect if it's a stack file
        if any(s in str(file_path) for s in ("pyproject.toml", "package.json", "go.mod", "Cargo.toml", "requirements.txt")):
            self._on_stack_change({"packages": {file_path: event.get("content", "")}, "file": file_path})

    def _on_test_run(self, event: dict) -> None:
        log_test_result(
            self.slug,
            runner=event.get("runner", "unknown"),
            passed=event.get("passed", 0),
            failed=event.get("failed", 0),
            duration_s=event.get("duration_s", 0.0),
            output=event.get("output", ""),
        )

    def _on_stack_change(self, event: dict) -> None:
        log_stack_change(
            self.slug,
            runner=event.get("runner", "unknown"),
            packages=event.get("packages", {}),
        )

    def _propose_pattern(self, event: dict) -> None:
        """Patterns go to the project's evolution proposals."""
        import guardian_genome
        import guardian_shared as shared
        branch = shared.project_dir(self.slug)
        guardian_genome.accept_user_proposal(branch, {
            "kind": event.get("type", "pattern"),
            "content": event.get("content", ""),
            "why": event.get("why", ""),
            "ts": time.time(),
        })


# ── Module-level helpers ──────────────────────────────────────────

def get_observer(slug: str) -> Observer:
    return Observer(slug)


# ── Sanitizer exposed for tests ──────────────────────────────────

def _test_sanitize():
    """Test entrypoint: returns the sanitizer without side effects."""
    return sanitize


# ═══════════════════════════════════════════════════════════════════
# Neural Classifier — kNN sobre embeddings (Opción B)
# ═══════════════════════════════════════════════════════════════════

_KNN_CACHE = {"topics": [], "topic_labels": [], "examples": []}


def _ensure_knn_data(slug: str = None):
    """Load known topics + examples from brain. Lazy, cached."""
    if _KNN_CACHE["topic_labels"] and slug is None:
        return
    if not slug:
        return
    try:
        import guardian_brain as brain
        nodes = brain.list_nodes(slug, "semantic", filters={"min_importance": 0.4},
                                  limit=200, include_embedding=True)
        topics = {}
        for n in nodes:
            tk = n.get("topic_key") or ""
            if tk and tk != "general":
                emb = n.get("embedding")
                if emb:
                    topics.setdefault(tk, []).append(emb)
        _KNN_CACHE["topics"] = list(topics.keys())
        _KNN_CACHE["topic_labels"] = _KNN_CACHE["topics"]
        _KNN_CACHE["examples"] = topics
    except Exception:
        pass


def classify_topic_neural(prompt: str, slug: str = None) -> str:
    """Classify prompt topic using kNN over brain embeddings.

    Falls back to heuristic extract_topic_key() if not enough data.
    """
    _ensure_knn_data(slug)
    if not _KNN_CACHE["topic_labels"] or len(_KNN_CACHE["examples"]) < 3:
        return extract_topic_key(prompt)

    try:
        import guardian_brain as brain
        q_emb = brain.embed(prompt)

        best_topic = ""
        best_sim = 0.1
        for topic, embs in _KNN_CACHE["examples"].items():
            sims = brain.cosine_bulk(q_emb, embs)
            if sims:
                avg = sum(sims) / len(sims)
                if avg > best_sim:
                    best_sim = avg
                    best_topic = topic

        if best_topic:
            return best_topic
    except Exception:
        pass
    return extract_topic_key(prompt)


def classify_importance_neural(prompt: str, event_type: str = "chat.message",
                                slug: str = None) -> float:
    """Classify importance using embedding similarity + heuristics.

    Uses the most similar known node's importance as a base, then adjusts.
    """
    base = _heuristic_importance(prompt, event_type)

    try:
        import guardian_brain as brain
        q_emb = brain.embed(prompt)
        sim_nodes = brain.query(slug, "semantic", prompt, top_k=3, min_similarity=0.3) if slug else []

        if sim_nodes:
            sim_imps = [n.get("importance", 0.5) for n in sim_nodes]
            avg_sim = sum(n.get("similarity", 0) for n in sim_nodes) / len(sim_nodes)
            avg_imp = sum(sim_imps) / len(sim_imps)
            blend = avg_sim * avg_imp + (1 - avg_sim) * base
            return min(1.0, max(0.0, blend))
    except Exception:
        pass
    return base


def record_feedback(slug: str, prompt: str, correct_topic: str, correct_importance: float = None):
    """Record user feedback so the neural classifier can learn.

    Stores as a new observation in the brain so next kNN query benefits.
    """
    try:
        import guardian_brain as brain
        brain.write_observation(
            slug=slug,
            obs_type="classification_example",
            topic_key=correct_topic,
            content=prompt[:200],
            why="user_feedback",
            outcome="info",
            scope="project",
            tags=["knn_training"],
        )
    except Exception:
        pass
