# ANALYZE — Explorar código y verificar impacto

Proyecto: {{slug}} ({{stack}}/{{framework}})
Scope: {{scope}}
Archivos a tocar: {{files}}

## Instrucciones

Usá herramientas nativas para explorar el código:

1. **glob** — descubrí archivos existentes en el scope
2. **grep** — buscá símbolos, imports, patrones
3. **Read** — leé archivos existentes para entender estructura

## Checklist

- [ ] ¿Ya existe código similar? → evitar duplicados
- [ ] ¿Hay imports/archivos que cambian? → verificar impacto
- [ ] ¿El cambio rompe tests existentes? → revisar
- [ ] ¿Cambia la interfaz pública? → actualizar exports
- [ ] ¿Afecta tipos compartidos? → revisar types

## Output

```
Hallazgos:
- <hallazgo 1>
- <hallazgo 2>

Impacto: <archivos afectados además de los planeados>
Duplicados: <sí/no — si sí, dónde>
```
