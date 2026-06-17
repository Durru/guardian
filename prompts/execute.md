# EXECUTE — Ejecutar el cambio con hooks

Proyecto: {{slug}} ({{stack}}/{{framework}})
Archivos: {{files}}

## Flujo de ejecución

1. **Pre-change hook**
   - Snapshot de archivos a modificar
   - Verificar paths protegidos
   - Scope match contra docs

   ```
   guardian snapshot <path> {{slug}}
   guardian protect <path> {{slug}}  # si aplica
   ```

2. **Hacer el cambio**
   - Escribir/modificar archivos según lo evaluado
   - Seguir patrones del doc scope

3. **Post-change hook**
   - Verificar diff
   - Guardar decisión en memoria
   - Registrar en auditoría

   ```
   guardian diff {{slug}}
   guardian memory save decision "{{decision}}" {{slug}}
   ```

4. **Verificación**
   - Preguntar: "¿Ejecuto tests/lint?"
   - Si sí: `guardian test {{slug}}`
   - Si hay skills: considerar aprender

## Output final

```
✓ Cambio completado
Archivos: {{files}}
Decisión guardada: <decisión>
¿Siguiente paso? <deploy / más cambios / finalizar>
```
