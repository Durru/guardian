# Nexxoria Guardian v3

**Universal project guardian for OpenCode AI sessions — con memoria cognitiva.**

Guardian es un ser orgánico que protege, guía y evoluciona tus proyectos.
v3 introduce **memoria cognitiva persistente**: el cerebro digital que recuerda, olvida, reflexiona y evoluciona entre proyectos y sesiones.

---

## Características v3

- **5 niveles de memoria** — Working Memory + 4 project DBs (semantic/episodic/procedural/reflection) + 3 global DBs
- **GUARDIAN.md** — archivo ≤200 líneas cargado en cada sesión, regenerado automáticamente
- **Governor** — memoria con importance/TTL/duplicate/contradiction (puede olvidar)
- **Reflection Agent** — post-sesión: extrae lecciones, actualiza procedural/reflection
- **5 modes** — read, plan, build, commit, review
- **Specializations** — stack-aware: odoo, nextjs, fastapi, postgres, python
- **OpenSpec + planes ad-hoc** — state machine para propuestas
- **Publish/Clone/Fork** — sanitización + linaje de proyectos
- **Capability routing** — model card con EMA, decide si delegar al LLM

---

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
2. Copia el repo a `/opt/nexxoria-guardian/` (o `~/.local/nexxoria-guardian/`)
3. Crea `/var/lib/nexxoria-guardian/` para datos runtime
4. Crea symlink `/usr/local/bin/guardian`
5. Registra servicio systemd (modo `--system`)
6. Instala skill en `~/.agents/skills/nexxoria-guardian/`
7. Instala comando `@guardian` en OpenCode
8. Registra MCP server
9. Verifica instalación con `doctor`

**Después de instalar, reiniciá OpenCode y decí "activo guardian".**

## Uso básico

```bash
# Ver ayuda
guardian --help

# Activar Guardian en un proyecto (idempotente)
cd /ruta/de/mi/proyecto
guardian activate

# Ver GUARDIAN.md esencial
guardian brain read

# Buscar en memoria
guardian brain query semantic "fastapi auth"

# Escribir nodo (pasa por el Governor)
guardian brain write semantic "api auth via JWT" --kind pattern --importance 0.8

# Activar especialización
guardian specialization enable odoo

# Diagnosticar proyecto
guardian maintain

# Publicar como template
guardian publish my-template 1.0.0
```

Desde OpenCode:
```
@guardian context --brief
@guardian mode build
@guardian brain query "odoo ORM"
@guardian maintain
```

## Arquitectura

```
  CEREBRO (v3):
    WM: GUARDIAN.md (≤200 líneas, always-loaded)
    SM/EM/PM/RM: 4 SQLite DBs por proyecto
    SM-G/PM-G/RM-G: 3 SQLite DBs globales
    Governor: importance/TTL/dup/contradiction
    Reflection Agent: post-sesión

  CONCIENCIA:
    N1: percibir → decidir → reflexionar (modo)
    N2: meta (calibrar percentiles)

  OJOS: RAG + Specializations + Skills como tomos
  MANOS: CLI + Git + Hooks
  PIERNAS: Backend :9787 + Scheduler + API REST
  NANOS: MCP tools (35 totales)
```

## Stack

- **Runtime:** Python 3.9+ (stdlib only, **cero dependencias externas**)
- **Storage:** SQLite (4 project + 3 global)
- **Embeddings:** Hashing 256-dim (zero-deps, deterministic)
- **Tests:** pytest
- **Lint:** ruff
- **Packaging:** pyproject.toml + install.sh

## Comandos principales

```bash
guardian activate [slug]                 # setup + absorb + conciencia
guardian brain read|write|query|reflect  # memoria cognitiva
guardian session start|continue|end      # lifecycle de sesión
guardian knowledge research|refresh      # research con TTL
guardian specialization enable|disable   # stack-aware knowledge
guardian plan new|list|status            # OpenSpec + ad-hoc
guardian maintain                        # drift + health report
guardian publish|clone|fork              # distribución
guardian capability status|routing        # model card
guardian backend start|stop|status       # servicio
guardian mode read|plan|build|commit|review
guardian conciencia cycle                # N1+N2
```

Ayuda completa: `guardian --help` o ver [docs/REFERENCIA.md](docs/REFERENCIA.md).

## Tests

```bash
python3 -m pytest tests/ -v
# 223/223 passing
```

## Distribución

```bash
git tag v3.0.0
git push origin main --tags
```

## Documentación

- [docs/PLAN_V3.md](docs/PLAN_V3.md) — Plan maestro v3
- [docs/CONCEPTOS.md](docs/CONCEPTOS.md) — Filosofía + capa cognitiva
- [docs/FLUJOS.md](docs/FLUJOS.md) — Workflows
- [docs/REFERENCIA.md](docs/REFERENCIA.md) — CLI, API, MCP completos
- [docs/GUIA.md](docs/GUIA.md) — Inicio rápido
- [docs/INSTALACION.md](docs/INSTALACION.md) — Instalación detallada

## Licencia

MIT
