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
| `@guardian rollback` | Sugerir revertir último cambio |
| `@guardian hooks` | Estado de hooks |
| `@guardian build|dev|test|lint|typecheck|deploy|logs` | Stack helpers |
| `@guardian git branch|commit` | Git helpers |

Todo comando chequea config.yaml del proyecto actual.
