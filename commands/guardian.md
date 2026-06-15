---
name: guardian
description: Comando @guardian para OpenCode — invoca el CLI Guardian v3 desde chat
---

# @guardian — CLI desde OpenCode

`@guardian <subcomando> [args]` invoca el CLI Guardian v3.

## Comandos principales

### Sesión
```
@guardian activate                          # setup + absorb + conciencia
@guardian session start <slug>
@guardian session continue <slug>
@guardian session end <slug>                 # reflection + GUARDIAN.md regen
@guardian mode <read|plan|build|commit|review>
```

### Cerebro
```
@guardian brain read                        # GUARDIAN.md esencial
@guardian brain query <level> "consulta"    # semantic|episodic|procedural|reflection
@guardian brain write <level> "texto" --kind pattern --importance 0.8
@guardian brain reflect <slug>              # post-sesión reflection
@guardian brain regenerate-guardian <slug>
@guardian brain auto-compact <slug>
```

### Knowledge
```
@guardian knowledge research <slug> "tema" --depth quick|deep
@guardian knowledge refresh <slug>
@guardian knowledge scrape <slug> <url>
```

### Specializations
```
@guardian specialization enable <slug> odoo
@guardian specialization disable <slug> odoo
@guardian specialization list
```

### Plan
```
@guardian plan new <slug> "título"
@guardian plan list <slug>
@guardian plan status <slug> <plan-id>
@guardian plan transition <slug> <plan-id> <state>
```

### Mantenimiento
```
@guardian maintain <slug>                   # drift + health
@guardian global status                     # cross-project memory
@guardian global promote <node-id>          # ascender a global
@guardian capability status                 # model card
@guardian capability routing <task>         # delegar al LLM?
```

### Publicar / Distribuir
```
@guardian publish <slug> 1.0.0              # template sanitizado
@guardian clone <template> <new-slug>
@guardian fork <parent> <child>
@guardian migrate <slug>                    # v2 → v3
```

### Backend y sistema
```
@guardian backend start|stop|status
@guardian conciencia cycle <slug>
@guardian context --brief
@guardian --help
```

## Ejemplos

```
@guardian mode plan
@guardian brain read

@guardian brain query semantic "fastapi auth jwt"
@guardian brain write semantic "API usa JWT con refresh tokens" --kind pattern --importance 0.85

@guardian specialization enable odoo
@guardian plan new myproject "Migrar módulo a v18"
@guardian maintain myproject
@guardian publish myproject 1.0.0

@guardian session end myproject
```

## Reglas

1. Antes de actuar: `@guardian brain read`
2. Cambios grandes: `@guardian mode plan` primero
3. Implementar: `@guardian mode build`
4. Cerrar sesión: `@guardian session end` (dispara reflection)
5. Duda sobre algo histórico: `@guardian brain query`
