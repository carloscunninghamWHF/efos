# EFOS v0.4.7 — Football Native UX

## Navegación (8 features)
1. Selección de Equipo
2. Informe Ejecutivo
3. Modelo de Juego y DT
4. Ataque Organizado
5. Defensa Organizada
6. Transiciones
7. Balón Parado
8. Momentos del Partido

## Selección automática
La aplicación escanea `data/raw/statsbomb/` y construye el flujo:

`Liga -> Temporada -> Equipo -> Periodo`

No hay carga manual de CSV en la interfaz principal. Para añadir nueva información basta incorporar los archivos al repositorio siguiendo la convención de nombres; el equipo focal se infiere por cobertura de `match_id`, no por el nombre del archivo.

## Metadatos del DT
`config/team_metadata.yaml` contiene metadatos editoriales (por ejemplo, nombre del DT). Estos datos no afectan las fórmulas EFOS. Si no existe un DT documentado, la UI muestra “DT no informado en catálogo”; nunca lo infiere a partir del estilo.

## Similitud Liga MX
Solo se muestran similitudes cuando existen al menos dos perfiles CTS calculados con el mismo motor y guardados en `data/processed/league_profiles/`. No se muestran porcentajes simulados ni arquetipos europeos.

## Visualizaciones
- CTS radar: Construcción, Progresión, Ataque, Defensa, Transición, Adaptación.
- Ataque: mapa de acciones por zonas + OBV por partido.
- Defensa: presión seguida de recuperación ≤5s, recuperaciones y vulnerabilidad OBV rival.
- Transiciones: counterpress y recuperaciones que terminan en tiro ≤15s.
- Balón parado: entregas hacia dentro/fuera cuando StatsBomb las etiqueta y mapas de remate/xG.
- Momentos: ESI por ventanas de 15 minutos con explicación in-situ.

## Guardrails metodológicos
- Altura de intervención ≠ posición exacta de línea defensiva.
- Offside rival ≠ prueba de trampa deliberada.
- DTE sigue marcado como experimental.
- Marcaje zonal/personal y primer contacto exacto no se infieren sin 360/tracking o etiquetado de vídeo.
- Similitud técnica se calcula solo con perfiles reales disponibles.
