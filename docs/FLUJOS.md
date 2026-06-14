# Guardian v2 — Flujos

## Flujo 1: Inicio de sesión

```
Usuario inicia sesión en OpenCode
       │
       ▼
Guardian detecta proyecto (git remote o PWD)
       │
       ▼
Carga config.yaml del proyecto
       │
       ▼
¿Existe rama para este usuario?
       ├── Sí → Cargar estado de conciencia anterior
       └── No  → Fork de rama default
                    │
                    ▼
               Crear identity.yaml + state.json
                    │
                    ▼
               Registrar metadatos de sesión
       │
       ▼
Detectar modo:
  ¿Primer mensaje es "qué pasaría si..."? → Modo Plan
  ¿Primer mensaje es "hacé esto"?         → Modo Build
       │
       ▼
Ejecutar ciclo de conciencia N1 (percibir)
  - Cargar contexto del proyecto
  - Consultar RAG (según modo)
  - Computar confianza
  - Determinar acción (assume/ask_little/ask_much/investigate)
       │
       ▼
Inyectar contexto + acción en el prompt del LLM
```

**Comandos:**
```bash
guardian detect                           # Detectar proyecto
guardian context --brief [slug]           # Cargar contexto
guardian mode status [slug]               # Ver modo actual
guardian conciencia status [slug]         # Ver estado de conciencia
guardian branch status [slug]             # Ver rama actual
```

---

## Flujo 2: Ciclo de conciencia completo

```
Ciclo de conciencia (N1 + N2)
       │
       ▼
── N1: PERCIBIR ──
  - Recibir pregunta/input del usuario
  - Cargar modo actual (plan/build)
  - Consultar RAG con la pregunta
  - Recibir contexto adicional (memoria, skills, errores)
       │
       ▼
── N1: DECIDIR ──
  - score_context() computa confianza (0.0 - 1.0)
  - consciousness_action() determina acción según umbrales + bonus de modo
  - Resultado: assume / ask_little / ask_much / investigate
       │
       ▼
── N1: REFLEXIONAR ──
  - Guardar ciclo en conciencia-state.json
  - Si hay RAG results relevantes, guardar como referencia
       │
       ▼
── N2: META-EVOLUCIÓN (automática si ≥5 ciclos) ──
  - Analizar últimos 5-20 ciclos
  - Calcular distribución de acciones
  - Si es necesario, ajustar umbrales
  - Guardar aprendizaje (learning)
       │
       ▼
── RESPUESTA ──
  - Devolver acción + confianza + meta (si hubo)
```

**API:**
```bash
curl -X POST :9787/conciencia/cycle \
  -H "Content-Type: application/json" \
  -d '{"slug":"mi-proyecto","question":"¿debería usar React o Vue?","mode":"plan"}'

# Respuesta:
# {
#   "action": "ask_much",
#   "confidence": 0.35,
#   "meta": { ... }  # si hubo meta-evolución
# }
```

**CLI:**
```bash
guardian conciencia cycle "mi pregunta" [slug]
guardian conciencia status [slug]
guardian conciencia history [slug]
guardian conciencia meta [slug]
```

---

## Flujo 3: Ingest de conocimiento (skills → tomos → RAG)

```
Skills globales (skills-global.json)
       │
       ▼
absorb scan        ─── Actualiza índice global de skills
       │
       ▼
absorb match <slug> ─── Matches skills relevantes al proyecto
       │
       ▼ (automático)
absorb ingest <slug> ─── Convierte skills matcheados en tomos
       │                     (knowledge/tomes/<skill>.md)
       │
       ▼ (automático)
RAG index          ─── Indexa los tomos al RAG
```

**Comandos:**
```bash
guardian absorb scan                           # Escanear skills globales
guardian absorb match mi-proyecto              # Matchear skills
guardian absorb ingest mi-proyecto             # Convertir a tomos (automático tras match/classify)
guardian absorb classify mi-proyecto           # Clasificar (también hace ingest automático)
guardian knowledge status mi-proyecto          # Ver tomos disponibles
guardian knowledge search mi-proyecto "consulta"  # Buscar en tomos
```

**API:**
```bash
curl -X POST :9787/absorb/ingest -d '{"slug":"mi-proyecto"}'
curl -X POST :9787/absorb/scan -d '{"slug":"mi-proyecto"}'
curl -X POST :9787/absorb/classify -d '{"slug":"mi-proyecto"}'
curl :9787/knowledge/tomes?slug=mi-proyecto
curl :9787/knowledge/search?slug=mi-proyecto&q=consulta
```

---

## Flujo 4: Documentación → RAG

```
Templates (templates/*.template)
       │
       ▼
docs scan <slug>    ─── Genera docs/ a partir de templates
       │
       ▼ (automático)
RAG index --force   ─── Re-indexa los docs generados al RAG
       │
       ▼
Consultas RAG incluyen docs como fuente
```

**Comandos:**
```bash
guardian docs scan mi-proyecto                 # Generar docs
guardian docs route /api/users mi-proyecto     # Ver qué doc aplica
guardian rag "consulta" --slug mi-proyecto     # Buscar en RAG
```

**API:**
```bash
curl -X POST :9787/docs/scan -d '{"slug":"mi-proyecto"}'
curl :9787/rag?slug=mi-proyecto&q=consulta&mode=plan
```

---

## Flujo 5: Evolución de rama

```
La meta-conciencia detecta umbrales mal calibrados
       │
       ▼
Ajusta umbrales en conciencia-thresholds.json
       │
       ▼
Guarda aprendizaje en learnings/<ts>.json
       │
       ▼
Usuario puede disparar evolución manual:
       │
       ▼
evolve <slug>       ─── Ejecuta meta-evolución sobre ciclos existentes
       │
       ▼
consolidate <slug>  ─── Limpia memoria vencida + re-indexa RAG + compacta learnings
```

**Comandos:**
```bash
guardian evolve mi-proyecto                    # Evolucionar rama
guardian consolidate mi-proyecto               # Consolidar (GC + RAG)
guardian branch status mi-proyecto             # Ver estado de rama
guardian branch diff mi-proyecto               # Diff genoma vs rama
guardian genome status                         # Ver identidad
guardian genome diff mi-proyecto               # Diff genoma vs rama
```

**API:**
```bash
curl -X POST :9787/evolve -d '{"slug":"mi-proyecto"}'
curl -X POST :9787/consolidate -d '{"slug":"mi-proyecto"}'
curl :9787/genome
curl :9787/branch?slug=mi-proyecto
curl -X POST :9787/branch/fork -d '{"slug":"nuevo-usuario"}'
```

---

## Flujo 6: Backend lifecycle

```
── INICIO ──
guardian backend start
  - Crea PID file en /var/guardian/guardian-backend.pid
  - Logs en /var/guardian/guardian-backend.log
  - Escucha en 127.0.0.1:9787
       │
       ▼
── OPERACIÓN ──
  - Endpoints REST disponibles
  - CLI usa el backend via HTTP (curl/subprocess)
  - MCP server separado via stdio
  - Meta-evolución automática post ciclo
       │
       ▼
── FIN ──
guardian backend stop
  - Envía SIGTERM al proceso
  - Limpia PID file
```

**Comandos:**
```bash
guardian backend start        # Iniciar daemon
guardian backend status       # Ver estado
guardian backend stop         # Detener
guardian backend restart      # Reiniciar
```

---

## Flujo 7: MCP Integration

```
Agente OpenCode
       │
       ▼
Conecta a MCP server via stdio
       │
       ▼
initialize ─── Obtiene protocolVersion + capabilities
       │
       ▼
list_tools ─── Obtiene lista de 9 herramientas
       │
       ▼
call_tool:
  ├── read_file         → Leer archivo
  ├── write_file        → Escribir (solo build)
  ├── run_command       → Ejecutar bash
  ├── rag_query         → Consultar RAG
  ├── conciencia_cycle  → Ciclo de conciencia
  ├── mode_switch       → Cambiar modo
  ├── knowledge_search  → Buscar tomos
  ├── genome_status     → Ver genoma
  └── branch_fork       → Crear rama
```

**Iniciar MCP server:**
```bash
python3 lib/guardian_mcp.py    # Lee JSON-RPC de stdin, escribe a stdout
```

**O via backend HTTP:**
```bash
curl -X POST :9787/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"slug":"mi-proyecto","tool":"rag_query","args":{"query":"cómo se configura el proyecto"}}'
```
