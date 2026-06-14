#!/usr/bin/env bash
# Nexxoria Guardian — install.sh
# Instalación automática en Ubuntu/Debian con OpenCode
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}  →${NC} $1"; }
ok()    { echo -e "${GREEN}  ✓${NC} $1"; }
warn()  { echo -e "${YELLOW}  ⚠${NC} $1"; }
fail()  { echo -e "${RED}  ✗${NC} $1"; exit 1; }
prompt() {
    local msg="$1" default="$2"
    local val
    read -r -p "$(echo -e "${CYAN}  ?${NC} ${msg} [${default}]: ")" val
    echo "${val:-$default}"
}

HOME_DIR="${HOME}"
NO_OPENCODE=false
for arg in "$@"; do
    [ "$arg" == "--no-opencode" ] && NO_OPENCODE=true
done

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║       Nexxoria Guardian — Instalación    ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""

# ── 1. Detectar entorno ─────────────────────────────────────────
info "Detectando entorno..."

OS="$(uname -s)"
if [ "$OS" != "Linux" ]; then
    fail "Sistema operativo no soportado: $OS. Se requiere Linux (Ubuntu/Debian)."
fi

if [ -f /etc/os-release ]; then
    . /etc/os-release
    if [ "$ID" != "ubuntu" ] && [ "$ID" != "debian" ]; then
        warn "Distribución no probada: $ID. Continuando de todas formas..."
    fi
else
    warn "No se pudo detectar distribución. Continuando..."
fi
ok "Sistema: $OS / ${ID:-unknown} ${VERSION_ID:-}"

PYTHON=""
for candidate in python3.12 python3.11 python3.10 python3.9 python3; do
    if command -v "$candidate" &>/dev/null; then
        ver=$("$candidate" --version 2>&1 | grep -oP '\d+\.\d+')
        major="${ver%%.*}"
        minor="${ver#*.}"
        if [ "$major" -gt 3 ] || { [ "$major" -eq 3 ] && [ "$minor" -ge 9 ]; } 2>/dev/null; then
            PYTHON="$candidate"
            break
        fi
    fi
done
[ -z "$PYTHON" ] && fail "Python 3.9+ no encontrado. Instalá python3."
ok "Python: $($PYTHON --version 2>&1)"

# Verificar/instalar PyYAML
if $PYTHON -c "import yaml" 2>/dev/null; then
    ok "PyYAML: ya instalado"
else
    info "Instalando PyYAML..."
    if command -v apt-get &>/dev/null; then
        sudo apt-get install -y python3-yaml 2>/dev/null || $PYTHON -m pip install pyyaml 2>/dev/null || {
            warn "No se pudo instalar PyYAML automáticamente. Intentá: sudo apt install python3-yaml"
        }
    else
        $PYTHON -m pip install pyyaml 2>/dev/null || warn "No se pudo instalar PyYAML."
    fi
    if $PYTHON -c "import yaml" 2>/dev/null; then
        ok "PyYAML: instalado"
    fi
fi

if $NO_OPENCODE; then
    ok "Modo --no-opencode: saltando chequeo de OpenCode"
else
    if command -v opencode &>/dev/null; then
        OC_VER=$(opencode --version 2>&1 | head -1)
        ok "OpenCode: $OC_VER"
    else
        warn "OpenCode no encontrado en PATH. Podés instalarlo luego desde https://opencode.ai"
        NO_OPENCODE=true
    fi
fi

if command -v git &>/dev/null; then
    ok "Git: $(git --version 2>&1)"
else
    fail "Git no encontrado. Instalá git: sudo apt install git"
fi

# ── 2. Determinar source ────────────────────────────────────────
GUARDIAN_HOME="/opt/nexxoria-guardian"
GUARDIAN_DATA="/var/lib/nexxoria-guardian"
SYSTEMD_DIR="/etc/systemd/system"

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
IS_REPO=false
if [ -f "$SCRIPT_DIR/lib/guardian.py" ] && [ -f "$SCRIPT_DIR/genome/identity.yaml" ]; then
    IS_REPO=true
    info "Instalando desde el repositorio local: $SCRIPT_DIR"
else
    info "Instalando desde GitHub..."
    TEMP_DIR=$(mktemp -d)
    trap "rm -rf $TEMP_DIR" EXIT
    git clone --depth 1 https://github.com/nexxoria/guardian.git "$TEMP_DIR/guardian" 2>/dev/null || {
        fail "No se pudo clonar el repositorio. Verificá la conexión a Internet."
    }
    SCRIPT_DIR="$TEMP_DIR/guardian"
    ok "Repositorio clonado"
fi

# ── 3. Crear directorios ────────────────────────────────────────
info "Creando directorios..."
sudo mkdir -p "$GUARDIAN_HOME"
sudo mkdir -p "$GUARDIAN_DATA/genome/branches/default/memory"
sudo mkdir -p "$GUARDIAN_DATA/genome/branches/default/knowledge/tomes"
sudo mkdir -p "$GUARDIAN_DATA/genome/branches/default/learnings"
ok "Directorios creados en $GUARDIAN_HOME y $GUARDIAN_DATA"

# ── 4. Copiar código ────────────────────────────────────────────
info "Copiando archivos..."
sudo cp -r "$SCRIPT_DIR/lib"    "$GUARDIAN_HOME/lib"
sudo cp -r "$SCRIPT_DIR/genome" "$GUARDIAN_HOME/genome"
sudo cp -r "$SCRIPT_DIR/docs"   "$GUARDIAN_HOME/docs"
sudo cp -r "$SCRIPT_DIR/templates" "$GUARDIAN_HOME/templates"
sudo cp -r "$SCRIPT_DIR/prompts" "$GUARDIAN_HOME/prompts"
sudo cp -r "$SCRIPT_DIR/tests"  "$GUARDIAN_HOME/tests"
sudo cp  "$SCRIPT_DIR/SKILL.md" "$GUARDIAN_HOME/SKILL.md"
sudo cp  "$SCRIPT_DIR/LICENSE"  "$GUARDIAN_HOME/LICENSE" 2>/dev/null || true
sudo cp  "$SCRIPT_DIR/README.md" "$GUARDIAN_HOME/README.md" 2>/dev/null || true
sudo cp  "$SCRIPT_DIR/commands/guardian.md" "$GUARDIAN_HOME/commands/guardian.md" 2>/dev/null || true
# systemd
if [ -d "$SCRIPT_DIR/systemd" ]; then
    sudo cp -r "$SCRIPT_DIR/systemd" "$GUARDIAN_HOME/systemd"
fi
# .gitignore
sudo cp "$SCRIPT_DIR/.gitignore" "$GUARDIAN_HOME/.gitignore" 2>/dev/null || true

# Copiar identity.yaml a datos
if [ ! -f "$GUARDIAN_DATA/genome/identity.yaml" ]; then
    sudo cp "$GUARDIAN_HOME/genome/identity.yaml" "$GUARDIAN_DATA/genome/identity.yaml"
fi

# Fijar permisos
sudo chmod +x "$GUARDIAN_HOME/lib/guardian.py"
sudo chmod -R 755 "$GUARDIAN_HOME"
ok "Archivos copiados a $GUARDIAN_HOME"

# ── 5. Crear symlink CLI ────────────────────────────────────────
info "Configurando CLI..."
sudo ln -sf "$GUARDIAN_HOME/lib/guardian.py" /usr/local/bin/guardian
ok "Comando 'guardian' disponible en PATH"

# ── 6. Configurar systemd ───────────────────────────────────────
info "Configurando servicio systemd..."
SERVICE_FILE="$GUARDIAN_HOME/systemd/nexxoria-guardian.service"
if [ -f "$SERVICE_FILE" ]; then
    sudo cp "$SERVICE_FILE" "$SYSTEMD_DIR/nexxoria-guardian.service"
    sudo systemctl daemon-reload
    sudo systemctl enable nexxoria-guardian 2>/dev/null || warn "No se pudo habilitar el servicio"
    sudo systemctl start nexxoria-guardian 2>/dev/null || warn "No se pudo iniciar el servicio (puede que no haya OpenCode/entorno completo)"
    if sudo systemctl is-active --quiet nexxoria-guardian 2>/dev/null; then
        ok "Servicio nexxoria-guardian activo"
    else
        warn "Servicio nexxoria-guardian configurado pero no activo (iniciará en boot)"
    fi
else
    warn "Archivo de servicio no encontrado en $SERVICE_FILE"
fi

# ── 7. Configurar OpenCode Skill ────────────────────────────────
if ! $NO_OPENCODE; then
    info "Instalando skill para OpenCode..."
    AGENTS_DIR="$HOME_DIR/.agents"
    SKILL_DIR="$AGENTS_DIR/skills/nexxoria-guardian"
    mkdir -p "$SKILL_DIR"
    ln -sf "$GUARDIAN_HOME/SKILL.md" "$SKILL_DIR/SKILL.md"
    ok "Skill instalado en $SKILL_DIR"

    # ── 8. Configurar @guardian command ─────────────────────────
    info "Instalando comando @guardian..."
    CMD_DIR="$HOME_DIR/.config/opencode/commands"
    mkdir -p "$CMD_DIR"
    cp "$GUARDIAN_HOME/commands/guardian.md" "$CMD_DIR/guardian.md" 2>/dev/null || \
        warn "No se pudo instalar el comando @guardian"
    ok "Comando @guardian instalado en $CMD_DIR"

    # ── 9. Registrar MCP server ────────────────────────────────
    info "Registrando MCP server..."
    if command -v opencode &>/dev/null; then
        # Eliminar si ya existe
        opencode mcp remove nexxoria-guardian 2>/dev/null || true
        opencode mcp add nexxoria-guardian \
            --description "Nexxoria Guardian MCP tools" \
            --command "$PYTHON" \
            --args "$GUARDIAN_HOME/lib/guardian_mcp.py" \
            --transport stdio 2>/dev/null || \
            warn "No se pudo registrar MCP automáticamente. Hacelo manual: opencode mcp add ..."
        ok "MCP server registrado"
    fi
else
    info "Saltando configuración de OpenCode (modo --no-opencode)"
fi

# ── 9. Variables de entorno en perfil ───────────────────────────
PROFILE_FILE="$HOME_DIR/.bashrc"
if grep -q "GUARDIAN_HOME" "$PROFILE_FILE" 2>/dev/null; then
    info "Variables de entorno ya configuradas en $PROFILE_FILE"
else
    cat >> "$PROFILE_FILE" << 'EOF'

# Nexxoria Guardian
export GUARDIAN_HOME="/opt/nexxoria-guardian"
export GUARDIAN_DATA="/var/lib/nexxoria-guardian"
export GUARDIAN_PORT="9787"
EOF
    ok "Variables de entorno agregadas a $PROFILE_FILE"
fi

# ── 10. Verificar ──────────────────────────────────────────────
info "Verificando instalación..."
ERRORS=0

if command -v guardian &>/dev/null; then
    ok "CLI: guardian --help funciona"
else
    warn "CLI: guardian no encontrado en PATH"
    ERRORS=$((ERRORS + 1))
fi

if $PYTHON -c "import guardian_shared" 2>/dev/null; then
    ok "Módulo: guardian_shared importable"
else
    warn "Módulos: no se pudieron importar (PYTHONPATH puede necesitar configuración)"
    ERRORS=$((ERRORS + 1))
fi

if [ -f "$GUARDIAN_DATA/genome/identity.yaml" ]; then
    ok "Genoma: $GUARDIAN_DATA/genome/identity.yaml"
else
    warn "Genoma: no encontrado"
    ERRORS=$((ERRORS + 1))
fi

if sudo systemctl is-active --quiet nexxoria-guardian 2>/dev/null; then
    ok "Backend: servicio activo"
elif command -v guardian &>/dev/null; then
    warn "Backend: servicio no activo (ejecutá 'guardian backend start' manualmente)"
else
    warn "Backend: no verificado"
fi

MCP_CHECK=false
if ! $NO_OPENCODE && command -v opencode &>/dev/null; then
    if opencode mcp list 2>/dev/null | grep -q nexxoria-guardian; then
        ok "MCP: registrado en OpenCode"
        MCP_CHECK=true
    fi
fi
$MCP_CHECK || warn "MCP: no verificado (ejecutá 'opencode mcp list' para confirmar)"

echo ""
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  ✅ Nexxoria Guardian instalado correctamente        ║${NC}"
    echo -e "${GREEN}║                                                     ║${NC}"
    echo -e "${GREEN}║  Después de reiniciar OpenCode, decí:                ║${NC}"
    echo -e "${GREEN}║                                                     ║${NC}"
    echo -e "${GREEN}║    activo guardian                                   ║${NC}"
    echo -e "${GREEN}║                                                     ║${NC}"
    echo -e "${GREEN}║  O desde terminal:                                   ║${NC}"
    echo -e "${GREEN}║                                                     ║${NC}"
    echo -e "${GREEN}║    cd /ruta/de/mi/proyecto                           ║${NC}"
    echo -e "${GREEN}║    guardian activate                                 ║${NC}"
    echo -e "${GREEN}║                                                     ║${NC}"
    echo -e "${GREEN}║  Documentación:                                      ║${NC}"
    echo -e "${GREEN}║    $GUARDIAN_HOME/docs/                          ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
else
    echo -e "${YELLOW}╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║  ⚠ Instalación completada con $ERRORS advertencia(s) ║${NC}"
    echo -e "${YELLOW}╚══════════════════════════════════════════════════════╝${NC}"
fi
echo ""
