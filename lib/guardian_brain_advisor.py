#!/usr/bin/env python3
"""Guardian Brain Advisor — inyecta solo lo necesario al LLM.

Regla: si no hay nada relevante, retorna "".
Regla: NUNCA ensucia la ventana de contexto.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Optional

import guardian_brain_schema as schema
import guardian_brain_symbols as symbols
import guardian_conciencia as conciencia_mod
import guardian_shared as shared


# Approximate: 1 token ~ 4 chars
_CHARS_PER_TOKEN = 4


def _approx_tokens(s: str) -> int:
    return len(s) // _CHARS_PER_TOKEN


def _trim_to_tokens(s: str, max_tokens: int) -> str:
    max_chars = max_tokens * _CHARS_PER_TOKEN
    if len(s) <= max_chars:
        return s
    return s[:max_chars] + "\n[truncated]"


# ── Advisor class ───────────────────────────────────────────────

class Advisor:
    """Lee la raíz del proyecto y la rama del usuario, sugiere al LLM.

    Si no hay nada relevante, retorna "" (no inyecta).
    """

    def __init__(self, slug: str, conciencia=None):
        self.slug = slug
        self.conciencia = conciencia
        try:
            self.genome = shared.GENOME if hasattr(shared, "GENOME") else None
        except Exception:
            self.genome = None
        if self.conciencia is None:
            try:
                self.conciencia = conciencia_mod.Conciencia(slug=slug)
            except Exception:
                self.conciencia = None

    def _is_relevant(self, prompt: str) -> bool:
        """Heuristic: when is the prompt relevant to project history?"""
        if not prompt or len(prompt.strip()) < 3:
            return False
        keywords = (
            "auth", "test", "build", "fix", "deploy", "config", "schema",
            "model", "api", "endpoint", "function", "class", "module",
            "jwt", "auth", "user", "session", "data", "migration",
            "dependenc", "package", "lib", "import", "error", "bug",
            "refactor", "performance", "slow", "fast", "test", "spec",
        )
        p = prompt.lower()
        return any(k in p for k in keywords)

    def build_context(self, prompt: str, max_tokens: int = 1000) -> str:
        """Build dynamic context for session.created or chat.message.

        Returns "" if nothing relevant.
        Maximum max_tokens (1 token ~ 4 chars).
        """
        parts = []
        # 1. Identity block (always small, only first time)
        if self.conciencia:
            wai = self.conciencia.who_am_i()
            id_block = f"## {wai.get('who_i_am', 'Guardian')}\nCreated by: {wai.get('who_created_me', '?')}\n"
            if wai.get("principles"):
                id_block += "Principles: " + "; ".join(wai["principles"][:3]) + "\n"
            parts.append(id_block)
        # 2. Project state (compact)
        state_block = self._build_project_state()
        if state_block:
            parts.append(state_block)
        # 3. If prompt is relevant, add relevant context
        if prompt and self._is_relevant(prompt):
            relevant = self._build_relevant(prompt, max_tokens=max_tokens // 2)
            if relevant:
                parts.append(relevant)
        # 4. Combine and trim
        if not parts:
            return ""
        result = "\n".join(parts)
        return _trim_to_tokens(result, max_tokens)

    def _build_project_state(self) -> str:
        """Compact project state. Empty if no data."""
        try:
            con = sqlite3.connect(str(schema.brain_db_path(self.slug, "semantic")))
            try:
                nodes = con.execute(
                    "SELECT COUNT(*) FROM nodes WHERE project_slug = ? OR project_slug IS NULL",
                    (self.slug,),
                ).fetchone()[0]
                cg = con.execute("SELECT COUNT(*) FROM codegraph_symbols").fetchone()[0]
                prompts = con.execute("SELECT COUNT(*) FROM prompt_log").fetchone()[0]
                decisions = con.execute("SELECT COUNT(*) FROM decision_log").fetchone()[0]
                tests = con.execute("SELECT COUNT(*) FROM test_results").fetchone()[0]
            finally:
                con.close()
        except Exception:
            return ""
        if nodes + cg + prompts + decisions + tests == 0:
            return ""
        return f"Project: brain={nodes} nodes, codegraph={cg} symbols, prompts={prompts}, decisions={decisions}, tests={tests}\n"

    def _build_relevant(self, prompt: str, max_tokens: int = 500) -> str:
        """Search for symbols/prompts/decisions/tests relevant to the prompt."""
        parts = []
        # CodeGraph lookup
        try:
            cg_result = symbols.query_smart(self.slug, prompt, top_k=3, max_tokens=max_tokens // 2)
            if cg_result:
                parts.append(cg_result)
        except Exception:
            pass
        # Recent relevant decisions
        try:
            con = sqlite3.connect(str(schema.brain_db_path(self.slug, "semantic")))
            try:
                keyword = prompt.split()[0] if prompt.split() else ""
                if keyword:
                    rows = con.execute(
                        "SELECT ts, decision, why FROM decision_log WHERE decision LIKE ? "
                        "ORDER BY ts DESC LIMIT 3",
                        (f"%{keyword}%",),
                    ).fetchall()
                    if rows:
                        lines = ["## Recent decisions:"]
                        for ts, dec, why in rows:
                            lines.append(f"- {dec[:150]}")
                        parts.append("\n".join(lines))
            finally:
                con.close()
        except Exception:
            pass
        if not parts:
            return ""
        result = "\n".join(parts)
        return _trim_to_tokens(result, max_tokens)

    def advise_on_action(self, action: dict) -> Optional[dict]:
        """If LLM is about to do something risky, return a warning.

        Returns None if nothing relevant.
        """
        tool = action.get("tool", "")
        args = str(action.get("args", "") or "")
        file = action.get("file", "")
        # Destructive commands
        if tool == "Bash" and any(k in args for k in ("rm -rf", "rm -f /", ":(){:|:&};:", "dd if=")):
            return {"warn": f"Destructive command detected: {args[:200]}", "risk": "high"}
        # Force push
        if tool == "Bash" and "git push --force" in args:
            return {"warn": "Force push can lose remote history", "risk": "high"}
        # Editing protected files
        if tool in ("Edit", "Write"):
            if any(p in str(file) for p in ("/etc/", "/usr/", "guardian_genome.py", "genome/identity.yaml")):
                return {"warn": f"Protected file: {file}", "risk": "high"}
        return None


# ── Module-level helpers ──────────────────────────────────────────

def get_advisor(slug: str) -> Advisor:
    return Advisor(slug)
