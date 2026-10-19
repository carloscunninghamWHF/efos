# EFOS v0.4.29 — Lectura del Perfil por fase

Debajo de la tabla «Perfil por fase» aparece una lectura para el cuerpo técnico que cambia con los filtros:

- **Temporada completa:** balance, cómo dominó (balón, llegada, peligro), eficacia a favor y en contra, y qué decidir.
- **Un partido:** título con rival, marcador, resultado y dibujo; qué pasó en ese partido y qué revisar en vídeo.
- **Varios partidos (formación o rival):** balance de esa selección y qué cambia frente a su temporada.
- **Estado del marcador:** cuántos partidos se dieron en ese estado y cómo terminaron. No comenta goles, porque cada gol cambia el estado del marcador; usa xG, remates y posesión.

Estructura: **Lo que pasó · Por qué importa · Qué decidir**. Las reglas son descriptivas o condicionales (p. ej. «el resultado no refleja el juego» sólo si la diferencia de xG supera a la de goles en 0.3 o más por partido) y no atribuyen causas ni intenciones. Con menos de 3 partidos se avisa que describe lo ocurrido, no un patrón.

Archivo: `visualization/phase_profile.py` (`phase_reading`, `render_phase_reading`).
