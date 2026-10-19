# EFOS v0.4.25 — «Cómo ataca» y «Cómo defiende» por preguntas

El módulo «Cómo ataca» deja de ser una página larga y se navega con cinco botones. Cada uno abre una pregunta futbolística con su respuesta, sus mapas y su evidencia:

| Botón | Pregunta | Contenido |
|---|---|---|
| 01 · Defensa → ataque | ¿Qué hace al recuperar el balón? | Capítulo de transición ofensiva (recuperaciones, remate en ≤15 s, mapa) |
| 02 · Origen y construcción | ¿Cómo construye sus posesiones? | Respuesta EFOS (origen y productividad), tarjetas, gráfico por corredor |
| 03 · Conexiones | ¿Quiénes sostienen su juego? | Respuesta EFOS (conexiones), top 5 conexiones, red de pases, explorador |
| 04 · Progresión | ¿Cómo progresa el ataque? | Secuencia representativa y rutas por zona |
| 05 · Desenlace | ¿Dónde termina y qué consigue? | Respuesta EFOS (llegada al área), mapa de remates / entradas al área |

- La respuesta del diagnóstico conectado (`interpretation/tactical_reasoning.py`) aparece dentro de la pregunta que le corresponde, en lugar de mostrarse toda junta arriba.
- Filtros de muestra, «Análisis avanzado» y «Evidencia y metodología» siguen siendo comunes a todas las preguntas.
- Botones anterior / siguiente al pie de cada pregunta.
- No cambian los cálculos ni las métricas: solo la presentación. Solo se calcula la pregunta abierta, así que la página carga más rápido.

Archivos: `visualization/organized_attack_app.py`, `visualization/reasoning_ui.py` (`render_answer`, `render_lane_chart`), `visualization/efos_dashboard.py` (`_on_ball_page`).

---

## «Cómo defiende» por preguntas

Mismo sistema de botones, con cinco preguntas:

| Botón | Pregunta | Contenido |
|---|---|---|
| 01 · Tras la pérdida | ¿Qué hace al perder el balón? | Respuesta EFOS (reacción tras pérdida), presión ≤5 s, recuperación, remate rival ≤15 s, mapa |
| 02 · Situaciones rivales | ¿Cómo le atacan y cuándo le rematan? | Respuesta EFOS (situaciones de amenaza), gráfico de remate por escenario, mapa de cada situación, presión tras pérdida |
| 03 · Momentos y protagonistas | ¿Cuándo sufre y quién interviene? | Resumen de la situación filtrada, evolución por tramo, red de intervenciones |
| 04 · Jugada a jugada | ¿Cómo se ve en una posesión concreta? | Selector de posesión (primero las que acaban en remate rival), secuencia, cronología, 360 si existe |
| 05 · Para el cuerpo técnico | ¿Qué debe revisar y entrenar? | Informe integral: qué ocurrió, cuándo y con quién, qué contrastar, qué entrenar, qué falta |

- Equipo base, rival, partido, situación, tramo y marcador están en «Muestra y filtros».
- «Evidencia verificable» y «Archivo complementario» siguen al pie.
- Los botones son un componente común (`visualization/question_nav.py`) que usan ambos módulos.
- `render_defensive_module` (vista con pestañas) se conserva para compatibilidad; la página usa `render_defense_questions`.
