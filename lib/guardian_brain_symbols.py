#!/usr/bin/env python3
"""Guardian Brain Symbols — CodeGraph: AST real del proyecto.

Indexa el código fuente usando tree-sitter. Produce un mapa real
del proyecto (functions, classes, methods, routes, imports).

Vive en la raíz del proyecto (project_root_path).
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import time
from pathlib import Path
from typing import Optional

import guardian_brain_schema as schema
import guardian_shared as shared


# ── Language detection ────────────────────────────────────────────

EXT_TO_LANG = {
    ".py": "python",
    ".pyi": "python",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".go": "go",
}


def _lang_for_file(path: Path) -> Optional[str]:
    return EXT_TO_LANG.get(path.suffix.lower())


# ── Tree-sitter parsers (lazy loaded) ─────────────────────────────

_PARSERS = {}


def _get_parser(lang: str):
    if lang in _PARSERS:
        return _PARSERS[lang]
    if lang == "python":
        import tree_sitter_python
        import tree_sitter
        ts_lang = tree_sitter.Language(tree_sitter_python.language())
    elif lang in ("typescript", "tsx"):
        import tree_sitter_typescript
        import tree_sitter
        ts_lang = tree_sitter.Language(tree_sitter_typescript.language_typescript())
    elif lang == "javascript":
        import tree_sitter_javascript
        import tree_sitter
        ts_lang = tree_sitter.Language(tree_sitter_javascript.language())
    elif lang == "go":
        import tree_sitter_go
        import tree_sitter
        ts_lang = tree_sitter.Language(tree_sitter_go.language())
    else:
        return None
    parser = tree_sitter.Parser(ts_lang)
    _PARSERS[lang] = parser
    return parser


# ── Extractors (per language) ─────────────────────────────────────


def _extract_python(node, source_bytes: bytes) -> list[dict]:
    """Extract functions, classes, methods from a Python AST."""
    out = []
    if node.type == "function_definition":
        name_node = node.child_by_field_name("name")
        name = source_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace") if name_node else "<anon>"
        params_node = node.child_by_field_name("parameters")
        sig_end = params_node.end_byte if params_node else node.end_byte
        sig = source_bytes[node.start_byte:sig_end].decode("utf-8", errors="replace")
        docstring = ""
        body = node.child_by_field_name("body")
        if body and body.child_count > 0:
            first = body.child(0)
            if first.type == "expression_statement":
                inner = first.child(0)
                if inner and inner.type == "string":
                    docstring = source_bytes[inner.start_byte:inner.end_byte].decode("utf-8", errors="replace").strip("\"'")
        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1
        out.append({
            "kind": "function" if node.parent.type != "class_definition" else "method",
            "name": name,
            "qualified_name": name,
            "signature": sig,
            "line_start": line_start,
            "line_end": line_end,
            "docstring": docstring[:500],
        })
    elif node.type == "class_definition":
        name_node = node.child_by_field_name("name")
        name = source_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace") if name_node else "<anon>"
        out.append({
            "kind": "class",
            "name": name,
            "qualified_name": name,
            "signature": f"class {name}",
            "line_start": node.start_point[0] + 1,
            "line_end": node.end_point[0] + 1,
            "docstring": "",
        })
    elif node.type == "import_statement" or node.type == "import_from_statement":
        out.append({
            "kind": "import",
            "name": source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace"),
            "qualified_name": "",
            "signature": "",
            "line_start": node.start_point[0] + 1,
            "line_end": node.end_point[0] + 1,
            "docstring": "",
        })
    for child in node.children:
        out.extend(_extract_python(child, source_bytes))
    return out


def _extract_javascript_like(node, source_bytes: bytes) -> list[dict]:
    """Extract functions, classes from JS/TS AST."""
    out = []
    if node.type in ("function_declaration", "function", "method_definition"):
        name_node = node.child_by_field_name("name")
        name = source_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace") if name_node else "<anon>"
        kind = "method" if node.type == "method_definition" else "function"
        sig = source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace").split("\n", 1)[0][:200]
        out.append({
            "kind": kind,
            "name": name,
            "qualified_name": name,
            "signature": sig,
            "line_start": node.start_point[0] + 1,
            "line_end": node.end_point[0] + 1,
            "docstring": "",
        })
    elif node.type in ("class_declaration", "class"):
        name_node = node.child_by_field_name("name")
        name = source_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace") if name_node else "<anon>"
        out.append({
            "kind": "class",
            "name": name,
            "qualified_name": name,
            "signature": f"class {name}",
            "line_start": node.start_point[0] + 1,
            "line_end": node.end_point[0] + 1,
            "docstring": "",
        })
    elif node.type in ("import_statement", "import_specifier"):
        out.append({
            "kind": "import",
            "name": source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")[:200],
            "qualified_name": "",
            "signature": "",
            "line_start": node.start_point[0] + 1,
            "line_end": node.end_point[0] + 1,
            "docstring": "",
        })
    for child in node.children:
        out.extend(_extract_javascript_like(child, source_bytes))
    return out


def _extract_go(node, source_bytes: bytes) -> list[dict]:
    """Extract functions, methods, types from Go AST."""
    out = []
    if node.type in ("function_declaration", "method_declaration"):
        name_node = node.child_by_field_name("name")
        name = source_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace") if name_node else "<anon>"
        kind = "method" if node.type == "method_declaration" else "function"
        sig = source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace").split("\n", 1)[0][:200]
        out.append({
            "kind": kind,
            "name": name,
            "qualified_name": name,
            "signature": sig,
            "line_start": node.start_point[0] + 1,
            "line_end": node.end_point[0] + 1,
            "docstring": "",
        })
    elif node.type == "type_declaration":
        name_node = node.child_by_field_name("name")
        if name_node:
            name = source_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace")
            out.append({
                "kind": "class",
                "name": name,
                "qualified_name": name,
                "signature": f"type {name}",
                "line_start": node.start_point[0] + 1,
                "line_end": node.end_point[0] + 1,
                "docstring": "",
            })
    elif node.type == "import_declaration":
        out.append({
            "kind": "import",
            "name": source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")[:200],
            "qualified_name": "",
            "signature": "",
            "line_start": node.start_point[0] + 1,
            "line_end": node.end_point[0] + 1,
            "docstring": "",
        })
    for child in node.children:
        out.extend(_extract_go(child, source_bytes))
    return out


_EXTRACTORS = {
    "python": _extract_python,
    "javascript": _extract_javascript_like,
    "typescript": _extract_javascript_like,
    "tsx": _extract_javascript_like,
    "go": _extract_go,
}


# ── CodeGraph class ──────────────────────────────────────────────


class CodeGraph:
    """Mapa del proyecto. AST real indexado en codegraph_symbols + FTS5 fallback."""

    def __init__(self, project_root: Path, slug: str = None):
        self.project_root = Path(project_root)
        self.slug = slug or self.project_root.parent.name
        self.db_path = schema.brain_db_path(self.slug, "semantic")
        # Ensure DB exists
        schema.init_project(self.slug)

    def _conn(self):
        return sqlite3.connect(str(self.db_path))

    def has_index(self) -> bool:
        if not self.db_path.exists():
            return False
        try:
            con = self._conn()
            count = con.execute("SELECT COUNT(*) FROM codegraph_symbols").fetchone()[0]
            con.close()
            return count > 0
        except sqlite3.OperationalError:
            return False

    def full_index(self, source_root: Path) -> dict:
        """Index the entire project. One-shot, called from `guardian activate`."""
        if not self.has_index():
            schema.init_project(self.slug)
        source_root = Path(source_root)
        files = [p for p in source_root.rglob("*") if p.is_file() and _lang_for_file(p)]
        indexed = 0
        symbols_found = 0
        edges_found = 0
        t0 = time.time()
        for f in files:
            res = self._index_file(f, source_root)
            indexed += 1
            symbols_found += res.get("symbols", 0)
            edges_found += res.get("edges", 0)
        return {
            "files_indexed": indexed,
            "symbols": symbols_found,
            "edges": edges_found,
            "duration_s": round(time.time() - t0, 2),
        }

    def incremental_index(self, source_root: Path, since: float) -> dict:
        """Index only files modified after `since`."""
        source_root = Path(source_root)
        files = []
        for p in source_root.rglob("*"):
            if p.is_file() and _lang_for_file(p):
                try:
                    if p.stat().st_mtime > since:
                        files.append(p)
                except OSError:
                    pass
        indexed = 0
        symbols_found = 0
        for f in files:
            res = self._index_file(f, source_root)
            indexed += 1
            symbols_found += res.get("symbols", 0)
        return {"files_reindexed": indexed, "symbols_updated": symbols_found}

    def _index_file(self, file_path: Path, source_root: Path) -> dict:
        """Parse a single file and write symbols to the DB."""
        lang = _lang_for_file(file_path)
        if not lang:
            return {"symbols": 0, "edges": 0}
        parser = _get_parser(lang)
        if not parser:
            return {"symbols": 0, "edges": 0}
        extractor = _EXTRACTORS.get(lang)
        if not extractor:
            return {"symbols": 0, "edges": 0}
        try:
            source_bytes = file_path.read_bytes()
        except (OSError, UnicodeDecodeError):
            return {"symbols": 0, "edges": 0}
        try:
            tree = parser.parse(source_bytes)
        except Exception:
            return {"symbols": 0, "edges": 0}
        symbols = extractor(tree.root_node, source_bytes)
        rel_path = str(file_path.relative_to(source_root)) if file_path.is_relative_to(source_root) else str(file_path)
        try:
            source_hash = hashlib.md5(source_bytes).hexdigest()[:16]
        except Exception:
            source_hash = ""
        con = self._conn()
        try:
            # Remove old symbols for this file
            con.execute("DELETE FROM codegraph_symbols WHERE file = ? AND project_slug = ?",
                        (rel_path, self.slug))
            con.execute("DELETE FROM codegraph_edges WHERE file = ?", (rel_path,))
            inserted = 0
            for sym in symbols:
                con.execute("""
                    INSERT INTO codegraph_symbols
                    (project_slug, file, kind, name, qualified_name, signature,
                     line_start, line_end, language, docstring, hash, last_indexed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    self.slug, rel_path, sym["kind"], sym["name"], sym["qualified_name"],
                    sym["signature"], sym["line_start"], sym["line_end"], lang,
                    sym.get("docstring", ""), source_hash, time.time(),
                ))
                inserted += 1
            con.commit()
        finally:
            con.close()
        return {"symbols": inserted, "edges": 0}

    def lookup(self, query: str, top_k: int = 10, depth: int = 2, max_tokens: int = 2000) -> str:
        """The '1 tool = 40 calls' function.

        Combines FTS-like search + source retrieval in one call.
        Returns a formatted string ready to inject into LLM context.
        """
        if not self.db_path.exists():
            return ""
        con = self._conn()
        try:
            # Search by name LIKE (since we don't have FTS5 reliably)
            rows = con.execute("""
                SELECT id, file, kind, name, qualified_name, signature,
                       line_start, line_end, docstring
                FROM codegraph_symbols
                WHERE project_slug = ? AND (
                    name LIKE ? OR qualified_name LIKE ? OR docstring LIKE ?
                )
                ORDER BY
                    CASE WHEN name = ? THEN 0
                         WHEN name LIKE ? THEN 1
                         ELSE 2 END,
                    length(name)
                LIMIT ?
            """, (self.slug, f"%{query}%", f"%{query}%", f"%{query}%",
                  query, f"{query}%", top_k)).fetchall()
        finally:
            con.close()
        if not rows:
            return ""
        lines = [f"# CodeGraph: matches for '{query}'", ""]
        for r in rows:
            rid, file, kind, name, qn, sig, ls, le, doc = r
            sig_short = sig.replace("\n", " ")[:120]
            doc_short = (doc or "")[:200].replace("\n", " ")
            lines.append(f"- **{qn}** ({kind}) in `{file}:{ls}`")
            if sig_short and sig_short != name:
                lines.append(f"  - Signature: `{sig_short}`")
            if doc_short:
                lines.append(f"  - Doc: {doc_short}")
        return "\n".join(lines)

    def lookup_smart(self, query: str, top_k: int = 5, max_tokens: int = 2000) -> str:
        """The '1 tool = 40 calls'.

        Combines: symbol search + signature + docstring + (optional) source excerpt.
        Returns a string ready to inject into LLM context, trimmed to max_tokens.
        """
        results = self.lookup(query, top_k=top_k, max_tokens=max_tokens)
        if not results:
            return ""
        # Approximate token count: 1 token ~ 4 chars
        max_chars = max_tokens * 4
        if len(results) > max_chars:
            results = results[:max_chars] + "\n...(truncated)..."
        return results


# ── Module-level helpers ──────────────────────────────────────────


def get_codegraph(slug: str, project_root: Path = None) -> CodeGraph:
    """Get or create the CodeGraph for a project."""
    if project_root is None:
        config = shared.read_config(slug)
        root_str = config.get("project_root", "")
        project_root = Path(root_str) if root_str else Path.cwd()
    return CodeGraph(project_root, slug=slug)


def index_project(slug: str, source_root: Path, full: bool = True) -> dict:
    """Index a project. Called from `guardian activate`."""
    cg = get_codegraph(slug)
    if full or not cg.has_index():
        return cg.full_index(source_root)
    return cg.incremental_index(source_root, since=time.time() - 86400)


def codegraph_lookup(slug: str, query: str, top_k: int = 10, depth: int = 2,
                     max_tokens: int = 2000, project_root: Path = None) -> str:
    """The '1 tool = 40 calls'. Forwarder."""
    cg = get_codegraph(slug, project_root=project_root)
    return cg.lookup(query, top_k=top_k, depth=depth, max_tokens=max_tokens)


def query_smart(slug: str, query: str, top_k: int = 5, max_tokens: int = 2000,
                project_root: Path = None) -> str:
    """The '1 tool = 40 calls' main entrypoint.

    Returns a string with symbol matches, signatures, and docstrings.
    """
    cg = get_codegraph(slug, project_root=project_root)
    return cg.lookup_smart(query, top_k=top_k, max_tokens=max_tokens)
