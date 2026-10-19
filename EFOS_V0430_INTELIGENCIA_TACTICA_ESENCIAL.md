# EFOS v0.4.30 · Inteligencia táctica esencial

## Objetivo

Simplificar la experiencia del entrenador sin desactivar los motores de cálculo. El diagnóstico parte de preguntas futbolísticas, muestra evidencia de la **misma muestra seleccionada** y permite profundizar en eventos sin presentar una acumulación de gráficas.

## Interfaz y navegación

Seis entradas principales: **Equipo y datos, Informe Ejecutivo, Modelo de Juego, Con balón, Sin balón y Balón parado**. La transición ofensiva se consulta bajo Con balón, y la respuesta tras pérdida bajo Sin balón. La pestaña adicional «Momentos del partido» y vistas de tablas/índices redundantes no se muestran en el menú principal; el código analítico heredado se conserva.

- Cabecera oscura en el área de trabajo, controles más compactos, identidad visual con seis nodos y acento dorado. Login oscuro inspirado en la referencia de interfaz del proyecto, consultada como `efos_login_preview.html`.
- Ataque y Defensa: selector breve de preguntas y una sola pregunta activa, con navegación anterior/siguiente que conserva el estado.
- Defensa: enfoque visual en una situación elegida, con representación y relato por situación. El detalle estadístico queda desplegable.
- Informe Ejecutivo: hasta tres hallazgos vinculados a remates propios, situación defensiva y reacción tras pérdida; un ejemplo real de posesión con secuencia y resultado. Se evita presentar mapas de porcentajes como si explicaran tácticas.
- PDF ejecutivo generado exactamente desde el diagnóstico de la muestra visible.

## Coherencia y límites de los datos

- Selector global **rival → partido**. Posesiones ofensivas, posesiones defensivas y pérdidas de balón se restringen a los mismos identificadores de partido, y sus diagnósticos se recalculan.
- La comparación de Modelo de Juego muestra **8** indicadores fundamentales, frente a los rivales enfrentados en esos partidos; otros 24 indicadores técnicos permanecen accesibles desplegando «Detalle».
- «Posesión» aproximada por cantidad de pases se renombra **Proporción de pases (%)**; no equivale a tiempo de posesión.
- Los colores de desempeño no clasifican automáticamente como favorable un mayor volumen de acciones que depende del contexto. No se imputan percentiles de liga cuando faltan clubes.
- En la evaluación de transición se registra intervención defensiva dentro de 5 segundos; **no** se interpreta como recuperación efectiva.
- El CT S y el once histórico conservan su muestra de temporada; la interfaz lo advierte cuando se selecciona un partido concreto. La evidencia de secuencias sí cambia con el partido.
- StatsBomb 360 solo respalda posiciones observadas en instantáneas. La animación interpolada no es tracking continuo real.
- No cambian las fórmulas ESI, CTS y OBV ni la carga básica StatsBomb.

## Validación en este entorno

- 58 pruebas aprobadas, incluida la nueva regresión sobre síntesis, alcance de las pérdidas y PDF.
- 74 pruebas adicionales del motor aprobadas. Otras 4 pruebas de Voronoi heredadas fallan por APIs (`LENGTH`, `frame_metrics`, `analyze_transitions`, `ownership`) ausentes de `intelligence/transition_voronoi.py` en el ZIP de partida; esta visualización no se habilita en el menú principal.
- El caso de prueba con un partido real de América produjo una síntesis de tres hallazgos y un PDF ejecutivo de una página.
- No se ha podido lanzar ni hacer QA visual en Streamlit porque Streamlit no está instalado en este entorno. Pruebas que importan `streamlit.testing` quedan pendientes en tu Mac.

## Ejecutar en tu equipo

Desde la carpeta `efos`:

```bash
python3 -m pip install -r requirements.txt
python3 -m streamlit run visualization/efos_dashboard.py
```

Primero prueba **Informe Ejecutivo** con la temporada completa. Después elige un solo rival y un partido: deben cambiar la historia, el ejemplo de posesión y las observaciones específicas de las situaciones. Verifica Con balón, Sin balón, Balón parado y la descarga PDF. No interpretes las instantáneas 360 como seguimiento real de jugadores.
