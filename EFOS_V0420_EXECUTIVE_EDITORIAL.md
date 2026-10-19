# EFOS v0.4.20 — Informe Ejecutivo guiado e identidad integrada

## Qué cambió
1. La portada ejecutiva abandona las tres prescripciones tácticas categóricas y presenta tres capítulos: **con balón, sin balón y respuesta tras pérdida**. En cada uno explica un hallazgo, la evidencia/denominador, la lectura para discutir y los límites de inferencia.
2. Cada capítulo enlaza directamente con su módulo de observaciones (Ataque Organizado, Defensa Organizada, Transiciones).
3. Se incorpora una única red de pases a tamaño completo en portada, sobre la misma muestra canónica ofensiva de v0.4.19; no muestra formaciones ni posiciones simultáneas.
4. Modelo de Juego y DT usa la misma narrativa, antes de las alineaciones y del radar CTS. Se conserva la capa avanzada y todo el motor de v0.4.19.
5. Se elimina el nombre fijo de América en un subtítulo de la capa defensiva técnica, de modo que el texto sirva a cualquier equipo.
6. Las reglas previas de «cómo jugarle» siguen accesibles como **hipótesis históricas**, con una advertencia de que no son planes validados. Los PDF anteriores continúan intactos, advertidos como un formato previo.

## Alcance de datos
- `coach_story/executive_narrative.py` es una capa exclusivamente descriptiva; usa `offensive_story`, `defensive_open_play_possessions` y `transitions` del mismo `result`.
- **No modifica** los eventos, el motor de ingestión/normalización, ESI, CTS, HPS, RPS, OC, DS, DER, figuras de ataque v0.4.19 ni las segmentaciones defensivas.
- Ausencia de cobertura produce la indicación «no evaluable» y nunca genera valores simulados.
- La categoría «tras pérdida» es un enfoque temporal que puede solaparse con secuencias del módulo «sin balón»; no se deben sumar sus denominadores como particiones excluyentes.
- El workbench de importación flexible conserva la funcionalidad anterior: carga CSV de terceros y habilita análisis según columnas; no equivale todavía a pipeline ejecutivo completo para todo proveedor.

## Pruebas
- 147 pruebas superadas con `python3 -m pytest -q --ignore=tests/test_defense_story_csv.py --ignore=tests/test_defensive_connected_story.py`.
- La batería completa requiere `streamlit`, ausente en el entorno de pruebas. No se validó render visual en navegador ni exportación PDF con datos nuevos en esta revisión.

## Arranque Mac (sin entorno virtual)
```bash
cd efos
python3 -m pip install -r requirements.txt
python3 -m streamlit run visualization/efos_dashboard.py
```

## Prioridad posterior
- Validación visual responsive en el navegador, versiones del PDF alineadas con esta narrativa y filtros globales compartidos entre todos los módulos.
- Preparación de carga genérica de datos a través del pipeline completo, con gates de capacidades y sin inferir cobertura ausente.
- Revisión de licencias y privacidad antes de subir datasets reales y `auth/users.txt` a repositorios públicos.
