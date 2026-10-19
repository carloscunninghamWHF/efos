# EFOS v0.4.19 — Ataque Organizado · Storytelling editorial

## Objetivo
Reemplazar cinco subvistas y los atlas miniaturizados por una lectura continua y comprobable:
**Qué define su inicio → Quién conecta → Cómo progresa → Qué produce**.

## Cambios en la experiencia
- Selector compacto de **Temporada completa / Un partido / Comparar partidos**; nombres de rival desde los eventos disponibles, sin exponer `match_id` ni inventar jornadas o fechas.
- La primera muestra es **Todo el juego abierto**; incluye transiciones y posesiones no clasificadas y se declara de forma explícita. En la versión previa, el filtro por `is_controlled_possession` cubría sólo una pequeña fracción de los ataques; sigue disponible pero no sustituye a la muestra completa.
- Tres canchas principales legibles: **red dirigida de pases**, **una secuencia observada seleccionable**, **remates o entradas al área**. La vista por zonas se mantiene como exploración opcional.
- Resumen narrativo según **muestra filtrada**, nunca un texto de toda la temporada bajo un filtro de un solo partido.
- Los atlas de seis paneles, medios espacios, presión, tablas, exportaciones y conceptos se conservan dentro de capas **avanzadas** que el usuario activa deliberadamente. No se recalculan diagramas pesados si esas opciones están desactivadas.
- `run_sprint4.py` prepara una muestra compartida y alimenta **Ataque**, **Modelo de Juego y DT**, **Informe Ejecutivo**, **Coach Story**, **Evidence Layer** y **PDF del cuerpo técnico**. La integración añade `offensive_story.json` a los resultados.

## Metodología
- Secuencias = objetos existentes de `organized_attack.py`, segmentados por partido/periodo/posesión e interrupciones.
- Conexiones = pases completos con destinatario registrado, con tamaño de muestra y partidos explícitos.
- Corredor de inicio = y de la primera intervención registrada. No es estructura simultánea ni intención del entrenador.
- xG por corredor de inicio sólo se compara en secuencias con **cobertura completa de xG de sus remates**, conservando secuencias sin disparo como 0; nunca se considera una atribución causal.
- Un clip es un **ejemplo real**, no una demostración de recurrencia. El resumen declara si la selección tiene menos de 20 secuencias o de tres partidos.
- El motor no altera CTS, ESI, HPS, OC, DS, RPS, DER ni el origen de los eventos StatsBomb.

## Archivos nuevos
- `intelligence/offensive_story.py`: narración descriptiva y claims trazables.
- `visualization/attack_story_figures.py`: figuras individuales grandes y jugadas observadas.
- `tests/test_offensive_story.py`: recuentos, filtros, metadatos, ausencia de valores y figuras.

## Modificados
- `visualization/organized_attack_app.py`: rediseño de la pestaña Ataque Organizado.
- `run_sprint4.py`: creación y exportación del resumen ofensivo.
- `visualization/efos_dashboard.py`: reutilización de datos y acceso a la síntesis en el Informe Ejecutivo y Modelo de Juego.
- `VERSION.txt` y `README.md`.

## Verificación en este entorno
- `python -m pytest -q --ignore=tests/test_defense_story_csv.py --ignore=tests/test_defensive_connected_story.py`: **144 passed**.
- La batería completa no pudo recolectar dos módulos que requieren `streamlit`: el paquete no estaba instalado y la descarga de dependencias no estaba disponible.
- `organized_attack.py` + historia ofensiva sobre **124,353 eventos / 38 partidos**: **2,235 secuencias de juego abierto**, 263 remates observados. Incluye juego abierto sin clasificación y transiciones, no sólo ataque organizado.
- `run_sprint4.py` sobre **un partido real**: ejecutó y generó `offensive_story.json`, `coach_story.json`, `evidence.json`, Markdown y PDF del cuerpo técnico; la historia fue consistente entre las tres salidas.
- No se comprobó visualmente la interfaz Streamlit en un navegador ni se ejecutó el pipeline completo sobre todos los 38 partidos en esta versión.

## Ejecutar en Mac
```bash
python3 -m pip install -r requirements.txt
python3 -m pytest -q
python3 -m streamlit run visualization/efos_dashboard.py
```
La muestra se selecciona desde EFOS → Selección de equipo, y luego → Ataque Organizado.
