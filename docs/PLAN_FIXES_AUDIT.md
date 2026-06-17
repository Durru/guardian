# Plan de Fixes — Auditoría Completa Guardian v4.1.0

## 🔴 CRÍTICOS (bugs reales)

| # | Bug | Archivo | Fix |
|---|-----|---------|-----|
| 1 | `quick_check()` no existe en conciencia | `guardian_backend.py:492`, `guardian.py:2030` | Implementar `Conciencia.quick_check()` |
| 2 | `THRESHOLD_KEYS` no definido | `guardian_backend.py:438` | Agregar constante o inline |
| 3 | `build_context_for_cycle()` no existe | `guardian_conciencia.py:415` | Implementar función o eliminar call |
| 4 | `write_observation(scope="global")` escribe en path equivocado | `guardian_brain.py:924` | Usar `schema.global_db_path()` |
| 5 | `run_command` con `shell=True` | `guardian_mcp.py:601` | Cambiar a lista de args |
| 6 | MCP read/write sin path validation | `guardian_mcp.py:573-591` | Validar path contra GUARDIAN_HOME |
| 7 | forja_patch path traversal | `guardian_forja.py` | Resolver path, checkear prefijo |

## 🟡 ALTOS

| # | Issue | Fix |
|---|-------|-----|
| 8 | `install_builtin()` sin return | Agregar return exitoso |
| 9 | `create_user_spec()` dead code | Eliminar líneas post-return |
| 10 | `cmd == "knowledge"` duplicado | Eliminar el segundo |
| 11 | `lib/lib/` duplicados | Eliminar directorio |
| 12 | Tests de observaciones | Agregar tests |
| 13 | Tests de guardian_forja | Agregar tests |
| 14 | Tests de guardian_backend | Agregar tests |

## 🟢 BAJOS

| # | Issue | Fix |
|---|-------|-----|
| 15 | Imports sin usar | Eliminar |
| 16 | Paths hardcodeados | Usar shared.BACKEND_DIR |
| 17 | Excepciones MCP filtradas | Sanitizar mensajes |
| 18 | Tests sin aislamiento | Agregar setUp/tearDown |

## Orden de implementación

1. Fix 1-3 (broken imports)
2. Fix 4 (global DB path)
3. Fix 5-7 (security: shell + paths)
4. Fix 8-11 (quality: specialization, duplicates, dead code)
5. Fix 12-14 (tests)
6. Fix 15-18 (cleanup)
