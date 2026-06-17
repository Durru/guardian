# Nexxoria Guardian — Plan Open Source

> Objetivo: repo open source en GitHub, instalable en Ubuntu con un solo comando,
> compatible con OpenCode, backend centralizado, skill + MCP auto-detectados.

---

## 1. Estructura del repo

```
nexxoria-guardian/
├── LICENSE (MIT)
├── README.md                    ← Qué es, cómo instalar, cómo usar
├── install.sh                   ← Único script de instalación
├── SKILL.md                     ← Skill definition (auto-detectable por OpenCode)
├── commands/
│   └── guardian.md              ← @guardian command definition
├── systemd/
│   └── nexxoria-guardian.service  ← Unit file para systemd
├── genome/
│   └── identity.yaml            ← ADN default del ser
├── lib/                         ← 11 módulos del sistema
│   ├── guardian.py              ← CLI principal
│   ├── guardian_shared.py
│   ├── guardian_memory.py
│   ├── guardian_rag.py
│   ├── guardian_absorb.py
│   ├── guardian_web.py
│   ├── guardian_backend.py
│   ├── guardian_genome.py
│   ├── guardian_conciencia.py
│   ├── guardian_evolution.py
│   └── guardian_mcp.py
├── prompts/                     ← 5 templates de workflow
├── templates/                   ← Doc templates
├── tests/                       ← Suite de tests
└── docs/                        ← Documentación
    ├── CONCEPTOS.md
    ├── FLUJOS.md
    ├── REFERENCIA.md
    ├── GUIA.md
    ├── INSTALACION.md
    └── CONSTRAINTS.md
```

---

## 2. Rutas de instalación

| Componente | Origen | Destino |
|-----------|--------|---------|
| Código | repo/ | `/opt/nexxoria-guardian/` |
| CLI symlink | — | `/usr/local/bin/guardian` → `/opt/nexxoria-guardian/lib/guardian.py` |
| Datos runtime | — | `/var/lib/nexxoria-guardian/` (branches, projects, skills, PID, logs) |
| systemd unit | `systemd/nexxoria-guardian.service` | `/etc/systemd/system/nexxoria-guardian.service` |
| Skill symlink | `SKILL.md` | `~/.agents/skills/nexxoria-guardian/SKILL.md` |
| @guardian command | `commands/guardian.md` | `~/.config/opencode/commands/guardian.md` |
| MCP registration | — | `opencode mcp add nexxoria-guardian` |
| User config | — | `~/.config/nexxoria-guardian/config.yaml` |

---

## 3. `install.sh` — Script único de instalación

El script hace todo en orden:

```
1. DETECTAR ENTORNO
   - OS: Ubuntu (o Debian-based)
   - Python 3.9+
   - OpenCode instalado (busca binary en PATH)
   - Git disponible

2. CLONAR / COPIAR REPO
   - Si se ejecuta desde el repo: copia local
   - Si se ejecuta standalone: git clone de GitHub
   - Destino: /opt/nexxoria-guardian/

3. CREAR DIRECTORIO DE DATOS
   - /var/lib/nexxoria-guardian/
   - /var/lib/nexxoria-guardian/genome/branches/default/
   - /var/lib/nexxoria-guardian/genome/branches/default/memory/
   - /var/lib/nexxoria-guardian/genome/branches/default/knowledge/tomes/
   - /var/lib/nexxoria-guardian/genome/branches/default/learnings/

4. INSTALAR DEPENDENCIAS
   - PyYAML: apt install python3-yaml  (o pip install pyyaml)

5. CONFIGURAR CLI
   - Hacer ejecutable: chmod +x lib/guardian.py
   - Symlink: ln -sf /opt/nexxoria-guardian/lib/guardian.py /usr/local/bin/guardian

6. CONFIGURAR SYSTEMD
   - Copiar unit file
   - systemctl daemon-reload
   - systemctl enable nexxoria-guardian
   - systemctl start nexxoria-guardian
   - Verificar: systemctl is-active nexxoria-guardian

7. CONFIGURAR OPENCODE SKILL
   - mkdir -p ~/.agents/skills/nexxoria-guardian/
   - ln -sf /opt/nexxoria-guardian/SKILL.md ~/.agents/skills/nexxoria-guardian/SKILL.md

8. CONFIGURAR @guardian COMMAND
   - mkdir -p ~/.config/opencode/commands/
   - cp commands/guardian.md ~/.config/opencode/commands/guardian.md

9. REGISTRAR MCP SERVER
   - opencode mcp add nexxoria-guardian \
     --command "python3" \
     --args "/opt/nexxoria-guardian/lib/guardian_mcp.py" \
     --transport stdio

10. CREAR GENOMA DEFAULT
    - cp genome/identity.yaml /var/lib/nexxoria-guardian/genome/identity.yaml

11. VERIFICAR
    - guardian --help  → muestra ayuda
    - guardian backend status → running
    - curl :9787/health → {"ok": true}
    - ls ~/.agents/skills/nexxoria-guardian/SKILL.md → existe
    - opencode mcp list | grep nexxoria-guardian → configurado

12. MENSAJE FINAL
    - "✅ Nexxoria Guardian instalado. Reiniciá OpenCode y decí 'activo guardian'"
```

---

## 4. systemd unit

```ini
[Unit]
Description=Nexxoria Guardian Backend
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/nexxoria-guardian/lib/guardian_backend.py serve
Restart=on-failure
RestartSec=5
PIDFile=/var/lib/nexxoria-guardian/guardian-backend.pid
StandardOutput=append:/var/lib/nexxoria-guardian/guardian-backend.log
StandardError=append:/var/lib/nexxoria-guardian/guardian-backend.log

[Install]
WantedBy=multi-user.target
```

Modo bajo demanda (socket activation) como alternativa:

```ini
[Unit]
Description=Nexxoria Guardian Backend (socket)
[Socket]
ListenStream=127.0.0.1:9787
[Install]
WantedBy=sockets.target
```

---

## 5. Backend centralizado

El backend pasa a ser el punto único de todo el estado y operaciones.

### Estado actual (disperso)
- CLI llama subprocess a otros scripts
- Archivos de estado en `/var/guardian/` y `/srv/guardian/genome/`
- MCP server independiente

### Estado target (centralizado)
- CLI es thin client: todas las operaciones van por HTTP al backend
- Backend maneja todo el estado: conciencia, genoma, ramas, RAG, absorb, docs
- MCP server se integra como endpoint `/mcp/call` además de stdio
- Un solo punto de datos: `/var/lib/nexxoria-guardian/`

### Refactor necesario
```
guardian.py:
  - cmd_*() ya no ejecutan subprocess, llaman a backend HTTP
  - Si backend no responde, lo arranca (socket activation o fork)
  - Toda la lógica pesada está en guardian_backend.py

guardian_backend.py:
  - Ya tiene 19 endpoints, se extiende con /activate
  - Maneja todo: conciencia, genoma, ramas, RAG, absorb, docs, MCP
  - Scheduler para tareas periódicas

guardian_mcp.py:
  - Sigue siendo servidor stdio independiente
  - También expone tools via POST /mcp/call en backend
```

---

## 6. Flujo "activo guardian"

Disparador: usuario dice "activo guardian" en OpenCode, o `guardian activate [slug]`, o `POST /activate`.

```
1. DETECTAR
   - Si hay slug: usarlo
   - Si no: detectar desde git remote o PWD

2. SETUP
   - guardian setup <slug>  (crea config.yaml si no existe)
   - Detectar stack (python, node, etc.)

3. RAMA
   - guardian branch fork <slug>  (fork de genoma default)
   - Si ya existe: cargar estado existente

4. SKILLS
   - guardian absorb scan  (actualizar skills globales)
   - guardian absorb match <slug>  (matchear al proyecto)
   - guardian absorb ingest <slug>  (skills → tomos → RAG)

5. DOCS
   - guardian docs scan <slug>  (generar docs desde templates)

6. RAG
   - guardian rag index --slug <slug> --force  (indexar todo)

7. CONCIENCIA
   - guardian conciencia cycle "activar guardian" <slug>
   - Modo: si hay package.json/build files → build, si no → plan

8. BACKEND
   - Asegurar que backend está corriendo
   - Sincronizar estado

9. OUTPUT
   - Proyecto: <slug>
   - Stack: <detectado>
   - Rama: <hash>
   - Tomos: <N>
   - Skills: <N> relevantes
   - Conciencia: <acción> (confianza <X>%)
   - Modo: <plan|build>
```

Disponible como:
- `guardian activate [slug]` — CLI
- `POST /activate` — backend endpoint
- MCP tool `activate_guardian` — para el agente
- Parte del prompt del skill cuando detecta proyecto nuevo

---

## 7. Lo que hay que crear

### Archivos nuevos
| Archivo | Propósito |
|---------|-----------|
| `LICENSE` | MIT License |
| `systemd/nexxoria-guardian.service` | Unit file systemd |
| `docs/INSTALACION.md` | Documentación de instalación |
| `.gitignore` | Ignorar archivos generados |

### Modificaciones a lib/

| Archivo | Cambio |
|---------|--------|
| `guardian.py` | Agregar `cmd_activate()`, refactor a thin client del backend |
| `guardian_backend.py` | Agregar `POST /activate`, scheduler, socket activation |
| `guardian_mcp.py` | Agregar tool `activate_guardian` |
| `guardian_shared.py` | Paths configurables por instalación |

---

## 8. Lo que NO cambia (ya funciona)

- 11 módulos de `lib/` (solo extensiones)
- SKILL.md (solo actualizar si cambia algo)
- Tests existentes (se agregan nuevos)
- Temas/plantillas/prompts
- Documentación de concepto/flujo/referencia/guía

---

## 9. Orden de implementación

```
Fase 1: LICENSE + .gitignore + README base
Fase 2: systemd unit file
Fase 3: install.sh
Fase 4: docs/INSTALACION.md
Fase 5: cmd_activate + POST /activate + MCP tool activate_guardian
Fase 6: Refactor CLI → thin client del backend
Fase 7: Tests de instalación y activación
Fase 8: Push a GitHub + verificar instalación desde cero
```

---

## 10. Verificación

```bash
# Test de instalación en fresh Ubuntu
sudo apt update
sudo apt install -y python3 python3-pip git
pip install opencode  # o descargar binary
git clone https://github.com/nexxoria/guardian.git
cd guardian
bash install.sh

# Verificar
guardian --help
guardian backend status
curl http://127.0.0.1:9787/health
ls ~/.agents/skills/nexxoria-guardian/
opencode mcp list

# Activar en proyecto
cd /mi/proyecto
guardian activate

# En OpenCode
# El skill ya está disponible, solo reiniciar
```
