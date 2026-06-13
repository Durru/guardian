# Nexxoria Guardian

Universal project guardian for OpenCode AI sessions. Auto-detects projects,
prevents LLMs from breaking things, manages docs, runs hooks, integrates
CodeGraph + OpenSpec/SDD + Engram.

## Triggers

- Starting work in a project
- User asks for a code change
- User mentions "guardian", "proyecto", "project"
- User runs `@guardian` or any `@guardian <subcommand>`
- Before deploy, after change, on structural refactors

---

## Rule #1: Flow mode (automatic)

**No need to memorize commands.** The guardian operates in flow mode:

| Cuándo | Qué hace el guardian |
|--------|---------------------|
| Entrás a un proyecto | Detecta, carga config, reporta estado |
| Pedís un cambio | Ejecuta workflow 5 pasos automáticamente |
| Algo está protegido | Frena y pregunta antes de tocar |
| Detecta duplicados | "Esto ya existe en X. ¿Crear otro?" |
| Algo cambia de estructura | "Detecté cambios. ¿Actualizo docs?" |
| Antes de deploy | Corre checks automáticos |
| Algo va mal | Sugiere `@guardian report` o `@guardian rollback` |

Comandos existen SOLO para cuando querés control manual. El día a día es
sin comandos — el AI lo resuelve solo.

---

## Architecture

```
/srv/guardian/                  ← REPO (git-versionable, GitHub)
├── SKILL.md                     ← this file
├── commands/guardian.md         ← @guardian command
├── install.sh                   ← symlink setup
├── README.md                    ← for GitHub
└── .gitignore

/var/guardian/
├── skills-global.json           ← global skill index (ONE file)
├── projects/<slug>/             ← DATA (per-project, NOT in repo)
│   ├── config.yaml              ← detected stack, rules, paths
│   ├── audit.json               ← change audit trail (JSON)
│   └── skills.json              ← relevant skill references
```

---

## 1. Detection + lazy load

On session start or `@guardian`:

```
1. git remote origin → extract repo name → slug
2. If no git: basename $PWD → slug
3. If /var/guardian/projects/<slug>/config.yaml exists:
   → load ONLY that project's config.yaml
   → report: "Guardian activo para <slug> (stack: <detected>)"
4. If not found:
   → run Setup Wizard
```

**skills-global.json se carga solo cuando hace falta** (absorb, check, status).
No se lee en cada sesión. skills.json por proyecto solo tiene nombres de
skills relevantes, no la data completa.

### Setup Wizard

```
1. Confirm PROJECT_ROOT
2. Scan for package.json / Cargo.toml / pyproject.toml / composer.json
3. Detect stack (framework, language, CSS, test runner, linter)
4. Detect OpenSpec: /root/p/openspec/
   └── Ask mode: openspec | engram | hybrid (default: hybrid)
5. Detect CodeGraph: .codegraph/ exists?
   └── If missing → suggest codegraph init
6. Ask: protected paths? (default: none)
7. Ask: project rules? (e.g. "no modificar .env")
8. Save /var/guardian/projects/<slug>/config.yaml
9. Run absorb + docs scan
10. mem_save: "Project <slug> registered in guardian"
```

### config.yaml

```yaml
project_root: /srv/myapp
slug: myapp
registered: 2026-06-12
stack:
  detected: [next, react, tailwind, typescript]
  build: npm run build
  dev: npm run dev
  test: npm test
  lint: npm run lint
  deploy: pm2 restart myapp
  logs: pm2 logs myapp --lines 20
docs:
  protected: []
  last_scan: ~
openspec:
  enabled: true
  mode: hybrid
codegraph:
  enabled: true
  path: /srv/myapp
rules: []
audit: true
```

---

## 2. Change workflow (5 steps — automatic)

Execute on ANY code change. Do not skip.

```
┌─────────────────────────────────────────────────────────┐
│ 1. IDENTIFY                                             │
│    Classify: component / api / style / structure /      │
│              bugfix / refactor / feature                 │
├─────────────────────────────────────────────────────────┤
│ 2. CONSULT                                              │
│    ├── Read project docs if they exist                  │
│    ├── OpenSpec: search /root/p/openspec/specs/         │
│    │   └── If feature + no spec → suggest SDD           │
│    ├── Engram: mem_search for past decisions             │
│    └── config.yaml rules — check restrictions           │
├─────────────────────────────────────────────────────────┤
│ 3. ANALYZE                                              │
│    ├── CodeGraph context/impact/callers/callees         │
│    └── Check for existing code to avoid duplicates      │
├─────────────────────────────────────────────────────────┤
│ 4. EVALUATE                                             │
│    ├── ¿Ya existe? ¿Se rompe algo? ¿Docs actualizados?  │
│    └── ¿Hay spec que seguir?                            │
├─────────────────────────────────────────────────────────┤
│ 5. EXECUTE                                              │
│    ├── Present to user: "Tipo: X. Impacto: Y. ¿Procedo?"│
│    ├── On approval: pre-change hook → change →          │
│    │   post-change hook → audit.json + mem_save         │
│    └── On rejection: wait                               │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Hooks (automatic)

### Pre-change (before writing code)

```
1. Check if affected paths are protected in config.yaml
2. If protected → STOP + ask user
3. Check if file exists and is about to be deleted
   → "¿Estás seguro? Esto elimina X."
4. Check Engram for relevant past decisions
```

### Post-change (after code written)

```
1. Run tests (config.stack.test) if configured
2. Run linter (config.stack.lint) if configured
3. Detect new/deleted components or routes
4. If structural change:
   → "Nuevo componente. ¿Actualizo docs?"
5. Write to audit.json + mem_save
```

### Pre-deploy (before deploy)

```
1. Run build (config.stack.build)
2. If build fails → STOP
3. If active SDD change → suggest sdd-verify
```

### Post-deploy (after deploy)

```
1. Smoke test (curl health endpoint)
2. Write to audit.json
3. mem_save session summary
```

---

## 4. Audit log (JSON)

```json
[
  {"ts":"2026-06-12T10:30:00","type":"change","file":"src/components/Navbar.tsx","desc":"Added mobile menu","status":"ok"},
  {"ts":"2026-06-12T10:32:00","type":"pre_deploy","build":"passed","deploy":"ok","status":"ok"},
  {"ts":"2026-06-12T10:35:00","type":"violation","file":".env","desc":"Intentó modificar path protegido","status":"blocked"}
]
```

Guarda en `/var/guardian/projects/<slug>/audit.json`.

---

## 5. Documentation (unified)

### Auto-generation from code (automatic + @guardian docs scan)

```
1. codegraph files → project tree
2. Scan component files (JSX/TSX patterns)
3. Scan API routes
4. Generate/update:
   ├── STYLE.md, COMPONENTS.md, API_SPEC.md, ARCHITECTURE.md
   └── AGENTS.md (via agents-md-generator)
5. Save to project root
6. Update last_scan in config.yaml
```

### Narrative docs (@guardian docs write)

```
1. Ask what kind: tutorial / how-to / explanation / reference
2. Invoke documentation-writer with project context
```

### Sync (automatic in post-change)

```
- New component + COMPONENTS.md exists
  → "¿Actualizo COMPONENTS.md?"
- Docs stale > 7 days
  → "¿Corro @guardian docs scan?"
```

---

## 6. Skill registry & absorb

### Global (ONE file for all projects)

`/var/guardian/skills-global.json` — skills completos con rating.

### Per-project (just references)

`/var/guardian/projects/<slug>/skills.json` — SOLO nombres de skills relevantes.

```json
{
  "relevant": ["007", "bug-hunter", "documentation-writer"],
  "last_absorb": "2026-06-12"
}
```

### Absorption (@guardian absorb)

```
1. Scan /root/.agents/skills/*/SKILL.md
2. Scan /root/.config/opencode/skills/*/SKILL.md
3. Extract: name, description, triggers
4. Rate (0-50): clarity + triggers + workflow + DOs/DON'Ts + examples
5. Stars: 0-16★ / 17-33★★ / 34-50★★★
6. Save global: /var/guardian/skills-global.json
7. For each project: determine relevant skills → save references
```

**Flujo automático:** se ejecuta en setup wizard y cuando el usuario menciona
"nuevo skill" o "actualizar skills". No requiere comando en el día a día.

---

## 7. Stack helpers (automatic + manual)

When user asks to build/test/deploy → run configured command from config.yaml.

```
@guardian build      @guardian test       @guardian dev
@guardian lint       @guardian typecheck  @guardian deploy
@guardian logs       @guardian git branch @guardian git commit
```

If command not configured:
> "No hay comando configurado para <action>. Usá @guardian setup."

---

## 8. Integrations (optional — external tools)

| Tool | Integration |
|------|-------------|
| **Engram** | mem_search in step 2, mem_save after changes and sessions |
| **CodeGraph** | context/impact/callers/callees in step 3 |
| **OpenSpec/SDD** | Check specs in step 2, suggest SDD for features |
| **documentation-writer** | Narrative docs (@guardian docs write) |
| **agents-md-generator** | AGENTS.md generation |

All optional. Guardian works fully without them.

---

## 9. Commands (reference — not required)

| Command | What it does |
|---------|-------------|
| `@guardian` | Load skill + detect project |
| `@guardian setup` | Re-run setup wizard |
| `@guardian absorb` | Re-scan + rate all skills |
| `@guardian status` | Dashboard: rules, last changes, protected paths |
| `@guardian report` | Violations, most/least followed rules |
| `@guardian check` | Verify all rules and protected paths |
| `@guardian protect <path>` | Add a protected path |
| `@guardian snapshot <path>` | Backup a file before modifying |
| `@guardian forget <slug>` | Remove project from guardian |
| `@guardian docs scan` | Auto-generate docs from code |
| `@guardian docs write` | Narrative documentation |
| `@guardian rollback` | Suggest reverting last change |
| `@guardian hooks` | Show hook status |
| `@guardian build | dev | test | lint | typecheck | deploy | logs` | Stack helpers |
| `@guardian git branch | commit` | Git helpers |
