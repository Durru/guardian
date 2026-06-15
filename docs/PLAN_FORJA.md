# Plan: `guardian_forja.py` — La Forja

> Módulo meta para crear, modificar, validar y eliminar cualquier parte del core de Guardian.
> Uso personal — taller del arquitecto.

---

## Propósito

`guardian_forja.py` es un módulo con poder total sobre el sistema Guardian. Permite:
- **Scaffoldear** nuevos módulos, funciones, endpoints y tools MCP
- **Validar** que el código siga las convenciones del proyecto
- **Analizar impacto** de cambios antes de hacerlos
- **Editar y eliminar** módulos del core
- **Diagnosticar** la salud de toda la base de código

## Exposición

| Capa | Cómo |
|------|------|
| **CLI** | `guardian forja <subcomando> [args]` |
| **Backend** | Endpoints `/api/forja/*` en puerto :9787 |
| **MCP** | Tools `forja_scaffold`, `forja_validate`, `forja_impact` |

---

## Comandos CLI

```
guardian forja module new <name>              # Scaffold nuevo guardian_*.py
guardian forja function <mod> <name>          # Agregar cmd_ función + registro
guardian forja endpoint <name> <method>       # Crear endpoint REST en backend
guardian forja mcp-tool <name>                # Crear tool MCP
guardian forja validate [module]              # Validar módulo contra convenciones
guardian forja impact <change>                # Mostrar qué archivos tocar
guardian forja doctor                          # Check de salud de toda la base
guardian forja list                            # Listar módulos y símbolos públicos
guardian forja edit <file>                     # Editar archivo del core
guardian forja rm <module>                     # Eliminar módulo (con confirmación)
```

---

## Capacidades detalladas

### 1. `module new` — Scaffold de módulo completo

Crea un módulo nuevo con todo incluido:

**Template del módulo** (`guardian_<name>.py`):
```python
#!/usr/bin/env python3
"""
guardian_<name> — <descripción breve>

CLI:
  guardian <name> <action> [args]
"""

import sys
import json
from pathlib import Path
import guardian_shared as shared
from guardian_shared import _

# ── constants ──────────────────────────────────────────

# ── core functions ─────────────────────────────────────

# ── CLI handler ────────────────────────────────────────

def main():
    ...

if __name__ == "__main__":
    sys.exit(main())
```

**Registros automáticos**:
1. `guardian.py` — agrega `cmd_<name>()` + `FORJA_SCRIPT` constant + dispatch entry + help text
2. `docs/REFERENCIA.md` — agrega fila en tabla CLI
3. `docs/AGENTS.md` — agrega fila en File Map
4. `docs/MODULOS.md` — agrega sección

### 2. `function` — Agregar función a módulo existente

```bash
guardian forja function guardian_evolucion algo
  → Agrega cmd_algo() a guardian_evolution.py
  → Registra en dispatch() de guardian.py
  → Agrega endpoint POST /api/evolution/algo en backend.py
```

### 3. `endpoint` — Crear endpoint REST

```bash
guardian forja endpoint forja/validate POST
  → Agrega handler en guardian_backend.py (do_POST)
  → Agrega entrada en docs/REFERENCIA.md tabla API
```

### 4. `mcp-tool` — Crear tool MCP

```bash
guardian forja mcp-tool forja_scaffold
  → Agrega tool definition + handler en guardian_mcp.py
  → Agrega tool en guardian.ts plugin
```

### 5. `validate` — Validación de convenciones

Verifica contra las reglas de `AGENTS.md`:

| Regla | Check |
|-------|-------|
| **Naming** | `cmd_<name>()` para handlers CLI |
| **Imports** | Usa `guardian_shared as shared` y `from guardian_shared import _` |
| **i18n** | Strings pasan por `_()` |
| **Headers** | Secciones con `# ── title ──` |
| **Delegación** | Módulos complejos usan subprocess con `sys.executable` |
| **Error handling** | Try/except con mensajes i18n |

### 6. `impact` — Análisis de impacto

Usa la **Change Impact Matrix** del `AGENTS.md`:

| Si querés... | Mostrar qué tocar |
|--------------|-------------------|
| Nuevo CLI command | guardian.py + docs + opcional: backend, plugin |
| Nuevo endpoint | backend.py + lib + docs |
| Nueva MCP tool | mcp.py + plugin + backend + docs |
| Nuevo módulo lib | archivo nuevo + guardian.py + docs + backend |

### 7. `doctor` — Diagnóstico del sistema

Escanea toda la base y reporta:

- **Módulo check**: cada `lib/guardian_*.py` existe y es importable
- **Dispatch check**: cada `cmd_*` en guardian.py tiene entry en `main()`
- **Backend check**: cada endpoint tiene handler
- **MCP check**: cada tool tiene handler
- **Import check**: todos los imports entre módulos resuelven
- **Orphan check**: funciones sin uso

### 8. `list` — Inventario

```
Módulos:
  guardian.py          (2961 lines) — CLI dispatcher, 37 cmd_* functions
  guardian_shared.py   (1353 lines) — shared utilities, i18n, paths
  guardian_genome.py   (311 lines) — genome + branches
  ...

Endpoints:
  GET  /health
  GET  /metrics
  POST /conciencia/cycle
  ...

MCP Tools:
  read_file, write_file, run_command, rag_query, ...
```

### 9. `edit` — Editar archivo del core

```bash
guardian forja edit lib/guardian_forja.py
  → Abre con $EDITOR o muestra el contenido para editar
```

### 10. `rm` — Eliminar módulo

```bash
guardian forja rm guardian_viejo
  → Confirmación: "¿Eliminar lib/guardian_viejo.py y sus registros? (s/N)"
  → Si sí: borra archivo + limpia registros en guardian.py, backend.py, mcp.py, docs
```

---

---

## Auto-conocimiento (índice vivo)

La Forja mantiene un índice JSON (`~/.forja/index.json`) que se **reconstruye automáticamente** en cada operación.

```json
{
  "modules": [
    {
      "file": "guardian_conciencia.py",
      "name": "guardian_conciencia",
      "loc": 562,
      "functions": ["consciousness_cycle", "meta_evolution", "score_context", ...],
      "endpoints": ["/conciencia/state", "/conciencia/percentiles"],
      "mcp_tools": ["conciencia_cycle"],
      "cli_commands": ["conciencia"]
    }
  ],
  "files": 11,
  "functions": 120,
  "endpoints": 25,
  "mcp_tools": 10,
  "scanned_at": 1747350000
}
```

- Se actualiza **en cada operación** de la Forja
- Cualquier modificación al core (scaffold, edit, rm) dispara `auto_update_index()`
- La Forja lo usa para saber qué existe, qué hace cada cosa, y cómo crear nuevas consistentemente
- Auditoría de cambios en `~/.forja/audit/changes.jsonl`

## Interfaz directa

Un solo comando para delegar cualquier tarea:

```bash
guardian forja "creame un modulo que audite el rendimiento"
  → Interpreta el pedido (vía conciencia si hace falta)
  → Elige el mejor nombre
  → Scaffold + registra + valida
```

Esto funciona a través del subcomando `run`, que toma un string en lenguaje natural y lo resuelve.

## Seguridad

| Medida | Descripción |
|--------|-------------|
| **Protegidos por defecto** | `guardian_shared`, `guardian_genome`, `guardian_conciencia`, `guardian_forja`, `guardian` |
| **Protección explícita** | `guardian forja protect <module>` para marcar cualquier módulo como no-eliminable |
| **Snapshots pre-delete** | Backup automático del archivo en `.forja/backups/` antes de borrar |
| **Doble confirmación** | `¿Eliminar? (s/N)` + requiere flag `--force` |
| **Audit obligatorio** | Cada eliminación se registra en `.forja/audit/changes.jsonl` |
| **Dry-run** | `guardian forja rm --dry-run <module>` muestra qué pasaría sin ejecutar |

## Reglas de operación

1. **Auto-conocimiento primero** — el índice siempre está actualizado antes de operar
2. **Siempre validar** antes de escribir — `forja validate` implícito en scaffold
3. **Siempre preguntar** antes de eliminar — confirmación obligatoria + `--force`
4. **Siempre registrar** en docs — scaffold actualiza REFERENCIA.md, AGENTS.md, MODULOS.md
5. **Siempre exponer** — CLI + Backend + MCP

---

## Dependencias

```
guardian_forja.py
└── guardian_shared.py        (paths, config, i18n)
└── guardian.py               (lee & modifica dispatch, help, constantes)
└── guardian_backend.py       (lee & modifica handlers)
└── guardian_mcp.py           (lee & modifica tools)
└── pathlib / os              (escritura de archivos)
└── subprocess                (python -c "import X" para validar imports)
```

---

## Archivos a modificar

| Archivo | Qué agregar |
|---------|-------------|
| `lib/guardian_forja.py` | **Crear** — el módulo completo |
| `lib/guardian.py` | `cmd_forja()` + `FORJA_SCRIPT` + dispatch entry + help |
| `lib/guardian_backend.py` | Endpoints `/api/forja/*` |
| `lib/guardian_mcp.py` | Tools `forja_scaffold`, `forja_validate`, `forja_impact` |
| `.opencode/plugins/guardian.ts` | Plugin mirrors para MCP tools |
| `docs/REFERENCIA.md` | CLI table + API table + MCP table |
| `docs/AGENTS.md` | File Map + Change Impact Matrix entry |
| `docs/MODULOS.md` | Sección para guardian_forja.py |

---

## Checklist de implementación

- [x] Crear `lib/guardian_forja.py` con todas las funciones
- [x] Agregar `cmd_forja()` en `guardian.py`
- [x] Agregar `FORJA_SCRIPT` constant y dispatch en `guardian.py`
- [x] Agregar help text en `guardian.py main()`
- [x] Agregar endpoints `/api/forja/*` en `guardian_backend.py`
- [x] Agregar tools MCP en `guardian_mcp.py`
- [x] Actualizar `docs/REFERENCIA.md`
- [x] Actualizar `docs/AGENTS.md`
- [x] Actualizar `docs/MODULOS.md`
- [x] Agregar `cmd_endpoint()` — scaffold endpoint REST
- [x] Agregar `cmd_mcp_tool()` — scaffold tool MCP
- [x] Agregar `function_add()` con flag `--register` — registro en dispatch
- [x] Agregar `_register_in_guardian_py()` — wiring automático en guardian.py
- [x] Agregar `diff_snapshot()` — snapshot diff del índice
- [x] Agregar `graph_deps()` — grafo ASCII de dependencias
- [x] Agregar `patch_file()` — edición parcial find+replace
- [x] `delete_module()`: dry-run + confirmación interactiva
- [x] `module_new()`: flag `--register` para registro full
- [x] `run_direct()`: soporte para endpoint, graph, diff, patch
