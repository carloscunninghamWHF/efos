# EFOS v0.4.26 — Modelo de Juego y DT por formación, rival y partido

## Qué cambia

1. **Partidos por formación.** Al elegir un dibujo en «Dibujo base y alineaciones», junto al campo aparece la lista de partidos en que el equipo inició con ese dibujo: número de partido, rival, marcador registrado y resultado (con el balance V/E/D).
2. **Radar «Firma Táctica del Entrenador (CTS)»** (cinco dimensiones: construcción, progresión, ataque, defensa y transición; Adaptación retirada del radar). Botones de formación + lista de partidos. Se superponen:
   - **Temporada completa** (azul, discontinua).
   - **Selección** (dorado): todos los partidos con esa formación, o un partido concreto.
   Debajo: frase con lo que sube y baja (±5 puntos o más) y tabla Temporada / Selección / Diferencia.
3. **«Cómo cambia el equipo según el marcador».** Filtros de formación, rival (sólo los enfrentados con esa formación) y estado del marcador (Perdiendo, Empatando, Ganando). Cada panel muestra la selección (dorado), la temporada completa del equipo (azul) y a los rivales en la misma situación dentro de la selección (gris).

## Cómo se calcula

- Mismo motor que la temporada, restringido a los partidos elegidos: `tactical_summary`, `compute_cts`, `compute_adaptation_score` y `by_segment`. Con todos los partidos se reproduce exactamente la cifra de temporada (verificado en `tests/test_coach_formation_v0426.py`).
- Formación = dibujo inicial (titulares antes del primer cambio), igual que la sección de alineaciones.
- **Sin datos inventados:** si una dimensión del radar no tiene oportunidades observables (p. ej. Transición sin pérdidas registradas), se rotula «sin dato» y no se dibuja; si el equipo nunca estuvo en un estado del marcador, ese punto no aparece. Con menos de 300 eventos del equipo en un estado, el punto se dibuja vacío (muestra baja).

Archivos: `visualization/coach_formation_ui.py` (nuevo), `visualization/efos_dashboard.py` (`_lineup_section`, `_coach_page`), `tests/test_coach_formation_v0426.py`.
