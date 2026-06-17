# EVALUATE — Evaluar enfoque y riesgos

Proyecto: {{slug}} ({{stack}}/{{framework}})
Scope: {{scope}}

## Preguntas a responder

1. **¿El enfoque es correcto?**
   - Sigue los patrones del proyecto (según docs)
   - Respeta constraints activas
   - Es consistente con decisiones pasadas (memoria)

2. **¿Hay riesgos?**
   - ¿Rompe algo existente?
   - ¿Introduce debt técnico?
   - ¿Dependencia externa nueva?

3. **¿Está completo?**
   - ¿Faltan archivos por crear/modificar?
   - ¿Faltan tests?
   - ¿Falta documentación?

## Output

```
Enfoque: ✓ correcto / ⚠️ revisar / ❌ cambiar
Riesgos: <lista de riesgos o "ninguno">
Completo: ✓ sí / ⚠️ falta <qué>
Próximo paso: ejecutar / pedir aprobación / replanificar
```
