# Nexxoria Guardian — Instalación

## Requisitos

- **Sistema:** Ubuntu 22.04+ (o Debian-based con systemd)
- **Python:** 3.9 o superior
- **OpenCode:** v1.17 o superior ([instalación oficial](https://opencode.ai))
- **Git:** para clonar el repo

## Instalación estándar

```bash
git clone https://github.com/nexxoria/guardian.git
cd guardian
sudo bash install.sh
```

### Instalación desde curl (una línea)

```bash
curl -fsSL https://raw.githubusercontent.com/nexxoria/guardian/main/install.sh | sudo bash
```

## Qué instala

| Componente | Destino | Descripción |
|-----------|--------|-------------|
| Código | `/opt/nexxoria-guardian/` | Todos los módulos y assets |
| CLI | `/usr/local/bin/guardian` → symlink | Comando `guardian` en PATH |
| Datos | `/var/lib/nexxoria-guardian/` | Ramas, proyectos, skills, logs, PID |
| systemd | `/etc/systemd/system/nexxoria-guardian.service` | Servicio auto-inicio |
| Skill | `~/.agents/skills/nexxoria-guardian/SKILL.md` | Auto-detectado por OpenCode |
| Comando | `~/.config/opencode/commands/guardian.md` | `@guardian` en OpenCode |
| MCP | Registrado via `opencode mcp add` | Tools disponibles para el agente |

## Verificar instalación

```bash
# CLI funciona
guardian --help

# Backend corriendo
guardian backend status

# API responde
curl http://127.0.0.1:9787/health

# Skill instalado
ls -la ~/.agents/skills/nexxoria-guardian/

# MCP registrado
opencode mcp list
```

## Después de instalar

1. **Reiniciá OpenCode** (cerrar y abrir de nuevo)
2. **Decí "activo guardian"** en cualquier proyecto
3. O ejecutá `guardian activate` desde la terminal

El skill se auto-detecta. El backend arranca solo con systemd.  
El MCP está registrado y disponible.

## Desinstalación

```bash
# Detener y deshabilitar servicio
sudo systemctl stop nexxoria-guardian
sudo systemctl disable nexxoria-guardian
sudo rm /etc/systemd/system/nexxoria-guardian.service
sudo systemctl daemon-reload

# Eliminar archivos
sudo rm -rf /opt/nexxoria-guardian
sudo rm -rf /var/lib/nexxoria-guardian
sudo rm /usr/local/bin/guardian

# Eliminar skill y comando
rm -rf ~/.agents/skills/nexxoria-guardian
rm -f ~/.config/opencode/commands/guardian.md

# Eliminar MCP (si opencode mcp remove existe)
opencode mcp remove nexxoria-guardian 2>/dev/null || true
```

## Instalación en servidores headless

El backend funciona sin OpenCode. Sirve la API REST en `127.0.0.1:9787`:

```bash
# Solo backend (sin OpenCode)
sudo bash install.sh --no-opencode

# Usar via API
curl http://127.0.0.1:9787/genome
curl -X POST http://127.0.0.1:9787/evolve -d '{"slug":"mi-proyecto"}'
```

## Variables de entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `GUARDIAN_LANG` | `en` | Idioma (`en` o `es`) |
| `GUARDIAN_HOME` | `/opt/nexxoria-guardian` | Directorio de instalación |
| `GUARDIAN_DATA` | `/var/lib/nexxoria-guardian` | Directorio de datos |
| `GUARDIAN_PORT` | `9787` | Puerto del backend |
