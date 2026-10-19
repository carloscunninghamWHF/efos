# EFOS v0.4.31 — Persistencia Supabase (actualización de infraestructura)

**Primero lee [`EFOS_V0431_PERSISTENCIA_SUPABASE.md`](EFOS_V0431_PERSISTENCIA_SUPABASE.md)** para vincular Supabase Auth, preparar snapshots tácticos desde el Mac y desplegar esta versión en una rama de GitHub. La versión antigua en `main` no debe sobreescribir el código actualizado. Los CSV originales se conservan en Supabase Storage y no se incluyen en este paquete de código.

---

# EFOS v0.4.31 — navegación fija y Supabase

**NUEVO:** ver [`EFOS_V0431_SUPABASE_Y_NAVEGACION.md`](EFOS_V0431_SUPABASE_Y_NAVEGACION.md) para configurar Supabase Auth, vista del catálogo, acceso RLS y Storage privado. No se utilizan claves administrativas en Streamlit.

# EFOS v0.4.30 — Inteligencia táctica esencial

Seis secciones principales, filtro global rival/partido, diagnóstico editorial verificable, acceso oscuro y PDF de la muestra activa. **Consulta [EFOS_V0430_INTELIGENCIA_TACTICA_ESENCIAL.md](EFOS_V0430_INTELIGENCIA_TACTICA_ESENCIAL.md) para cambios, limitaciones y pruebas.**

# Parche v0.4.29 · Lectura del Perfil por fase

Descripción para el cuerpo técnico de la temporada, de cada partido y de cada selección (formación, rival, marcador). Ver `EFOS_V0429_LECTURA_PERFIL.md`.

# Parche v0.4.28 · Perfil por fase

Tabla de 24 métricas StatsBomb (ofensiva, organizativa, defensiva) frente a la media de sus rivales, filtrable por formación, rival y marcador. Ver `EFOS_V0428_PERFIL_POR_FASE.md`.

# Parche v0.4.27 · Lectura de temporada para el cuerpo técnico

Bajo el radar y bajo las gráficas del marcador en «Modelo de Juego y DT»: qué pasó, por qué importa y qué decidir, calculado con los datos de la temporada. Ver `EFOS_V0427_LECTURA_TEMPORADA.md`.

# Parche v0.4.26 · Modelo de Juego y DT por formación

Partidos por formación, radar CTS (temporada vs formación/partido) y reacción al marcador filtrada por formación, rival y estado. Ver `EFOS_V0426_MODELO_JUEGO_POR_FORMACION.md`.

# Parche v0.4.25 · «Cómo ataca» y «Cómo defiende» por preguntas

Los módulos «Cómo ataca» y «Cómo defiende» se navegan con cinco botones cada uno; cada pregunta muestra su respuesta, mapas y evidencia. Ver `EFOS_V0425_PREGUNTAS_ATAQUE_DEFENSA.md`.

# EFOS v0.4.24 — Diagnóstico Táctico Conectado

Esta versión conecta las evidencias de ataque, defensa y pérdidas verificadas para construir una identidad de juego, un diagnóstico por pregunta futbolística, gráficos con contexto y preguntas de decisión para el entrenador. El razonamiento solo utiliza resultados calculados a partir de la muestra cargada de StatsBomb: no atribuye intenciones ni calcula posiciones no observadas. Las referencias conceptuales externas no aparecen en la interfaz ni en los informes.

**Iniciar:** desde la carpeta `efos`, ejecutar `python3 -m streamlit run visualization/efos_dashboard.py`; entrar, cargar el CSV nativo, elegir equipo y partidos, y abrir «Informe Ejecutivo». Consulta [`EFOS_V0424_DIAGNOSTICO_CONECTADO.md`](EFOS_V0424_DIAGNOSTICO_CONECTADO.md) para las definiciones, cambios, cobertura y pruebas.

---

# Parche v0.4.22 · Importación StatsBomb automática

**Corregida la carga de CSV de StatsBomb:** ya no es necesario mapear las 254 columnas manualmente. Se seleccionan equipo y partidos y se abre el pipeline EFOS completo; los datos auxiliares de remates y alineaciones quedan trazables sin inventar StatsBomb 360. Ver `EFOS_IMPORTACION_STATSBOMB_AUTOMATICA.md` para instrucciones y limitaciones.

# EFOS v0.4.22 — Storytelling táctico conectado

La mejora editorial integra secuencias verificables en Informe Ejecutivo, armado de juego y conexiones principales en Ataque, análisis explicativo por situación y filtros equipo base → rival → partido en Defensa, y animación opcional basada en fotografías StatsBomb 360. **Revisa alcance y límites en `EFOS_V0422_STORYTELLING_TACTICO.md`.**

# EFOS v0.4.20 — Informe Ejecutivo narrativo e identidad integrada

Ver `EFOS_V0420_EXECUTIVE_EDITORIAL.md`. El Informe Ejecutivo y Modelo de Juego ahora comparten los capítulos con balón, sin balón y tras pérdida, con evidencia, cobertura y enlaces a los módulos. No cambian los motores de datos ni el módulo editorial ofensivo v0.4.19.

# Actualización v0.4.18 — Capa conceptual

Textos contextuales y preguntas tácticas en ataque, defensa y Coach Story. Ver `CAPA_CONCEPTUAL_V0418.md`.

# Actualización v0.4.17 — Ataque premium

Módulo integrado: ocho gráficas con datos reales, filtros, hallazgos y evidencia por secuencia. Instrucciones y metodología: `ATAQUE_PREMIUM_V0417.md`. Vista real autónoma: `docs/ataque_atlas_real.html`.

# Actualización v0.4.15 · Recuperación y vulnerabilidad

Sin balón incorpora contrapresión etiquetada, primer control posterior confirmado, entradas rivales al último tercio y patrones auditables. Consulta `DEFENSA_RECUPERACION_V0415.md`.

# Actualización v0.4.14 · Defensa explicada y conectada

La sección **Sin balón** incorpora tres pasos: entender situaciones, conectar tiempo/jugadores/jugadas y análisis integral. Consulta `DEFENSA_CONECTADA_V0414.md` para el alcance de filtros y validación.

# EFOS v0.4.10 — Premium Set Piece Story

**Nueva pestaña de Balón Parado:** narrativa orientada al entrenador, mapas comparativos izquierda/derecha, patrón más repetido vs mayor xG cubierto, secuencias observadas, vista espacial 3D ilustrativa opcional y evidencia P0→P1→P2 plegable. La información completa está en [`EFOS_V0410_PREMIUM_SET_PIECE_STORY.md`](EFOS_V0410_PREMIUM_SET_PIECE_STORY.md).

**La vista 3D no es tracking ni una curva de vuelo medida.**

# EFOS v0.4.8 — Explorador de acciones sobre el campo

Alineaciones por dibujo en «Modelo de Juego y DT»; en Ataque, Defensa y Transiciones, un campo mplsoccer por
acción, mapa de calor y valor acumulado (OBV/xG) con filtros colectivo/individual y por partido; balón parado
con filtros de tipo, ejecutor y rematador y trayectorias. Ver `EFOS_V048_EXPLORADOR.md`. 77 tests.

---

# EFOS v0.4.6 — Informe para cuerpo técnico

**Novedad:** EFOS habla el idioma del fútbol. El entregable principal es `informe_cuerpo_tecnico.pdf`,
organizado por momentos del juego, con datos en unidades de fútbol comparados con los rivales, jugadas
sugeridas para vídeo, el once medio y conclusiones accionables. El portal se reorganizó igual.
Ver `INFORME_CUERPO_TECNICO.md`. 70 tests automatizados.

---

# EFOS v0.4.5 — Visual Coach Story PDF

**Estado actual:** portal autenticado + carga multi-CSV + Coach Story evidence-first + marco táctico derivado de video.

Novedades v0.4.5:

- `coach_story.pdf`: reporte ejecutivo visual generado automáticamente por cada análisis.
- Vista previa PDF embebida en la pestaña Coach Story del portal.
- Descarga PDF como entregable principal; `.md` queda como anexo metodológico.
- El PDF resume identidad, sin balón, con balón, momentos, CTS, principios, evidencia y límites.

Base táctica heredada de v0.4.4:
- `coach_story/tactical_framework.py`: perfil defensivo, Fishing, liberación bajo presión, half-spaces, tercer hombre A→B→C, intervalos, Aliup proxy, xG/OBV y foco semanal.
- Observación y proxy se separan explícitamente; no se atribuye intención del entrenador sin evidencia.
- `run_sprint4.py` exporta `tactical_framework.json`.
- El dashboard traduce estas señales en **Resumen / Con balón / Sin balón / Evidencia**.
- 58 tests automatizados.

Ver `TACTICAL_FRAMEWORK_COACH_STORY.md` para definiciones y caveats.

---

# EFOS v0.3.1 — Correr con los datos reales de StatsBomb (América 2025-26)

## Inicio rápido (terminal de VS Code)

Desde la carpeta `efos/`:

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate      Mac/Linux:  source .venv/bin/activate
pip install pandas numpy pydantic PyYAML pytest
python -m pytest tests -q          # 35 tests
python run_real.py                 # 38 partidos, ~1 minuto
```

`run_real.py` lee los CSV de `data/raw/statsbomb/`, los une, los normaliza y
corre Sprint 3 completo. Los resultados quedan en `data/processed/sprint3_real/`.
Opciones: `--team "América"` (nombre exacto como aparece en los datos),
`--expected-matches 38`, `--inputs ruta/*.csv`, `--out carpeta`.

Solo preparar el CSV normalizado: `python prepare_statsbomb.py`.
`requirements.txt` incluye librerías de sprints futuros (shap, streamlit...);
para correr lo actual basta con la línea de `pip install` de arriba.

## Cambios v0.3.1

- Nuevo `ingestion/statsbomb_wide_csv.py`: lee el CSV ancho de StatsBomb (254 columnas),
  une p1 + p2, elimina las filas repetidas por freeze frame y conserva xG, OBV,
  probabilidad de pase, control_degree, outcome_name, period, etc.
- Tiempo por partido construido con `period`: el añadido del 1T ya no se mezcla con el 2T.
- El marcador cuenta autogoles (`Own Goal For`).
- El cambio de periodo ya no cuenta como transición.
- ESI por marcador usa solo las transiciones de ese marcador; las ventanas de 15 min
  usan solo las transiciones de esa ventana.
- Si el equipo no existe en los datos, el programa se detiene y lista los equipos disponibles.
- Nuevos tests en `tests/test_statsbomb_real.py`.

Pendiente (no se tocó en esta versión): la definición de OC, DS y LAP, los umbrales DTC
escritos en `intelligence/dtc.py` (distintos de `config/thresholds.yaml`) y los pesos del ESI
escritos en `metrics/esi.py` en vez de leerse de `config/weights.yaml`.

---

# EFOS Prototype v0.2 — Football Behavioral Intelligence Engine

> PIP captura y organiza la realidad del fútbol. EFOS interpreta su complejidad.

Prototipo modular que transforma eventos de fútbol (StatsBomb, StatsBomb 360,
PIP One) en una narrativa táctica interpretable, pasando por un pipeline de
motores matemáticos (ESI, estados del sistema, transiciones, patrones,
explicabilidad y "coach story").

**Estado actual: Sprint 2 — Integridad + Contexto + Posesiones + Secuencias + Transiciones + baseline táctico.**

## Instalación

```bash
pip install -r requirements.txt
```

## Uso — Sprint 1

```bash
# Modo demo: genera datos sintéticos y corre el pipeline completo
python main.py --demo

# Modo real (StatsBomb JSON): usa tus propios archivos StatsBomb / PIP One
python main.py --data ruta/a/carpeta
# Busca automáticamente: events.json, frames_360.json (opcional), pip_one.json (opcional)

# Modo CSV: usa un archivo plano (una fila = un evento)
python main.py --csv ruta/a/carpeta
# Busca automáticamente: events.csv (requerido), pip_one.csv (opcional)
# 360 no tiene formato CSV estándar en este prototipo -> reporta "360 available: NO"
```

## Formato CSV de eventos (`events.csv`)

Columnas mínimas requeridas: `team`, `event_type`. El resto es opcional y se
propaga como valor faltante si no está presente (nunca se inventa un dato).

| Columna            | Descripción                                   |
|--------------------|------------------------------------------------|
| match_id           | ID del partido (si falta, se usa el nombre de archivo) |
| event_id, index    | Identificador y orden del evento                |
| possession, possession_team | Fase de posesión                      |
| team, player       | Equipo y jugador (team es obligatorio)          |
| minute, second     | Minuto y segundo del evento                     |
| event_type         | Tipo de evento (Pass, Carry, Shot, ...)         |
| x, y               | Coordenadas en el sistema StatsBomb (120x80)    |
| pass_outcome, shot_outcome, duel_outcome | Resultado del evento, si aplica |
| under_pressure, duration | Presión defensiva y duración del evento   |

Nombres alternativos como `type`, `loc_x`/`loc_y`, `team_name`, `player_name`
se reconocen automáticamente (ver `COLUMN_ALIASES` en `ingestion/csv_events.py`).

`pip_one.csv` usa las mismas columnas que el JSON de PIP One: `match_id,
timestamp, team, player, event_type, zone, target_player, context,
confidence, analyst_id`.

Un ejemplo funcional de ambos archivos está en `data/raw/csv_demo/`.

## Tests

```bash
pytest tests/ -v
```

## Principio de diseño

Todas las fórmulas de EFOS (pesos, umbrales, ventanas temporales) son
**hipótesis matemáticas v0.1**, no verdades científicas validadas. Viven en
`config/*.yaml`, nunca hardcodeadas en el código de los motores, para que un
investigador deportivo sin experiencia en programación pueda ajustarlas.

## Estructura del proyecto

Ver la especificación completa en el documento de diseño. Sprint 1
implementa: `data/`, `ingestion/`, `normalization/`, `config/`, `tests/`,
`main.py`. El resto de carpetas (`behavior/`, `context/`, `esi/`, `states/`,
`transitions/`, `ml/`, `explainability/`, `coach_story/`, `visualization/`)
están creadas como esqueleto (`__init__.py`) a la espera de los siguientes
sprints, según el orden de desarrollo definido (sección 32).

## Limitaciones conocidas de Sprint 1

- No se implementan aún motores de comportamiento, ESI, estados, transiciones,
  clustering, SHAP ni coach story (Sprints 2–14).
- `normalization/players.py` hace limpieza básica de nombres; no resuelve
  identidad cruzada entre fuentes.
- El merge PIP One usa coincidencia por `match_id + team + player` dentro de
  una tolerancia temporal configurable; no desambigua dos eventos manuales
  simultáneos del mismo jugador.
- Los datos sintéticos son estructuralmente válidos pero no calibrados contra
  distribuciones reales de un partido.

## Siguiente sprint

**Sprint 2 — Posesión + secuencias comportamentales**, sobre el dataset
normalizado que produce este Sprint 1.


## Sprint 2 (v0.2)

Implementado:
- Gate de integridad y desduplicación por `match_id + event_id`.
- Validación de coordenadas 120x80 y número esperado de partidos.
- Reconstrucción de score state relativo al equipo focal.
- Objetos de posesión, fases espaciales y ventanas N-5..N-1.
- Transiciones con delta temporal real (no `duration <= 5`).
- Resumen táctico MECE inicial y CTS baseline transparente.
- Nuevos tests automatizados en `tests/test_sprint2.py`.

Pendiente para v0.3: ingesta directa del CSV ancho de 254 columnas preservando OBV/xG/probabilidades, ESI completo, DTC, LAP, set pieces P0/P1, CatBoost/SHAP y Coach Story final.

## Sprint 3 — Intelligence Engine
Adds auditable baseline implementations for OC/HPS/RPS/DS/DER, ESI overall and by score context, 15-minute match windows, DTC states/transitions, LAP, and evidence-first Coach Story principle candidates. These scores remain methodological baselines until calibrated on the official 38-match dataset. No example percentage is promoted to a finding before the real run.

Run:
`python run_sprint3.py --events <normalized.csv> --team "Club América" --expected-matches 38 --out data/processed/sprint3`

---

## EFOS v0.4 — Pressure & Constraint Engine (Sprint 4)

This version completes roadmap points 1–7:

1. Removes ESI/DTC hardcoded weights and thresholds in favor of `/config`.
2. Preserves StatsBomb Defensive Responsibility aggregate fields and provides a long-form DefR extractor.
3. Adds `intelligence/pressure_context.py` with PCI EVENT proxies.
4. Adds `metrics/hps.py` (HPS v2), separating external pressure context from team stability response.
5. Adds `intelligence/trap_detection.py` and DTE / Trap Rate.
6. Expands Coach Story and CTS with pressure resistance, direct pressure, touchline funnel, lane denial (when 360 exists), and trap efficiency.
7. Adds a 360 interface: snapshot lane closure is computed only where valid 360 frames exist. `tti` and `reachability` remain null until tracking data exists.

### Run Sprint 4

```bash
python run_sprint4.py --events data/processed/events_normalized.csv --team "Club América" --expected-matches 38 --out data/processed/sprint4
```

Optional StatsBomb 360 file:

```bash
python run_sprint4.py --events data/processed/events_normalized.csv --team "Club América" --360 path/to/frames_360.json --out data/processed/sprint4
```

### Methodological guardrail

`EVENT_PROXY` and `360_SNAPSHOT` are explicit source labels. EFOS v0.4 does **not** infer player velocity, orientation or Time-to-Intercept from event snapshots. Those fields remain null until tracking/EVI is connected.

## Team-agnostic execution (v0.4 Sprint 4)

EFOS no está ligado a América ni a 38 partidos. Consulte `GENERIC_INPUT_OUTPUT_CONTRACT.md`.

```bash
# Dataset centrado en un club: detección automática
python run_sprint4.py --events my_team.csv --team auto --out outputs/my_team

# Selección explícita
python run_sprint4.py --events dataset.csv --team "Tigres UANL" --out outputs/tigres

# Mismo pipeline para todos los equipos de un dataset
python run_sprint4.py --events league.csv --all-teams --min-matches 5 --out outputs/league
```

`--expected-matches` es únicamente un gate opcional de validación. Si se omite, EFOS utiliza los partidos disponibles y no presupone una temporada de 38 encuentros.

## Portal v0.4.3 — Multi-CSV + Enterprise Coach UI

El portal autenticado permite cargar múltiples CSV en una sola sesión. Todos los archivos se normalizan y consolidan antes de ejecutar EFOS, por lo que el resultado es un único análisis/Coach Story del dataset combinado.

```bash
python -m streamlit run visualization/efos_dashboard.py
```

La navegación se movió a la cabecera y prioriza lenguaje de entrenador: Resumen, Identidad, Presión, Con balón, Sin balón, Momentos clave, Jugadores, Evidencia y Método. La barra lateral ya no se utiliza.


## v0.4.13 — Atlas narrativo de defensa sin balón

Integración del prototipo Smart Defensive v0.4.13 del usuario: tres situaciones de **juego abierto**, atlas comparativo y secuencias observadas. Reutiliza los eventos normalizados y conserva v0.4.12 para defensa ante balón parado. Consulta `DEFENSIVE_OPEN_PLAY_ATLAS_V0413.md`.

`python -m streamlit run visualization/efos_dashboard.py`


## EFOS v0.4.19 — Ataque Organizado y Coach Story editorial

La lectura principal sigue la cadena **inicio → conexión → progresión → resultado**, sobre secuencias verificables. Los filtros de partido utilizan rival y ordinal interno (no jornada inferida); las tablas y los atlas originales se conservan en análisis avanzado. El mismo motor de historia aporta evidencia al Coach Story y al informe técnico. Ver `EFOS_V0419_EDITORIAL_ATTACK_STORY.md` para metodología y límites.
