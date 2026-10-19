# EFOS v0.4.23 — Transiciones conectadas con Ataque y Defensa

## Qué cambia

- Se conserva la importación automática CSV de StatsBomb de la v0.4.22.
- Menú visible: **Selección de Equipo**, **★ Informe Ejecutivo**, **Modelo de Juego y DT**, **Cómo ataca**, **Cómo defiende**, **Balón Parado**, **Momentos del Partido**.
- No existe una pestaña principal separada de Transiciones.
- **Cómo ataca** comienza con «Tras recuperar», después continúa con el ataque organizado y sus conexiones.
- **Cómo defiende** comienza con «Tras perder», después continúa con la lectura de las situaciones de ataque rival.
- Los motores y textos heredados no se eliminan: la antigua lectura complementaria de Defensa permanece en un desplegable.

## Lecturas nuevas: basadas en eventos, con trazabilidad

### Tras recuperar
- Solo computa Ball Recovery / Interception del equipo dentro de una nueva posesión cuyo dueño previo era un rival.
- Excluye resultados de recuperación etiquetados «Lost In Play» o «Lost Out».
- Observa los siguientes 15 s **de la misma posesión**, identifica primer gesto con balón registrado y su tiempo de aparición, remates y xG si existe.
- Muestra denominadores y mapas de las coordenadas originales de las recuperaciones.
- El número de transiciones estudiadas no representa necesariamente todas las formas posibles de recuperar, solamente las elegibles con etiquetas verificables.

### Tras perder
- Exige un evento de pérdida candidato (Dispossessed / Miscontrol / pase fallido) y un cambio real al dueño de posesión rival dentro de los siguientes 15 s del mismo periodo.
- Estudia acciones Pressure del equipo y recuperaciones etiquetadas dentro de los primeros 5 s.
- Cuenta remates y xG rivales únicamente en la posesión rival inmediata y en la ventana de 15 s.
- No llama «presión colectiva» a una etiqueta individual Pressure ni «estructura» a una distribución de puntos de eventos.

## Exploración 360 y animación (opcional)

- Se activa expresamente en un desplegable dentro de Ataque o Defensa.
- Requiere **archivos nativos JSON de StatsBomb 360** con fotografías enlazadas por `event_uuid` a eventos de la muestra. El CSV ancho de StatsBomb puede incluir freeze frames de tiros, pero eso no equivale a snapshots 360 de toda una transición.
- Ofrece primero «Fotografía original» de un evento realmente observado. En esa fotografía puede encenderse **Voronoi de proximidad geométrica**, solo con información espacial y área visible suficientes.
- Si el evento que abre la transición no tiene fotografía, se permite usar una fotografía posterior en los siguientes 15 s y se advierte su desfase temporal.
- «Animación ilustrativa» interpola fotografías observadas y está etiquetada claramente como **NO TRACKING**. No calcula velocidad real, control del espacio, pressing efectivo ni alimenta ESI / CTS / métricas canónicas.
- Las diez supuestas métricas espaciales extra del parche externo NO se incorporaron porque faltan sus dos motores fuente y la validación contra datos reales.

## Ejemplo real de verificación

`Liga MX 2026_2027 Guadalajara p1.csv` (10 partidos) procesado por el adaptador StatsBomb sin mapeo manual:

- 36,523 eventos únicos.
- 332 recuperaciones/intercepciones elegibles. De ellas, 24 tuvieron al menos un remate del equipo en los siguientes 15 s de la misma posesión (25 remates, xG observado 25/25).
- 548 pérdidas candidatas con cambio de posesión rival verificado. En 148 se registró al menos una acción Pressure en los 5 s siguientes; en 36 el rival remató en 15 s (37 remates, xG observado 37/37).
- Estos son conteos descriptivos de una muestra; no demuestran superioridad, causalidad, estrategia preferida ni efectividad de una presión colectiva.

## Pruebas y limitaciones

- `python3 -m pytest -q tests/test_transition_chapters_v0423.py tests/test_auto_csv_ingestion.py tests/test_offensive_story.py tests/test_editorial_v0422.py tests/test_v047_navigation.py`
- Resultado en este entorno: **25 pruebas pasadas**.
- La suite global no pudo completarse aquí: Streamlit no está instalado y no hay acceso a descarga del paquete. Tampoco se pudo verificar la interfaz en un navegador. Las rutas Python nuevas compilan correctamente.
- Rendimiento real: el análisis de transiciones de los 10 partidos de Guadalajara tardó aproximadamente 15 segundos después de importar el CSV en este entorno; Streamlit lo cachea por conjunto de datos, equipo y selección de partidos.

## Inicio en macOS

Desde la carpeta `efos`:

```bash
python3 -m streamlit run visualization/efos_dashboard.py
```

Cargar un CSV nativo de StatsBomb y consultar **Cómo ataca** y **Cómo defiende**. Para la capa espacial, cargar archivos nativos StatsBomb 360 JSON opcionalmente desde el apartado «Exploración espacial».
