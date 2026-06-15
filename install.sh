#!/usr/bin/env bash
# Nexxoria Guardian v3 — install.sh
# Zero-deps cognitive memory ecosystem for OpenCode.
#
# Modes:
#   --system (default): install to /opt + /var (requires sudo)
#   --user:             install to ~/.local (no sudo)
#   --dev:              don't copy, just verify the repo is usable
#   --uninstall:        remove Guardian and its config
#   --version=X.Y.Z:    install a specific tag/branch (default: main)
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Durru/guardian/v3.0.0/install.sh | sudo bash
#   curl -fsSL ... | bash -s -- --user
#   ./install.sh --dev

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ── Parse args ────────────────────────────────────────────────────────

MODE="system"
VERSION="main"
UNINSTALL=false
NO_OPENCODE=false
NO_SYSTEMD=false
SOURCE_DIR=""

for arg in "$@"; do
    case "$arg" in
        --system)    MODE="system" ;;
        --user)      MODE="user" ;;
        --dev)       MODE="dev" ;;
        --uninstall) UNINSTALL=true ;;
        --no-opencode) NO_OPENCODE=true ;;
        --no-systemd) NO_SYSTEMD=true ;;
        --version=*) VERSION="${arg#--version=}" ;;
        --source=*)  SOURCE_DIR="${arg#--source=}" ;;
        --help|-h)
            echo "Usage: install.sh [--system|--user|--dev|--uninstall] [--version=X.Y.Z] [--no-opencode] [--no-systemd] [--source=PATH]"
            exit 0
            ;;
        *) echo "Unknown arg: $arg"; exit 1 ;;
    esac
done

# ── Logging helpers ───────────────────────────────────────────────────

info()  { echo -e "${CYAN}  →${NC} $1"; }
ok()    { echo -e "${GREEN}  ✓${NC} $1"; }
warn()  { echo -e "${YELLOW}  ⚠${NC} $1"; }
fail()  { echo -e "${RED}  ✗ ${BOLD}$1${NC}"; exit 1; }
section() { echo -e "\n${BOLD}${CYAN}── $1 ──${NC}"; }

# ── Banner ────────────────────────────────────────────────────────────

banner() {
    echo ""
    echo -e "${GREEN}${BOLD}"
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║          🛡️  Nexxoria Guardian v3 — Installer              ║"
    echo "║          Cognitive memory ecosystem · zero deps          ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# ── Detect env ────────────────────────────────────────────────────────

detect_env() {
    section "Detectando entorno"
    OS="$(uname -s)"
    if [ "$OS" != "Linux" ]; then
        fail "Sistema no soportado: $OS. Se requiere Linux."
    fi
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        if [ "${ID:-}" != "ubuntu" ] && [ "${ID:-}" != "debian" ]; then
            warn "Distribución no probada: ${ID:-unknown}. Continuando..."
        fi
    fi
    ok "OS: $OS / ${ID:-unknown} ${VERSION_ID:-}"

    PYTHON=""
    for candidate in python3.13 python3.12 python3.11 python3.10 python3.9 python3; do
        if command -v "$candidate" &>/dev/null; then
            ver=$("$candidate" --version 2>&1 | grep -oP '\d+\.\d+')
            major="${ver%%.*}"
            minor="${ver#*.}"
            if [ "${major:-0}" -gt 3 ] || { [ "${major:-0}" -eq 3 ] && [ "${minor:-0}" -ge 9 ]; } 2>/dev/null; then
                PYTHON="$candidate"
                break
            fi
        fi
    done
    [ -z "$PYTHON" ] && fail "Python 3.9+ no encontrado. Instalá: sudo apt install python3"
    ok "Python: $($PYTHON --version 2>&1)"

    if command -v git &>/dev/null; then
        ok "Git: $(git --version 2>&1)"
    else
        fail "Git no encontrado. Instalá: sudo apt install git"
    fi

    if command -v curl &>/dev/null; then
        ok "curl: presente"
    else
        warn "curl no encontrado (necesario para modo --user/--system sin repo local)"
    fi
}

# ── Determine paths ──────────────────────────────────────────────────

determine_paths() {
    case "$MODE" in
        system)
            GUARDIAN_HOME="/opt/nexxoria-guardian"
            GUARDIAN_DATA="/var/lib/nexxoria-guardian"
            GUARDIAN_BIN="/usr/local/bin/guardian"
            SUDO_CMD="sudo"
            ;;
        user)
            GUARDIAN_HOME="${HOME}/.local/share/nexxoria-guardian"
            GUARDIAN_DATA="${HOME}/.local/state/nexxoria-guardian"
            GUARDIAN_BIN="${HOME}/.local/bin/guardian"
            SUDO_CMD=""
            case ":$PATH:" in
                *":${HOME}/.local/bin:"*) ;;
                *) export PATH="${HOME}/.local/bin:$PATH" ;;
            esac
            ;;
        dev)
            if [ -n "$SOURCE_DIR" ]; then
                GUARDIAN_HOME="$(cd "$SOURCE_DIR" && pwd)"
            else
                GUARDIAN_HOME="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
            fi
            GUARDIAN_DATA="${GUARDIAN_HOME}/.dev-data"
            GUARDIAN_BIN=""
            SUDO_CMD=""
            ;;
    esac

    info "GUARDIAN_HOME: $GUARDIAN_HOME"
    info "GUARDIAN_DATA: $GUARDIAN_DATA"
    if [ -n "$GUARDIAN_BIN" ]; then
        info "GUARDIAN_BIN:  $GUARDIAN_BIN"
    fi
}

# ── Get source ────────────────────────────────────────────────────────

get_source() {
    section "Obteniendo código fuente"

    if [ "$MODE" = "dev" ]; then
        if [ ! -f "$GUARDIAN_HOME/lib/guardian.py" ]; then
            fail "Modo --dev requiere ejecutar install.sh desde el repo, o usar --source=PATH"
        fi
        ok "Usando repo local: $GUARDIAN_HOME"
        SOURCE_DIR="$GUARDIAN_HOME"
        return
    fi

    SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
    if [ -f "$SCRIPT_DIR/lib/guardian.py" ] && [ -f "$SCRIPT_DIR/lib/guardian_brain.py" ]; then
        SOURCE_DIR="$SCRIPT_DIR"
        ok "Usando repo local: $SOURCE_DIR"
        return
    fi

    if ! command -v git &>/dev/null; then
        fail "Se necesita git para clonar desde GitHub"
    fi
    if [ -z "$VERSION" ] || [ "$VERSION" = "main" ]; then
        REF="main"
    else
        REF="v$VERSION"
    fi
    info "Clonando desde GitHub (ref: $REF)..."
    TEMP_DIR=$(mktemp -d -t guardian-install-XXXXXX)
    trap '[ -n "${TEMP_DIR:-}" ] && rm -rf "$TEMP_DIR" || true' EXIT
    if ! git clone --depth 1 --branch "$REF" https://github.com/Durru/guardian.git "$TEMP_DIR/guardian" 2>/dev/null; then
        if ! git clone --depth 1 https://github.com/Durru/guardian.git "$TEMP_DIR/guardian" 2>/dev/null; then
            fail "No se pudo clonar el repositorio. Verificá tu conexión a Internet."
        fi
    fi
    SOURCE_DIR="$TEMP_DIR/guardian"
    ok "Repositorio clonado en $SOURCE_DIR"
}

# ── Install files ────────────────────────────────────────────────────

install_files() {
    section "Instalando archivos"

    if [ "$MODE" = "dev" ]; then
        info "Modo --dev: no se copian archivos (se usa el repo in-place)"
        mkdir -p "$GUARDIAN_DATA"
        return
    fi

    info "Creando directorios..."
    $SUDO_CMD mkdir -p "$GUARDIAN_HOME" "$GUARDIAN_DATA"

    info "Copiando código (lib/, docs/, templates/, prompts/, tests/)..."
    $SUDO_CMD cp -r "$SOURCE_DIR/lib"        "$GUARDIAN_HOME/lib"
    $SUDO_CMD cp -r "$SOURCE_DIR/genome"     "$GUARDIAN_HOME/genome"
    $SUDO_CMD cp -r "$SOURCE_DIR/docs"       "$GUARDIAN_HOME/docs"
    $SUDO_CMD cp -r "$SOURCE_DIR/templates"  "$GUARDIAN_HOME/templates"
    $SUDO_CMD cp -r "$SOURCE_DIR/prompts"    "$GUARDIAN_HOME/prompts"
    $SUDO_CMD cp -r "$SOURCE_DIR/tests"      "$GUARDIAN_HOME/tests"
    $SUDO_CMD cp -r "$SOURCE_DIR/commands"   "$GUARDIAN_HOME/commands"
    $SUDO_CMD cp -r "$SOURCE_DIR/systemd"     "$GUARDIAN_HOME/systemd" 2>/dev/null || true
    $SUDO_CMD cp -r "$SOURCE_DIR/.github"     "$GUARDIAN_HOME/.github" 2>/dev/null || true

    for f in SKILL.md LICENSE README.md AGENTS.md pyproject.toml; do
        if [ -f "$SOURCE_DIR/$f" ]; then
            $SUDO_CMD cp "$SOURCE_DIR/$f" "$GUARDIAN_HOME/$f"
        fi
    done

    if [ ! -f "$GUARDIAN_DATA/genome/identity.yaml" ] && [ -f "$SOURCE_DIR/genome/identity.yaml" ]; then
        $SUDO_CMD mkdir -p "$GUARDIAN_DATA/genome"
        $SUDO_CMD cp "$SOURCE_DIR/genome/identity.yaml" "$GUARDIAN_DATA/genome/identity.yaml"
    fi

    $SUDO_CMD chmod +x "$GUARDIAN_HOME/lib/guardian.py" 2>/dev/null || true
    $SUDO_CMD chmod -R 755 "$GUARDIAN_HOME" 2>/dev/null || true
    ok "Archivos copiados a $GUARDIAN_HOME"
}

# ── CLI symlink ─────────────────────────────────────────────────────

install_cli() {
    section "Configurando CLI"
    if [ "$MODE" = "dev" ] || [ -z "$GUARDIAN_BIN" ]; then
        info "Modo --dev: symlink del CLI no creado. Usá: PYTHONPATH=$GUARDIAN_HOME/lib python3 -m guardian"
        return
    fi

    if [ -L "$GUARDIAN_BIN" ]; then
        local current
        current=$(readlink "$GUARDIAN_BIN")
        if [ "$current" = "$GUARDIAN_HOME/lib/guardian.py" ]; then
            ok "Symlink del CLI ya correcto"
            return
        fi
        info "Removiendo symlink viejo..."
        $SUDO_CMD rm -f "$GUARDIAN_BIN"
    elif [ -e "$GUARDIAN_BIN" ]; then
        warn "Ya existe $GUARDIAN_BIN (no es symlink). No se reemplaza."
        return
    fi

    info "Creando symlink: $GUARDIAN_BIN → $GUARDIAN_HOME/lib/guardian.py"
    $SUDO_CMD ln -sf "$GUARDIAN_HOME/lib/guardian.py" "$GUARDIAN_BIN"
    ok "Comando 'guardian' disponible en PATH"
}

# ── OpenCode integration ────────────────────────────────────────────

install_opencode() {
    if [ "$NO_OPENCODE" = true ]; then
        info "Saltando integración con OpenCode (--no-opencode)"
        return
    fi

    section "Configurando OpenCode"

    if ! command -v opencode &>/dev/null; then
        warn "OpenCode no encontrado en PATH. Saltando integración. Instálalo de https://opencode.ai y volvé a correr este script."
        return
    fi
    ok "OpenCode: $(opencode --version 2>&1 | head -1)"

    # 1. Skill
    local skill_dir="${HOME}/.agents/skills/nexxoria-guardian"
    info "Instalando skill: $skill_dir"
    mkdir -p "$skill_dir"
    if [ -L "$skill_dir/SKILL.md" ] && [ "$(readlink "$skill_dir/SKILL.md")" = "$GUARDIAN_HOME/SKILL.md" ]; then
        ok "Skill ya enlazada"
    else
        rm -f "$skill_dir/SKILL.md"
        ln -sf "$GUARDIAN_HOME/SKILL.md" "$skill_dir/SKILL.md"
        ok "Skill instalada"
    fi

    # 2. Slash command
    local cmd_file="${HOME}/.config/opencode/commands/guardian.md"
    info "Instalando @guardian command: $cmd_file"
    mkdir -p "$(dirname "$cmd_file")"
    if [ -f "$cmd_file" ] && [ "$cmd_file" -ef "$GUARDIAN_HOME/commands/guardian.md" ]; then
        ok "Comando @guardian ya instalado"
    elif [ -f "$cmd_file" ]; then
        cp "$GUARDIAN_HOME/commands/guardian.md" "$cmd_file"
        ok "Comando @guardian actualizado"
    else
        cp "$GUARDIAN_HOME/commands/guardian.md" "$cmd_file"
        ok "Comando @guardian instalado"
    fi

    # 3. Plugin (TS)
    local plugin_src="$SOURCE_DIR/.opencode/plugins/guardian.ts"
    if [ -f "$plugin_src" ]; then
        local plugin_dst_dir="${HOME}/.config/opencode/plugins"
        mkdir -p "$plugin_dst_dir"
        cp "$plugin_src" "$plugin_dst_dir/guardian.ts" && \
            ok "Plugin OpenCode instalado en $plugin_dst_dir" || \
            warn "No se pudo instalar el plugin"
    fi

    # 4. MCP server
    local oc_config="${HOME}/.config/opencode/opencode.json"
    info "Registrando MCP server..."
    if [ -f "$oc_config" ]; then
        "$PYTHON" -c "
import json
path = '$oc_config'
with open(path) as f:
    cfg = json.load(f)
mcp = cfg.setdefault('mcp', {})
mcp['nexxoria-guardian'] = {
    'command': ['$PYTHON', '$GUARDIAN_HOME/lib/guardian_mcp.py'],
    'type': 'local',
}
with open(path, 'w') as f:
    json.dump(cfg, f, indent=2, ensure_ascii=False)
    f.write('\n')
print('ok')
" 2>/dev/null && ok "MCP server registrado" || warn "No se pudo registrar MCP automáticamente"
    else
        warn "OpenCode config no encontrado en $oc_config. Agregá el MCP manualmente."
    fi
}

# ── systemd ──────────────────────────────────────────────────────────

install_systemd() {
    if [ "$NO_SYSTEMD" = true ] || [ "$MODE" != "system" ]; then
        info "Saltando systemd (--no-systemd o modo no-system)"
        return
    fi

    section "Configurando servicio systemd"

    local svc_src="$GUARDIAN_HOME/systemd/nexxoria-guardian.service"
    if [ ! -f "$svc_src" ]; then
        warn "Archivo de servicio no encontrado: $svc_src"
        return
    fi

    $SUDO_CMD cp "$svc_src" "/etc/systemd/system/nexxoria-guardian.service"
    $SUDO_CMD systemctl daemon-reload 2>/dev/null || warn "systemctl daemon-reload falló"
    $SUDO_CMD systemctl enable nexxoria-guardian 2>/dev/null || warn "systemctl enable falló"
    ok "Servicio nexxoria-guardian habilitado"

    if $SUDO_CMD systemctl is-active --quiet nexxoria-guardian 2>/dev/null; then
        ok "Servicio nexxoria-guardian activo"
    else
        info "Iniciando servicio..."
        if $SUDO_CMD systemctl start nexxoria-guardian 2>/dev/null; then
            ok "Servicio nexxoria-guardian iniciado"
        else
            warn "No se pudo iniciar el servicio (inicielo manualmente: sudo systemctl start nexxoria-guardian)"
        fi
    fi
}

# ── Env vars ─────────────────────────────────────────────────────────

setup_env_vars() {
    section "Variables de entorno"

    local profile_file="${HOME}/.bashrc"
    if [ -f "${HOME}/.zshrc" ] && [ ! -f "$profile_file" ]; then
        profile_file="${HOME}/.zshrc"
    fi

    if grep -q "GUARDIAN_HOME" "$profile_file" 2>/dev/null; then
        info "Variables de entorno ya configuradas en $profile_file"
    else
        cat >> "$profile_file" << EOF

# Nexxoria Guardian v3
export GUARDIAN_HOME="$GUARDIAN_HOME"
export GUARDIAN_DATA="$GUARDIAN_DATA"
export GUARDIAN_PORT="9787"
EOF
        ok "Variables agregadas a $profile_file"
    fi

    local env_dir="${HOME}/.guardian"
    mkdir -p "$env_dir"
    cat > "$env_dir/.env" << EOF
GUARDIAN_HOME=$GUARDIAN_HOME
GUARDIAN_DATA=$GUARDIAN_DATA
GUARDIAN_PORT=9787
GUARDIAN_LANG=en
EOF
    ok ".env escrito en $env_dir/.env"
}

# ── Verify ───────────────────────────────────────────────────────────

verify_zero_deps() {
    local lib_dir="$1"
    if [ ! -d "$lib_dir" ]; then
        warn "No se encontró lib/ en $lib_dir"
        return 1
    fi
    info "Importando módulos guardian_* (sin deps externas)..."
    local test_output
    test_output=$(cd "$lib_dir/.." && "$PYTHON" -c "
import sys
sys.path.insert(0, 'lib')
for m in list(sys.modules.keys()):
    if m.startswith('guardian'):
        del sys.modules[m]
mods = [
    'guardian_brain_schema', 'guardian_brain',
    'guardian_knowledge', 'guardian_specialization', 'guardian_plan',
    'guardian_maintain', 'guardian_global', 'guardian_capability',
    'guardian_publish', 'guardian_lineage', 'guardian_brain_migration',
    'guardian_conciencia', 'guardian_genome', 'guardian_evolution',
    'guardian_absorb', 'guardian_forja',
    'guardian_memory', 'guardian_rag',
    'guardian_backend', 'guardian_mcp', 'guardian_web',
    'guardian_shared', 'guardian',
]
ok = 0
fails = []
for m in mods:
    try:
        __import__(m)
        ok += 1
    except Exception as e:
        fails.append(f'{m}: {e}')
print(f'OK_COUNT={ok}')
print(f'TOTAL={len(mods)}')
for f in fails:
    print(f'FAIL: {f}')
" 2>&1)
    local ok_count
    ok_count=$(echo "$test_output" | grep -oP "OK_COUNT=\K\d+" | head -1)
    if [ -z "$ok_count" ]; then
        warn "No se pudo verificar imports"
        echo "$test_output" | sed 's/^/      /'
        return 1
    fi
    if [ "$ok_count" = "23" ]; then
        ok "Zero-deps confirmado: $ok_count/23 módulos importan (todo stdlib)"
    else
        warn "Solo $ok_count/23 módulos importan"
        echo "$test_output" | sed 's/^/      /'
    fi
}

verify_install() {
    section "Verificación post-instalación"
    local errors=0

    if [ "$MODE" != "dev" ] && command -v guardian &>/dev/null; then
        ok "CLI: guardian $(command -v guardian)"
    elif [ "$MODE" = "dev" ]; then
        ok "CLI: dev mode, usar PYTHONPATH=lib python3 -m guardian"
    else
        warn "CLI: guardian no encontrado en PATH"
        errors=$((errors + 1))
    fi

    verify_zero_deps "$GUARDIAN_HOME/lib"

    info "Corriendo tests..."
    local test_log
    test_log=$(mktemp)
    if (cd "$GUARDIAN_HOME" && "$PYTHON" -m unittest discover -s tests -p "test_*.py" 2>&1) > "$test_log" 2>&1; then
        local passed
        passed=$(grep -oP "Ran \K\d+" "$test_log" | head -1)
        ok "Tests: $passed pasaron"
    else
        warn "Algunos tests fallaron. Log:"
        tail -20 "$test_log" | sed 's/^/      /'
        errors=$((errors + 1))
    fi
    rm -f "$test_log"

    if ! $NO_OPENCODE && command -v opencode &>/dev/null; then
        if opencode mcp list 2>/dev/null | grep -q nexxoria-guardian; then
            ok "MCP: registrado en OpenCode"
        else
            warn "MCP: no registrado (verificá con 'opencode mcp list')"
        fi
    fi

    return $errors
}

# ── Uninstall ────────────────────────────────────────────────────────

do_uninstall() {
    banner
    section "Desinstalando Guardian v3"
    warn "Esto va a borrar:"
    warn "  - /opt/nexxoria-guardian (o ~/.local/share/nexxoria-guardian)"
    warn "  - /var/lib/nexxoria-guardian (o ~/.local/state/nexxoria-guardian)"
    warn "  - ~/.guardian/ (env vars, templates, specializations)"
    warn "  - /usr/local/bin/guardian symlink (o ~/.local/bin/guardian)"
    warn "  - ~/.agents/skills/nexxoria-guardian/"
    warn "  - ~/.config/opencode/{commands,plugins,opencode.json} entry for guardian"
    if [ -f "/etc/systemd/system/nexxoria-guardian.service" ]; then
        warn "  - /etc/systemd/system/nexxoria-guardian.service"
    fi
    echo ""

    # SAFETY: don't delete the directory where the install.sh script lives
    local script_dir
    script_dir="$(cd "$(dirname "$(readlink -f "$0")")" 2>/dev/null && pwd 2>/dev/null || echo "")"
    local safe_system=true
    local safe_user=true
    if [ -n "$script_dir" ] && [ "$script_dir" = "/opt/nexxoria-guardian" ]; then
        warn "SAFETY: el script corre desde /opt/nexxoria-guardian (el repo)."
        warn "         NO se borrará ese path. Hacelo manualmente si querés."
        safe_system=false
    fi
    if [ -n "$script_dir" ] && [ "$script_dir" = "${HOME}/.local/share/nexxoria-guardian" ]; then
        warn "SAFETY: el script corre desde el dir user install. NO se borrará ese path."
        safe_user=false
    fi

    local confirm
    read -r -p "$(echo -e "${RED}  ?${NC} Escribí 'uninstall' para confirmar: ")" confirm
    if [ "$confirm" != "uninstall" ]; then
        info "Cancelado."
        exit 0
    fi

    # Service
    if [ -f "/etc/systemd/system/nexxoria-guardian.service" ]; then
        sudo systemctl stop nexxoria-guardian 2>/dev/null || true
        sudo systemctl disable nexxoria-guardian 2>/dev/null || true
        sudo rm -f "/etc/systemd/system/nexxoria-guardian.service"
        sudo systemctl daemon-reload 2>/dev/null || true
        ok "Servicio systemd removido"
    fi

    # Install dirs (with safety)
    if [ "$safe_system" = true ] && [ -d "/opt/nexxoria-guardian" ]; then
        sudo rm -rf "/opt/nexxoria-guardian" 2>/dev/null || rm -rf "/opt/nexxoria-guardian"
        ok "Removido: /opt/nexxoria-guardian"
    fi
    if [ "$safe_user" = true ] && [ -d "${HOME}/.local/share/nexxoria-guardian" ]; then
        rm -rf "${HOME}/.local/share/nexxoria-guardian"
        ok "Removido: ~/.local/share/nexxoria-guardian"
    fi

    # Data dirs (ask per dir)
    for dir in /var/lib/nexxoria-guardian "${HOME}/.local/state/nexxoria-guardian"; do
        if [ -d "$dir" ]; then
            local keep_data
            read -r -p "$(echo -e "${CYAN}  ?${NC} ¿Borrar datos de usuario en $dir? [y/N]: ")" keep_data
            if [[ "$keep_data" =~ ^[Yy]$ ]]; then
                sudo rm -rf "$dir" 2>/dev/null || rm -rf "$dir"
                ok "Removido: $dir"
            else
                info "Datos preservados en: $dir"
            fi
        fi
    done

    # Symlinks
    for bin in /usr/local/bin/guardian "${HOME}/.local/bin/guardian"; do
        if [ -L "$bin" ]; then
            sudo rm -f "$bin" 2>/dev/null || rm -f "$bin"
            ok "Symlink removido: $bin"
        fi
    done

    # OpenCode integration
    for f in "${HOME}/.agents/skills/nexxoria-guardian" \
             "${HOME}/.config/opencode/commands/guardian.md" \
             "${HOME}/.config/opencode/plugins/guardian.ts"; do
        if [ -e "$f" ] || [ -L "$f" ]; then
            rm -rf "$f" 2>/dev/null || sudo rm -rf "$f"
            ok "Removido: $f"
        fi
    done

    # opencode.json MCP entry
    local oc_config="${HOME}/.config/opencode/opencode.json"
    if [ -f "$oc_config" ]; then
        "$PYTHON" -c "
import json
path = '$oc_config'
try:
    with open(path) as f:
        cfg = json.load(f)
    mcp = cfg.get('mcp', {})
    if 'nexxoria-guardian' in mcp:
        del mcp['nexxoria-guardian']
        with open(path, 'w') as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
            f.write('\n')
        print('MCP entry removido de opencode.json')
except Exception as e:
    print(f'warn: {e}')
" 2>/dev/null || true
    fi

    # ~/.guardian (config, ask)
    if [ -d "${HOME}/.guardian" ]; then
        local keep_g
        read -r -p "$(echo -e "${CYAN}  ?${NC} ¿Borrar ~/.guardian (env vars, templates, specializations)? [y/N]: ")" keep_g
        if [[ "$keep_g" =~ ^[Yy]$ ]]; then
            rm -rf "${HOME}/.guardian"
            ok "Removido: ~/.guardian"
        fi
    fi

    warn "Las variables GUARDIAN_HOME/DATA siguen en tu .bashrc/.zshrc. Borralas manualmente si querés."

    echo ""
    ok "🛡️  Guardian v3 desinstalado."
}

# ── Final message ───────────────────────────────────────────────────

final_message() {
    echo ""
    if [ "$MODE" = "dev" ]; then
        echo -e "${GREEN}${BOLD}"
        echo "╔══════════════════════════════════════════════════════════╗"
        echo "║  ✅ Modo --dev: Guardian v3 listo en el repo           ║"
        echo "║                                                          ║"
        echo "║  Para usar:                                              ║"
        echo "║    cd $GUARDIAN_HOME"
        echo "║    PYTHONPATH=lib python3 -m guardian --help             ║"
        echo "║                                                          ║"
        echo "║  Tests:                                                  ║"
        echo "║    python3 -m unittest discover -s tests -p 'test_*.py' ║"
        echo "╚══════════════════════════════════════════════════════════╝"
        echo -e "${NC}"
    else
        echo -e "${GREEN}${BOLD}"
        echo "╔══════════════════════════════════════════════════════════╗"
        echo "║  ✅ Guardian v3 instalado correctamente                  ║"
        echo "║                                                          ║"
        echo "║  Próximos pasos:                                         ║"
        echo "║    1. Reiniciá tu terminal (o: source ~/.bashrc)         ║"
        echo "║    2. En tu proyecto:                                    ║"
        echo "║         cd /ruta/a/mi/proyecto                           ║"
        echo "║         guardian start                                   ║"
        echo "║                                                          ║"
        echo "║  Si tenés código existente:                              ║"
        echo "║         guardian activate                                ║"
        echo "║                                                          ║"
        echo "║  Documentación: $GUARDIAN_HOME/docs/"
        echo "║  Desinstalar:  curl ... | bash -s -- --uninstall        ║"
        echo "╚══════════════════════════════════════════════════════════╝"
        echo -e "${NC}"
    fi
}

# ── Main ─────────────────────────────────────────────────────────────

main() {
    if $UNINSTALL; then
        do_uninstall
        exit 0
    fi

    banner
    info "Modo: $MODE"
    if [ "$VERSION" != "main" ]; then
        info "Versión: $VERSION"
    fi

    detect_env
    determine_paths
    get_source
    install_files
    install_cli
    install_opencode
    install_systemd
    setup_env_vars
    verify_install
    final_message
}

main "$@"
