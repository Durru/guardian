# @guardian

Carga Nexxoria Guardian y detecta el proyecto actual.

En el día a día NO necesitás comandos — el guardian opera solo.
Usá estos solo cuando quieras control manual:

| Comando | Qué hace |
|---------|----------|
| `@guardian` | Cargar + detectar proyecto |
| `@guardian setup` | Re-ejecutar wizard de configuración |
| `@guardian absorb` | Re-escanear + calificar skills |
| `@guardian status` | Dashboard: reglas activas, últimos cambios |
| `@guardian report` | Violaciones, tendencias, reglas más/menos seguidas |
| `@guardian check` | Verificar reglas y paths protegidos |
| `@guardian protect <path>` | Agregar path protegido |
| `@guardian snapshot <path>` | Backup de archivo antes de modificar |
| `@guardian forget <slug>` | Eliminar proyecto del guardian |
| `@guardian docs scan` | Generar docs desde templates según stack |
| `@guardian docs write` | Documentación narrativa |
| `@guardian docs route <path>` | Mostrar qué doc se serviría para un path |
| `@guardian rollback` | Revertir último cambio |
| `@guardian hooks` | Estado de hooks |
| `@guardian build|dev|test|lint|typecheck|deploy|logs` | Stack helpers |
| `@guardian git branch|commit` | Git helpers |

---

### Command implementations

**@guardian status**
- Project + stack + active docs
- Protected paths count
- Last 5 changes from audit.json
- Hook statuses
- Docs last_scan date

**@guardian report**
- Total changes, violations, most changed files
- Docs update rate, rule compliance
- 30-day trends

**@guardian check**
- Protected paths not modified
- No forbidden deps
- Docs not stale (< 7 days)
- All available docs exist
- Skills loaded

**@guardian rollback**
- Shows last change from audit.json
- Asks confirmation
- git checkout + audit entry

**@guardian protect <path>**
- Adds to config.yaml routes + CONSTRAINTS.md
- Updates config

**@guardian snapshot <path>**
- Creates .guardian-snapshot-<timestamp>
- Records in audit.json

**@guardian docs route <path>**
- Matches path against routes with priority
- Shows which doc would be served

**@guardian hooks**
- Shows all 4 hook statuses with checks

Todo comando chequea config.yaml del proyecto actual.
