# Plan V4 — Guardian como ser que razona, evoluciona y completa a cualquier IA

## Visión

Guardian v4 es un **sistema operativo cognitivo** que vive entre el humano, el LLM y el proyecto. No compite con el LLM: lo complementa. El LLM hace lo que sabe (generar, leer); Guardian hace lo que el LLM no puede (recordar, indexar, razonar sobre el pasado, conocer al usuario, conocer al creador, no alucinar).

## Reglas inmutables

1. **Guardian actúa en base a lo que sabe y no a lo que se imagina** — toda decisión es trazable a un dato del cerebro.
2. **Guardian tiene un mapa real de cada proyecto** — codegraph (AST real indexado en la raíz).
3. **La rama es lo que va llenando** — la rama ES el contenedor de la evolución.
4. **Guardian no ensucia la ventana de contexto** — Advisor retorna `""` si nada relevante.
5. **El genoma es único y solo yo lo puedo modificar** — `genome/*.yaml` es tuyo, runtime lo lee.
6. **La Conciencia sabe quién es** — Guardian, vos (creator), el usuario actual.
7. **Las manos y los pies son las herramientas** — CLI, HTTP, MCP, Web, Plugin TS son herramientas, no Conciencia.
8. **Guardian evoluciona según sea necesario y tiene la rama para eso** — el genoma se actualiza con tags, las ramas absorben.

## Modelo de filesystem

```
$GUARDIAN_DATA/
└── users/
    └── <machine-id>/                  # Tu rama (única por usuario)
        ├── branch.json                # metadata
        ├── identity.json              # quién es el usuario
        ├── evolution/                 # lo que Guardian aprendió del usuario
        │   ├── models/
        │   ├── capabilities/
        │   ├── functions/
        │   ├── restrictions/
        │   ├── proposals/             # patterns propuestos al genoma (pending)
        │   └── learnings/
        └── projects/
            └── <slug>/
                ├── root/               # LA RAÍZ DEL PROYECTO
                │   ├── config.yaml
                │   ├── mode-state.json
                │   ├── brain/
                │   │   ├── semantic.db
                │   │   ├── episodic.db
                │   │   ├── procedural.db
                │   │   ├── reflection.db
                │   │   ├── codegraph.sqlite
                │   │   ├── prompts.jsonl
                │   │   ├── decisions.jsonl
                │   │   ├── stack_history.jsonl
                │   │   ├── test_results.jsonl
                │   │   ├── events.log
                │   │   └── GUARDIAN.md
                │   ├── lineage.json
                │   └── ...
                └── root-link.json
```

## Tres pilares

### Pilar 1: Razona (Conciencia)

`Conciencia` es un motor de razonamiento trazable. Lee del brain, no inventa. Cada decisión tiene `sources: list[str]`.

### Pilar 2: Evoluciona (Genoma + Rama)

- Vos actualizás el genoma (push + tag en el repo).
- El usuario hace `guardian update` y absorbe.
- Guardian propone patterns → el genoma decide si pasan a la rama.

### Pilar 3: Completa al LLM (Advisor + Observer)

- **Observer**: captura TODO evento del LLM y del usuario. Procesa. Guarda.
- **Advisor**: cuando el LLM necesita contexto, le da SOLO lo necesario (max 1k tokens, "" si nada).

## Roadmap (4 semanas)

### Semana 1: Modelo de razonamiento + filesystem
- D1: Filesystem nuevo + paths
- D2: Genoma separado en 3 archivos
- D3-4: Conciencia razona con sources trazables
- D5: Workflow de updates

### Semana 2: El mapa del proyecto
- D6-7: Schema del codegraph (5 tablas nuevas)
- D8-9: Indexer tree-sitter (Python, TS, Go)
- D10: query_smart (1 tool = 40 calls)

### Semana 3: Observer + Advisor
- D11-12: Observer (event bus + classifier + sanitizer)
- D13-14: Advisor (context dinámico)
- D15: Conciencia integrada con Advisor

### Semana 4: Plugin TS + tests + polish
- D16-17: Plugin TS refactor (5 hooks)
- D18-19: Tests E2E
- D20: Tag v4.0.0 + release

## Criterios de aceptación

1. **Razona**: cada `Conciencia.decide()` retorna decisiones con `sources: list[str]` no vacía.
2. **Evoluciona**: `guardian update` absorbe el nuevo genoma sin perder datos.
3. **No ensucia**: `Advisor.build_context()` retorna `""` cuando no hay nada relevante.
4. **No alucina**: `Conciencia.assume()` solo con `confidence >= 0.8` Y al menos 1 source.
5. **El genoma es tuyo**: ningún código de runtime modifica `genome/*.yaml`.
6. **Los 915 proyectos existentes no se rompen**: la migración preserva los datos.

## Archivos

**Nuevos (6):**
- `lib/guardian_migration_v3_layout.py`
- `lib/guardian_observer.py`
- `lib/guardian_brain_symbols.py`
- `lib/guardian_brain_advisor.py`
- `genome/schema.yaml`
- `genome/consciousness.yaml`

**Refactorizados (5):**
- `lib/guardian_conciencia.py`
- `lib/guardian_genome.py`
- `lib/guardian_brain_schema.py`
- `lib/guardian_brain.py`
- `lib/guardian_shared.py`

**Extender (3):**
- `lib/guardian.py`
- `lib/guardian_backend.py`
- `.opencode/plugins/guardian.ts`

**Sin tocar (intactos):** todo lo demás. 0 archivos borrados.

## Dependencias

```toml
dependencies = [
    "tree-sitter>=0.21",
    "tree-sitter-python>=0.21",
    "tree-sitter-typescript>=0.21",
    "tree-sitter-javascript>=0.21",
    "tree-sitter-go>=0.21",
]

[project.optional-dependencies]
embeddings = ["sentence-transformers"]
telemetry = ["requests"]
```

**Eliminada:** la regla "zero-deps".

## Lo que le falta a cualquier IA (lo que Guardian resuelve)

| Limitación del LLM | Cómo la resuelve Guardian |
|---|---|
| No recuerda entre sesiones | Brain persistente (5 niveles × 2 scopes) |
| Alucina cuando no sabe | Conciencia: si no hay dato, INVESTIGA |
| No conoce al usuario | Rama del usuario |
| No conoce al creador | Genoma |
| No tiene mapa del proyecto | CodeGraph |
| Olvida prompts | Observer |
| No aprende de errores propios | Reflection Agent |
| No detecta cambios de stack | Stack Watcher |
| No corre tests automáticamente | Test Watcher |
| No sabe qué tests pasaban antes | Test baseline |
| No inyecta contexto relevante | Advisor (5-15 líneas) |
| No bloquea acciones destructivas | Permission System + Conciencia |
| Ensucia la ventana de contexto | Advisor retorna "" si nada |
| No razona sobre el pasado | Conciencia con brain + codegraph + decisiones |
