# EFOS v0.4.28 — Perfil por fase

En «Modelo de Juego y DT», la tabla **Perfil por fase** sustituye a las cuatro gráficas lineales del marcador (que siguen disponibles en un desplegable debajo de la lectura de temporada).

- **24 métricas** en tres bloques: Ofensiva (8), Organizativa (8) y Defensiva (8).
- **Comparación:** el equipo frente a la media de sus rivales en los mismos partidos. El CSV sólo trae partidos del equipo analizado, por eso no es la media de la liga.
- **Filtros:** formación (dibujo inicial), rival y estado del marcador (todo el partido, perdiendo, empatando, ganando).
- **Colores:** verde = mejor que sus rivales; rojo = peor; gris = similar (diferencia menor al 10 %, o a 3 puntos en porcentajes). En goles, xG y remates recibidos, menos es mejor. La longitud de pase no se colorea. La raya negra marca la media de los rivales.

## Sin métricas nuevas
Todas son campos o conteos directos de StatsBomb (goles, xG, remates, pases clave, centros, córners, pases y su acierto, intercepciones, duelos, duelos aéreos), zonas fijas del campo (área rival, último tercio, campo rival) o definiciones que EFOS ya tenía (posesión = proporción de pases; pase largo ≥ 32). Las definiciones se pueden consultar dentro de la app.

Para el % de duelos aéreos ganados, el cargador StatsBomb conserva ahora el campo `aerial_won` del CSV original (antes se descartaba). No cambia ningún otro cálculo.

Verificado: los valores coinciden con un recuento independiente de los eventos (p. ej. América 1.61 goles, 14.82 remates, 527 pases por partido y 56.3 % de posesión en la temporada).

Archivos: `visualization/phase_profile.py` (nuevo), `ingestion/statsbomb_wide_csv.py` (campo `aerial_won`), `visualization/efos_dashboard.py`, `tests/test_coach_formation_v0426.py`.
