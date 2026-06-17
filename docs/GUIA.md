# Guardian v2 — Guía de inicio rápido

## Requisitos

- Python 3.9+ (stdlib, sin dependencias externas excepto PyYAML opcional)
- Sistema Linux (para daemon backend con PID file)

## Instalación

```bash
# El proyecto ya está en /srv/guardian/
cd /srv/guardian

# Verificar que todo funciona
python3 -m unittest discover -s tests -p "test_*.py"

# Verificar lint
python3 -c "import ast; ast.parse(open('lib/guardian.py').read())"
```

## Primeros pasos

### 1. Detectar un proyecto

```bash
# Desde cualquier directorio dentro del proyecto
guardian detect

# O especificar slug directamente
guardian status mi-proyecto
```

### 2. Configurar un proyecto nuevo

```bash
guardian setup mi-proyecto
# Esto crea config.yaml, configura stack, escanea docs y skills
```

### 3. Probar los modos

```bash
# Ver modo actual
guardian mode status

# Cambiar a modo build
guardian mode build "Voy a implementar"

# Cambiar a modo plan
guardian mode plan "Necesito investigar primero"
```

### 4. Probar conciencia

```bash
# Ver estado de conciencia
guardian conciencia status mi-proyecto

# Ejecutar ciclo de conciencia
guardian conciencia cycle "¿Cómo estructuro este módulo?" mi-proyecto

# Ver historial
guardian conciencia history mi-proyecto

# Ejecutar meta-evolución
guardian conciencia meta mi-proyecto
```

### 5. Probar RAG

```bash
# Indexar docs al RAG
guardian docs scan mi-proyecto

# Buscar en RAG
guardian rag "cómo se configura el stack" --slug mi-proyecto --json
```

### 6. Probar absorb (skills → tomos)

```bash
# Escanear skills globales
guardian absorb scan

# Matchear skills al proyecto
guardian absorb match mi-proyecto

# Ver tomos generados
guardian knowledge status mi-proyecto

# Buscar en tomos
guardian knowledge search mi-proyecto "autenticación"
```

### 7. Iniciar backend persistente

```bash
# Iniciar daemon
guardian backend start

# Verificar salud
curl http://127.0.0.1:9787/health

# Consultar RAG vía API
curl "http://127.0.0.1:9787/rag?slug=mi-proyecto&q=consulta"

# Ejecutar ciclo de conciencia vía API
curl -X POST http://127.0.0.1:9787/conciencia/cycle \
  -H "Content-Type: application/json" \
  -d '{"slug":"mi-proyecto","question":"¿debería usar SQLite?"}'

# Detener backend
guardian backend stop
```

### 8. Ver genoma y ramas

```bash
# Ver identidad de Guardian
guardian genome status

# Listar ramas existentes
guardian branch list

# Crear rama para nuevo usuario
guardian branch fork nuevo-usuario

# Ver estado de rama
guardian branch status mi-proyecto

# Ver diferencias genoma vs rama
guardian genome diff mi-proyecto
```

### 9. Evolución y consolidación

```bash
# Disparar evolución de rama (meta-evolución)
guardian evolve mi-proyecto

# Consolidar (GC memoria + re-index RAG + compactar learnings)
guardian consolidate mi-proyecto
```

## Ejemplos rápidos

### Ejemplo 1: Workflow diario

```bash
# 1. LLegar al proyecto
cd /ruta/del/proyecto

# 2. Cargar contexto
guardian context --brief

# 3. Ver estado
guardian status

# 4. Cambiar a modo build
guardian mode build "Implementar feature X"

# 5. Trabajar...
# (OpenCode usa RAG y conciencia automáticamente)

# 6. Al final del día, consolidar
guardian consolidate
```

### Ejemplo 2: Investigación (Modo Plan)

```bash
# El agente detecta automáticamente modo Plan por la pregunta
# "Qué pasaría si migramos a PostgreSQL?"

# O manualmente:
guardian mode plan "Evaluar migración a PostgreSQL"

# Consultar RAG para contexto
guardian rag "patrones de migración PostgreSQL" --slug mi-proyecto

# Ejecutar conciencia para decidir si preguntar o investigar
guardian conciencia cycle "¿conviene migrar?" mi-proyecto
```

### Ejemplo 3: Usar MCP desde OpenCode

```bash
# Iniciar MCP server (el agente OpenCode lo conecta automáticamente)
python3 lib/guardian_mcp.py

# El agente puede ahora invocar tools:
# - read_file: leer archivos del proyecto
# - rag_query: consultar RAG antes de implementar
# - conciencia_cycle: ejecutar ciclo de conciencia
# - mode_switch: cambiar entre plan y build
# - write_file: solo funciona en modo build
```

### Ejemplo 4: API-driven automation

```bash
# Script que usa el backend para automatizar

BACKEND="http://127.0.0.1:9787"
SLUG="mi-proyecto"

# Cambiar a modo build
curl -X POST "$BACKEND/mode" -d "{\"slug\":\"$SLUG\",\"mode\":\"build\",\"reason\":\"auto\"}"

# Ejecutar ciclo de conciencia
curl -X POST "$BACKEND/conciencia/cycle" \
  -d "{\"slug\":\"$SLUG\",\"question\":\"refactorizar módulo auth\"}"

# Consultar RAG
curl "$BACKEND/rag?slug=$SLUG&q=estructura+auth"

# Ingestar skills
curl -X POST "$BACKEND/absorb/ingest" -d "{\"slug\":\"$SLUG\"}"

# Consolidar
curl -X POST "$BACKEND/consolidate" -d "{\"slug\":\"$SLUG\"}"

# Ver estado de conciencia
curl "$BACKEND/conciencia/state?slug=$SLUG"
```

## Troubleshooting

### Error: "Proyecto no encontrado"
```bash
# Primero crear el proyecto
guardian setup mi-proyecto
```

### Error: Backend no responde
```bash
guardian backend status     # Ver si está corriendo
guardian backend start      # Iniciar si no
guardian backend restart    # Reiniciar si está colgado
```

### Error: Rama no existe
```bash
guardian branch fork mi-proyecto  # Crear rama para el usuario
```

### Error: Sin skills globales
```bash
guardian absorb scan        # Escanear skills disponibles
```

### Error: MCP no conecta
```bash
# Verificar que el server está corriendo
python3 lib/guardian_mcp.py
# Debe responder a mensajes JSON-RPC en stdin
```

## Variables de entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `GUARDIAN_LANG` | `en` | Idioma (es/en) para mensajes |
