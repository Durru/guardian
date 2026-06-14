# IDENTIFY — Clasificar el cambio

Proyecto: {{slug}} ({{stack}}/{{framework}})
Scope: {{scope}}

Clasificá el cambio que pide el usuario:

| Tipo | Cuándo |
|------|--------|
| component | Nuevo componente UI o modificación de existente |
| api | Nuevo endpoint, ruta, o lógica de backend |
| style | Estilos, CSS, tokens, layout |
| structure | Refactor de estructura de archivos/directorios |
| bugfix | Corrección de bug |
| refactor | Mejora de código sin cambiar comportamiento |
| feature | Funcionalidad nueva con lógica de negocio |
| config | Configuración, dependencias, tooling |

## Instrucciones

1. Escuchá lo que pide el usuario
2. Clasificá el tipo de cambio
3. Identificá los archivos que se van a tocar
4. Declará el alcance en formato estructurado

## Output requerido

```
Tipo: <tipo>
Archivos: [<path1>, <path2>, ...]
Scope doc: <frontend|backend|ui|features>
Descripción: <1 línea>
```

Luego ejecutá: `guardian prompt consult --scope <scope>`
