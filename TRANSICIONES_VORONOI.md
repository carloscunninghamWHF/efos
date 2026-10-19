# EFOS v0.4.15 — Transiciones con StatsBomb 360 · 10 mapas de Voronoi

Cuando existe la carpeta de StatsBomb 360 junto a los CSV (`data/raw/statsbomb_360/` o `data/raw/stastbomb_360/`,
un JSON por partido), la sección Voronoi de **Transiciones** analiza el **instante real** de cada recuperación y de
cada pérdida (no solo los remates). Sin 360 se mantiene el análisis anterior basado en remates (v0.4.14).

Código: `intelligence/transition_voronoi_360.py` (cálculo), `visualization/transition_voronoi_360_maps.py`
(mapas), `visualization/efos_dashboard.py` (sección del portal). Tests: `tests/test_transition_voronoi_360.py`.

## Muestra (América 2025-26)
- 37 de 38 partidos con 360 (falta el 4038856). 108.144 fotografías; cubren el 87 % de las recuperaciones y el 85 % de las pérdidas.
- 1.555 recuperaciones y 3.215 pérdidas del América con fotografía (≈ 1.437 y 3.182 fiables: ≥ 2 atacantes y ≥ 3 defensores visibles),
  más las de sus rivales en esos partidos para comparar.
- Cálculo: ≈ 35–50 s la primera vez que se abre Transiciones; después se reutiliza.

## Cómo se calcula
- Las fotografías 360 vienen orientadas hacia el ataque del equipo que ejecuta el evento (verificado: el actor coincide con la
  ubicación del evento). Todo se calcula en el sistema del equipo que pasa a atacar.
- Voronoi rasterizado en una malla de 2 × 2 yardas: cada celda pertenece al jugador más cercano.
- Solo cuentan las celdas dentro del área que ve la cámara (`visible_area`); los jugadores fuera de imagen no se estiman.
- Recuperación = Ball Recovery o Interception ganada. Pérdida = pase fallado en juego abierto, Dispossessed o Miscontrol;
  el balón se sitúa donde lo recibe el rival (destino del pase).

## Los 10 análisis y sus mapas
| | Análisis | Mapa | Medida |
|---|---|---|---|
| O1 | Espacios disponibles tras recuperación | Campo: % de veces que cada zona es del equipo | % y m² del espacio visible por delante del balón (< 35 m) controlado |
| O2 | Líneas de progresión | Campo: control de cada corredor + primeras progresiones reales | carril más abierto y carril por el que realmente progresa |
| O3 | Espacios vulnerables del rival | Campo: % de veces que la zona queda a ≥ 8 m de un defensor | % libre a < 25 m del balón y atacantes dentro |
| O4 | Apoyos al jugador que recupera | Relativo al balón: compañeros a < 20 m, línea de pase libre/tapada | apoyos, líneas libres, por delante/detrás |
| O5 | Ventajas espaciales | Relativo al balón: atacantes libres (≥ 5 m) por delante | atacantes libres, superioridad a < 25 m, % que acaba en remate en 15 s |
| D1 | Eficacia de la presión tras pérdida | Relativo al balón: jugadores propios, anillos 5 y 10 m | jugadores a < 5/10 m (sin el que pierde) y m² del poseedor rival |
| D2 | Protección de espacios centrales | Campo: control del carril central entre balón y portería | % del carril central controlado |
| D3 | Espacios libres para el rival | Campo: zonas a ≥ 8 m de cualquier jugador propio | % libre a < 25 m del balón |
| D4 | Coberturas defensivas | Relativo al que presiona: compañeros detrás y a < 15 m | coberturas por jugada y % sin cobertura |
| D5 | Compactación tras pérdida | Relativo al balón: ocupación en la pérdida vs. 2–6 s después | superficie, anchura y profundidad del bloque a < 35 m del balón |

Cada análisis muestra el valor del equipo y el de sus rivales en la misma situación. Filtros: transición ofensiva/defensiva,
partido(s) y jugador que recupera o pierde. Desplegable «Jugada a jugada»: Voronoi completo de una recuperación o pérdida concreta.

## Animación 2D de una transición (v0.4.16 · recorrido continuo)
En «Jugada a jugada» → pestaña **Animación 2D de la transición** (`visualization/transition_animation.py`).
- Recorre los 15 s posteriores a la recuperación o la pérdida (hasta un gol) como un **recorrido continuo** a tiempo
  real de juego, sin detenerse en cada evento. ▶ a tiempo real, ▶▶ al doble; el deslizador es una línea de tiempo.
- Las fotografías 360 reales son los puntos de paso. Entre dos fotografías, cada jugador se desplaza en línea recta
  hacia su posición más probable en la siguiente: emparejamiento de mínima distancia total por equipo
  (asignación húngara) con un tope de 8,5 yd/s + 3 yd de tolerancia. Quien no se puede emparejar (entra o sale de la
  cámara) aparece o se desvanece. El Voronoi y el encuadre de la cámara se recalculan en cada fotograma.
- El balón recorre origen → destino de cada pase, conducción o remate y enlaza con la siguiente acción; el último
  remate llega a portería. Eventos simultáneos se separan 0,6 s para que se vean.
- **Límite:** StatsBomb 360 no es tracking ni identifica a los jugadores; el movimiento entre fotografías es una
  estimación visual. Las posiciones exactas son solo las de cada fotografía (los instantes del rótulo).
- Botón para generar y descargar un **GIF** del mismo recorrido (Pillow, sin ffmpeg).

## Decisiones y límites
- El 360 se usa **solo** en esta sección: no se inyecta en el resto del pipeline, para no alterar ESI, presión (PCI/HPS) ni otras cifras validadas.
- La cámara 360 no ve todo el campo: el espacio libre se mide a < 25 m del balón y el bloque a < 35 m.
- D1 y D4 excluyen al jugador que acaba de perder el balón (siempre está junto a él).
- D5 compara dos fotografías con encuadres distintos; es una lectura de tendencia, no una medición de tracking.

---

