# EFOS v0.4.8 — Explorador de acciones sobre el campo

Todo se dibuja con **mplsoccer** (coordenadas StatsBomb 120×80; el equipo analizado ataca hacia la derecha).
Código: `visualization/action_explorer.py` (lógica y dibujo) y `visualization/efos_dashboard.py` (filtros).

## 1. Modelo de Juego y DT · Dibujo base y alineaciones
Campo con el once del dibujo base y selector para **todos los dibujos que usó el entrenador** (de más a menos
frecuente). En cada posición: el jugador más veces titular en ella con ese dibujo, cuántas veces y su alternativa.
El dibujo se reconstruye con las posiciones de los titulares antes del primer cambio.

## 2–4. Ataque organizado · Defensa organizada · Transiciones
Mismos controles en las tres fases:
- **Tipo de análisis**: colectivo (equipo) o individual (jugador).
- **Partido(s)**: uno, varios o todo el torneo (vacío).
- **Acciones**: un campo por acción (flechas para pases, trayectorias para conducciones, puntos con éxito/sin éxito,
  tiros con tamaño = xG y estrella = gol) + tabla con total, por partido y % de éxito.
- **Mapa de calor** suavizado de las acciones seleccionadas, con % por tercio.

| Fase | Acciones |
|---|---|
| Ataque organizado | Pases, pases progresivos, pases al área, conducciones (≥5 m), regates, tiros (juego abierto, sin penaltis) |
| Defensa organizada | Presiones, recuperaciones, intercepciones, duelos, bloqueos, despejes, faltas |
| Transiciones | Pérdidas, contrapresión ≤5 s, recuperación ≤5 s tras perder, recuperaciones, recuperaciones que acaban en tiro, pases/conducciones/tiros ≤15 s tras recuperar (misma posesión) |

**Valor acumulado** (con sus propios filtros de jugador y partido):
- OBV = suma del cambio en la probabilidad de marcar (menos la de recibir) que generan las acciones.
- xG = suma de la probabilidad de gol de los remates.
- Un partido → curva minuto a minuto. Varios / torneo → barras por partido + xG acumulado. Ranking de jugadores en vista colectiva.
- Defensa: OBV de acciones defensivas y xG concedido. Transiciones: OBV y xG en los 15 s tras recuperar; xG concedido tras perder.

## 5. Balón parado
Filtros: a favor / en contra · **tipo** (tiro de esquina, tiro libre directo, indirecto, lateral, lejano, penalti) ·
partido(s) · **ejecutor** · **rematador** (o «solo jugadas con remate»). Campo con trayectoria inicio → fin de cada
ejecución y remates (tamaño = xG, estrella = gol), tablas por tipo, ejecutor y lista de remates con primer receptor.

Clasificación (los datos no dicen si el árbitro señaló falta indirecta):
- Directo: falta lanzada a portería · Penalti: tipo de tiro StatsBomb.
- Indirecto: falta frontal (x ≥ 80, carril central) jugada como pase · Lateral: x ≥ 80 desde los costados (y < 18 o y > 62).
- Lejano: falta en campo rival antes del último tercio (60 ≤ x < 80). Faltas en campo propio no se incluyen.
- Rematador: primer remate del mismo equipo, misma posesión, en los 10 s siguientes.

Tests: `tests/test_action_explorer.py` (77 tests en total).

## 6. Momentos del Partido · momentos clave por partido (v0.4.8.2)
En «Partido por partido» (selector «J01 · vs Rival»): resultado, ESI por tramos y los **momentos más importantes**
en ataque organizado, defensa organizada, transiciones y balón parado, a favor y en contra, con línea de tiempo
(tamaño = xG, estrella = gol) y lista por fase con minuto y protagonista.
- Prioridad: goles (siempre aparecen todos, incluidos autogoles) > xG de la ocasión > valor de la acción (OBV); hasta 3 por fase y lado.
- Cada remate se asigna a una sola fase: balón parado > transición (15 s tras recuperar o perder) > ataque/defensa organizada.
- Balón parado incluye segundas jugadas de córner, falta o saque de banda.
- Validado con los 38 partidos del América: los 61 goles a favor y 44 en contra aparecen exactamente una vez.
