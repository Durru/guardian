# Guardian v3.0.4 — Validation Report

This document records the validation of 8 unverified v3.0.3 zones and the bugs found/fixed.

## Summary

| ID | Zone | Status | Notes |
|---|---|---|---|
| T0 | session_end regenera GUARDIAN.md | ✅ OK | 17 líneas, identidad + procedimientos + aprendizajes |
| T1 | migración v2 → v3 | ✅ OK con fix | Backup en `legacy/memory.jsonl.v2`; clasificador buscaba `type` y debería ser `kind`; importance no se respetaba (arreglado) |
| T2 | auto-compact | ✅ OK | Governor bloquea importance 0.2 en write; GC remueve los 20 forzados con TTL expirado |
| T3 | specializations cargan tomos | ✅ OK | 5 nodos procedural (odoo_module_*, fastapi_*) en GUARDIAN.md |
| T4 | concurrent access | ✅ OK | 25 writes concurrentes, 0 crashes, merge automático |
| T5 | recovery crash mid-session | ✅ OK con fix | WM JSON corrupto → regenerado; DB SQLite corrupto → movido a `.corrupt-<ts>` + recreado |
| T6 | performance 10k nodos | ⚠️ Con caveat | 119 ops/s con cache (era 32 ops/s); 10k writes < 90s, query 30ms; cosine_bulk añadido |
| T7 | otros flujos secundarios | ✅ OK con 2 fixes | `/mode` sin slug → default JSON; `/genome` → serialización date/datetime |

## Bugs encontrados y arreglados

### 🔴 T1-1: migration buscaba `entry["type"]` cuando los items usaban `kind`

**Archivo:** `lib/guardian_brain_migration.py:100`

**Bug:**
```python
classification = classify_v2_kind(
    entry.get("type", "note"),  # ← bug: los items v2 usan "kind"
    entry.get("content", ""),
)
```

**Fix:**
```python
raw_kind = entry.get("type") or entry.get("kind") or "note"
raw_importance = entry.get("importance")
classification = classify_v2_kind(raw_kind, entry.get("content", "))
node = {
    "kind": classification["kind"],
    ...
    "importance": raw_importance if isinstance(raw_importance, (int, float)) else classification["importance"],
    ...
}
```

**Verificación:** items con `kind=pattern` ahora se respetan; importance 0.85 se preserva (antes era 0.4 default).

### 🔴 T5-2: DB SQLite corrupta → crash con traceback

**Archivo:** `lib/guardian_brain_schema.py:150`

**Bug:** Si el `semantic.db` se corrompe (disco lleno, kill -9, etc.), el siguiente `init_project()` ejecuta `executescript(NODE_DDL)` sobre bytes basura y sqlite3 tira `DatabaseError`.

**Fix:** agregar `PRAGMA integrity_check` antes de `executescript`; si falla, mover a `<name>.corrupt-<ts>` y recrear vacío.

```python
if db_path.exists() and db_path.stat().st_size > 0:
    try:
        test_conn = sqlite3.connect(str(db_path))
        test_conn.execute("PRAGMA integrity_check").fetchone()
        test_conn.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1").fetchone()
        test_conn.close()
    except sqlite3.DatabaseError:
        import shutil
        corrupt_path = db_path.with_suffix(db_path.suffix + f".corrupt-{int(datetime.now().timestamp())}")
        shutil.move(str(db_path), str(corrupt_path))
        print(f"  ⚠ DB corrupto movido a: {corrupt_path.name}")
```

⚠️ **Trade-off:** los datos del DB corrupto se pierden (movidos al archivo `.corrupt-<ts>`). Es la mejor opción vs. crash.

### 🟡 T7-1: `/mode` exigía slug pero a nivel global no debería

**Archivo:** `lib/guardian_backend.py:135`

**Bug:** `GET /mode` sin slug → 400.

**Fix:** cuando no hay slug, devolver JSON con `mode=default` + `hint`:
```json
{"mode": "plan", "default": true, "hint": "pass ?slug=<name> for project-specific mode"}
```

### 🟡 T7-2: `/genome` retornaba empty reply cuando genome contenía `datetime.date`

**Archivo:** `lib/guardian_backend.py:145`

**Bug:** `json.dumps(genome)` fallaba con `TypeError: Object of type date is not JSON serializable`.

**Fix:** serializador custom que convierte `date`/`datetime` a `isoformat()`:
```python
def _serialize(obj):
    if isinstance(obj, (date, _dt)):
        return obj.isoformat()
    raise TypeError(f"Not JSON serializable: {type(obj)}")
```

## Performance (T6)

### Hallazgos
- **Sin optimizaciones:** 32 writes/segundo (1k writes = 31s)
- **Con conn cache + limit_scan=50:** 98 writes/segundo
- **Con branch_hash cache + cosine_bulk:** 119 writes/segundo
- **Query (vector search) en 5k nodos:** 30ms (full scan), 5ms (limit_scan=200)

### Optimizaciones aplicadas

1. **`_CONN_CACHE`** (`lib/guardian_brain.py`): cache de conexiones SQLite por db_path con WAL mode. Evita 5k connects por 5k writes.

2. **`limit_scan` param en `query()`**: solo escanea los últimos N nodos. El Governor no necesita revisar toda la DB para detectar duplicados, solo los más recientes.

3. **`cosine_bulk()`**: unpacks del query embedding una vez y reutiliza para N candidates. ~3x más rápido que `cosine()` en loop.

4. **`_BRANCH_HASH_CACHE`** (`lib/guardian_shared.py`): cache del hash del branch. Se llamaba 3+ veces por write; ahora se computa una vez.

### Caveat

Para 10k+ nodos en un solo write batch, el bottleneck sigue siendo el cosine Python loop (~1µs/cosine). Una solución real sería:
- HNSW index (requiere faiss o hnswlib — sumaría dependencia)
- numpy vectorización (sumaría dependencia)
- Pre-filtrado por hash bucket en SQL (zero-deps)

**Decisión:** mantener zero-deps. Documentar el límite y recomendar para proyectos grandes usar FAISS externo.

## Verificación end-to-end final

```
T1 tests:        223/223 ✓
T2 v3 CLI:       18/18 ✓
T3 HTTP:         22/22 GET+POST 200 ✓
T4 MCP:          35/35 tools registered ✓
T5 Plugin TS:    19 tools (6 v2 + 13 v3) ✓
T6 Backend:      71 unique paths, 0 AttributeError ✓
T7 con proyecto real: brain write/query/conciencia all OK ✓
T8 223 tests post-fixes: still pass ✓
```

## Files changed (v3.0.4)

- `lib/guardian_brain.py`: conn cache, limit_scan, cosine_bulk, branch_hash usage
- `lib/guardian_brain_schema.py`: DB corruption recovery
- `lib/guardian_brain_migration.py`: read `kind` not `type`, preserve importance
- `lib/guardian_shared.py`: branch_hash cache
- `lib/guardian_backend.py`: /mode default, /genome date serialization

## Migration notes

- `git pull origin master` después de tag v3.0.4
- `sudo bash install.sh` (no uninstall)
- `systemctl restart nexxoria-guardian`
- 915 proyectos en `/var/guardian/` **no se tocan** — el schema es compatible

## What remains for v3.1+

- User-defined specializations (YAML)
- Web UI for GUARDIAN.md editor
- Optional real embeddings (sentence-transformers)
- Cross-project lineage visualization
- Auto-fork governor thresholds based on drift
