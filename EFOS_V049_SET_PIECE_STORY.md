# EFOS v0.4.9 — Set Piece Story

## Qué entrega

Una sección **Balón Parado** orientada a lectura del entrenador, no a acumulación de tablas:

1. **Tres hallazgos automáticos** por tipo de acción (córners, tiros libres del último tercio, saques laterales peligrosos), selección de partido y perspectiva a favor/en contra.
2. **Mapa doble izquierda/derecha**, con destinos de pase y opción de visualizar flechas individuales.
3. **Patrón más repetido** vs. **patrón de mayor xG por ejecución**, mostrado únicamente si hay una muestra mínima y cobertura suficiente.
4. **Mapa de zona de primer remate concedido** para acciones defensivas, sin atribuir el tipo de marcaje.
5. **Tabla P0→P1→P2 en un desplegable** con exportación CSV y filtros por ejecutor y banda.
6. Informe del cuerpo técnico, Coach Story y Evidence Layer con relatos auditables, no afirmaciones sin muestra.

## Cómo ejecutar en Mac / VS Code

Desde la carpeta `efos/`:

```bash
python3 -m pip install -r requirements.txt
python3 -m pytest -q tests
python3 -m streamlit run visualization/efos_dashboard.py
```

También es posible generar documentos fuera de la interfaz:

```bash
python3 run_sprint4.py \
  --events data/processed/sprint3_real/events_normalized.csv \
  --team "América" \
  --out data/processed/efos_v049_output
```

El último comando exporta `corner_sequences.csv`, `corner_summary.json`, `set_piece_sequences.csv`, `set_piece_summary.json`, `evidence.json`, `coach_story.json`, `informe_cuerpo_tecnico.md` y PDF, entre otros.

## Estructura añadida

- `intelligence/corner_engine.py`: ejecución P0, intervención registrada P1 y remate P2 para córners.
- `intelligence/set_piece_patterns.py`: normalización de faltas y saques laterales peligrosos + narrativa por banda, zona y muestra.
- `visualization/set_piece_story_maps.py`: visualizaciones de destinos por banda y mapa defensivo de primer remate.
- `visualization/efos_dashboard.py`: pantalla narrativa minimalista; tabla relegada a Evidencia.
- `run_sprint4.py`: cálculo único conectado con informes.
- `coach_story/football_report.py`: **mismo denominador de córners** que el Corner Engine: evento `Pass` con `type_name=Corner`.
- `config/thresholds.yaml`: parámetros editables en sección `set_piece_story`.
- `tests/test_corner_engine.py` y `tests/test_set_piece_story.py`.

## Definiciones metodológicas

- **P0**: una ejecución registrada de balón parado. No contamos cada pase posterior de la fase `From Corner` como otra ejecución.
- **P1**: primera intervención **registrada** en los eventos siguientes durante 6 s; no primer contacto físico ni movimiento sin balón confirmado.
- **P2**: uno o varios remates del ejecutor de la jugada en 10 s de la **misma posesión, partido y periodo**. La ventana se corta por otra ejecución.
- **Izquierda/derecha**: siempre mirando en dirección de ataque hacia +x con coordenadas StatsBomb normalizadas: y<40 izquierda, y≥40 derecha. Si un proveedor entrega coordenadas sin normalización, validar orientación antes de narrar la banda.
- **Zona objetivo**: coordenadas **de destino registrado del pase**. No es punto real de caída o recepción validada.
- **Corto**: desplazamiento de ejecución menor o igual a 15 unidades StatsBomb (heurística).
- **Tiros libres de peligro**: evento tiro o pase `Free Kick` originado en x≥80.
- **Saque lateral peligroso**: `Throw-in` desde x≥80.
- **Comparación de peligrosidad**: xG medio solo entre ejecuciones con datos completos o sin remate (0), con n mínimo y cobertura ≥80%. Un remate sin xG no se toma como cero.
- **Patrón consistente**: se describe explícitamente número de ejecuciones y número de partidos. Se evita atribuir intención al entrenador cuando solo hay eventos.

Todos los parámetros exploratorios ajustables se encuentran en `config/thresholds.yaml`. Este motor **no** usa ni afirma tener XGBoost, SHAP, reconocimiento de marcaje real ni tracking.

## Validación realizada

- `pytest -q tests`: **90 pruebas aprobadas** en el entorno de desarrollo.
- Ejecución de `run_sprint4.py` sobre los **38 partidos y 124,353 eventos** de `data/processed/sprint3_real/events_normalized.csv`: **terminó con exit code 0** y generó los informes y nuevos CSV/JSON.
- Vista de mapa Matplotlib creada y verificada con los datos reales.
- Limitación: en el entorno de preparación no se instaló Streamlit, por lo que la interfaz se verificó por compilación, integración y tests, pero **no mediante navegador Streamlit real**; revisarla al abrirla en tu equipo.

## Lectura de ejemplo basada en la muestra oficial

- Córners a favor: 226 ejecuciones, con remate en 32.7%.
- Córners en contra: 131 ejecuciones, con remate del rival en 38.9%.
- Desde la derecha a favor, el destino más frecuente es la zona central aproximada: 39 de 119 córners (33%), en 20 partidos para esa combinación. **No es un predominio absoluto**.
- Los porcentajes son descriptivos y relativos a la metodología de ventana de 10 segundos.

## Próximos pasos antes de presentar al jurado

Verificar sobre clips una muestra de acciones clasificadas, corroborar izquierda/derecha y comparar episodios entre partidos y rivales. La cobertura de 360 disponible en el pipeline actual es parcial u opcional y **no** convierte estos hallazgos en detección de movimientos sin balón.
