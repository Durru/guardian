# Nexxoria Guardian v4

**Sistema operativo cognitivo para sesiones de IA — razona, evoluciona y completa a cualquier LLM.**

Guardian v4 es un ser orgánico que vive entre el humano, el LLM y el proyecto. No compite con el LLM: lo complementa. El LLM genera código; Guardian recuerda, indexa, razona sobre el pasado, conoce al usuario y no alucina.

---

## Los 3 pilares de v4

| Pilar | Qué hace | Cómo |
|-------|----------|------|
| **Razona** | Conciencia trazable con `sources` | `Conciencia.decide()` retorna decisiones con fuentes verificables |
| **Evoluciona** | Genoma + rama de usuario | `guardian update` absorbe el nuevo genoma; la rama evoluciona sin perder datos |
| **Completa al LLM** | Advisor + Observer + CodeGraph | Contexto dinámico (5-15 líneas), eventos capturados, mapa AST del proyecto |

## Características v4

- **🧠 Conciencia N1+N2** — ciclo percibir→decidir→reflexionar con trazabilidad. ASSUME solo con `confidence >= 0.8` Y al menos 1 source
- **📖 CodeGraph (tree-sitter)** — mapa AST real del proyecto en Python, TypeScript, JavaScript, Go. `query_smart` busca símbolos con firmas y docstrings
- **💡 Advisor** — contexto dinámico al LLM. Retorna `""` si no hay nada relevante (no ensucia la ventana de contexto)
- **👁️ Observer** — captura eventos del LLM y del usuario, sanitiza secrets (API keys, JWT, tokens), clasifica prompts
- **🧬 Genoma en 3 archivos** — `identity.yaml` (inmutable), `schema.yaml`, `consciousness.yaml`
- **🔐 Sistema de permisos** — módulos con guardias: `blocked`, `readonly`, `conciencia`, `allowed`
- **🔄 Migración v3→v4** — `guardian migrate migrate <slug>` preserva todos los datos
- **🧪 ~260 tests** — test unitarios + E2E del ciclo completo

## Requisitos

- **OS:** Ubuntu 22.04+ (o Debian-based)
- **Python:** 3.9+
- **OpenCode:** `>= 1.17`

## Instalación

```bash
git clone https://github.com/nexxoria/guardian.git
cd guardian
sudo bash install.sh
```

Opciones del instalador:
```bash
sudo bash install.sh --system      # default, instala en /opt/
sudo bash install.sh --user        # instala en ~/.local/
sudo bash install.sh --dev         # dev mode, no crea systemd
sudo bash install.sh --uninstall   # limpia todo (con safety check)
```

### Qué hace `install.sh`

1. Detecta OS + Python + OpenCode
2. Copia el repo a `/opt/nexxoria-guardian/`
3. Crea `/var/lib/nexxoria-guardian/` para datos runtime
4. Crea symlink `/usr/local/bin/guardian`
5. Registra servicio systemd (modo `--system`)
6. Instala skill en `~/.agents/skills/nexxoria-guardian/`
7. Instala comando `@guardian` en OpenCode
8. Registra MCP server
9. Instala tree-sitter (Python, TypeScript, JavaScript, Go)
10. Verifica instalación con import check + tests

**Después de instalar, reiniciá OpenCode y ejecutá `guardian activate` en tu proyecto.**

## Uso básico

```bash
# Ver ayuda
guardian --help

# Activar Guardian en un proyecto (idempotente)
cd /ruta/de/mi/proyecto
guardian activate

# Crear CodeGraph (AST del proyecto)
guardian codegraph index <slug>

# Buscar símbolos en el codegraph
guardian codegraph query <slug> "UserService"

# Migrar datos de v3 a v4
guardian migrate migrate <slug>

# Aplicar nuevo genoma
guardian update

# Ciclo de conciencia
guardian conciencia cycle "quiero agregar auth"

# Ver identidad del genoma
guardian genome status

# Estado de la rama de evolución
guardian branch status
```

Desde OpenCode:
```
@guardian context --brief
@guardian mode build
@guardian codegraph query <slug> "Calculator"
```

## Arquitectura

```
                    ┌─────────────────────────────┐
                    │    CEREBRO (LLM + Razonamiento)  │
                    │  Conciencia N1 + Advisor + RAG  │
                    └────────────┬────────────────┘
                                 │
    ┌────────────────────────────┼────────────────────────────┐
    ▼                            ▼                            ▼
┌──────────┐              ┌──────────┐              ┌────────────────┐
│ OJOS      │              │ MANOS    │              │ PIERNAS         │
│ (Contexto │              │ (CLI +   │              │ (Backend :9787  │
│  RAG +    │              │  Hooks + │              │  + MCP + API)   │
│  CodeGraph│              │  Git)    │              │                 │
│  + Skills)│              │          │              │                 │
└──────────┘              └──────────┘              └────────────────┘
                                 │
                            ┌────┴────┐
                            │ NANOS   │
                            │ (MCP    │
                            │  Tools) │
                            └─────────┘
```

### Stack

- **Runtime:** Python 3.9+
- **Storage:** SQLite (brain DBs + codegraph)
- **Dependencias:** tree-sitter, PyYAML
- **Tests:** pytest
- **Packaging:** pyproject.toml + install.sh

## Comandos principales

```bash
# Proyecto
guardian activate [slug]              # setup + branch + brain + absorb + docs + codegraph + conciencia
guardian status [slug]                # dashboard del proyecto
guardian detect                       # detectar proyecto actual

# CodeGraph (v4)
guardian codegraph index <slug>       # indexar AST del proyecto
guardian codegraph query <slug> <q>   # buscar símbolos
guardian codegraph status <slug>      # ver estado del índice

# Conciencia (v4)
guardian conciencia cycle [question]  # N1 percibir→decidir→reflexionar
guardian conciencia meta              # N2 meta-evolución

# Migración (v4)
guardian migrate status <slug>        # detectar datos v3
guardian migrate migrate <slug>       # migrar v3→v4
guardian migrate rollback <slug>      # revertir migración

# Genoma
guardian update                       # aplicar nuevo genoma
guardian genome status                # ADN del ser
guardian branch status                # rama de evolución
guardian propose <kind> <content>     # proponer patrón

# Sistemas
guardian mode plan|build|status       # modo de operación
guardian backend start|stop|status    # backend persistente
guardian rag <query>                  # búsqueda RAG
guardian context                      # contexto para AI
guardian memory <args>                # memoria persistente
guardian forja <sub> [args]           # La Forja (meta-módulo)
```

Ayuda completa: `guardian --help` o ver [docs/REFERENCIA.md](docs/REFERENCIA.md).

## Tests

```bash
python3 -m pytest tests/ -v
# ~260 tests passing
```

## Documentación

- [docs/CONCEPTOS.md](docs/CONCEPTOS.md) — Filosofía, ser orgánico, conciencia N1+N2
- [docs/FLUJOS.md](docs/FLUJOS.md) — Workflows
- [docs/REFERENCIA.md](docs/REFERENCIA.md) — CLI, API, MCP completos
- [docs/GUIA.md](docs/GUIA.md) — Inicio rápido
- [docs/PLAN_V4.md](docs/PLAN_V4.md) — Plan maestro v4

## Licencia

MIT
