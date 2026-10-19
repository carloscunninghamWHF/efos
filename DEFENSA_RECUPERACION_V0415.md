# EFOS v0.4.15 — Recuperación y vulnerabilidad observada

## Qué incorpora
Dentro de Sin balón, sin separar de nuevo la navegación:
- Mapa de primera contrapresión etiquetada y primer control posterior confirmado.
- Conteo de secuencias con control y control en ≤10 segundos, localización y tiempo mediano.
- Mapa de primera entrada rival al último tercio y remate posterior en la misma posesión.
- Patrones por zona inicial de contrapresión, con posesiones y partidos.
- Evidencia por partido, posesión y evento, con descarga CSV.
- Integración de las señales en el análisis integral y en la posesión seleccionada.
- Selector «Otro juego abierto» para revisar también las posesiones fuera de las tres categorías principales.

## Tactical Gap
Los antecedentes del proyecto describían Tactical Gap/TGE y propuestas GOS/GES, pero no una fórmula calibrada para estos eventos. Esta entrega implementa una capa descriptiva de señales de vulnerabilidad, no una puntuación 0–100 ni el índice conceptual completo. Tampoco infiere compactación, huecos entre jugadores, marcas o estados psicológicos.

## Definiciones operativas
### Contrapresión
Posesión rival con al menos una acción defensiva del equipo cuyo campo `counterpress` sea verdadero. Es transversal a las categorías: puede aparecer en un contraataque o en una posesión clasificada como otro juego abierto. No es el denominador de todas las pérdidas ni de todos los intentos de presión.

### Control posterior confirmado
Se exige una acción propia con balón (`Pass`, `Carry`, `Dribble` o `Shot`) en la siguiente posesión propia de juego abierto, mismo periodo, sin reinicio ni interrupción registrada y a un máximo de cinco segundos del último evento rival. Se excluyen secuencias con faltas, fueras de juego, interrupciones o desenlaces fuera/gol registrados. Cuando hay un campo explícito de recuperación fallida en la secuencia, no se da por confirmada.

El mapa verde marca esa primera acción de control: no necesariamente el lugar ni instante exacto del robo. El tiempo se mide desde la primera acción de contrapresión, no desde una pérdida inferida. La categoría ≤10 segundos es un corte descriptivo explícito, no un umbral científico validado.

Esta regla es conservadora: puede omitir recuperaciones reales. Los casos sin confirmación NO son automáticamente fracasos. Una secuencia presión → control no demuestra causalidad.

### Entrada y vulnerabilidad zonal
Primera acción rival de pase completado o conducción con inicio x<80 y final x≥80, usando coordenadas StatsBomb válidas. Para pases se usa `outcome_name`: vacío significa completado según la convención de exportación utilizada; los resultados incompletos no se incluyen. Un archivo externo sin resultados de pase por una causa diferente requiere validar su esquema antes de usar esta definición.

Cada posesión entra una sola vez en una franja transversal (inferior, central, superior del dibujo). Se cuentan remates posteriores por orden de evento en esa misma posesión. El tiro puede suceder en otra zona; no atribuimos la causa al carril inicial. Posesiones que empiezan dentro del último tercio o carecen de coordenadas no se fuerzan a una entrada.

Porcentaje = posesiones con remate posterior / posesiones con primera entrada observada por ese carril.
xG medio = suma de xG posterior / posesiones con xG posterior completo. Sin tiro = cero observado; tiro sin xG = dato incompleto, no cero.

### Muestras
Menos de 30 posesiones o cinco partidos se rotula exploratorio. Es una convención editorial, no un test de significación ni prueba de estabilidad. En la síntesis se priorizan carriles que cumplen ambas cantidades, sin asignarles causalidad.

## Coordenadas corregidas
Las acciones de ambos equipos estaban superpuestas sin convertir las coordenadas relativas al equipo actor. Para representar el ataque rival hacia x=120 se rotan las acciones propias: x'=120−x; y'=80−y. Se aplica en atlas, red, secuencias, primera intervención del relato y fotogramas 360 del equipo focal. Los datos originales no se modifican. El nuevo mapa de recuperación sigue la misma convención.

## Comprobación con el archivo incluido
Base: `data/processed/sprint3_real/events_normalized.csv`, 124,353 eventos, 38 partidos.
Todos los escenarios de juego abierto, incluido «Otro juego abierto», sin filtro temporal ni de marcador:
- 1,989 posesiones rivales.
- 980 con contrapresión etiquetada.
- 394 con control posterior confirmado; las 394 tienen ubicación.
- 277 con control en ≤10 segundos desde la primera contrapresión.
- Mediana de 6 segundos exclusivamente entre las 394 confirmadas.
- Primera entrada central: 82 posesiones, 32 partidos, 20 con remate posterior (24.39%).
- Primera entrada por franja inferior: 154 posesiones, 36 partidos, 27 con remate (17.53%).
- Primera entrada por franja superior: 173 posesiones, 37 partidos, 28 con remate (16.18%).
Estos totales no coinciden con un filtro específico de la interfaz y no se muestran como constantes: la interfaz recalcula la selección.

## Validación
21 pruebas del atlas, navegación e insights superadas. Incluyen reinicios, interrupciones, cambio de periodo, ausencia de control, entrada incompleta, xG ausente, una sola entrada por posesión y orientación de defensores/360. Prueba adicional de Streamlit con contrapresión y control positivo. Las muestras sintéticas se usan solo para pruebas; ningún número de demostración se usa como hallazgo del dataset real.

## Referencia del proveedor
StatsBomb Open Data Specification v1.1:
https://github.com/statsbomb/open-data/blob/master/doc/StatsBomb%20Open%20Data%20Specification%20v1.1.pdf
Campos de eventos expuestos por statsbombpy:
https://github.com/hudl/statsbombpy
Las reglas de vinculación y denominadores anteriores son operativas de EFOS, no métricas oficiales del proveedor.

## Ejecutar
Desde la carpeta `efos`, con las dependencias del proyecto:

```bash
python -m streamlit run visualization/efos_dashboard.py
```
