# Guardian — Inicio rápido

## Instalación

```bash
git clone https://github.com/Durru/guardian.git /opt/nexxoria-guardian
ln -s /opt/nexxoria-guardian/lib/guardian.py /usr/local/bin/guardian
guardian --version  # v4.5.1
```

## Activar en un proyecto

```bash
cd /tu/proyecto
guardian activate
```

Esto:
1. Crea `projects/<slug>/` con `branch.json`, `config.yaml`
2. Inicializa `brain/` con 4 DBs SQLite
3. Escanea skills globales y los ingesta como tomos de conocimiento
4. Indexa CodeGraph (AST del proyecto)
5. Ejecuta el primer ciclo de conciencia

## Uso diario

### Clasificar un intent
```bash
guardian analyze-intent "necesito migrar la base de datos"
# → topic: db/migration, importance: 0.65
```

### Planificar o actuar
```bash
guardian plan-or-act "voy a crear un endpoint" --confidence=0.9
# → action: assume (confianza alta)
```

### Guardar observación
```bash
guardian save-observation <slug> decision auth/jwt "usamos JWT con refresh tokens"
```

### Governor adaptativo
```bash
guardian learn <slug> merge_was_wrong       # Bajar threshold de duplicado
guardian learn <slug> discard_should_happen  # Subir floor de importancia
```

### Entrenar clasificador
```bash
guardian feedback <slug> db/migration "migrar la base de datos de A a B"
```

### Spiking Memory
```bash
guardian brain spike <slug> semantic <node_id> 0.3
guardian brain decay <slug> semantic 0.95
guardian brain gc-potential <slug> semantic 0.15
```

### Ver estado
```bash
guardian status <slug>
guardian brain status <slug>
```

## Tests

```bash
pytest tests/                    # Suite completa (~314)
pytest tests/test_neural.py      # Tests neuronales (24)
```

## GitHub

```bash
git push origin master
```
