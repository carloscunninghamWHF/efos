# EFOS v0.4.11 — Defensa Organizada (primer sprint)

## Qué cambia
La pestaña empieza con lectura en lenguaje de entrenador, después mapa de distribución de acciones y finalmente evidencia desplegable. Se incluye una vista separada de Presiones y Recuperaciones, con conteos explícitos y porcentajes sobre eventos con ubicación.

## Archivos nuevos
- `intelligence/organized_defense_story.py`: zonas por tercio, recuperación, presión, narrativa auditable.
- `visualization/defense_story_maps.py`: mapa editorial de distribución 2D.
- `tests/test_organized_defense_story.py`: pruebas de denominadores, cobertura, muestras, gráfico.

## Archivos modificados
- `run_sprint4.py`: registra `defensive_story`, añade un claim a la evidencia y exporta `defensive_story.json`.
- `visualization/efos_dashboard.py`: rediseño de Defensa Organizada sin borrar el explorador, solo moviéndolo a una sección opcional.

## Limitaciones
- Mapa de acciones no equivale a mapa de posiciones de jugadores ni altura real del bloque.
- No se infiere marcaje zonal/individual, mecanismos colectivos de pressing, compactación o distancia entre líneas sin observaciones 360/tracking adecuadas.
- La frecuencia de recuperación no es por sí sola eficacia. Para un próximo sprint: secuencia rival en posesión, presión→pérdida, pases progresivos permitidos, posición defensiva contextual y consistencia entre partidos.

## Pruebas
`python -m pytest -q tests` — 100 aprobadas localmente (incluidas cinco nuevas).

## Arranque
`python -m streamlit run visualization/efos_dashboard.py`
