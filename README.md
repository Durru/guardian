# Nexxoria Guardian

**Universal project guardian for OpenCode AI sessions.**

Guardian es un ser orgánico que protege, guía y evoluciona tus proyectos.  
Tiene conciencia (2 niveles), genoma, ramas de evolución, RAG unificado, backend persistente y MCP.

---

## Requisitos

- **OS:** Ubuntu 22.04+ (o Debian-based)
- **Python:** 3.9+
- **OpenCode:** `>= 1.17` ([instalar](https://opencode.ai))

## Instalación

```bash
git clone https://github.com/nexxoria/guardian.git
cd guardian
sudo bash install.sh
```

O en una línea:

```bash
curl -fsSL https://raw.githubusercontent.com/nexxoria/guardian/main/install.sh | sudo bash
```

### Qué hace `install.sh`

1. Detecta Ubuntu + Python 3.9+ + OpenCode
2. Instala en `/opt/nexxoria-guardian/`
3. Crea datos runtime en `/var/lib/nexxoria-guardian/`
4. Instala dependencia PyYAML
5. Crea symlink `/usr/local/bin/guardian`
6. Registra servicio systemd (auto-start en boot)
7. Instala skill en `~/.agents/skills/nexxoria-guardian/`
8. Instala comando `@guardian` en OpenCode
9. Registra MCP server
10. Verifica instalación

**Después de instalar, reiniciá OpenCode y decí "activo guardian".**

## Uso básico

```bash
# Ver ayuda
guardian --help

# Estado del backend
guardian backend status

# Activar Guardian en un proyecto
cd /ruta/de/mi/proyecto
guardian activate

# O desde OpenCode
# @guardian context --brief
```

## Arquitectura

```
  CEREBRO: LLM + Conciencia N1/N2 + RAG
  OJOS:    Contexto + Skills como tomos
  MANOS:   CLI + Hooks + Git
  PIERNAS: Backend :9787 + Scheduler + MCP
  NANOS:   MCP Tools
```

Documentación completa en [docs/](docs/):
- [CONCEPTOS.md](docs/CONCEPTOS.md) — Filosofía, ser orgánico, conciencia
- [FLUJOS.md](docs/FLUJOS.md) — Workflows detallados
- [REFERENCIA.md](docs/REFERENCIA.md) — CLI, API, MCP
- [GUIA.md](docs/GUIA.md) — Inicio rápido
- [INSTALACION.md](docs/INSTALACION.md) — Instalación detallada

## Stack

- **Runtime:** Python 3.9+ (stdlib, sin dependencias externas)
- **Opcional:** PyYAML (para archivos YAML)
- **Datos:** JSON + YAML
- **Sin Docker, sin ORM, sin Node.js**

## Licencia

MIT
