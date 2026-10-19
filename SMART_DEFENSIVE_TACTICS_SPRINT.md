# EFOS Smart Defensive Tactics — Sprint v0.4.12

## Pregunta táctica

**¿Cómo responde el equipo a diferentes tipos de posesión del rival, quién interviene y qué resultados defensivos se observan?**

Smart Tactics **NO** es una alineación fija, un algoritmo que identifique marcaje hombre/zona ni una simulación de intención del entrenador. Es una lectura situacional del comportamiento **observado** mediante StatsBomb Events. El análisis del Club América (38 partidos, 124,353 eventos) es reproducible con el archivo `data/processed/america_events.csv`.

## Taxonomía de situación (prioridad excluyente)

1. Balón parado rival: **córner, tiro libre, saque lateral**, con `play_pattern_name` o saque de tipo inequívoco.
2. **Contraataque etiquetado**: únicamente la etiqueta `From Counter`. No se inventan contraataques usando una ventana temporal.
3. **Tras recuperación rival**: recuperación o intercepción explícita al principio de la posesión; esto **no** demuestra un contragolpe.
4. **Ataque posicional / otros**: categoría residual que incluye posesiones con información insuficiente para determinar un patrón más específico. No equivale a una verificación de ataque posicional táctico.

La unidad es una posesión rival con dueño explícito `possession_team`, identificada por `match_id + period + possession`. El equipo focal debe estar en el partido. Se excluyen posesiones de dueño contradictorio o sin acciones ofensivas elegibles. No todas las 124,353 filas son posesiones; el motor encontró 3,639 posesiones rivales para la muestra oficial.

## Outputs

| Archivo | Contenido |
|---|---|
| `smart_defense_possessions.csv` | Una fila por posesión rival: partido, minuto, tipo de situación, origen de clasificación, presión, progresión al último tercio/área, remates, xG, marcador y límites. |
| `smart_defense_players.csv` | Cada intervención individual etiquetada durante una posesión rival, con jugador, acción, partido y ubicación. |
| `smart_defense_summary.json` | Comparaciones contextuales y nombres de jugadores más implicados, muestras y cobertura del xG. |
| `evidence.json`, `coach_story.json`, PDF | Hallazgos contextualizados cuando hay muestra; no se afirma causalidad. |

## Pantalla Streamlit

**Defensa Organizada → Smart Defensive Tactics**:
- Selector: situación rival (6 categorías), tramo de partido, marcador.
- Hallazgo narrativo: intervención predominante, zona de concentración, mínimo de partidos.
- Tres apoyos numéricos: presiones por 100 posesiones rivales, porcentaje de posesiones que terminan en remate, xG concedido por posesión con dato válido.
- Dos campos editorial: intervenciones del equipo y remates rivales (alineados a portería propia).
- Jugadores con más acciones observadas en ese contexto; se identifica el tipo de acción más repetido, número de eventos y partidos.
- Evidencia individual y desglose temporal ocultos por defecto.
- Balón Parado sigue mostrando los destinos de envíos; Defensa Organizada muestra **cómo responde** el equipo ante ellos.

### Interpretación responsable

- Un `Pressure` es **una acción de presión registrada**, no un sistema defensivo completo. Más presiones no significan automáticamente mejor defensa.
- Un despeje, duelo o intercepción registrados no prueban por sí mismos que la presión causó la pérdida del rival.
- Los jugadores se ordenan por **volumen de eventos defensivos registrados durante posesiones rivales**. No por calidad, desempeño per 90 ni distancia recorrida. La intervención que recae en una posesión ya cambiada puede no entrar al ranking.
- `post_recovery_5s` significa una recuperación observada cerca del final de la última acción rival; **no** prueba una recuperación causada por la defensa ni la finalización exacta de la posesión.
- La ausencia de remates o de penetración no prueba intervención exitosa.
- El `score_state` reconstruido refleja marcador relativo al equipo focal (con límites en instantes de gol).
- Las coordenadas (120×80) son eventos normalizados, no posiciones continuas de los 22 jugadores. Los remates del rival se reflejan visualmente respecto a la portería del equipo focal, no se altera el dato analítico.
- Para verificar **defensa zonal, hombre a hombre, altura real del bloque, coberturas y rotación colectiva**, se requieren posiciones simultáneas suficientes de StatsBomb 360, video anotado o tracking; eso NO está implementado en esta versión.
- Los umbrales de muestra y de espacio se configuran en `config/thresholds.yaml`, sección `smart_defensive_tactics`.
- La respuesta por `From Counter` puede subestimar contragolpes reales que StatsBomb no haya etiquetado.

## Hallazgos de la muestra (descriptivos, no causalidad)

Para `data/processed/america_events.csv`, ejecución directa del motor (38 partidos, 124,353 eventos):

| Situación | Posesiones rivales | Con remate | Presiones por 100 posesiones | Mayor participante registrado |
|---|---:|---:|---:|---|
| Ataque posicional / otros | 1,296 | 7.0% | 146.8 | Alejandro Zendejas (202 acciones) |
| Contraataque etiquetado | 48 | 16.7% | 83.3 | Israel Reyes (8 acciones) |
| Tras recuperación rival | 1,049 | 8.6% | 151.1 | Cristian Borja (167 acciones) |
| Córner rival | 131 | 41.2% | 57.3 | Israel Reyes (18 acciones) |
| Tiro libre rival | 435 | 14.9% | 133.6 | Cristian Borja (62 acciones) |
| Saque lateral rival | 680 | 6.6% | 148.8 | Cristian Borja (115 acciones) |

Estas tasas son **por posesión rival**, no las mismas ventanas de 10 segundos utilizadas por el motor P0–P1–P2 de córners. Por eso no deben compararse directamente con la tasa de remate de esa otra pestaña. No extrapolar el rango de jugadores a "mejor defensor"; la muestra de contragolpes explícitos es especialmente pequeña.

## Validación

- 107 pruebas automatizadas del repositorio pasadas durante la preparación de este Sprint, incluidas 7 nuevas del módulo Smart Defense.
- Motor ejecutado directamente sobre 38 partidos y 124,353 eventos StatsBomb.
- Pipeline completo `run_sprint4.py` ejecutado con **un partido real** y exportaciones `smart_defense_*.csv/.json`, Coach Story y PDF creados correctamente.
- **Aún no** se verificó el flujo visual de Streamlit en Mac ni se reejecutó el pipeline **completo** de 38 partidos con todos los motores simultáneos. Validador 360 espacial específico tampoco se realizó.

## Ejecución

```bash
python3 -m pip install -r requirements.txt
python3 -m pytest -q
python3 -m streamlit run visualization/efos_dashboard.py
```

Para exportar evidencias sin abrir la interfaz:

```bash
python3 run_sprint4.py --events data/processed/america_events.csv --team "América" --out data/processed/smart_defense_run
```

## Siguiente fase, NO implementada

Validar las estructuras defensivas sin balón mediante secuencias espaciotemporales de 360, comparaciones entre rivales y etiquetado video. Ningún marcador de "zonal", "hombre a hombre", "repliegue" o "bloque compacto" debe activarse sin observar simultáneamente la disposición y los movimientos del equipo.
