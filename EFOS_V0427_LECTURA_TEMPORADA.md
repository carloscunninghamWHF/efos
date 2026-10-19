# EFOS v0.4.27 — Lectura de temporada para el cuerpo técnico

En «Modelo de Juego y DT» se añaden dos lecturas en lenguaje sencillo, calculadas con los datos de toda la temporada (no son textos fijos: cambian con el equipo y la muestra cargada).

**Bajo el radar · «¿Qué tipo de equipo fue…?»**
- Balance de la temporada (V/E/D y puntos por partido) y las dimensiones que más y menos aparecen.
- *Lo que pasó:* cada dimensión traducida a fútbol (acciones en último tercio, presiones por partido, reacción en 5 s, salida desde atrás, pases de su campo al último tercio).
- *Por qué importa:* interpretación condicionada (p. ej. baja progresión = forma de avanzar, no necesariamente carencia).
- *Según el dibujo:* dibujos con 3 o más partidos, resultados, puntos por partido y en qué cambia su firma.
- *Qué decidir:* prioridades para el cuerpo técnico.

**Bajo las 4 gráficas · «¿Cómo reacciona… al marcador?»**
- Cuánto se juega empatando, ganando y perdiendo.
- Qué cambia de ir perdiendo a ir ganando en posesión, presión, altura de defensa y pase largo, comparado con lo que hacen sus rivales en la misma situación.
- Ventajas no convertidas en victoria (con rivales y marcadores) y partidos rescatados yendo por detrás.
- *Qué decidir:* gestión de la ventaja, reacción cuando pierde, partidos empatados.

Reglas: cada cifra sale de los datos EFOS; las frases son descriptivas o condicionales y nunca atribuyen causas ni intenciones del entrenador. Archivo nuevo: `visualization/coach_season_reading.py`.
