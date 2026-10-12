# EFOS Corner Sequence Engine v0.1 — integración

La unidad de análisis es **cada córner** identificado en StatsBomb (`Pass`, `type_name=Corner`).

- **P0**: trayectoria, ejecutor, destino y zona estimada (unidades espaciales StatsBomb 120x80).
- **P1**: primera intervención **registrada** en 6 segundos. No confirma contacto físico.
- **P2**: remates del equipo ejecutor en la misma posesión y dentro de 10 segundos; suma de xG disponible, goles y cobertura. Una segunda ejecución trunca la ventana de la anterior.

## Código integrado

- `intelligence/corner_engine.py` — secuencias, resúmenes y claims auditables.
- `run_sprint4.py` — motor en el pipeline; `corner_sequences.csv`, `corner_summary.json`, `evidence.json`, `coach_story.json`, informe del cuerpo técnico.
- `visualization/efos_dashboard.py` — panel Balón Parado, métricas P0→P1→P2.
- `tests/test_corner_engine.py` — regresión de ventanas, xG ausente, 360 parcial y solapamiento de ejecuciones.

## Correr

```bash
python -m pytest -q tests/test_corner_engine.py
python -m pytest -q tests
python run_sprint4.py --events data/processed/sprint3_real/events_normalized.csv --team "América" --out data/processed/sprint4_corner_validation
```

Nota: el archivo de entrada debe conservar `type_name`, `period`, `possession`, `timestamp_seconds`; si no, se marca el motor `NOT_COMPUTABLE` y no se inventan resultados. La carga de 360 es opcional.

## Metodología y limitaciones

No usa ni afirma XGBoost, SHAP o inferencia causal. Son indicadores descriptivos de secuencias observadas. Los cortes de zonas, ventana temporal y high-threat son parámetros exploratorios. El 360 es un snapshot parcial y no permite afirmar bloqueos, tipo de marcaje, velocidades ni primer contacto real. El reporte debe mostrar N y cobertura; sus resultados requieren contraste posterior con vídeo y la muestra oficial.

**Estado de validación:** pruebas sintéticas del motor, no validación completa de la temporada, ejecución de CI o revisión táctica externa.
