# Plan v4.1.0 — Memoria persistente, Conciencia delegada, Contexto inteligente

## Visión

Guardian v4.1 convierte al sistema en una **conciencia delegada**: un agente primario que solo
piensa (percibe, decide, delega, reflexiona) y subagentes que ejecutan (escriben código,
investigan, gestionan memoria). GUARDIAN.md se vuelve el único archivo de documentación,
siempre compacto (~25 líneas), inyectado al inicio de cada sesión.

## Arquitectura

```
GUARDIAN (primary agent — CONCIENCIA)
  Tools: read + task SOLO (no escribe, no edita, no bash)
  ├── guardian-executor (subagent) → escribe código, edita, corre comandos
  ├── guardian-researcher (subagent) → investiga, busca, analiza
  ├── guardian-memory (subagent) → guarda/recupera del brain
  ├── guardian-observer (subagent) → clasifica eventos
  └── sdd-* (subagents) → planificación compleja
```

## Cambios

### guardian_brain.py
- `GUARDIAN_MD_MAX_LINES`: 200 → 30
- `generate_guardian_md()`: formato compacto estilo CLAUDE.md (Objetivo, Stack, Decisiones activas, Últimos errores)
- Nueva `write_observation()`: guarda con obs_type, topic_key, content, why, where, outcome, scope, tags
- Nueva `get_observations()`: busca por topic_key en proyecto + global
- Nueva `get_last_good()`: última observación exitosa
- Nueva `append_guardian_md_line()`: agrega 1 línea progresivamente, compacta si > 30
- Nueva `compact_guardian_md()`: compacta archivo

### guardian_observer.py
- Nueva `extract_topic_key()`: extrae topic_key del prompt por keywords
- Nueva `classify_importance()`: clasifica importancia 0-1 según longitud, keywords, tipo
- Observer._on_prompt(): auto-guarda en brain si importancia > 0.5

### guardian_mcp.py
- 6 nuevas tools: `analyze_intent`, `save_observation`, `get_observation`, `get_last_good`, `plan_or_act`, `compact_memory`

### guardian.py
- `cmd_docs_scan` reescrito: no genera templates, escribe stack en brain, regenera GUARDIAN.md
- Eliminados: `DOC_TEMPLATES`, `_render_and_maybe_write`

### .opencode/plugins/guardian.ts
- `session.created`: solo inyecta GUARDIAN.md (sin Advisor)
- `chat.message`: analiza intent + busca observaciones + auto-save
- `tool.execute.after`: guarda observación si fue edit/write
- `experimental.session.compacting`: re-inyecta GUARDIAN.md

### prompts/guardian-agent.md (NUEVO)
Prompt completo del agente primario: personalidad, ciclo, subagentes, reglas

### opencode.json
Agente `guardian` (primary) + `guardian-executor`, `guardian-researcher`, `guardian-memory`, `guardian-observer` (subagents)

### install.sh
Nueva función `install_agent()`: registra agente Guardian en opencode.json
