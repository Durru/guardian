# Plan: OpenCode Plugin Guardian

> Plugin que integra Nexxoria Guardian v2 como plugin de OpenCode.
> Features: contexto (2), conciencia (3), modo detect (4)

## Resumen

El plugin se instala en `.opencode/plugins/guardian.ts` y se activa automáticamente
al iniciar OpenCode. Usa el hook API de OpenCode para:

1. **Context Injection**: Inyectar genoma/identidad/modo en cada sesión
2. **Conciencia Integration**: Custom tools para ciclo conciencia, RAG, modo
3. **Auto Mode Detection**: Detectar plan vs build desde el prompt del usuario

## Arquitectura

```
OpenCode (TS)        Guardian MCP (Python)
  │                        │
  ├─ session.created ──────├─ genome_status
  ├─ session.compacting ───├─ mode_switch
  ├─ custom tools ─────────├─ conciencia_cycle
  └─ shell.env ────────────├─ rag_query
                           └─ knowledge_search
```

El plugin NO duplica lógica — delega al MCP via Python CLI calls con `$`.

## Modulos

### 1. Context Injection (`session.created`)

Hook `session.created`:
- Lee modo actual del proyecto via `guardian mode status`
- Inyecta en el prompt del LLM:
  - Modo actual (plan/build)
  - Identidad del genoma
  - Rama activa
  - Breve resumen de estado

Hook `experimental.session.compacting`:
- Inyecta estado actual de Guardian en el compaction
- Previene pérdida de contexto entre compactaciones

### 2. Custom Tools

- `guardian_status()` → genome + branch + mode
- `guardian_conciencia(question?)` → ciclo N1/N2
- `guardian_rag(query)` → buscar en conocimiento
- `guardian_mode_switch(mode, reason)` → toggle plan/build

### 3. Auto Mode Detection (`tui.prompt.append`)

- Escanea el texto del prompt del usuario
- Si contiene palabras clave de exploración (plan, think, analyze, design, architect)
  → cambia a modo `plan`
- Si contiene palabras clave de ejecución (build, implement, fix, add, create)
  → cambia a modo `build`
- No cambia si el usuario especificó explícitamente el modo

## Files

- `.opencode/plugins/guardian.ts` — Plugin principal
- `.opencode/package.json` — Dependencias (@opencode-ai/plugin)
- `PLAN-OPENCODE-PLUGIN.md` — Este documento

## Orden

1. ✅ Crear `.opencode/package.json`
2. ✅ Crear `.opencode/plugins/guardian.ts`
3. ✅ Registrar plugin en `opencode.json`
4. ⏳ Push a GitHub
4. Verificar que OpenCode carga el plugin
