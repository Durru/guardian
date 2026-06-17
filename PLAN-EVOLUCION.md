# Nexxoria Guardian — Sistema de Evolución Generativa

> Basado en discusiones: rama única por máquina, evolución sin límite,
> sin API key externa, sin riesgo de romper nada, todo automático salvo cambios muy grandes,
> función existente del core puede evolucionarse sin tocarla.

---

## Principios inviolables

1. **El core nunca se toca.** `lib/guardian_*.py`, `genome/identity.yaml`, `install.sh`, `systemd/` son intocables por la evolución. Todo código generado vive en `evolved/`.
2. **El ADN muta pero preserva el origen.** La rama tiene `forked_from`, `forked_at`, `creator`. El creador y los principios raíz nunca cambian.
3. **La evolución no rompe nada.** 6 barreras de seguridad: aislamiento, validación sintáctica, import safety, sin builtins peligrosos, tamaño máximo, rollback.
4. **TODO se registra con versión.** Manifest + history append-only. Nada se pierde.
5. **El agente OpenCode es el implementador.** Guardian detecta patrones y genera propuestas. El agente decide, revisa y activa.

---

## Arquitectura general

```
                    ┌──────────────────────┐
                    │    OPENCODE AGENT     │
                    │ (implementa, revisa,  │
                    │  activa propuestas)   │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  GUARDIAN EVOLUTION   │
                    │                      │
                    │  ┌────────────────┐  │
                    │  │  N2 STATS      │  │ ← ajusta thresholds ±0.05
                    │  │  (automático)   │  │
                    │  └────────────────┘  │
                    │  ┌────────────────┐  │
                    │  │  GENERATIVA    │  │ ← detecta patrones
                    │  │  (automático)  │  │
                    │  └───────┬────────┘  │
                    │          │           │
                    │  ┌───────▼────────┐  │
                    │  │  PROPOSAL      │  │ ← escribe propuestas YAML
                    │  │  ENGINE        │  │
                    │  └───────┬────────┘  │
                    │          │           │
                    │  ┌───────▼────────┐  │
                    │  │  TEMPLATE      │  │ ← llena templates con params
                    │  │  ENGINE        │  │
                    │  └───────┬────────┘  │
                    │          │           │
                    │  ┌───────▼────────┐  │
                    │  │  VALIDATOR     │  │ ← 6 barreras de seguridad
                    │  │  (syntax,      │  │
                    │  │   import,      │  │
                    │  │   size,        │  │
                    │  │   checksum)    │  │
                    │  └───────┬────────┘  │
                    │          │           │
                    │  ┌───────▼────────┐  │
                    │  │  MANIFEST      │  │ ← registro + historial
                    │  │  REGISTRY      │  │
                    │  └────────────────┘  │
                    └──────────────────────┘
```

### Conexión con el resto de Guardian

```
conciencia.run_cycle()
├── N1: percibe → decide → reflexiona
└── N2: evolve()
      ├── estadístico: ajusta thresholds ±0.05
      ├── generativo: detecta patrones, genera propuestas
      │   └── si es automático (pequeño/mediano/grande):
      │         template → validación → manifest → activate
      └── guarda history.jsonl

cmd_activate()
├── setup → branch → globalscan → match → docs
├── conciencia.run_cycle()
└── evolution.check_pending_proposals()

guardian evolution proposals   ← Muestra propuestas pendientes
guardian evolution approve     ← Activa propuesta (solo "muy grande" / "crítico")
guardian evolution reject      ← Descarta propuesta
guardian evolution history     ← Muestra historial completo
guardian evolution status      ← Estado actual de la rama evolutiva
guardian evolution rollback    ← Revierte una evolución activa
```

---

## Estructura de archivos

### Rama única por máquina

```
$GUARDIAN_DATA/genome/branches/<hash>/
│
├── identity.yaml                    ← ADN mutado (forked_from genome/identity.yaml)
│   ├── version, creator (preservado)
│   ├── forked_from, forked_at
│   ├── principles (extensibles por evolución)
│   └── consciousness.thresholds (evolucionados)
│
├── state.json                       ← Estado global de la rama
│   ├── session_count, evolution_version
│   ├── mode_preferences, patterns
│   └── last_generative_evolution
│
├── consciousness/
│   ├── cycles.jsonl                 ← TODOS los ciclos N1 (cross-project)
│   ├── thresholds.json              ← Thresholds base + evolucionados
│   └── meta-learnings.json          ← Aprendizaje del N2
│
├── memory/
│   ├── cross-project.jsonl          ← Memoria global
│   └── projects/<slug>.jsonl        ← Memoria por proyecto
│
├── knowledge/
│   ├── tomes/                       ← Tomos globales (skills, 1 vez)
│   └── projects/<slug>/            ← Skills + tomos del proyecto
│
├── learnings/
│   ├── cross-project/               ← Learnings cross-project
│   └── projects/<slug>/            ← Learnings del proyecto
│
├── context/
│   ├── session-<slug>.json          ← Dedup de sesión (qué ya se mostró)
│   └── usage-stats.json             ← Stats para N2 (qué contexto se ignora)
│
├── evolved/                         ← CÓDIGO GENERADO POR EVOLUCIÓN
│   ├── manifest.json                ← Registro de todo lo generado (con versiones)
│   ├── evolution-history.jsonl      ← Historial append-only (NUNCA se borra)
│   │
│   ├── commands/                    ← Nuevos comandos CLI
│   │   └── guardian_<name>.py
│   │
│   ├── mcp_tools/                   ← Nuevos tools MCP
│   │   └── tool_<name>.py
│   │
│   ├── context_providers/           ← Nuevas fuentes de contexto
│   │   └── provider_<name>.py
│   │
│   ├── conciencia_actions/          ← Nuevas acciones N1
│   │   └── action_<name>.py
│   │
│   ├── thresholds/                  ← Nuevos parámetros evolucionables
│   │   └── thresholds_custom.json
│   │
│   └── patches/                     ← Override de funciones existentes del core
│       └── <module>/<function>.py
│           └── def <function>(...):  ← Versión evolucionada
│
└── evolution/
    ├── proposals/                    ← Propuestas pendientes
    │   └── <id>.yaml
    └── generation-counter.txt       ← # generaciones en esta sesión
```

---

## El Manifest: registro con versión de todo

```yaml
# evolved/manifest.json
version: "2.0.0"
branch_hash: "a1b2c3d4"
forked_from_genome: "2.0.0"
forked_from_genome_created: "2026-06-14"
current_evolution_version: 47

evolutions:
  - id: evo_001
    type: command                    # command | mcp_tool | context_provider
                                     # | conciencia_action | threshold | patch
    evolution_type: extension        # extension = nuevo | override = reemplaza existente
    name: quick_match
    version: "1.0.0"
    status: active                   # proposed → generating → validated → active → deprecated
    created: "2026-06-14T12:00:00"
    activated: "2026-06-14T12:05:00"
    checksum: "sha256:abc123..."
    file: evolved/commands/guardian_quick_match.py
    applied_to: ~                    # extension: null; override: "guardian_absorb.cmd_scan"
    template: command.py.tpl
    description: "Combina scan + classify en un solo comando"
    size_bytes: 2841
    validated_by:
      - syntax_ok: true
      - imports_safe: true
      - no_dangerous_builtins: true
      - size_ok: true

  - id: evo_002
    type: patch                      # Override de función core
    evolution_type: override
    name: cmd_scan_patched
    version: "1.0.0"
    status: active
    applied_to: "guardian_absorb.cmd_scan"
    file: evolved/patches/absorb/cmd_scan.py
    description: "cmd_scan con auto-ingesta a global"
    ...

disabled: []                         # IDs de evoluciones desactivadas
```

## El Historial: append-only, NUNCA se borra

```jsonl
{"id":"evo_001","action":"proposed","ts":"2026-06-14T11:59:00","trigger":"pattern:scan+classify_always_together"}
{"id":"evo_001","action":"generated","ts":"2026-06-14T12:01:00","template":"command.py.tpl","params":{...}}
{"id":"evo_001","action":"validated","ts":"2026-06-14T12:03:00","result":"pass"}
{"id":"evo_001","action":"activated","ts":"2026-06-14T12:05:00","evolution_version":47}
{"id":"evo_002","action":"proposed","ts":"2026-06-14T13:00:00","trigger":"pattern:scan_output_always_modified"}
{"id":"evo_002","action":"generated","ts":"2026-06-14T13:02:00","template":"patch.py.tpl"}
{"id":"evo_002","action":"validated","ts":"2026-06-14T13:04:00","result":"pass"}
{"id":"evo_002","action":"activated","ts":"2026-06-14T13:05:00","evolution_version":48}
```

---

## Categorías de evolución y automatismo

### Automático (no pregunta)

| # | Tipo | Ejemplo |
|---|------|---------|
| 1 | **Nuevo comando CLI** | `guardian quick-match` que combina scan + classify |
| 2 | **Nuevo flag en comando existente** | `guardian activate --with-scan` |
| 3 | **Nuevo alias** | `guardian as` = `guardian absorb scan` |
| 4 | **Nuevo context provider** | Provider de git log activo |
| 5 | **Nuevo threshold** | `max_context_tokens`, `evolution_rate` |
| 6 | **Override de función core (patch)** | `cmd_scan()` que auto-ingiere a global |
| 7 | **Ajuste de prioridad de contexto** | Dejar de servir tipo X si nunca se usa |

### Pregunta (solo "muy grande")

| # | Tipo | Ejemplo |
|---|------|---------|
| 8 | **Nueva acción de conciencia N1** | `action_deep_analyze` |
| 9 | **Nuevo modo** | `guardian mode review` |
| 10 | **Nuevo tipo de evolución** | que no esté en la lista allowed |
| 11 | **Cambio estructural en thresholds** | Cambiar `max_cycles_for_analysis` de 20 a 50 |
| 12 | **Generación con LLM** | Si un día se conecta a un LLM externo |

### ¿Qué define "muy grande"?

```yaml
# Umbrales en state.json
evolution:
  auto_thresholds:
    max_new_files_per_session: 3       # Si genera >3 archivos, pregunta
    max_lines_per_generation: 200      # Si genera >200 líneas, pregunta
    max_changes_to_existing: 30        # Si modifica >30 líneas de código existente
    new_action_types: false            # Nueva acción de conciencia = pregunta
    new_modes: false                   # Nuevo modo = pregunta
    core_threshold_changes: false      # Cambiar max_cycles_for_analysis = pregunta
```

---

## Templates de evolución

Los templates son archivos `.py.tpl` con placeholders `{{variable}}`. Guardian los llena con los parámetros detectados.

### Template: Nuevo comando CLI

```python
# template: command.py.tpl
# Genera: evolved/commands/guardian_{{command_name}}.py

from __future__ import annotations
import json
from pathlib import Path

import guardian_shared as shared

def cmd_{{command_name}}({{params}}):
    \"\"\"{{description}}\"\"\"
    slug = shared.discover_projects()[0] if shared.discover_projects() else None
    if not slug:
        print("No hay proyectos activos")
        return 1
    {% for action in actions %}
    # {{action.description}}
    from {{action.module}} import {{action.function}}
    result = {{action.function}}(slug)
    {% endfor %}
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(cmd_{{command_name}}(sys.argv[1:] if len(sys.argv) > 1 else []))
```

### Template: Override de función core (patch)

```python
# template: patch.py.tpl
# Genera: evolved/patches/{{module}}/{{function}}.py
# Override de: {{applied_to}}

from __future__ import annotations
import json
from pathlib import Path

import guardian_shared as shared

def {{function}}({{params}}):
    \"\"\"{{description}}\"\"\"
    # Evolved override of {{applied_to}}
    # Original behavior preserved, enhanced with:
    {{# enhancements}}
    # - {{.}}
    {{/ enhancements}}

    {{implementation}}
    return result
```

### Template: Nuevo tool MCP

```python
# template: mcp_tool.py.tpl
# Genera: evolved/mcp_tools/tool_{{tool_name}}.py

TOOL_DEFINITION = {
    "name": "{{tool_name}}",
    "description": "{{description}}",
    "inputSchema": {{input_schema}}
}

def handle_{{tool_name}}(args: dict) -> dict:
    \"\"\"{{description}}\"\"\"
    {{implementation}}
    return {"content": [{"type": "text", "text": result}]}
```

### Template: Nuevo context provider

```python
# template: provider.py.tpl
# Genera: evolved/context_providers/provider_{{provider_name}}.py

PROVIDER_NAME = "{{provider_name}}"
PROVIDER_PRIORITY = {{priority}}

def get_context(query: str, slug: str = None, mode: str = "plan") -> list[dict]:
    \"\"\"{{description}}\"\"\"
    {{implementation}}
    return results
```

---

## El ciclo de evolución automática completo

```
1. CONCIENCIA.run_cycle(slug)
       │
       ├── N1: percibe → decide → reflexiona
       │     └── guarda ciclo en consciousness/cycles.jsonl
       │
       └── N2: evolve(slug, cycles, thresholds)
             │
             ├── 2a. ESTADÍSTICO (siempre)
             │     ├── calcula promedios de confianza
             │     ├── detecta tendencias (regresión lineal simple)
             │     ├── detecta anomalías (ciclos outlier)
             │     ├── cross-project learning
             │     └── ajusta thresholds ±0.05
             │
             └── 2b. GENERATIVO (cada 10 ciclos)
                   │
                   ├── 3. DETECTAR PATRONES
                   │     ├── ¿comandos que siempre se ejecutan juntos?
                   │     ├── ¿stack detectado → comandos útiles?
                   │     ├── ¿contexto siempre ignorado → eliminar provider?
                   │     ├── ¿misma pregunta repetida → nuevo comando?
                   │     ├── ¿threshold nunca cambia → eliminar?
                   │     ├── ¿función infrautilizada → evolucionar?
                   │     └── ¿patrón de uso → nuevo alias?
                   │
                   ├── 4. ¿PATRÓN DETECTADO?
                   │     No → terminar
                   │     Sí → crear proposal YAML
                   │
                   ├── 5. EVALUAR AUTOMATISMO
                   │     ├── ¿Es "muy grande" o "crítico"?
                   │     │   Sí → proposal status: "pending"
                   │     │         (visible en `guardian evolution proposals`,
                   │     │          el agente decide approve/reject)
                   │     │
                   │     │   No → AUTO:
                   │     │     5a. Buscar template matching
                   │     │     5b. Llenar template con params
                   │     │     5c. Escribir evolved/<tipo>/<nombre>.py
                   │     │     5d. VALIDAR:
                   │     │         - compile() → syntax check
                   │     │         - import safety (allowed list)
                   │     │         - no exec/eval/__import__
                   │     │         - max 50KB
                   │     │         - checksum
                   │     │     5e. Registrar en manifest.json
                   │     │     5f. Estado: "active"
                   │     │     5g. evolution_version++
                   │     │
                   │     └── 6. GUARDAR EN HISTORIAL
                   │           ├── history.jsonl append
                   │           └── NUNCA se borra ni edita
                   │
                   └── 7. INYECTAR en contexto
                         ├── próximos ciclos ven:
                         │   "evo_001: quick-match disponible"
                         └── el agente sabe que hay nuevo código
```

---

## Override de funciones core (lo más poderoso)

El core **nunca se modifica en disco**. El override se carga en memoria:

```python
# guardian.py (core) — INTOCABLE
def main():
    cmd = sys.argv[1]
    
    # 1. Manifest loader busca overrides PRIMERO
    override = manifest.get_override("guardian.main")
    if override:
        return override(sys.argv)
    
    # 2. Core dispatch (intacto)
    if cmd == "detect": ...
```

```python
# guardian_conciencia.py (core) — INTOCABLE
def run_cycle(slug, question="", mode="plan", ...):
    # 1. Manifest loader busca override
    override = manifest.get_override("guardian_conciencia.run_cycle")
    if override:
        return override(slug, question, mode, ...)
    
    # 2. Core implementation (intacta)
    confidence = score_context(...)
    ...
```

**¿Qué funciones son evolucionables?**

| Función | ¿Overrideable? | ¿Por qué? |
|---------|:-------------:|-----------|
| `run_cycle()` | ✅ | Puede necesitar más señales de contexto |
| `score_context()` | ✅ | Diferentes pesos según el proyecto |
| `evolve()` | ✅ | Diferente lógica de evolución |
| `cmd_scan()` | ✅ | Auto-ingesta a global |
| `cmd_match()` | ✅ | Diferentes criterios de matching |
| `cmd_activate()` | ✅ | Pasos adicionales en activación |
| `cmd_context()` | ✅ | Diferentes fuentes de contexto |
| `consolidate()` | ✅ | Diferente política de GC |
| `fork_branch()` | ❌ | Muy cerca del core |
| `load_genome()` | ❌ | Nunca tocar el ADN |
| `main()` | ❌ | Muy cerca del core |
| `_detect_project_features()` | ❌ | Helper interno |

Regla: **todo lo que es "cmd_" o "cycle" es overrideable**. Lo que es `_internal`, `load_`, o `main()` no.

---

## Seguridad: 6 barreras

### 1. Aislamiento espacial

```
Solo escribe en: branches/<hash>/evolved/
NUNCA escribe en: lib/, genome/, templates/, tests/, docs/, install.sh, systemd/
```

### 2. Validación sintáctica

```python
def validate_syntax(code: str) -> bool:
    try:
        compile(code, "<evolved>", "exec")
        return True
    except SyntaxError as e:
        log(f"EVOLUTION: syntax error: {e}")
        return False
```

### 3. Import safety

```python
ALLOWED_IMPORTS = {
    "guardian_shared", "guardian_conciencia", "guardian_rag",
    "guardian_absorb", "guardian_genome", "guardian_evolution",
    "guardian_context",
    "json", "pathlib.Path", "typing", "datetime", "hashlib",
    "re", "math",
}

BLOCKED_IMPORTS = {
    "os", "subprocess", "sys", "importlib", "__import__",
    "shutil", "signal", "multiprocessing", "threading",
    "socket", "http", "urllib", "requests", "ctypes",
}

def validate_imports(code: str) -> bool:
    imports = re.findall(r'^import (\w+)|^from (\w+)', code, re.MULTILINE)
    for imp in imports:
        name = imp[0] or imp[1]
        if name in BLOCKED_IMPORTS:
            return False
        if name not in ALLOWED_IMPORTS:
            return False  # Unknown import = blocked
    return True
```

### 4. Sin builtins peligrosos

```python
DANGEROUS_BUILTINS = {"exec", "eval", "compile", "__import__", "open"}

def validate_builtins(code: str) -> bool:
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in DANGEROUS_BUILTINS:
                    return False
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in {"execute", "run", "popen", "system", "call"}:
                    return False
    return True
```

### 5. Tamaño máximo

```python
MAX_FILE_SIZE_BYTES = 50 * 1024  # 50KB

def validate_size(code: str) -> bool:
    return len(code.encode("utf-8")) <= MAX_FILE_SIZE_BYTES
```

### 6. Rollback

```python
def rollback(evo_id: str) -> dict:
    manifest = load_manifest()
    evo = manifest.get_evolution(evo_id)
    if not evo:
        return {"ok": False, "error": "not found"}
    
    # 1. Mover archivo a backup (no borrar, por si acaso)
    backup_path = evo.file + ".bak." + shared.ts()
    Path(evo.file).rename(backup_path)
    
    # 2. Mover a disabled
    evo.status = "deprecated"
    manifest.add_to_disabled(evo_id)
    manifest.save()
    
    # 3. Registrar en history
    append_history(evo_id, "rolled_back", {"backup": backup_path})
    
    return {"ok": True, "backup": backup_path}
```

---

## El ADN mutable con preservación de origen

```
genome/identity.yaml                     ← INTOCABLE por evolución
├── version: 2.0.0
├── creator: durru
├── created: 2026-06-14
├── identity:
│   ├── name: Nexxoria Guardian
│   ├── purpose: "Universal project guardian..."
│   └── principles: [5 principios inmutables]
├── origin:
│   ├── repository: "https://github.com/anomalyco/opencode"
│   └── lineage: "forked from Nexxoria Guardian v1"
├── consciousness:
│   └── default_thresholds: {...}
└── evolution: {...}

branches/<hash>/identity.yaml            ← MUTA pero preserva origen
├── version: 2.0.0                       ← Misma versión raíz
├── forked_from: "/opt/.../genome/identity.yaml"
├── forked_at: "2026-06-14T12:00:00"
├── creator: durru                       ← PRESERVADO
├── identity:
│   ├── name: Nexxoria Guardian
│   ├── purpose: "Universal project guardian..."
│   ├── principles: [...]                ← Extensibles (ADD, no remove)
│   └── evolved_principles:              ← NUEVOS por evolución
│       - "La evolución nunca rompe el core"
│       - "Cada máquina divergirá"
├── origin:                              ← PRESERVADO
│   ├── repository: "..."
│   └── lineage: "..."
├── consciousness:
│   ├── thresholds: {...}                ← EVOLUCIONADOS (diferentes)
│   └── evolved_params:                  ← NUEVOS por evolución
│       ├── evolution_rate: 0.3
│       ├── max_context_tokens: 4000
│       └── auto_approve_threshold: 0.7
├── evolution:
│   ├── current_version: 47
│   ├── total_generations: 12
│   └── last_generative_cycle: "..."
└── evolved_from_core:                   ← QUÉ del core fue overrideado
    - guardian_absorb.cmd_scan
    - guardian_conciencia.score_context
```

La rama preserva: `creator`, `identity.name`, `identity.principles` (base), `origin`.
La rama muta: `identity.evolved_principles`, `consciousness.thresholds`, `consciousness.evolved_params`, todo `evolution.*`.

---

## ¿Qué detecta el generative engine?

| Patrón | Señal | Resultado |
|--------|-------|-----------|
| **Comandos secuenciales** | `absorb scan` + `absorb classify` siempre seguidos en <5s | Nuevo comando compuesto |
| **Stack detectado** | `package.json` con `next` + `tailwind` | Comando `guardian next-setup` |
| **Contexto ignorado** | Provider X nunca se usa en 10 sesiones | Eliminar provider (ahorra tokens) |
| **Pregunta repetida** | Misma RAG query cada sesión | Nuevo context provider que responde automático |
| **Threshold estático** | `ask_much_floor` nunca cambió en 50 ciclos | Propuesta de eliminación |
| **Función infrautilizada** | `consolidate()` nunca se llama pero hay 1000+ memorias | Override que auto-consolida |
| **Patrón de error** | `TypeError` recurrente al llamar X | Propuesta de fix |
| **Modo preferido** | 90% de sesiones en modo "build" | Default mode = build, eliminar auto-detect |
| **Stack único** | Todos los proyectos son Django | Comandos django específicos |
| **Herramienta externa** | `poetry` siempre presente | Provider poetry para detectar deps |
| **Gap de habilidades** | Skills con score >50 pero nunca cargados | Reducir threshold de hot a 45 |

El generative engine corre cada 10 ciclos de conciencia. Busca estos patrones en:
1. `consciousness/cycles.jsonl` (últimos 50 ciclos)
2. `memory/cross-project.jsonl` (uso de comandos)
3. `context/usage-stats.json` (qué contexto se sirvió vs ignoró)
4. `knowledge/tomes/` (qué skills hay disponibles)
5. Proyectos registrados (qué stacks se usan)
6. `learnings/` (qué se aprendió)
7. Errores recientes (qué falló)

---

## Divergencia: dos instalaciones, dos guardianes distintos

```
Máquina A (durru, Python/Django/ML)
├── identity.yaml: forked_from=genome/identity.yaml, creator=durru
├── evolved/
│   ├── commands/
│   │   ├── guardian_django_check.py
│   │   ├── guardian_pip_audit.py
│   │   └── guardian_autopip.py
│   ├── mcp_tools/
│   │   └── tool_analyze_models.py
│   ├── context_providers/
│   │   └── provider_mlflow_runs.py
│   ├── conciencia_actions/
│   │   └── action_deep_analyze.py
│   ├── thresholds/
│   │   └── thresholds_custom.json
│   │       └── { assume: 0.72, max_context_tokens: 4000 }
│   └── patches/
│       ├── conciencia/score_context.py     ← Override con peso extra para ML
│       └── absorb/cmd_scan.py             ← Auto-ingiere modelos como skills
└── consciousness/
    ├── thresholds.json
    │   ├── assume: 0.72
    │   ├── evolution_rate: 0.4
    │   └── max_context_tokens: 4000
    └── cycles.jsonl                       ← 500+ ciclos, patrones ML

Máquina B (root, WordPress/PHP)
├── identity.yaml: forked_from=genome/identity.yaml, creator=durru (SÍ, el mismo)
├── evolved/
│   ├── commands/
│   │   ├── guardian_wp_deploy.py
│   │   ├── guardian_wp_sync.py
│   │   └── guardian_php_lint.py
│   ├── mcp_tools/
│   │   └── tool_woocommerce_sync.py
│   ├── context_providers/
│   │   └── provider_wp_cli.py
│   ├── conciencia_actions/
│   │   └── action_auto_deploy.py
│   ├── thresholds/
│   │   └── thresholds_custom.json
│   │       └── { assume: 0.85, build_assume_bonus: 0.2 }
│   └── patches/
│       └── conciencia/consciousness_action.py  ← Override: más propenso a "assume"
└── consciousness/
    ├── thresholds.json
    │   ├── assume: 0.85
    │   ├── evolution_rate: 0.2
    │   └── build_assume_bonus: 0.2
    └── cycles.jsonl                       ← 200+ ciclos, patrones WP
```

Mismo creador (`durru`), mismo `identity.yaml` original. Ramas completamente irreconocibles.

---

## Migración desde el sistema actual

### Estado actual

```
/var/guardian/
├── genome/branches/<hash>/          ← Ramas por proyecto (vacíos)
├── projects/<slug>/                 ← ACÁ está toda la data real
│   ├── conciencia-state.json
│   ├── conciencia-thresholds.json
│   ├── memory.jsonl
│   ├── learnings/
│   ├── skills.json
│   ├── knowledge/tomes/
│   └── config.yaml
└── skills-global.json
```

### Estado futuro

```
/var/lib/nexxoria-guardian/genome/branches/<hash>/
├── identity.yaml                    ← Migrado de genome/identity.yaml + forked
├── state.json                       ← Nuevo
├── consciousness/
│   ├── cycles.jsonl                 ← Migrado de projects/*/conciencia-state.json
│   └── thresholds.json              ← Migrado de projects/*/conciencia-thresholds.json
├── memory/
│   ├── cross-project.jsonl          ← Nuevo
│   └── projects/<slug>.jsonl       ← Migrado de projects/*/memory.jsonl
├── knowledge/
│   ├── tomes/                       ← Migrado de projects/*/knowledge/tomes/ (dedup)
│   └── projects/<slug>/            ← Projects config + skills
├── learnings/
│   ├── cross-project/
│   └── projects/<slug>/
├── context/
│   ├── session-<slug>.json          ← Nuevo
│   └── usage-stats.json             ← Nuevo
├── evolved/                         ← Nuevo
│   ├── manifest.json
│   ├── evolution-history.jsonl
│   ├── commands/
│   ├── mcp_tools/
│   ├── context_providers/
│   ├── conciencia_actions/
│   ├── thresholds/
│   └── patches/
└── evolution/                       ← Nuevo
    └── proposals/
```

### Estrategia de migración

```
Fase 1: Crear estructura nueva sin tocar la vieja
Fase 2: Migrar datos (copia, no corte)
Fase 3: Dual-write (escribe en ambos lados)
Fase 4: Cutover (la nueva es la única fuente)
Fase 5: Limpiar vieja
```

---

## Implementación: fases y orden

### Fase 1 — Rama única por máquina (refactor de ramas)
- [ ] `guardian_genome.py`: cambiar `fork_branch(slug)` → `fork_branch()` (sin slug, única por máquina)
- [ ] `guardian_genome.py`: `_branch_path()` usa hash de machine-id (o `$GUARDIAN_MACHINE_ID`)
- [ ] `guardian_genome.py`: `identity.yaml` de rama incluye `forked_from`, `forked_at`, `creator`
- [ ] `guardian_genome.py`: proyectos son subdirectorios dentro de la rama
- [ ] Migrar `list_branches()` a mostrar una sola rama + sus proyectos
- [ ] Tests: test_fork_unique_branch, test_branch_preserves_origin

### Fase 2 — Evolved directory + manifest
- [ ] Crear `evolved/` en el branch path
- [ ] `manifest.json`: schema + load/save/register
- [ ] `evolution-history.jsonl`: schema + append-only writer
- [ ] `guardian evolution status`: muestra rama, version, #evoluciones
- [ ] `guardian evolution history`: muestra historial completo
- [ ] `guardian evolution rollback <id>`: revierte evolución
- [ ] Tests: test_manifest, test_history, test_rollback

### Fase 3 — Sistema de seguridad (6 barreras)
- [ ] `validate_syntax()`: compile check
- [ ] `validate_imports()`: allowed imports only
- [ ] `validate_builtins()`: no exec/eval/__import__
- [ ] `validate_size()`: max 50KB
- [ ] Integrar validación como paso obligatorio antes de activar
- [ ] Tests para cada barrera + test de código malicioso rechazado

### Fase 4 — Template engine
- [ ] Directorio de templates: `$GUARDIAN_HOME/evolution/templates/`
- [ ] Template loader: carga `.py.tpl`, parsea placeholders `{{variable}}`
- [ ] Template renderer: llena con params, escribe `.py`
- [ ] Templates iniciales: `command.py.tpl`, `patch.py.tpl`, `mcp_tool.py.tpl`, `provider.py.tpl`
- [ ] `guardian evolution template list`: lista templates disponibles
- [ ] Tests: test_template_render, test_template_validation

### Fase 5 — Generative engine (detección de patrones)
- [ ] `guardian_evolution.py`: `detect_patterns()` escanea ciclos, memoria, contexto, errores
- [ ] Patrones: comandos secuenciales, stack detectado, contexto ignorado, pregunta repetida, threshold estático, función infrautilizada
- [ ] `generate_proposal(patron, params)`: escribe YAML en `evolution/proposals/`
- [ ] Auto-clasificar: pequeño/mediano → auto; grande/muy grande → pending
- [ ] `guardian evolution proposals`: lista propuestas pendientes
- [ ] `guardian evolution approve <id>`: activa propuesta
- [ ] `guardian evolution reject <id>`: descarta
- [ ] Tests: test_detect_patterns, test_generate_proposal, test_auto_classify

### Fase 6 — N2 generativo (integración con conciencia)
- [ ] `guardian_conciencia.py`: N2 extendido con 3 capas (estadístico, generativo, creativo)
- [ ] Generative engine corre cada `evolution_rate * 10` ciclos
- [ ] Inyectar en contexto: "evo_001: nuevo comando quick-match disponible"
- [ ] `generation-counter.txt`: límite por sesión
- [ ] Tests: test_n2_generative, test_context_injection

### Fase 7 — Override system (parches al core)
- [ ] Manifest loader escanea `evolved/patches/` al inicio
- [ ] Dispatcher en `guardian.py` consulta manifest antes de dispatch
- [ ] Dispatcher en `guardian_conciencia.py` consulta manifest antes de ciclo
- [ ] Dispatcher en `guardian_mcp.py` consulta manifest antes de tool call
- [ ] Lista blanca de funciones overrideables
- [ ] Tests: test_override_dispatch, test_override_not_core

### Fase 8 — Migración de datos
- [ ] Script `migrate_branches.py`: lee estructura vieja, escribe nueva
- [ ] Dual-write durante periodo de transición
- [ ] Cutover: nueva estructura es la única fuente
- [ ] Tests: test_migration, test_dual_write

### Fase 9 — Evolution thresholds expandidos
- [ ] Expandir `THRESHOLD_KEYS` en conciencia: `evolution_rate`, `max_context_tokens`, `auto_approve_threshold`
- [ ] Nuevos thresholds se crean en `evolved/thresholds/`
- [ ] `read_thresholds()` mergea base + evolucionados
- [ ] Tests: test_custom_thresholds, test_threshold_merge

### Fase 10 — Documentación + install.sh update
- [ ] `docs/EVOLUCION.md`: documentación del sistema de evolución
- [ ] Actualizar `SKILL.md` con evolución generativa
- [ ] Actualizar `install.sh` con directorios de evolución
- [ ] Tests e2e: ciclo completo N1 → N2 → pattern detect → proposal → auto-activate

---

## Resumen de comandos nuevos

| Comando | Descripción |
|---------|-------------|
| `guardian evolution status` | Estado de la rama evolutiva |
| `guardian evolution history` | Historial completo (append-only) |
| `guardian evolution proposals` | Propuestas pendientes |
| `guardian evolution approve <id>` | Activar propuesta pendiente |
| `guardian evolution reject <id>` | Rechazar propuesta |
| `guardian evolution rollback <id>` | Revertir evolución activa |
| `guardian evolution template list` | Listar templates disponibles |

---

## Archivos del plan

```
$GUARDIAN_HOME/evolution/
├── templates/                          ← Templates .py.tpl
│   ├── command.py.tpl
│   ├── patch.py.tpl
│   ├── mcp_tool.py.tpl
│   └── provider.py.tpl
└── thresholds/
    └── evolution-defaults.yaml         ← Umbrales de evolución

$GUARDIAN_DATA/genome/branches/<hash>/
├── evolved/
│   ├── manifest.json
│   ├── evolution-history.jsonl
│   ├── commands/
│   ├── mcp_tools/
│   ├── context_providers/
│   ├── conciencia_actions/
│   ├── thresholds/
│   └── patches/
└── evolution/
    ├── proposals/
    └── generation-counter.txt
```
