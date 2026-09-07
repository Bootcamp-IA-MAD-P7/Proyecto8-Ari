# Proyecto 8 — Servicio de riesgo de ictus

Backend en FastAPI descrito en `specs/spec_backend.md`.

## Tests

Los tests de integración viven en `tests/` y corren contra SQLite en
memoria (no requieren Postgres ni Docker instalados). Para correrlos:

```
uv run pytest
```

Cobertura: el camino completo de una sesión (abrir, clasificar tabular,
derivar, clasificar imagen, cerrar), el camino de alta directa sin imagen,
las transiciones de estado inválidas (409), sesión inexistente (404), la
validación de entrada (422) y los cuatro filtros de subida de imagen —
incluyendo que no quede ningún archivo temporal después de clasificar.

Pendiente: no hay todavía tests ni verificación en vivo contra una
Postgres real (persistencia y sobrevivencia a un reinicio). Queda para la
fase de despliegue — ver la nota en `app/database.py`.
